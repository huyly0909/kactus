"""``POST /internal/gold/import`` + the gold history reads.

The import endpoint is the data plane's only data-in surface, so the suite
covers all four edges: a good file lands and is idempotent, a bad file is a
400 (the caller's mistake, not a 500), an anonymous caller is rejected, and
the reads serve back what the import wrote — oldest first, capped, filtered.
"""

from __future__ import annotations

import pytest

SJC_CSV = (
    "date,buy_vnd_per_luong,sell_vnd_per_luong\n"
    "2026-07-22,133000000,138000000\n"
    "2026-07-23,134000000,139000000\n"
    "2026-07-24,134500000,139500000\n"
)


async def _import(client, csv_text: str, filename: str = "sjc.csv"):
    return await client.post(
        "/internal/gold/import",
        params={"filename": filename},
        content=csv_text.encode(),
        headers={"Content-Type": "text/csv"},
    )


@pytest.mark.asyncio
async def test_import_and_reimport_is_idempotent(client):
    resp = await _import(client, SJC_CSV)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["dataset"] == "sjc"
    assert data["filename"] == "sjc.csv"
    assert data["rows_parsed"] == "3"
    assert data["rows_imported"] == "3"
    assert data["rows_skipped"] == "0"
    assert data["codes"] == "1"

    again = await _import(client, SJC_CSV)
    assert again.json()["data"]["rows_imported"] == "3"

    codes = (await client.get("/internal/market/gold/history/codes")).json()["data"]
    assert len(codes) == 1
    assert codes[0]["code"] == "SJC"
    assert codes[0]["points"] == "3"
    assert codes[0]["first_date"] == "2026-07-22"
    assert codes[0]["last_date"] == "2026-07-24"


@pytest.mark.asyncio
async def test_import_rejects_unknown_header(client):
    resp = await _import(client, "date,price\n2026-01-01,5\n", "junk.csv")
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_import_requires_service_token(anon_client):
    resp = await anon_client.post("/internal/gold/import", content=SJC_CSV.encode())
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_history_read_is_oldest_first_and_filterable(client):
    await _import(client, SJC_CSV)

    resp = await client.get("/internal/market/gold/history", params={"code": "SJC"})
    assert resp.status_code == 200
    points = resp.json()["data"]
    assert [p["date"] for p in points] == [
        "2026-07-22",
        "2026-07-23",
        "2026-07-24",
    ]
    # Money survives the hop as an exact decimal string.
    assert points[-1]["buy_price"] == "134500000"
    assert points[0]["unit"] == "VND/luong"

    windowed = await client.get(
        "/internal/market/gold/history",
        params={"code": "SJC", "start": "2026-07-23", "end": "2026-07-23"},
    )
    assert [p["date"] for p in windowed.json()["data"]] == ["2026-07-23"]

    # The cap keeps the *newest* rows, re-sorted oldest → newest.
    capped = await client.get(
        "/internal/market/gold/history", params={"code": "SJC", "limit": 2}
    )
    assert [p["date"] for p in capped.json()["data"]] == [
        "2026-07-23",
        "2026-07-24",
    ]


@pytest.mark.asyncio
async def test_history_of_unknown_code_is_empty(client):
    resp = await client.get("/internal/market/gold/history", params={"code": "NOPE"})
    assert resp.status_code == 200
    assert resp.json()["data"] == []
