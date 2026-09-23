"""Optional row shaping for wide or long endpoints: sort_by / descending / limit / fields.

Agent harnesses cap tool output (~30k chars), so a 961-row, 100-column table is
unreadable however correct it is. These params let the caller ask for the rows
and columns it needs. Shaping runs on the normalized output rows, after the
provider fetch, so upstream requests (and record/replay keys) never change.

Semantics:
- ``fields``: comma-separated keep-list (or a list). The endpoint's identity
  columns and the ``sort_by`` column are always kept.
- ``sort_by``: one column. Numbers (and numeric strings) sort numerically,
  before any non-numeric strings; missing values (absent, None, NaN, "") always
  go last, whichever direction.
- ``descending``: default True; only meaningful with ``sort_by``.
- ``limit``: positive int, applied after sorting.

With none of ``sort_by``, ``limit`` or ``fields`` the rows are returned
untouched and no metadata is added, so default output is byte-for-byte
unchanged. Otherwise the caller merges ``total_rows`` (before limit) and
``returned_rows`` into its response.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


class ShapingError(ValueError):
    """A shaping parameter is invalid. The message is written for the agent."""


def _is_missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    try:
        return bool(value != value)  # NaN
    except Exception:
        return False


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in ("true", "1", "yes"):
        return True
    if text in ("false", "0", "no"):
        return False
    raise ShapingError(f"Invalid descending {value!r}: use true or false.")


def parse_limit(value: Any) -> int:
    try:
        if isinstance(value, bool):
            raise ValueError
        limit = int(value)
    except (TypeError, ValueError):
        raise ShapingError(f"Invalid limit {value!r}: must be a positive integer.") from None
    if limit < 1:
        raise ShapingError(f"Invalid limit {value!r}: must be a positive integer.")
    return limit


def _parse_fields(value: Any) -> list[str]:
    items = value.split(",") if isinstance(value, str) else list(value)
    fields = [str(f).strip() for f in items if str(f).strip()]
    if not fields:
        raise ShapingError("fields is empty: pass a comma-separated list of column names.")
    return fields


def _columns(rows: Sequence[Mapping[str, Any]], nested: str | None) -> list[str]:
    """All column names seen across rows, in first-seen order."""
    seen: dict[str, None] = {}
    for row in rows:
        for key in row:
            if key != nested:
                seen.setdefault(key, None)
        if nested and isinstance(row.get(nested), Mapping):
            for key in row[nested]:
                seen.setdefault(key, None)
    return list(seen)


def _get(row: Mapping[str, Any], column: str, nested: str | None) -> Any:
    if column in row and column != nested:
        return row[column]
    if nested and isinstance(row.get(nested), Mapping):
        return row[nested].get(column)
    return None


def _unknown(kind: str, names: Iterable[str], valid: list[str]) -> ShapingError:
    return ShapingError(
        f"Unknown {kind} {', '.join(repr(n) for n in names)}. Valid columns: {', '.join(valid)}"
    )


def shape_rows(
    rows: list[dict[str, Any]],
    params: Mapping[str, Any],
    *,
    identity: Sequence[str] = (),
    nested: str | None = None,
    total_rows: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Apply sort_by / descending / limit / fields to normalized rows.

    ``identity`` columns are always kept by ``fields``. ``nested`` names a dict
    column (e.g. nflverse's ``stats``) whose keys are addressable as columns too;
    it is kept as a dict holding only the selected keys. ``total_rows`` overrides
    the pre-limit count when the caller already truncated upstream of here.

    Returns ``(rows, meta)``; ``meta`` is empty when no shaping param was given.
    Raises ``ShapingError`` for invalid values or unknown columns.
    """
    sort_by = params.get("sort_by")
    limit = params.get("limit")
    fields = params.get("fields")
    if sort_by is None and limit is None and fields is None:
        return rows, {}

    descending = _parse_bool(params["descending"]) if params.get("descending") is not None else True
    limit = parse_limit(limit) if limit is not None else None
    fields = _parse_fields(fields) if fields is not None else None
    sort_by = str(sort_by).strip() if sort_by is not None else None

    total = len(rows) if total_rows is None else total_rows
    # With no rows there is nothing to validate against; an empty answer is correct.
    if rows:
        valid = _columns(rows, nested)
        if sort_by is not None and sort_by not in valid:
            raise _unknown("sort_by column", [sort_by], valid)
        if fields is not None:
            missing = [f for f in fields if f not in valid]
            if missing:
                raise _unknown("fields", missing, valid)

    if sort_by is not None:
        present, absent = [], []
        for row in rows:
            (absent if _is_missing(_get(row, sort_by, nested)) else present).append(row)

        def key(row):
            value = _get(row, sort_by, nested)
            num = _numeric(value)
            # Numbers come before non-numeric strings in both directions;
            # the leading rank flips because ``reverse`` flips it back.
            if num is not None:
                return (1, num, "") if descending else (0, num, "")
            return (0, 0.0, str(value)) if descending else (1, 0.0, str(value))

        rows = sorted(present, key=key, reverse=descending) + absent

    if limit is not None:
        rows = rows[:limit]

    if fields is not None:
        keep = set(identity) | set(fields)
        if sort_by is not None:
            keep.add(sort_by)
        shaped = []
        for row in rows:
            out = {k: v for k, v in row.items() if k in keep and k != nested}
            if nested and nested in row:
                inner = row[nested] if isinstance(row[nested], Mapping) else {}
                out[nested] = {k: v for k, v in inner.items() if k in keep}
            shaped.append(out)
        rows = shaped

    return rows, {"total_rows": total, "returned_rows": len(rows)}
