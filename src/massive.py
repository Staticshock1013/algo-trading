"""Download NQ minute bars from Massive Flat Files.

Credentials come from the environment (``.env``). This module never prints them.
"""

from __future__ import annotations

import io
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import boto3
import pandas as pd
from botocore.config import Config
from dotenv import load_dotenv

from src.paths import repo_root

ENDPOINT = "https://files.massive.com"
BUCKET = "flatfiles"
MINUTE_PREFIX = "us_futures_cme/minute_aggs_v1/"
# Outright NQ quarters only. Drops NQT micros-of-the-big and calendar spreads.
NQ_OUTRIGHT = r"^NQ[HMUZ]\d$"
USECOLS = [
    "ticker",
    "session_end_date",
    "window_start",
    "open",
    "high",
    "low",
    "close",
    "volume",
]


def s3_client():
    """S3 client for Massive Flat Files. Keys are read from ``.env``."""
    load_dotenv(repo_root() / ".env")
    access_key = os.getenv("MASSIVE_ACCESS_KEY")
    secret_key = os.getenv("MASSIVE_SECRET_KEY")
    if not access_key or not secret_key:
        raise RuntimeError(
            "Set MASSIVE_ACCESS_KEY and MASSIVE_SECRET_KEY in .env "
            "(see .env.example). Keys are not stored in the notebooks."
        )
    return boto3.client(
        "s3",
        endpoint_url=ENDPOINT,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4"),
    )


def list_child_prefixes(client, prefix: str = "") -> list[str]:
    response = client.list_objects_v2(Bucket=BUCKET, Prefix=prefix, Delimiter="/")
    return [item["Prefix"] for item in response.get("CommonPrefixes", [])]


def list_keys(client, prefix: str) -> list[str]:
    keys: list[str] = []
    token = None
    while True:
        kwargs = {"Bucket": BUCKET, "Prefix": prefix}
        if token:
            kwargs["ContinuationToken"] = token
        response = client.list_objects_v2(**kwargs)
        keys += [item["Key"] for item in response.get("Contents", [])]
        if not response.get("IsTruncated"):
            break
        token = response["NextContinuationToken"]
    return sorted(keys)


def available_years(client, prefix: str = MINUTE_PREFIX) -> list[str]:
    return [item.split("/")[-2] for item in list_child_prefixes(client, prefix)]


def _load_nq_day(client, key: str) -> pd.DataFrame:
    obj = client.get_object(Bucket=BUCKET, Key=key)
    day = pd.read_csv(
        io.BytesIO(obj["Body"].read()),
        compression="gzip",
        usecols=USECOLS,
    )
    return day[day["ticker"].astype(str).str.match(NQ_OUTRIGHT)]


def download_nq_minutes(
    client,
    years: list[str],
    data_dir: Path | None = None,
    prefix: str = MINUTE_PREFIX,
    max_workers: int = 8,
) -> None:
    """Save one parquet per year under ``data/``. Years already on disk are skipped.

    The files are licensed Massive data and are gitignored. Do not commit them.
    """
    root = repo_root()
    out_dir = Path(data_dir) if data_dir is not None else root / "data"
    out_dir.mkdir(parents=True, exist_ok=True)

    for year in years:
        out = out_dir / f"nq_1m_{year}.parquet"
        if out.exists():
            print(f"{year}: already downloaded, skipping")
            continue
        keys = list_keys(client, f"{prefix}{year}/")
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            parts = list(pool.map(lambda key: _load_nq_day(client, key), keys))
        year_frame = pd.concat(parts, ignore_index=True)
        year_frame.to_parquet(out)
        print(f"{year}: {len(keys)} days, {len(year_frame):,} NQ rows saved")
