import json
import logging
import sys
from pathlib import Path
from typing import TextIO

import httpx
from tqdm import tqdm

from ..client import MangaDexClient
from ..models.manga_model import MangaChapter
from ..resources.base import Methods

logger = logging.getLogger(__name__)


class MangaDownloader:

    def __init__(
            self,
            manga_id: str,
            file_path: Path | str,
            manga_dex_client: MangaDexClient,
            output: TextIO | None = None,
    ):
        self.manga_id = manga_id
        self.file_path = Path(file_path)
        self.manga_dex_client = manga_dex_client
        self.output = output or sys.stdout
        self.manga_chapters: dict[str, MangaChapter] = {}

        self._write("▶ Lade Manga-Informationen …")
        self.manga = self.manga_dex_client.manga.get_by_id(manga_id)

        if not self.manga:
            raise ValueError(f"Manga {manga_id} not found")

        with (self.get_manga_root_directory() / "manga.json").open("w", encoding="utf-8") as f:
            json.dump(self.manga.to_dict(), f)

        self._write(f"✓ Manga gefunden: {self.manga.attributes.title.first or self.manga_id}")
        self._write(f"  Zielordner: {self.get_manga_root_directory()}")

    def get_manga_chapter(self, chapter_id: str) -> MangaChapter | None:
        if self.manga_chapters.get(chapter_id) is None:
            try:
                self._write(f"▶ Lade Kapitelinformationen ({chapter_id}) …")
                manga_chapter = self.manga_dex_client.manga.get_chapter(chapter_id)
                self.manga_chapters[manga_chapter.id] = manga_chapter
            except httpx.HTTPStatusError as e:
                logger.warning("Kapitel %s konnte nicht geladen werden: %s", chapter_id, e)
                self._write(f"! Kapitel {chapter_id} konnte nicht geladen werden.")
                return None
        return self.manga_chapters[chapter_id]

    def get_manga_root_directory(self) -> Path:
        manga_path = self.file_path / self.manga_id
        manga_path.mkdir(parents=True, exist_ok=True)
        return manga_path

    def get_chapter_directory(self, chapter_id: str) -> Path:
        manga_chapter = self.get_manga_chapter(chapter_id)
        if not manga_chapter:
            raise ValueError(f"Chapter {chapter_id} not found")
        chapter_count = manga_chapter.attributes.chapter.replace(".", "_")
        chapter_path = self.get_manga_root_directory() / chapter_count / chapter_id
        chapter_path.mkdir(parents=True, exist_ok=True)
        return chapter_path

    def download_chapter(
            self,
            chapter_id: str,
            overwrite: bool = False,
            retry_on_403: bool = True,
            overall_progress: tqdm | None = None,
    ) -> tuple[int, int]:
        manga_chapter = self.get_manga_chapter(chapter_id)
        if manga_chapter is None:
            raise ValueError(f"Chapter {chapter_id} not found")

        chapter_directory = self.get_chapter_directory(chapter_id)
        downloaded_pages: list[str] = []
        known_pages = {
            file_path.stem
            for file_path in chapter_directory.iterdir()
            if file_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
        }
        chapter_label = manga_chapter.attributes.chapter or "Unnummeriert"
        page_progress: tqdm | None = None

        attempts = 0
        while True:
            try:
                attempts += 1
                logger.info("Lade Kapitel %s (%s)", chapter_label, chapter_id)
                self._write(f"▶ Kapitel {chapter_label}: Bildserver wird vorbereitet …")
                at_home_req = self.manga_dex_client.raw_request(
                    Methods.GET,
                    f"at-home/server/{chapter_id}"
                )
                base_url: str = at_home_req["baseUrl"]
                url_hash: str = at_home_req["chapter"]["hash"]
                chapters: list[str] = at_home_req["chapter"]["data"]
                page_progress = tqdm(
                    total=len(chapters),
                    desc=f"  Kapitel {chapter_label}",
                    unit="Seite",
                    dynamic_ncols=True,
                    leave=overall_progress is None,
                    position=1 if overall_progress is not None else 0,
                    file=self.output,
                )

                with httpx.Client() as httpx_client:
                    page_file: str
                    for page_file in chapters:
                        img_url = f"{base_url}/data/{url_hash}/{page_file}"
                        page = page_file.split("-")[0]
                        page_format = page_file.rsplit(".", maxsplit=1)[-1]

                        if page in downloaded_pages:
                            page_progress.update(1)
                            continue

                        if page in known_pages and not overwrite:
                            page_progress.update(1)
                            continue

                        response = httpx_client.get(img_url)
                        if response.status_code == 200:
                            with (chapter_directory / f"{page}.{page_format}").open("wb") as f:
                                f.write(response.content)
                            downloaded_pages.append(page)
                        else:
                            response.raise_for_status()
                        page_progress.update(1)

                    with (chapter_directory / "chapter.json").open("w", encoding="utf-8") as f:
                        json.dump(manga_chapter.to_dict(), f)

                    skipped_pages = len(chapters) - len(downloaded_pages)
                    logger.info(
                        "Kapitel %s abgeschlossen: %s heruntergeladen, %s übersprungen",
                        chapter_label,
                        len(downloaded_pages),
                        skipped_pages,
                    )
                    if overall_progress is not None:
                        overall_progress.update(1)
                    return len(downloaded_pages), skipped_pages

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403 and retry_on_403:
                    logger.warning("HTTP 403 für Kapitel %s; versuche es erneut.", chapter_id)
                    self._write(
                        f"! Kapitel {chapter_label}: Zugriff abgelehnt, neuer Versuch ({attempts})."
                    )
                    continue
                raise
            finally:
                if page_progress is not None:
                    page_progress.close()

    def download_complete_manga(
            self,
            overwrite: bool = False,
            language: str | list[str] | None = None,
            single_chapter_per: bool = False
    ) -> None:
        chapters = []
        while len(chapters) % 100 == 0:
            old_len = len(chapters)
            chapters += self.manga_dex_client.manga.get_chapters(self.manga_id, language=language, sort_by_chapter="asc", offset=len(chapters))
            if old_len == len(chapters):
                break
        sorted_chapters: dict[str, list[MangaChapter]] = {}
        manga_chapter: MangaChapter
        for manga_chapter in chapters:
            self.manga_chapters[manga_chapter.id] = manga_chapter
            chapter_number = manga_chapter.attributes.chapter.replace(".", "_")
            if chapter_number not in sorted_chapters:
                sorted_chapters[chapter_number] = []
            sorted_chapters[chapter_number].append(manga_chapter)

        chapters_to_download = self._select_chapters(sorted_chapters, single_chapter_per)
        self._print_download_summary(len(chapters_to_download), language, overwrite)

        downloaded_pages = 0
        skipped_pages = 0
        with tqdm(
                total=len(chapters_to_download),
                desc="Gesamtfortschritt",
                unit="Kapitel",
                dynamic_ncols=True,
                file=self.output,
        ) as overall_progress:
            for manga_chapter in chapters_to_download:
                new_pages, existing_pages = self.download_chapter(
                    manga_chapter.id,
                    overwrite=overwrite,
                    overall_progress=overall_progress,
                )
                downloaded_pages += new_pages
                skipped_pages += existing_pages

        self._write(
            f"✓ Download abgeschlossen: {len(chapters_to_download)} Kapitel, "
            f"{downloaded_pages} Seiten gespeichert, {skipped_pages} übersprungen."
        )

    @staticmethod
    def _select_chapters(
            sorted_chapters: dict[str, list[MangaChapter]], single_chapter_per: bool
    ) -> list[MangaChapter]:
        selected_chapters: list[MangaChapter] = []
        for chapter_number in sorted(sorted_chapters, key=_chapter_sort_key):
            chapter_versions = sorted_chapters[chapter_number]
            if not single_chapter_per:
                selected_chapters.extend(chapter_versions)
                continue

            newest_by_language: dict[str, MangaChapter] = {}
            for manga_chapter in sorted(
                    chapter_versions,
                    key=lambda item: (
                        item.attributes.publish_at is not None,
                        item.attributes.publish_at,
                    ),
                    reverse=True,
            ):
                newest_by_language.setdefault(manga_chapter.attributes.translated_language, manga_chapter)
            selected_chapters.extend(newest_by_language.values())
        return selected_chapters

    def _print_download_summary(
            self, chapter_count: int, language: str | list[str] | None, overwrite: bool
    ) -> None:
        selected_language = ", ".join(language) if isinstance(language, list) else language or "Alle"
        self._write("\nDownload wird vorbereitet")
        self._write(f"  Manga: {self.manga.attributes.title.first or self.manga_id}")
        self._write(f"  Kapitel: {chapter_count}")
        self._write(f"  Sprache: {selected_language}")
        self._write(f"  Vorhandene Dateien: {'Überschreiben' if overwrite else 'Überspringen'}\n")

    def _write(self, message: str) -> None:
        tqdm.write(message, file=self.output)


def _chapter_sort_key(chapter_number: str) -> tuple[tuple[bool, str], ...]:
    return tuple(
        (part.isdigit(), f"{int(part):010d}" if part.isdigit() else part)
        for part in chapter_number.split("_")
    )
