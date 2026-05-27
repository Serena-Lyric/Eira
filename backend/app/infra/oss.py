from functools import lru_cache
import os
import boto3
from botocore.client import Config


def _opts() -> dict:
    return {
        "endpoint_url": os.environ.get("EIRA_OSS_ENDPOINT", "http://localhost:9000"),
        "aws_access_key_id": os.environ.get("EIRA_OSS_KEY", "eira"),
        "aws_secret_access_key": os.environ.get("EIRA_OSS_SECRET", "eira-secret"),
        "region_name": os.environ.get("EIRA_OSS_REGION", "us-east-1"),
        "config": Config(signature_version="s3v4"),
    }


@lru_cache
def get_oss_client():
    return boto3.client("s3", **_opts())


def presign_get(bucket: str, key: str, expires: int = 600) -> str:
    return get_oss_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def presign_put(bucket: str, key: str, expires: int = 600) -> str:
    return get_oss_client().generate_presigned_url(
        "put_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )
