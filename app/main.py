import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError
from s3wrap import s3_client
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger("bucketbridge.startup")


app = FastAPI(
    title="BucketBridge API",
    description="Minimal FastAPI bridge to a private MinIO bucket",
    version="1.0.0"
)


class PresignUploadRequest(BaseModel):
    key: str = Field(..., description="Object key to upload to")
    content_type: Optional[str] = Field(
        None, description="Content type that the uploader must send"
    )
    content_length: int = Field(..., gt=0, description="Expected upload size in bytes")
    expires_in: int = Field(900, description="URL lifetime in seconds")

    @field_validator('key')
    def validate_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Key must be a non-empty string")
        return value

    @field_validator('expires_in')
    def validate_expires(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("expires_in must be positive")
        if value > 604800:
            raise ValueError("expires_in cannot exceed 7 days (604800 seconds)")
        return value


class PresignDownloadRequest(BaseModel):
    key: str = Field(..., description="Object key to download")
    expires_in: int = Field(900, description="URL lifetime in seconds")
    disposition: Optional[str] = Field(
        None,
        description="Optional content disposition (inline or attachment)")
    filename: Optional[str] = Field(
        None,
        description="Preferred filename to expose in content disposition"
    )
    content_type: Optional[str] = Field(
        None,
        description="Override the response content type"
    )

    @field_validator('key')
    def validate_key(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Key must be a non-empty string")
        return value

    @field_validator('disposition')
    def validate_disposition(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        lowered = value.lower()
        if lowered not in {'inline', 'attachment'}:
            raise ValueError("disposition must be 'inline' or 'attachment'")
        return lowered

    @field_validator('expires_in')
    def validate_expires(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("expires_in must be positive")
        if value > 604800:
            raise ValueError("expires_in cannot exceed 7 days (604800 seconds)")
        return value


def _format_expiry(seconds: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    return expires_at.isoformat().replace("+00:00", "Z")


@app.post("/files/presign-upload")
async def presign_upload(request: PresignUploadRequest):
    try:
        url, headers = s3_client.presign_put(
            key=request.key,
            expires_in=request.expires_in,
            content_type=request.content_type
        )

        response_headers: Dict[str, str] = dict(headers)
        response_headers['Content-Length'] = str(request.content_length)

        return {
            'key': request.key,
            'url': url,
            'method': 'PUT',
            'headers': response_headers,
            'expires_at': _format_expiry(request.expires_in)
        }

    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")


@app.post("/files/presign-download")
async def presign_download(request: PresignDownloadRequest):
    try:
        disposition_header: Optional[str] = None
        if request.disposition:
            filename = request.filename.strip() if request.filename else request.key.split('/')[-1]
            if filename:
                disposition_header = f"{request.disposition}; filename=\"{filename}\""
            else:
                disposition_header = request.disposition

        url, headers = s3_client.presign_get(
            key=request.key,
            expires_in=request.expires_in,
            content_disposition=disposition_header,
            response_content_type=request.content_type
        )

        response_headers = dict(headers)

        return {
            'key': request.key,
            'url': url,
            'method': 'GET',
            'headers': response_headers,
            'expires_at': _format_expiry(request.expires_in)
        }

    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code') if hasattr(e, 'response') else None
        if error_code == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download URL: {str(e)}")


@app.on_event("startup")
async def ensure_storage_ready():
    attempts = int(os.getenv("S3_HEALTH_RETRIES", "10"))
    backoff = float(os.getenv("S3_HEALTH_BACKOFF", "3"))

    for attempt in range(1, attempts + 1):
        if s3_client.health_check():
            return

        logger.warning(
            "MinIO health check failed (attempt %s/%s); retrying in %ss",
            attempt,
            attempts,
            backoff,
        )
        await asyncio.sleep(backoff)

    raise RuntimeError("MinIO health check failed after repeated attempts")


@app.post("/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    key: str = Query(None, description="Optional object key. If not provided, uses filename")
):
    """
    Upload a file to MinIO storage using streaming multipart upload.
    """
    try:
        # Use provided key or fallback to filename
        object_key = key if key else file.filename

        if not object_key:
            raise HTTPException(status_code=400, detail="No filename provided and no key specified")

        # Stream upload to MinIO
        s3_client.put_stream(
            key=object_key,
            fileobj=file.file,
            content_type=file.content_type or 'application/octet-stream'
        )

        return {
            "message": "File uploaded successfully",
            "key": object_key,
            "filename": file.filename,
            "content_type": file.content_type
        }

    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/files/{key}")
async def download_file(key: str):
    """
    Download a file from MinIO storage using streaming response.
    """
    try:
        # Get object from MinIO
        obj = s3_client.get_obj(key)

        # Create streaming response
        def stream_content():
            try:
                for chunk in obj['Body'].iter_chunks(chunk_size=8192):
                    yield chunk
            except Exception:
                pass
            finally:
                obj['Body'].close()

        headers = {
            'Content-Disposition': f'attachment; filename="{key}"'
        }

        return StreamingResponse(
            stream_content(),
            media_type=obj['ContentType'],
            headers=headers
        )

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@app.delete("/files/{key}")
async def delete_file(key: str):
    """
    Delete a file from MinIO storage.
    """
    try:
        # Delete object from MinIO
        s3_client.delete_obj(key)

        return {
            "message": "File deleted successfully",
            "key": key
        }

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")


@app.get("/files/{key}/metadata")
async def get_file_metadata(key: str):
    """
    Retrieve metadata for an existing object without streaming its contents.
    """
    try:
        metadata = s3_client.stat_obj(key)

        last_modified = metadata.get('last_modified')
        if isinstance(last_modified, datetime):
            last_modified = last_modified.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

        return {
            'key': metadata.get('key', key),
            'content_length': metadata.get('content_length'),
            'content_type': metadata.get('content_type'),
            'etag': metadata.get('etag'),
            'last_modified': last_modified
        }

    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            raise HTTPException(status_code=404, detail="File not found")
        raise HTTPException(status_code=500, detail=f"S3 error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Metadata lookup failed: {str(e)}")


@app.get("/health")
async def health_check():
    """
    Health check endpoint that verifies S3 connectivity.
    """
    try:
        # Perform a simple S3 operation to verify connectivity
        is_healthy = s3_client.health_check()

        if is_healthy:
            return {"ok": True}
        else:
            raise HTTPException(status_code=503, detail="S3 connection unhealthy")

    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Health check failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv('APP_PORT', 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
