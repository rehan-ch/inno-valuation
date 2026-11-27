"""Local file storage: what a key may be, and that files stay under the root."""

from pathlib import Path

import pytest

from app.core.storage import LocalFileStorage, check_key


def test_put_get_delete(tmp_path: Path) -> None:
    storage = LocalFileStorage(tmp_path)
    storage.put("reports/org/report.pdf", b"%PDF-1.7")
    assert storage.get("reports/org/report.pdf") == b"%PDF-1.7"
    storage.put("reports/org/report.pdf", b"%PDF-2.0")  # replaced whole
    assert storage.get("reports/org/report.pdf") == b"%PDF-2.0"
    assert [p.name for p in (tmp_path / "reports" / "org").iterdir()] == ["report.pdf"]
    storage.delete("reports/org/report.pdf")
    storage.delete("reports/org/report.pdf")  # deleting twice is fine
    with pytest.raises(FileNotFoundError):
        storage.get("reports/org/report.pdf")


@pytest.mark.parametrize(
    "key",
    [
        "../outside.pdf",
        "/etc/passwd",
        "reports/../../outside.pdf",
        "reports/a b.pdf",
        "reports/UPPER.pdf",
        "reports/no-extension",
        "",
        "reports//double.pdf",
    ],
)
def test_keys_that_could_leave_the_root_are_refused(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="Not a storage key"):
        check_key(key)
    with pytest.raises(ValueError, match="Not a storage key"):
        LocalFileStorage(tmp_path).put(key, b"x")
