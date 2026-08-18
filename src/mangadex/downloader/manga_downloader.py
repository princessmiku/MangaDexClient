import json
import os
import time
from pathlib import Path

import httpx

from ..client import MangaDexClient
from ..models.manga_model import MangaChapter
from ..resources.base import Methods


class MangaDownloader:

    def __init__(
            self,
            manga_id: str,
            file_path: Path | str,
            manga_dex_client: MangaDexClient
    ):
        self.manga_id = manga_id
        self.file_path = file_path
        self.manga_dex_client = manga_dex_client
        self.manga_chapters: dict[str, MangaChapter] = {}

        self.manga = self.manga_dex_client.manga.get_by_id(manga_id)
        if not self.manga:
            raise ValueError(f"Manga {manga_id} not found")

        with open(f"{self.get_manga_root_directory()}/manga.json", "w") as f:
            json.dump(self.manga.to_dict(), f)

    def get_manga_chapter(self, chapter_id: str) -> MangaChapter | None:
        if self.manga_chapters.get(chapter_id) is None:
            try:
                manga_chapter = self.manga_dex_client.manga.get_chapter(chapter_id)
                self.manga_chapters[manga_chapter.id] = manga_chapter
            except httpx.HTTPStatusError as e:
                print(f"Error getting chapter {chapter_id}: {e}")
                return None
        return self.manga_chapters[chapter_id]

    def get_manga_root_directory(self) -> Path:
        manga_path = Path(f"{self.file_path}/{self.manga_id}")
        if not os.path.exists(manga_path):
            os.makedirs(manga_path)
        return manga_path

    def get_chapter_directory(self, chapter_id: str) -> Path:
        manga_chapter = self.get_manga_chapter(chapter_id)
        if not manga_chapter:
            raise ValueError(f"Chapter {chapter_id} not found")
        chapter_count = manga_chapter.attributes.chapter.replace(".", "_")
        chapter_path = Path(f"{self.get_manga_root_directory()}/{chapter_count}/{chapter_id}")
        if not os.path.exists(chapter_path):
            os.makedirs(chapter_path)
        return chapter_path

    def download_chapter(self, chapter_id: str, overwrite: bool = False, retry_on_403: bool = True):
        manga_chapter = self.get_manga_chapter(chapter_id)
        if manga_chapter is None:
            raise ValueError(f"Chapter {chapter_id} not found")
        downloaded_pages = []
        known_pages = [x.split(".")[0] for x in os.listdir(self.get_chapter_directory(chapter_id)) if x.endswith(".jpg") or x.endswith(".png") and manga_chapter.attributes.translated_language in x]
        while retry_on_403:
            try:
                while not self.manga_dex_client.can_make_request():
                    time.sleep(0.2)
                at_home_req = self.manga_dex_client.raw_request(
                    Methods.GET,
                    f"at-home/server/{chapter_id}"
                )
                base_url: str = at_home_req["baseUrl"]
                url_hash: str = at_home_req["chapter"]["hash"]
                chapters: list[str] = at_home_req["chapter"]["data"]

                with httpx.Client() as httpx_client:
                    chapter: str
                    for chapter in chapters:
                        img_url = f"{base_url}/data/{url_hash}/{chapter}"
                        page = chapter.split("-")[0]
                        page_format = chapter.split(".")[-1]

                        if page in downloaded_pages:
                            continue

                        if page in known_pages and not overwrite:
                            continue

                        response = httpx_client.get(img_url)
                        if response.status_code == 200:
                            with open(f"{self.get_chapter_directory(chapter_id)}/{page}.{page_format}", "wb") as f:
                                f.write(response.content)
                            downloaded_pages.append(page)
                        else:
                            response.raise_for_status()

                    with open(f"{self.get_chapter_directory(chapter_id)}/chapter.json", "w") as f:
                        json.dump(manga_chapter.to_dict(), f)

                    break  # end the while loop !! important !!

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 403:
                    continue
                else:
                    raise e

    def download_complete_manga(self, overwrite: bool = False, language: str | list[str] | None = None, single_chapter_per: bool = False):
        chapters = self.manga_dex_client.manga.get_chapters(self.manga_id, language=language, sort_by_chapter="asc")
        sorted_chapters = {}
        manga_chapter: MangaChapter
        for manga_chapter in chapters:
            self.manga_chapters[manga_chapter.id] = manga_chapter
            chapter_number = manga_chapter.attributes.chapter.replace(".", "_")
            if not chapter_number in sorted_chapters:
                sorted_chapters[chapter_number] = []
            sorted_chapters[chapter_number].append(manga_chapter)

        # download chapters
        for chapter_number in sorted(sorted_chapters.keys()):
            if single_chapter_per:
                # download only the newest chapter
                sorted_chapters[chapter_number].sort(key=lambda x: x.attributes.publishAt, reverse=True)
                # filter chapter per language
                downloaded_languages = []
                for manga_chapter in sorted_chapters[chapter_number]:
                    for language in manga_chapter.attributes.translated_language:
                        if language in language and language not in downloaded_languages:
                            self.download_chapter(manga_chapter.id, overwrite=overwrite)
                            downloaded_languages.append(language)
            else:
                for manga_chapter in sorted_chapters[chapter_number]:
                    self.download_chapter(manga_chapter.id, overwrite=overwrite)
