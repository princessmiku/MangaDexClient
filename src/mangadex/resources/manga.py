from .base import BaseResource, Methods, CollectionResponse
from ..models.cover_model import Cover
from ..models.manga_model import Manga, MangaChapter


class MangaResource(BaseResource):

    def search(self, title: str) -> CollectionResponse[Manga]:
        return self._handle_collection_request(Manga, Methods.GET, "/manga", params={"title": title})

    def get_by_id(self, id: str) -> Manga:
        return self._handle_entity_request(Manga, Methods.GET, f"/manga/{id}")

    def get_chapters(self, id: str) -> CollectionResponse[MangaChapter]:
        return self._handle_collection_request(MangaChapter, Methods.GET, f"/manga/{id}/feed")

    def get_covers(self, id: str) -> CollectionResponse[Cover]:
        return self._handle_collection_request(Cover, Methods.GET, f"/cover?manga[]={id}&limit=100&offset=0&order[volume]=asc")
