from datetime import datetime
from collections.abc import Iterator
from typing import Any, Mapping

from .base_model import BaseModel, ModelError


class Title(BaseModel, Mapping[str, str]):
    lang: str | None
    title: str | None

    def __init__(self, lang: str | None, title: str | None) -> None:
        self.lang = lang
        self.title = title
        self._raw_data = {} if lang is None else {lang: title}
        self._extra_data: dict[str, Any] = {}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Title":
        if not data:
            return cls(lang=None, title=None)

        if not all(
            isinstance(lang, str) and isinstance(title, str)
            for lang, title in data.items()
        ):
            raise ModelError("Alternativtitel muss Sprache und Text enthalten")

        lang, title = next(iter(data.items()))
        instance = cls(lang=lang, title=title)
        instance._raw_data = dict(data)
        return instance

    @property
    def first(self) -> str | None:
        return self.title

    def get(self, lang: str | None = None, default: str | None = None) -> str | None:
        if lang is None:
            return self.title if self.title is not None else default

        return self._raw_data.get(lang, default)

    def __getitem__(self, lang: str) -> str:
        return self._raw_data[lang]

    def __iter__(self) -> Iterator[str]:
        return iter(self._raw_data)

    def __len__(self) -> int:
        return len(self._raw_data)


class TagAttributes(BaseModel):
    name: Title
    description: Title
    group: str
    version: int


class Tag(BaseModel):
    id: str
    type: str
    attributes: TagAttributes
    relationships: list[dict[str, Any]]


class Relationship(BaseModel):
    id: str
    type: str


class MangaAttributes(BaseModel):
    title: Title
    alt_titles: list[Title] | None
    description: Title | None
    is_locked: bool | None
    links: dict[str, str] | None
    official_links: dict[str, str] | None
    original_language: str | None
    last_volume: str | None
    last_chapter: str | None
    publication_demographic: str | None
    status: str | None
    year: int | None
    content_rating: str | None
    tags: list[Tag] | None
    state: str | None
    chapter_numbers_reset_on_new_volume: bool | None
    created_at: datetime | None
    updated_at: datetime | None
    version: int | None
    available_translated_languages: list[str] | None
    latest_uploaded_chapter: str | None


class Manga(BaseModel):
    id: str
    type: str
    attributes: MangaAttributes
    relationships: list[Relationship]


class MangaChapterAttributes(BaseModel):
    volume: str | None
    chapter: str
    title: str | None
    translated_language: str
    external_url: str | None
    is_unavailable: bool
    publish_at: datetime | None
    readable_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None
    version: int
    pages: int


class MangaChapter(BaseModel):
    id: str
    type: str
    attributes: MangaChapterAttributes
    relationships: list[Relationship]

