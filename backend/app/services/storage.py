"""Stockage objets S3 compatible : captures, crops, dataset. Les URLs présignées sont signées sur
l'adresse publique (celle que verra le navigateur), l'écriture passe par l'adresse interne."""

from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings


class Storage(Protocol):
    def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"
    ) -> None: ...
    def copy(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> None: ...
    def exists(self, bucket: str, key: str) -> bool: ...
    def get_bytes(self, bucket: str, key: str) -> bytes: ...
    def delete(self, bucket: str, key: str) -> None: ...
    def presigned_get_url(self, bucket: str, key: str, expires_in: int) -> str: ...
    def check(self) -> bool: ...


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        session = boto3.session.Session(
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )
        config = Config(
            s3={"addressing_style": "path"},
            retries={"max_attempts": 2},
            connect_timeout=3,
            read_timeout=10,
        )
        self._client = session.client("s3", endpoint_url=settings.s3_endpoint_url, config=config)
        self._public = session.client(
            "s3", endpoint_url=settings.s3_public_endpoint_url, config=config
        )
        self._captures_bucket = settings.s3_bucket_captures

    def put_bytes(
        self, bucket: str, key: str, data: bytes, content_type: str = "image/jpeg"
    ) -> None:
        self._client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)

    def copy(self, src_bucket: str, src_key: str, dst_bucket: str, dst_key: str) -> None:
        self._client.copy_object(
            Bucket=dst_bucket, Key=dst_key, CopySource={"Bucket": src_bucket, "Key": src_key}
        )

    def exists(self, bucket: str, key: str) -> bool:
        try:
            self._client.head_object(Bucket=bucket, Key=key)
        except ClientError:
            return False
        return True

    def get_bytes(self, bucket: str, key: str) -> bytes:
        return self._client.get_object(Bucket=bucket, Key=key)["Body"].read()

    def delete(self, bucket: str, key: str) -> None:
        self._client.delete_object(Bucket=bucket, Key=key)

    def presigned_get_url(self, bucket: str, key: str, expires_in: int) -> str:
        return self._public.generate_presigned_url(
            "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
        )

    def check(self) -> bool:
        try:
            self._client.head_bucket(Bucket=self._captures_bucket)
        except (ClientError, BotoCoreError):
            return False
        return True
