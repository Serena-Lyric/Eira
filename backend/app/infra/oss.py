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


def get_object_bytes(bucket: str, key: str) -> tuple[bytes, str]:
    """直接从 OSS 读取对象的完整字节（同 knowledge/service.py 的可用模式）。

    返回 (data, content_type)。供 Live2D 模型下载端点使用——后端直读后
    整体返回给前端，绕开浏览器经 Vite proxy 转发 presigned URL 时
    changeOrigin 改写 Host 导致的 MinIO 签名校验失败。
    """
    resp = get_oss_client().get_object(Bucket=bucket, Key=key)
    data = resp["Body"].read()
    content_type = resp.get("ContentType") or "application/octet-stream"
    return data, content_type
