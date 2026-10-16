"""Read JSON or CSV files into validated :class:`Company` objects."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any, NoReturn

from .models import STATEMENTS, Company, InputError, ValidationError
from .validate import DEFAULT_TOLERANCE, build_company

META_KEYS = ("company", "currency", "units", "synthetic", "note")


def _reject_constant(name: str) -> NoReturn:
    raise ValueError(f"{name} is not a valid number")


def parse_json(text: str, source: str = "input") -> Any:
    try:
        return json.loads(text, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise InputError(
            f"{source}: invalid JSON at line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except ValueError as exc:
        raise InputError(f"{source}: {exc}") from exc


def csv_to_raw(text: str, default_name: str = "Unnamed company") -> dict[str, Any]:
    """Convert the wide CSV layout into the JSON-shaped dictionary.

    Layout: header ``statement,item,<year>,<year>,...``; one row per line item; optional
    ``meta`` rows (``meta,company,Acme``) put their value in the third column.
    """
    rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    if not rows:
        raise InputError("CSV file is empty")
    header = [c.strip() for c in rows[0]]
    if header[:2] != ["statement", "item"] or len(header) < 3:
        raise InputError(
            "CSV header must start with 'statement,item' followed by one column per fiscal "
            "year, e.g. statement,item,2023,2024"
        )
    errors: list[str] = []
    year_cols: list[int] = []
    for cell in header[2:]:
        try:
            year_cols.append(int(cell))
        except ValueError:
            errors.append(f"CSV header: '{cell}' is not a fiscal year")
    if errors:
        raise ValidationError(errors)
    meta: dict[str, Any] = {}
    data: dict[int, dict[str, dict[str, float]]] = {
        y: {s: {} for s in STATEMENTS} for y in year_cols
    }
    for line_no, row in enumerate(rows[1:], start=2):
        stmt = row[0].strip()
        item = row[1].strip() if len(row) > 1 else ""
        if stmt == "meta":
            value = row[2].strip() if len(row) > 2 else ""
            meta[item] = value.lower() == "true" if item == "synthetic" else value
            continue
        if stmt not in STATEMENTS:
            errors.append(f"CSV line {line_no}: unknown statement '{stmt}'")
            continue
        for year, cell in zip(year_cols, row[2:], strict=False):
            cell = cell.strip().replace(",", "")
            if not cell:
                continue
            if item in data[year][stmt]:
                errors.append(f"CSV line {line_no}: duplicate item '{item}'")
                break
            try:
                data[year][stmt][item] = float(cell)
            except ValueError:
                errors.append(f"CSV line {line_no}: '{cell}' is not a number ({stmt}.{item})")
    if errors:
        raise ValidationError(errors)
    raw: dict[str, Any] = {k: v for k, v in meta.items() if k in META_KEYS}
    raw.setdefault("company", default_name)
    raw["years"] = [{"year": y, **data[y]} for y in year_cols]
    return raw


def load_company(path: str | Path, tolerance: float = DEFAULT_TOLERANCE) -> Company:
    """Load and validate a ``.json`` or ``.csv`` file."""
    p = Path(path)
    if not p.is_file():
        raise InputError(f"file not found: {p}")
    suffix = p.suffix.lower()
    if suffix not in (".json", ".csv"):
        raise InputError(f"{p.name}: unsupported file type '{suffix}', use .json or .csv")
    try:
        text = p.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        raise InputError(f"{p}: cannot read file as UTF-8 text ({exc})") from exc
    raw = parse_json(text, p.name) if suffix == ".json" else csv_to_raw(text, p.stem)
    return build_company(raw, tolerance)
