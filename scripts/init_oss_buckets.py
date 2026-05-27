import os
import boto3

ENDPOINT = os.environ.get("EIRA_OSS_ENDPOINT", "http://localhost:9000")
KEY = os.environ.get("EIRA_OSS_KEY", "eira")
SECRET = os.environ.get("EIRA_OSS_SECRET", "eira-secret")

BUCKETS = [
    "eira-documents",
    "eira-live2d",
    "eira-backgrounds",
    "eira-audio",
    "eira-avatars",
]


def main():
    s3 = boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=KEY,
        aws_secret_access_key=SECRET,
        region_name="us-east-1",
    )
    for b in BUCKETS:
        try:
            s3.create_bucket(Bucket=b)
            print(f"created {b}")
        except s3.exceptions.BucketAlreadyOwnedByYou:
            print(f"exists  {b}")


if __name__ == "__main__":
    main()
