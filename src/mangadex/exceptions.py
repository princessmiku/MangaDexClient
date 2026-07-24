from typing import Optional


class ModelError(ValueError):
    """Fehler beim Umwandeln einer API-Antwort in ein Model."""


class APIClientError(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)

        self.status_code = status_code
        self.response_body = response_body


class ResourceNotFoundError(APIClientError):
    """Die angefragte Ressource wurde nicht gefunden."""
