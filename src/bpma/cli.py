"""Command line: `bpma sync` (what the daily workflow runs) and `bpma extract` (read one image, for debugging)."""

import argparse
import datetime as dt
import logging
from pathlib import Path

from bpma.extract import extract
from bpma.gcal import GoogleCalendar
from bpma.page import PAGE_URL, fetch, find_sheets
from bpma.store import Store
from bpma.sync import sync


def main() -> None:
    parser = argparse.ArgumentParser(prog="bpma", description="Copy BPMA track bookings into Google Calendar.")
    commands = parser.add_subparsers(dest="command", required=True)
    sync_command = commands.add_parser("sync", help="Check the page and update the calendar if the sheets changed.")
    sync_command.add_argument("--dry-run", action="store_true", help="Show what would change without changing it.")
    sync_command.add_argument("--force", action="store_true", help="Rebuild future events even if nothing changed.")
    extract_command = commands.add_parser("extract", help="Read one sheet image and print the result.")
    extract_command.add_argument("image", type=Path)
    extract_command.add_argument("--model", help="e.g. google:gemini-3.5-flash")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.command == "sync":
        run = sync(
            now=dt.datetime.now(dt.UTC),
            sheets=find_sheets(fetch(PAGE_URL).text),
            store=Store(Path("data")),
            calendar=GoogleCalendar.from_env(),
            download=lambda url: fetch(url).content,
            extract=extract,
            force=args.force,
            dry_run=args.dry_run,
        )
        if run:
            print(f"Rebuilt the calendar: deleted {len(run.deleted)} future events, created {len(run.created)}.")
    elif args.command == "extract":
        image: Path = args.image
        media_type = "image/png" if image.suffix.lower() == ".png" else "image/jpeg"
        print(extract(image.read_bytes(), media_type, model=args.model).model_dump_json(indent=2))
