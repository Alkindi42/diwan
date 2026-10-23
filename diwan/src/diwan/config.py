"""Application settings stored in ~/diwan/config.yaml."""

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    saviom_timesheet_url: HttpUrl

    @field_validator("saviom_timesheet_url")
    @classmethod
    def require_https(cls, url: HttpUrl) -> HttpUrl:
        if url.scheme != "https":
            raise ValueError("saviom_timesheet_url must use HTTPS")
        return url


def load_config(path: Path | None = None) -> AppConfig:
    path = path if path is not None else Path.home() / "diwan" / "config.yaml"
    return AppConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
