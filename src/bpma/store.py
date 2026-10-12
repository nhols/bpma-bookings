"""Files under data/: the audit trail of every sheet seen and every calendar rebuild.

data/sheets/<asset_id>/image.jpg        the image as first downloaded
data/sheets/<asset_id>/source.json      where and when it was found
data/sheets/<asset_id>/extraction.json  what the model read from it
data/sheets/<asset_id>/expected.json    hand-checked reading, used by the evals
data/runs/<time>.json                   each time the future calendar was rebuilt
"""

import datetime as dt
import mimetypes
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from bpma.gcal import Event
from bpma.page import SheetRef
from bpma.sheet import Sheet


class Source(BaseModel):
    url: str
    filename: str
    first_seen: dt.datetime


class Extraction(BaseModel):
    model: str  # the model that actually answered
    extracted_at: dt.datetime
    sheet: Sheet
    problems: list[str] = []  # anything that still looked wrong after the model double-checked


class Run(BaseModel):
    """One rebuild of the future calendar."""

    ran_at: dt.datetime
    sheets: list[str]  # asset ids on the page
    deleted: list[Event]
    created: list[Event]


@dataclass(frozen=True)
class Store:
    root: Path

    def _dir(self, asset_id: str) -> Path:
        return self.root / "sheets" / asset_id

    def has_image(self, asset_id: str) -> bool:
        return any(self._dir(asset_id).glob("image.*"))

    def save_image(self, ref: SheetRef, image: bytes, now: dt.datetime) -> None:
        folder = self._dir(ref.asset_id)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"image{Path(ref.filename).suffix.lower() or '.jpg'}").write_bytes(image)
        _write(folder / "source.json", Source(url=ref.url, filename=ref.filename, first_seen=now))

    def image(self, asset_id: str) -> tuple[bytes, str]:
        """The image bytes and their media type, e.g. "image/png"."""
        path = next(self._dir(asset_id).glob("image.*"))
        return path.read_bytes(), mimetypes.guess_type(path.name)[0] or "image/jpeg"

    def has_extraction(self, asset_id: str) -> bool:
        return (self._dir(asset_id) / "extraction.json").exists()

    def save_extraction(self, asset_id: str, extraction: Extraction) -> None:
        _write(self._dir(asset_id) / "extraction.json", extraction)

    def extraction(self, asset_id: str) -> Extraction:
        return Extraction.model_validate_json((self._dir(asset_id) / "extraction.json").read_text())

    def source(self, asset_id: str) -> Source:
        return Source.model_validate_json((self._dir(asset_id) / "source.json").read_text())

    def expected(self) -> dict[str, Sheet]:
        """Hand-checked readings, by asset id."""
        return {
            path.parent.name: Sheet.model_validate_json(path.read_text())
            for path in sorted((self.root / "sheets").glob("*/expected.json"))
        }

    def last_run(self) -> Run | None:
        runs = sorted((self.root / "runs").glob("*.json"))
        return Run.model_validate_json(runs[-1].read_text()) if runs else None

    def save_run(self, run: Run) -> None:
        (self.root / "runs").mkdir(parents=True, exist_ok=True)
        _write(self.root / "runs" / f"{run.ran_at.astimezone(dt.UTC):%Y-%m-%dT%H%M%SZ}.json", run)


def _write(path: Path, model: BaseModel) -> None:
    path.write_text(model.model_dump_json(indent=2) + "\n")
