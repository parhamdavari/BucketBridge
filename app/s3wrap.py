import os
import boto3
from botocore.config import Config
from boto3.s3.transfer import TransferConfig


class S3Wrapper:
    def __init__(self):
        # Read configuration from environment variables
        self.endpoint_url = os.getenv('S3_ENDPOINT', 'http://minio:9000')
        self.bucket_name = os.getenv('S3_BUCKET')
        self.access_key = os.getenv('S3_ACCESS_KEY')
        self.secret_key = os.getenv('S3_SECRET_KEY')
        self.region = os.getenv('S3_REGION', 'us-east-1')

        if not all([self.bucket_name, self.access_key, self.secret_key]):
            raise ValueError("Missing required S3 configuration environment variables")

        # Configure boto3 for MinIO compatibility
        config = Config(
            s3={
                'addressing_style': 'path',  # Required for MinIO
                'signature_version': 's3v4'
            },
            region_name=self.region
        )

        # Create S3 client
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=config
        )

        # Configure multipart transfer settings
        # 8MB chunks with concurrency of 4
        self.transfer_config = TransferConfig(
            multipart_threshold=8 * 1024 * 1024,  # 8MB
            multipart_chunksize=8 * 1024 * 1024,  # 8MB
            max_concurrency=4,
            use_threads=True
        )

    def put_stream(self, key: str, fileobj, content_type: str = 'application/octet-stream'):
        """
        Upload a file-like object to S3 using multipart upload with streaming.

        Args:
            key: S3 object key
            fileobj: File-like object to upload
            content_type: MIME type of the file
        """
        extra_args = {'ContentType': content_type}

        self.client.upload_fileobj(
            fileobj,
            self.bucket_name,
            key,
            ExtraArgs=extra_args,
            Config=self.transfer_config
        )

    def get_obj(self, key: str):
        """
        Get an object from S3.

        Args:
            key: S3 object key

        Returns:
            dict: Object with 'Body' stream and 'ContentType'
        """
        response = self.client.get_object(Bucket=self.bucket_name, Key=key)
        return {
            'Body': response['Body'],
            'ContentType': response.get('ContentType', 'application/octet-stream')
        }

    def delete_obj(self, key: str):
        """
        Delete an object from S3.

        Args:
            key: S3 object key
        """
        self.client.delete_object(Bucket=self.bucket_name, Key=key)

    def health_check(self):
        """
        Perform a simple health check by listing objects in the bucket.

        Returns:
            bool: True if the connection is healthy
        """
        try:
            self.client.list_objects_v2(Bucket=self.bucket_name, MaxKeys=1)
            return True
        except Exception:
            return False


# Global instance
s3_client = S3Wrapper()