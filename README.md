# MinIO + FastAPI Storage Solution

## Quick Start

```bash
cp .env.example .env && docker compose up -d --build
```

## API Endpoints

- **Upload**: `POST http://localhost:8080/files/upload`
- **Download**: `GET http://localhost:8080/files/{key}`
- **Delete**: `DELETE http://localhost:8080/files/{key}`
- **Health**: `GET http://localhost:8080/health`

## Notes

- MinIO is **private** on `backend` network (no host ports)
- All file operations go through the FastAPI wrapper at `http://localhost:8080`
- Supports streaming uploads/downloads for large files