"""S3 helpers for data storage and dashboard."""

import json
from datetime import datetime, timezone

import boto3

from shared.config import AWS_REGION, S3_BUCKET_DATA, S3_BUCKET_DASHBOARD

_s3 = boto3.client("s3", region_name=AWS_REGION)


def write_json(bucket: str, key: str, data: dict, cache_control: str = "max-age=60") -> None:
    _s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(data, default=str),
        ContentType="application/json",
        CacheControl=cache_control,
    )


def read_json(bucket: str, key: str) -> dict | None:
    try:
        resp = _s3.get_object(Bucket=bucket, Key=key)
        return json.loads(resp["Body"].read().decode())
    except _s3.exceptions.NoSuchKey:
        return None
    except Exception:
        return None


def write_dashboard_data(filename: str, data: dict) -> None:
    write_json(S3_BUCKET_DASHBOARD, f"data/{filename}", data, cache_control="max-age=30")


def write_snapshot(chat_id: str, snapshot: dict) -> None:
    now = datetime.now(timezone.utc)
    key = f"snapshots/{chat_id}/{now.strftime('%Y/%m/%d')}/{now.strftime('%H%M%S')}.json"
    write_json(S3_BUCKET_DATA, key, {
        "timestamp": now.isoformat(),
        "snapshot": snapshot,
    })


def write_raw_data(source: str, data: dict) -> None:
    now = datetime.now(timezone.utc)
    key = f"raw/{source}/{now.strftime('%Y-%m-%d/%H%M%S')}.json"
    write_json(S3_BUCKET_DATA, key, data)
