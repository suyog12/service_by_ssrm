import os
import boto3
from botocore.config import Config


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{os.getenv('R2_ACCOUNT_ID')}.r2.cloudflarestorage.com",
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


BUCKET = os.getenv("R2_BUCKET_NAME", "service-by-ssrm")


def generate_upload_url(tenant_schema: str, room_id: str, filename: str) -> dict:
    client = get_r2_client()
    key = f"{tenant_schema}/{room_id}/{filename}"
    url = client.generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=300,
    )
    return {"upload_url": url, "key": key}


def generate_download_url(key: str) -> str:
    client = get_r2_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,
    )


def delete_object(key: str) -> None:
    client = get_r2_client()
    client.delete_object(Bucket=BUCKET, Key=key)