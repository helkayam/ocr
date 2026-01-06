from minio import Minio
from minio.error import S3Error
import os
from datetime import timedelta




MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "protocol-files")


client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=False
)


def generate_presigned_upload_url(object_name: str, expires: int = 3600) -> str:
    """
    Generate a signed URL for uploading a file directly to MinIO
    """
    return client.presigned_put_object(MINIO_BUCKET, object_name, expires=timedelta(hours=1))
