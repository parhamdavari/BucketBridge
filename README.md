# BucketBridge

Minimal FastAPI bridge to a private MinIO bucket. Provides upload, download, delete, and health endpoints while keeping MinIO off the public network.

## Highlights
- Docker Compose stack with MinIO, bootstrapper, and FastAPI app
- Streamed uploads/downloads so large files do not exhaust memory
- Opinionated bootstrap script that creates the bucket, user, and policy on startup

## Prerequisites
- Docker + Docker Compose v2
- Copy of the repo and permission to run containers locally

## Quick Start
```bash
cp .env.example .env
# Update credentials if needed, then:
docker compose up -d --build
```

The API becomes available at `http://localhost:8080` once the bootstrap container finishes.

## Configuration
Environment variables are read from `.env` by Docker Compose.

| Variable | Purpose |
| --- | --- |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Admin credentials used by the MinIO server and bootstrap container |
| `MINIO_BUCKET` | Bucket created at startup and used by the app |
| `OMS_ACCESS_KEY`, `OMS_SECRET_KEY` | Application user with RW access to the bucket |
| `S3_REGION` | Region name passed to the AWS SDK (defaults to `us-east-1`) |
| `APP_PORT` | Port exposed by FastAPI inside the container (default `8080`) |

## Services
- `minio`: MinIO server on an internal Docker network; console exposed at `http://localhost:9001`
- `minio-init`: One-shot container that waits for MinIO, then provisions the bucket, IAM policy, and app user
- `app`: FastAPI service exposing the REST API on `http://localhost:8080`

## API Reference
Base URL: `http://localhost:8080`

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/files/upload` | Multipart upload; optional `key` query parameter to override filename |
| `GET` | `/files/{key}` | Stream file download |
| `DELETE` | `/files/{key}` | Remove object from bucket |
| `GET` | `/health` | Verifies connectivity to MinIO |

### Example Requests
```bash
# Upload a file
curl -F "file=@README.md" http://localhost:8080/files/upload

# Download the same file
curl -o README.copy.md http://localhost:8080/files/README.md

# Remove it again
curl -X DELETE http://localhost:8080/files/README.md
```

## Development Notes
- App source lives in `app/main.py`; S3 helper in `app/s3wrap.py`
- Python dependencies defined in `app/requirements.txt`
- `init/bootstrap.sh` contains the provisioning logic for the MinIO user and bucket

Stop the stack with `docker compose down`. To remove MinIO data as well, add the `-v` flag.
