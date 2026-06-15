"""Reusable response helpers for file-related endpoints."""

from fastapi.responses import Response


class FileDownloadResponse(Response):
    """Binary file download response with Content-Disposition header.

    Usage::

        @router.get("/download", response_model=None)
        async def download_file(...):
            return FileDownloadResponse(content=item.file, filename=item.file_name)
    """

    def __init__(
        self,
        content: bytes,
        filename: str,
        media_type: str = "application/octet-stream",
        **kwargs,
    ):
        super().__init__(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
            **kwargs,
        )
