from __future__ import annotations

from enum import StrEnum
from typing import Any, Callable, Generic, Literal, Mapping, TypeVar, TypeAlias, Iterator

import httpx

from ..models.base_model import BaseModel, ModelError
from ..exceptions import APIClientError, ResourceNotFoundError


T = TypeVar("T", bound=BaseModel)

ResponseType = Literal["entity", "collection"]
RequestCallable = Callable[..., httpx.Response]


class Methods(StrEnum):
    GET = "GET"


class EntityResponse(Generic[T]):
    def __init__(
        self,
        *,
        result: str,
        data: T,
        raw_data: Mapping[str, Any],
    ) -> None:
        self.result = result
        self.response_type: Literal["entity"] = "entity"
        self.data = data
        self.raw_data = dict(raw_data)

    @property
    def is_entity(self) -> Literal[True]:
        return True

    @property
    def is_collection(self) -> Literal[False]:
        return False


class CollectionResponse(Generic[T]):
    def __init__(
        self,
        *,
        result: str,
        data: list[T],
        raw_data: Mapping[str, Any],
        limit: int | None = None,
        offset: int | None = None,
        total: int | None = None,
    ) -> None:
        self.result = result
        self.response_type: Literal["collection"] = "collection"
        self.data = data
        self.raw_data = dict(raw_data)

        self.limit = limit
        self.offset = offset
        self.total = total

    @property
    def is_entity(self) -> Literal[False]:
        return False

    @property
    def is_collection(self) -> Literal[True]:
        return True

    def __iter__(self) -> Iterator[T]:
        return iter(self.data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def __len__(self) -> int:
        return len(self.data)

    def __getitem__(self, key: int) -> T:
        return self.data[key]

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.data})"


ParsedResponse: TypeAlias = EntityResponse[T] | CollectionResponse[T]


class BaseResource:
    def __init__(
        self,
        client: httpx.Client,
        request: RequestCallable,
        debug: bool = False,
    ) -> None:
        self._client = client
        self._request = request
        self._debug = debug

    def _handle_request(
        self,
        model: type[T],
        method: Methods | str,
        url: str,
        **kwargs: Any,
    ) -> ParsedResponse[T] | None:
        """
        Führt einen HTTP-Request aus und wandelt die Antwort
        in das übergebene Model um.

        Bei HTTP 204 wird None zurückgegeben.
        """

        try:
            if self._debug:
                request_url = self._client.base_url.join(url)

                print(f"[DEBUG] {method} {request_url}")

                if "params" in kwargs:
                    print(f"[DEBUG] Params: {kwargs['params']}")

                if "json" in kwargs:
                    print(f"[DEBUG] JSON: {kwargs['json']}")

            response = self._request(
                method=str(method),
                url=url,
                **kwargs,
            )

            if self._debug:
                print(f"[DEBUG] Request sent to: {response.url}")
                print(
                    f"[DEBUG] Response status: "
                    f"{response.status_code}"
                )
                print(
                    f"[DEBUG] Response body: "
                    f"{response.text[:500]}"
                )

            response.raise_for_status()

            if response.status_code == httpx.codes.NO_CONTENT:
                return None

            try:
                payload = response.json()
            except ValueError as exc:
                raise APIClientError(
                    message="Response enthält kein gültiges JSON",
                    status_code=response.status_code,
                    response_body=response.text,
                ) from exc

            if not isinstance(payload, Mapping):
                raise ModelError(
                    "Die API-Antwort muss ein JSON-Objekt sein"
                )

            return self._parse_response(
                payload=payload,
                model=model,
            )

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            response_body = exc.response.text

            if status_code == httpx.codes.NOT_FOUND:
                raise ResourceNotFoundError(
                    message="Resource not found",
                    status_code=status_code,
                    response_body=response_body,
                ) from exc

            raise APIClientError(
                message=f"HTTP Error: {exc}",
                status_code=status_code,
                response_body=response_body,
            ) from exc

        except httpx.RequestError as exc:
            raise APIClientError(
                message=(
                    "Request konnte nicht ausgeführt werden: "
                    f"{exc}"
                )
            ) from exc

        finally:
            if self._debug:
                print("[DEBUG] Request completed")

    def _parse_response(
        self,
        payload: Mapping[str, Any],
        model: type[T],
    ) -> ParsedResponse[T]:
        """
        Wandelt eine rohe API-Antwort in eine EntityResponse
        oder CollectionResponse um.
        """

        result = payload.get("result")
        response_type = payload.get("response")

        if not isinstance(result, str):
            raise ModelError(
                "Response enthält kein gültiges 'result'-Feld"
            )

        if result != "ok":
            raise ModelError(
                f"API-Anfrage war nicht erfolgreich: {result!r}"
            )

        if response_type == "entity":
            raw_entity = payload.get("data")

            if not isinstance(raw_entity, Mapping):
                raise ModelError(
                    "Entity-Response enthält kein gültiges Objekt"
                )

            parsed_entity = model.from_dict(raw_entity)

            return EntityResponse(
                result=result,
                data=parsed_entity,
                raw_data=payload,
            )

        if response_type == "collection":
            raw_collection = payload.get("data")

            if not isinstance(raw_collection, list):
                raise ModelError(
                    "Collection-Response enthält keine gültige Liste"
                )

            parsed_items: list[T] = []

            for index, item in enumerate(raw_collection):
                if not isinstance(item, Mapping):
                    raise ModelError(
                        f"Collection-Eintrag an Position {index} "
                        "ist kein gültiges Objekt"
                    )

                parsed_items.append(model.from_dict(item))

            return CollectionResponse(
                result=result,
                data=parsed_items,
                raw_data=payload,
                limit=self._optional_int(payload, "limit"),
                offset=self._optional_int(payload, "offset"),
                total=self._optional_int(payload, "total"),
            )

        raise ModelError(
            f"Unbekannter Response-Typ: {response_type!r}"
        )

    def _handle_entity_request(
        self,
        model: type[T],
        method: Methods | str,
        url: str,
        **kwargs: Any,
    ) -> T:
        """
        Führt einen Request aus, bei dem eine einzelne Entity
        erwartet wird.
        """

        response = self._handle_request(
            model=model,
            method=method,
            url=url,
            **kwargs,
        )

        if response is None:
            raise ModelError(
                "Entity-Request lieferte keine Daten"
            )

        if response.response_type != "entity":
            raise ModelError(
                "Entity-Response erwartet, "
                "aber Collection erhalten"
            )

        return response.data

    def _handle_collection_request(
        self,
        model: type[T],
        method: Methods | str,
        url: str,
        **kwargs: Any,
    ) -> CollectionResponse[T]:
        """
        Führt einen Request aus, bei dem eine Collection
        erwartet wird.
        """

        response = self._handle_request(
            model=model,
            method=method,
            url=url,
            **kwargs,
        )

        if response is None:
            return CollectionResponse(
                result="ok",
                data=[],
                raw_data={},
                limit=0,
                offset=0,
                total=0,
            )

        if response.response_type != "collection":
            raise ModelError(
                "Collection-Response erwartet, "
                "aber Entity erhalten"
            )

        return response

    @staticmethod
    def _optional_int(
        payload: Mapping[str, Any],
        key: str,
    ) -> int | None:
        value = payload.get(key)

        if value is None:
            return None

        if isinstance(value, bool) or not isinstance(value, int):
            raise ModelError(
                f"Response-Feld {key!r} muss eine Ganzzahl sein"
            )

        return value
