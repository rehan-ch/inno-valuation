"""Model settings per AI touchpoint, read from ``backend/config/ai.yml`` (never from code).

The file is loaded once, on first use, and checked strictly: every touchpoint present, no
unknown keys (a stray ``temperature`` fails loudly instead of being sent), and a list
price for every model a touchpoint uses, so each run's cost can be logged.
"""

from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.settings import BACKEND_DIR
from app.models.enums import AiTouchpoint

AI_CONFIG_PATH = BACKEND_DIR / "config" / "ai.yml"

Effort = Literal["low", "medium", "high", "xhigh", "max"]


class ModelPrice(BaseModel):
    """List price in US dollars per million tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: Decimal = Field(ge=0)
    output: Decimal = Field(ge=0)

    def cost_micro_usd(self, input_tokens: int, output_tokens: int) -> int:
        """The cost in millionths of a dollar, rounded half up. Dollars per million tokens
        times tokens is already millionths of a dollar."""
        cost = self.input * input_tokens + self.output * output_tokens
        return int(cost.quantize(Decimal(1), rounding=ROUND_HALF_UP))


class TouchpointSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    model: str = Field(min_length=1)
    effort: Effort
    max_tokens: int = Field(ge=256, le=128_000)
    timeout_seconds: float = Field(gt=0, le=600)
    enabled: bool = True


class AiConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    models: dict[str, ModelPrice]
    touchpoints: dict[AiTouchpoint, TouchpointSettings]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        missing = sorted(set(AiTouchpoint) - set(self.touchpoints))
        if missing:
            raise ValueError(f"touchpoints missing from ai.yml: {missing}")
        unpriced = sorted({t.model for t in self.touchpoints.values()} - set(self.models))
        if unpriced:
            raise ValueError(f"models without a price in ai.yml: {unpriced}")
        return self

    def touchpoint(self, key: AiTouchpoint) -> TouchpointSettings:
        return self.touchpoints[key]

    def price(self, model: str) -> ModelPrice | None:
        return self.models.get(model)


def load_ai_config(path: Path = AI_CONFIG_PATH) -> AiConfig:
    with path.open(encoding="utf-8") as handle:
        return AiConfig.model_validate(yaml.safe_load(handle))


@lru_cache
def get_ai_config() -> AiConfig:
    return load_ai_config()
