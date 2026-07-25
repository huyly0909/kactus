"""Market admin API — superuser-only gold history import.

Takes the browser's multipart upload, applies a size guard, and forwards each
file's raw bytes to the data plane (the only process that may write DuckDB).
Format detection and parsing live there, beside the table definition — this
endpoint never looks inside the CSV.
"""

from __future__ import annotations

from fastapi import File, UploadFile
from kactus_common.exceptions import ValidationError
from kactus_common.market.schema import GoldImportResultSchema
from kactus_common.router import KactusAPIRouter, multipart_upload_openapi
from kactus_fin import data_client

#: Largest known backfill file is ~7.4 MB (PNJ, 92k rows); 25 MB leaves room
#: for growth while still bounding what gets buffered in memory per file.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

router = KactusAPIRouter(prefix="/api/market", tags=["market-admin"])


@router.post("/gold/import", **multipart_upload_openapi("files"))
async def import_gold_history(
    files: list[UploadFile] = File(...),
) -> list[GoldImportResultSchema]:
    """Import gold-history CSVs, one result per file (order preserved)."""
    results: list[GoldImportResultSchema] = []
    for upload in files:
        content = await upload.read()
        if len(content) > MAX_UPLOAD_BYTES:
            raise ValidationError(
                f"File '{upload.filename}' exceeds the "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit"
            )
        results.append(
            await data_client.import_gold_history(
                upload.filename or "upload.csv", content
            )
        )
    return results
