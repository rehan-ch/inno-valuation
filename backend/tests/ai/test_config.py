"""config/ai.yml: complete, strict, and priced. No database."""

from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from app.ai.config import AI_CONFIG_PATH, ModelPrice, get_ai_config, load_ai_config
from app.models.enums import AiTouchpoint


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load(AI_CONFIG_PATH.read_text())
    return data


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "ai.yml"
    path.write_text(yaml.safe_dump(data))
    return path


def test_every_touchpoint_is_configured_and_priced() -> None:
    config = get_ai_config()
    assert set(config.touchpoints) == set(AiTouchpoint)
    for settings in config.touchpoints.values():
        assert config.price(settings.model) is not None


def test_the_consultation_nudge_stays_off_until_built() -> None:
    assert get_ai_config().touchpoint(AiTouchpoint.CONSULTATION_NUDGE).enabled is False
    assert get_ai_config().touchpoint(AiTouchpoint.EXPLAIN_QUESTION).enabled is True


def test_temperature_is_refused(tmp_path: Path) -> None:
    # The API no longer takes it; the config must not pretend it does.
    data = _raw()
    data["touchpoints"]["explain_question"]["temperature"] = 0.4
    with pytest.raises(ValidationError, match="temperature"):
        load_ai_config(_write(tmp_path, data))


def test_a_missing_touchpoint_is_refused(tmp_path: Path) -> None:
    data = _raw()
    del data["touchpoints"]["bridge_gaps"]
    with pytest.raises(ValidationError, match="bridge_gaps"):
        load_ai_config(_write(tmp_path, data))


def test_an_unpriced_model_is_refused(tmp_path: Path) -> None:
    data = _raw()
    data["touchpoints"]["explain_question"]["model"] = "claude-haiku-5-5"
    with pytest.raises(ValidationError, match="claude-haiku-5-5"):
        load_ai_config(_write(tmp_path, data))


@pytest.mark.parametrize("effort", ["none", "extreme", ""])
def test_an_unknown_effort_is_refused(tmp_path: Path, effort: str) -> None:
    data = _raw()
    data["touchpoints"]["explain_question"]["effort"] = effort
    with pytest.raises(ValidationError):
        load_ai_config(_write(tmp_path, data))


def test_cost_is_whole_millionths_of_a_dollar_rounded_half_up() -> None:
    price = ModelPrice.model_validate({"input": "2.00", "output": "10.00"})
    # 612 x $2 + 148 x $10 per million tokens = 2704 millionths of a dollar.
    assert price.cost_micro_usd(612, 148) == 2704
    haiku_like = ModelPrice.model_validate({"input": "0.10", "output": "0.50"})
    assert haiku_like.cost_micro_usd(5, 1) == 1  # 0.5 + 0.5 = 1.0
    assert haiku_like.cost_micro_usd(5, 0) == 1  # 0.5 rounds half up
    assert haiku_like.cost_micro_usd(4, 0) == 0  # 0.4 rounds down
