"""The wait shown in a refused abuse limit: rounded up, so nobody retries too early."""

from datetime import timedelta

import pytest

from app.services.organisations import describe_wait


@pytest.mark.parametrize(
    ("delta", "phrase"),
    [
        (timedelta(seconds=0), "in 1 minute"),
        (timedelta(seconds=20), "in 1 minute"),
        (timedelta(minutes=1, seconds=1), "in 2 minutes"),
        (timedelta(minutes=59), "in 59 minutes"),
        (timedelta(minutes=59, seconds=30), "in about 1 hour"),
        (timedelta(hours=1, minutes=1), "in about 2 hours"),
        (timedelta(hours=23, minutes=59), "in about 24 hours"),
    ],
)
def test_describe_wait(delta: timedelta, phrase: str) -> None:
    assert describe_wait(delta) == phrase
