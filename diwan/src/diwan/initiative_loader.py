from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, PositiveInt


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        str_min_length=1,
        str_strip_whitespace=True,
    )


class Task(ConfigModel):
    name: str
    saviom_value: PositiveInt
    description: str = ""


class Initiative(ConfigModel):
    name: str
    saviom_value: PositiveInt
    tasks: list[Task]
    description: str = ""


class InitiativesConfig(ConfigModel):
    initiatives: list[Initiative]


def load_initiatives() -> list[Initiative]:
    cfg = yaml.safe_load(
        (Path.home() / "diwan" / "initiatives.yaml").read_text(encoding="utf-8")
    )

    return InitiativesConfig.model_validate(cfg).initiatives
