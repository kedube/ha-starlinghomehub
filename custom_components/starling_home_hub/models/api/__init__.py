"""Response models for the Starling Home Hub Developer Connect API."""

from dataclasses import fields
from typing import Any, Self


class ApiModel:
    """Mixin that builds a dataclass from an API payload, ignoring unknown fields."""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Create an instance, dropping keys the model does not declare."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})
