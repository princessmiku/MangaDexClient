from __future__ import annotations

import types
from datetime import date, datetime
from typing import (
    Any,
    ClassVar,
    Generic,
    Literal,
    Mapping,
    TypeVar,
    Union,
    get_args,
    get_origin,
    get_type_hints,
)
from uuid import UUID


T = TypeVar("T", bound="BaseModel")


class ModelError(ValueError):
    pass


class BaseModel:
    """
    Basisklasse für alle API-Modelle.

    Unterklassen definieren ihre Felder ausschließlich über Type-Hints.
    """

    __aliases__: ClassVar[dict[str, str]] = {}

    def __init__(self, data: Mapping[str, Any]):
        if not isinstance(data, Mapping):
            raise ModelError(
                f"{type(self).__name__} erwartet ein Mapping, "
                f"erhalten: {type(data).__name__}"
            )

        self._raw_data = dict(data)
        self._extra_data: dict[str, Any] = {}

        hints = get_type_hints(type(self))
        consumed_keys: set[str] = set()

        for field_name, field_type in hints.items():
            # ClassVar-Felder sind keine Model-Felder.
            if get_origin(field_type) is ClassVar:
                continue

            json_key = self.__aliases__.get(
                field_name,
                self._snake_to_camel(field_name),
            )

            if json_key not in data:
                if self._allows_none(field_type):
                    setattr(self, field_name, None)
                    continue

                raise ModelError(
                    f"Pflichtfeld {json_key!r} fehlt in "
                    f"{type(self).__name__}"
                )

            raw_value = data[json_key]
            value = self._convert_value(raw_value, field_type)

            setattr(self, field_name, value)
            consumed_keys.add(json_key)

        # Unbekannte Felder bleiben erhalten, ohne das Modell zu zerstören.
        self._extra_data = {
            key: value
            for key, value in data.items()
            if key not in consumed_keys
        }

    @property
    def raw_data(self) -> dict[str, Any]:
        return self._raw_data.copy()

    @property
    def extra_data(self) -> dict[str, Any]:
        return self._extra_data.copy()

    @classmethod
    def from_dict(cls: type[T], data: Mapping[str, Any]) -> T:
        return cls(data)

    @classmethod
    def _convert_value(cls, value: Any, target_type: Any) -> Any:
        if target_type is Any:
            return value

        if value is None:
            if cls._allows_none(target_type):
                return None

            raise ModelError(
                f"None kann nicht in {target_type!r} umgewandelt werden"
            )

        origin = get_origin(target_type)
        args = get_args(target_type)

        # Optional[T] beziehungsweise T | None
        if origin in (Union, types.UnionType):
            errors: list[Exception] = []

            for option in args:
                if option is type(None):
                    continue

                try:
                    return cls._convert_value(value, option)
                except (TypeError, ValueError, ModelError) as exc:
                    errors.append(exc)

            raise ModelError(
                f"{value!r} passt zu keinem Typ aus {target_type!r}"
            ) from (errors[-1] if errors else None)

        if origin is list:
            if not isinstance(value, list):
                raise ModelError(
                    f"Liste erwartet, erhalten: {type(value).__name__}"
                )

            item_type = args[0] if args else Any

            return [
                cls._convert_value(item, item_type)
                for item in value
            ]

        if origin is dict:
            if not isinstance(value, Mapping):
                raise ModelError(
                    f"Dictionary erwartet, erhalten: {type(value).__name__}"
                )

            key_type, value_type = args or (Any, Any)

            return {
                cls._convert_value(key, key_type):
                cls._convert_value(item, value_type)
                for key, item in value.items()
            }

        if origin is Literal:
            if value not in args:
                raise ModelError(
                    f"{value!r} ist kein erlaubter Wert aus {args!r}"
                )
            return value

        if isinstance(target_type, type) and issubclass(
            target_type,
            BaseModel,
        ):
            if not isinstance(value, Mapping):
                raise ModelError(
                    f"{target_type.__name__} erwartet ein Mapping"
                )

            return target_type.from_dict(value)

        if target_type is datetime:
            if isinstance(value, datetime):
                return value

            if not isinstance(value, str):
                raise ModelError("datetime erwartet einen ISO-String")

            return datetime.fromisoformat(value.replace("Z", "+00:00"))

        if target_type is date:
            if isinstance(value, date):
                return value

            if not isinstance(value, str):
                raise ModelError("date erwartet einen ISO-String")

            return date.fromisoformat(value)

        if target_type is UUID:
            if isinstance(value, UUID):
                return value

            return UUID(str(value))

        # bool muss gesondert behandelt werden, da bool("false") True ergibt.
        if target_type is bool:
            if isinstance(value, bool):
                return value

            raise ModelError(
                f"Boolean erwartet, erhalten: {value!r}"
            )

        if target_type in (str, int, float):
            try:
                return target_type(value)
            except (TypeError, ValueError) as exc:
                raise ModelError(
                    f"{value!r} kann nicht in "
                    f"{target_type.__name__} umgewandelt werden"
                ) from exc

        return value

    @staticmethod
    def _allows_none(field_type: Any) -> bool:
        origin = get_origin(field_type)

        return (
            origin in (Union, types.UnionType)
            and type(None) in get_args(field_type)
        )

    @staticmethod
    def _snake_to_camel(name: str) -> str:
        first, *rest = name.split("_")
        return first + "".join(part.capitalize() for part in rest)

    def __repr__(self) -> str:
        hints = get_type_hints(type(self))

        values = ", ".join(
            f"{name}={getattr(self, name, None)!r}"
            for name, field_type in hints.items()
            if get_origin(field_type) is not ClassVar
        )

        return f"{type(self).__name__}({values})"
