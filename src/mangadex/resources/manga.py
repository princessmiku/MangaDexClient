from .base import BaseResource, Methods, CollectionResponse
from ..models.cover_model import Cover
from ..models.manga_model import Manga, MangaChapter


class MangaResource(BaseResource):

    def search(self, title: str) -> CollectionResponse[Manga]:
        return self._handle_collection_request(Manga, Methods.GET, "/manga", params={"title": title})

    def get_by_id(self, id: str) -> Manga:
        return self._handle_entity_request(Manga, Methods.GET, f"/manga/{id}")

    def get_chapters(self, id: str, language: str | list[str] | None = None, include_unavailable: bool = False, sort_by_chapter: str | None = None, offset: int = 0) -> CollectionResponse[MangaChapter]:
        params = {}
        if language is not None:
            if isinstance(language, str):
                language = [language]
            params["translatedLanguage[]"] = language
        if include_unavailable:
            params["includeUnavailable"] = True
        if offset > 0:
            params["offset"] = offset
        collection: CollectionResponse[MangaChapter] = self._handle_collection_request(MangaChapter, Methods.GET, f"/manga/{id}/feed", params=params)
        if sort_by_chapter and sort_by_chapter in ["asc", "desc"]:
            collection.sort(key=lambda x: x.attributes.chapter, reverse=sort_by_chapter == "desc")
        return collection

    def get_chapter(self, id: str) -> MangaChapter:
        return self._handle_entity_request(MangaChapter, Methods.GET, f"/chapter/{id}")

    def get_covers(self, id: str) -> CollectionResponse[Cover]:
        return self._handle_collection_request(Cover, Methods.GET, f"/cover?manga[]={id}&limit=100&offset=0&order[volume]=asc")
