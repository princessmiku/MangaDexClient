import time
from threading import Lock
from typing import Any

import httpx

from mangadex.exceptions import (
    APIClientError,
    RateLimitError,
    ResourceNotFoundError,
)
from mangadex.resources.manga import MangaResource


class MangaDexClient:
    _AT_HOME_SERVER_REQUEST_INTERVAL = 60 / 40

    def __init__(
            self,
            debug: bool = False,
            *,
            timeout: float = 30.0,
            transport: httpx.BaseTransport | None = None,
            rate_limit_per_second: float = 0.5,
    ):
        if (
            isinstance(rate_limit_per_second, bool)
            or rate_limit_per_second <= 0
        ):
            raise ValueError("rate_limit_per_second must be greater than zero")

        self._base_url = "https://api.mangadex.org"
        self._debug = debug
        self._rate_limit_per_second = rate_limit_per_second
        self._request_interval = 1 / rate_limit_per_second
        self._next_request_time = 0.0
        self._next_at_home_server_request_time = 0.0
        self._request_lock = Lock()

        self._http_client = httpx.Client(
            base_url=self._base_url,
            headers={"User-Agent": "MangaDex.py/0.1"},
            follow_redirects=True,
            timeout=timeout,
            transport=transport,
        )

        self._manga = MangaResource(
            self._http_client,
            self._rate_limited_request,
            debug=self._debug,
        )

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def manga(self) -> MangaResource:
        return self._manga

    def can_make_request(self) -> bool:
        """Returns True if the client can make a request, False otherwise."""
        return time.monotonic() >= self._next_request_time

    def _rate_limited_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Sendet eine reguläre API-Anfrage unter Einhaltung des Limits."""
        with self._request_lock:
            now = time.monotonic()
            request_time = max(now, self._next_request_time)
            is_at_home_server_request = url.lstrip("/").startswith(
                "at-home/server/"
            )
            if is_at_home_server_request:
                request_time = max(
                    request_time,
                    self._next_at_home_server_request_time,
                )
            self._next_request_time = request_time + self._request_interval
            if is_at_home_server_request:
                self._next_at_home_server_request_time = (
                    request_time + self._AT_HOME_SERVER_REQUEST_INTERVAL
                )

        wait_time = request_time - now
        if wait_time > 0:
            time.sleep(wait_time)

        return self._http_client.request(method=method, url=url, **kwargs)

    def raw_request(
            self,
            method: str,
            url: str,
            **kwargs: Any,
    ) -> Any:
        """Executes an unprocessed API request and returns its JSON.

        Additional arguments are passed on unmodified to ``httpx.Client.request``
        , for example ``params``, ``json`` or ``headers``.
        """
        try:
            if self._debug:
                request_url = self._http_client.base_url.join(url)
                print(f"[DEBUG] {method} {request_url}")

                if "params" in kwargs:
                    print(f"[DEBUG] Params: {kwargs['params']}")

                if "json" in kwargs:
                    print(f"[DEBUG] JSON: {kwargs['json']}")

            response = self._rate_limited_request(
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

            if status_code == httpx.codes.TOO_MANY_REQUESTS:
                retry_after = exc.response.headers.get(
                    "X-RateLimit-Retry-After"
                )
                message = "MangaDex rate limit reached"
                if retry_after is not None:
                    message += f"; retry after UNIX timestamp {retry_after}"
                raise RateLimitError(
                    message=message,
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
        if hasattr(self, "_http_client"):
            self._http_client.close()

    def __del__(self):
        self.close()
