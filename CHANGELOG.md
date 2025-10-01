# Changelog

All notable changes to BucketBridge will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Production-grade multi-stage Dockerfile with non-root user
- Multi-architecture Docker image support (linux/amd64, linux/arm64)
- Automated GitHub Actions workflow for GHCR publishing
- Security scanning with Trivy
- SBOM (Software Bill of Materials) generation
- Pinned dependencies with requirements-lock.txt
- Comprehensive OCI image labels
- Docker image badges in README
- Pre-built image deployment instructions

### Changed
- Moved Dockerfile to repository root for better visibility
- Enhanced .dockerignore for optimal build context
- Renamed repository from rasa-storage to bucketbridge

### Security
- Running container as non-root user (bucketbridge:1000)
- Automated vulnerability scanning in CI/CD pipeline
- Multi-stage build reduces attack surface

## [1.0.0] - 2025-10-01

### Added
- Initial FastAPI bridge implementation
- MinIO S3 wrapper with streaming support
- Upload, download, delete, and metadata endpoints
- Presigned URL generation for direct client access
- Docker Compose stack with MinIO and initialization
- Health check endpoints and container healthchecks
- Comprehensive README with API documentation

### Features
- Multipart streaming uploads/downloads
- Configurable S3 endpoint and credentials
- Startup health check with retries
- Content type and disposition control
- Bootstrap script for automatic bucket provisioning

[Unreleased]: https://github.com/parhamdavari/bucketbridge/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/parhamdavari/bucketbridge/releases/tag/v1.0.0
