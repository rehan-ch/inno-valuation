"""Email address normalisation. Emails are stored and compared lowercased."""


def normalise_email(value: str) -> str:
    """Trim and lowercase an email address. The database rejects any other form."""
    return value.strip().lower()
