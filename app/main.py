import asyncio
import logging
import os
from datetime import datetime, timezone
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError
from s3wrap import s3_client


logger = logging.getLogger("bucketbridge.startup")


app = FastAPI(
    title="BucketBridge API",
    description="Minimal FastAPI bridge to a private MinIO bucket",
    version="1.0.0"
)


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
