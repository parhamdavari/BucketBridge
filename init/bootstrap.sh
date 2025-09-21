#!/usr/bin/env sh
set -eu

echo "Starting MinIO initialization..."

# Export MinIO client alias for this session
export MC_HOST_local="http://$MINIO_ROOT_USER:$MINIO_ROOT_PASSWORD@minio:9000"

# Retry loop to wait for MinIO to be ready (up to 60 seconds)
echo "Waiting for MinIO to be ready..."
RETRY_COUNT=0
MAX_RETRIES=60

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if mc alias set local "http://minio:9000" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" 2>/dev/null; then
        echo "MinIO is ready!"
        break
    fi
    echo "MinIO not ready, retrying in 1 second... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 1
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "ERROR: MinIO failed to become ready after $MAX_RETRIES seconds"
    exit 1
fi

# Create bucket idempotently
echo "Creating bucket: $MINIO_BUCKET"
mc mb "local/$MINIO_BUCKET" || true

# Create app user idempotently
echo "Creating app user: $OMS_ACCESS_KEY"
mc admin user add local "$OMS_ACCESS_KEY" "$OMS_SECRET_KEY" || true

# Generate policy file by substituting bucket name manually (no sed available)
echo "Generating IAM policy for bucket: $MINIO_BUCKET"
cat > /tmp/policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject"
            ],
            "Resource": "arn:aws:s3:::$MINIO_BUCKET/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket"
            ],
            "Resource": "arn:aws:s3:::$MINIO_BUCKET"
        }
    ]
}
EOF

# Create/ensure policy exists
echo "Creating IAM policy: app-rw"
mc admin policy create local app-rw /tmp/policy.json || true

# Attach policy to user
echo "Attaching policy to user: $OMS_ACCESS_KEY"
mc admin policy attach local app-rw --user "$OMS_ACCESS_KEY" || true

echo "✓ MinIO initialization completed successfully!"
echo "  - Bucket: $MINIO_BUCKET"
echo "  - User: $OMS_ACCESS_KEY"
echo "  - Policy: app-rw (RW access to $MINIO_BUCKET)"