"""The one error type the scoring engine raises for bad input or bad methodology data."""


class ScoringError(ValueError):
    """Raised when answers, scores, weights, costs or the question set are invalid."""


_MAX_SHOWN = 80


def describe(value: object) -> str:
    """A short, always-safe repr of a caller value for error messages.

    Huge integers cannot be turned into text (Python's digit limit), and long values would
    flood logs, so this never raises and caps the length.
    """
    try:
        text = repr(value)
    except ValueError:
        return f"<{type(value).__name__} too large to show>"
    return text if len(text) <= _MAX_SHOWN else text[: _MAX_SHOWN - 3] + "..."
