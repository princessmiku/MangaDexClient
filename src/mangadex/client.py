from typing import Any

import httpx

from mangadex.exceptions import APIClientError, ResourceNotFoundError
from mangadex.resources.manga import MangaResource


class MangaDexClient:
    def __init__(
        self,
        debug: bool = False,
        *,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self._base_url = "https://api.mangadex.org"
        self._debug = debug

        self._http_client = httpx.Client(
            base_url=self._base_url,
            headers={"User-Agent": "MangaDex.py/0.1"},
            follow_redirects=True,
            timeout=timeout,
            transport=transport,
        )

        self._manga = MangaResource(self._http_client, debug=self._debug)

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def manga(self) -> MangaResource:
        return self._manga

    def raw_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        """Führt einen unverarbeiteten API-Request aus und gibt dessen JSON zurück.

        Zusätzliche Argumente werden unverändert an ``httpx.Client.request``
        weitergegeben, zum Beispiel ``params``, ``json`` oder ``headers``.
        """
        try:
            if self._debug:
                request_url = self._http_client.base_url.join(url)
                print(f"[DEBUG] {method} {request_url}")

                if "params" in kwargs:
                    print(f"[DEBUG] Params: {kwargs['params']}")

                if "json" in kwargs:
                    print(f"[DEBUG] JSON: {kwargs['json']}")

            response = self._http_client.request(
                method=method,
                url=url,
                **kwargs,
            )

            if self._debug:
                print(f"[DEBUG] Request sent to: {response.url}")
                print(f"[DEBUG] Response status: {response.status_code}")
                print(f"[DEBUG] Response body: {response.text[:500]}")

            response.raise_for_status()

            try:
                return response.json()
            except ValueError as exc:
                raise APIClientError(
                    message="Response enthält kein gültiges JSON",
                    status_code=response.status_code,
                    response_body=response.text,
                ) from exc

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

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def close(self):
        self._http_client.close()

    def __del__(self):
        self.close()
