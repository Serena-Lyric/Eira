from functools import lru_cache
import boto3
from botocore.client import Config
from app.core.config import get_settings


def _opts() -> dict:
    s = get_settings().oss
    return {
        "endpoint_url": s.endpoint,
        "aws_access_key_id": s.key,
        "aws_secret_access_key": s.secret,
        "region_name": s.region,
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
