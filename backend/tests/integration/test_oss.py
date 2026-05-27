import pytest
from app.infra.oss import get_oss_client, presign_get


@pytest.mark.asyncio
async def test_put_and_presign():
    s3 = get_oss_client()
    s3.put_object(
        Bucket="eira-documents", Key="health/probe.txt", Body=b"hello"
    )
    url = presign_get("eira-documents", "health/probe.txt", expires=60)
    assert url.startswith("http")
    assert "X-Amz-Signature" in url or "Signature=" in url
