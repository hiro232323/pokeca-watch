#!/usr/bin/env python3
"""Import authorized CSV price observations; never invent prices or scrape marketplaces.

Configure GitHub Actions repository variable POKEWATCH_FEED_URL with an HTTPS URL
serving a CSV of confirmed observations. If access needs a bearer token, store it
as the repository secret POKEWATCH_FEED_TOKEN. A source must permit this use and
republication before being configured.
"""
from __future__ import annotations

import csv
import io
import os
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "data" / "price_updates.csv"
ALLOWED_COLUMNS = ("date", "card_id", "name", "raw_price", "psa10_price", "source")


def normalize_price(value: str) -> str:
    s = (value or "").strip().replace(",", "").replace("￥", "").replace("¥", "")
    if not s:
        return ""
    n = int(s)
    if n <= 0 or n > 100000000:
        raise ValueError("Price outside allowed range")
    return str(n)


def rows_from(text: str):
    reader = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    if not reader.fieldnames or any(x not in reader.fieldnames for x in ALLOWED_COLUMNS):
        raise ValueError("CSV requires: " + ",".join(ALLOWED_COLUMNS))
    return [{k: (row.get(k) or "").strip() for k in ALLOWED_COLUMNS} for row in reader]


def validate(row: dict, permitted_ids: set[str], today: date):
    day = date.fromisoformat(row["date"])
    if day > today:
        raise ValueError("Future observation date")
    if day.year < 2000:
        raise ValueError("Date outside expected range")
    if row["card_id"] not in permitted_ids:
        raise ValueError("Unrecognized card ID")
    if not row["name"] or not row["source"]:
        raise ValueError("Name and source must not be blank")
    row["raw_price"] = normalize_price(row["raw_price"])
    row["psa10_price"] = normalize_price(row["psa10_price"])
    if not row["raw_price"] and not row["psa10_price"]:
        raise ValueError("At least one price required")
    return row


def read_remote(url: str, token: str):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("POKEWATCH_FEED_URL must be an HTTPS URL")
    headers = {"User-Agent": "PokeWatch/1.0", "Accept": "text/csv"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(url, headers=headers)
    with urlopen(req, timeout=25) as res:
        if urlsplit(res.geturl()).scheme != "https":
            raise ValueError("Feed redirected to non-HTTPS")
        if res.status != 200:
            raise ValueError(f"Feed HTTP status: {res.status}")
        raw = res.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("Feed is too large")
    return raw.decode("utf-8-sig")


def main():
    if not LOCAL.exists():
        raise FileNotFoundError("data/price_updates.csv not found")
    text = LOCAL.read_text(encoding="utf-8-sig")
    existing = rows_from(text)
    allowed = {r["card_id"] for r in existing}
    if not allowed:
        print("No registered cards. Nothing to update.")
        return
    url = os.environ.get("POKEWATCH_FEED_URL", "").strip()
    if not url:
        print("POKEWATCH_FEED_URL not set. Preserving the current 100 cards and prices.")
        return
    incoming = rows_from(read_remote(url, os.environ.get("POKEWATCH_FEED_TOKEN", "")))
    if not incoming:
        print("Feed has no observations. Nothing to update.")
        return
    today = datetime.now().astimezone().date()
    prepared = []
    for line, row in enumerate(incoming, start=2):
        try:
            prepared.append(validate(row, allowed, today))
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Feed row {line}: {exc}") from exc
    # Same date/card/source should represent one observation, not conflicting values.
    existing_by_key = {(r["date"], r["card_id"], r["source"]): r for r in existing}
    to_add = []
    for row in prepared:
        key = (row["date"], row["card_id"], row["source"])
        if key in existing_by_key:
            if existing_by_key[key] != row:
                raise ValueError(f"Conflict for {key}: do not silently replace observations")
            continue
        existing_by_key[key] = row
        to_add.append(row)
    if to_add:
        with LOCAL.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=ALLOWED_COLUMNS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(existing + to_add)
    print(f"Imported {len(to_add)} verified observations (of {len(prepared)} supplied).")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Price import failed: {exc}", file=sys.stderr)
        sys.exit(1)
