"""Convert a local CSV file to newline-delimited JSON and upload it to S3.

Each CSV row becomes one JSON object. The uploaded object uses a .json extension
and is written as NDJSON (one JSON object per line), which is suitable for
Snowflake JSON ingestion into VARIANT columns.
"""
from __future__ import annotations

import csv
import json
import mimetypes
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(PROJECT_ROOT / ".env")

DATASETS = ("customers", "orders", "products", "suppliers", "shipping")
TIMEZONE = ZoneInfo("Asia/Kolkata")


def clean_entity(value: str) -> str:
    """Normalize a dataset name for use as an S3 prefix."""
    value = value.strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_-]", "", value)
    if not value:
        raise ValueError("Dataset name cannot be empty.")
    return value


def choose_dataset() -> str:
    print("\nSelect the dataset:")
    for index, name in enumerate(DATASETS, start=1):
        print(f"  {index}. {name}")
    print(f"  {len(DATASETS) + 1}. Custom dataset")

    choice = input("Enter choice: ").strip()
    if choice.isdigit() and 1 <= int(choice) <= len(DATASETS):
        return DATASETS[int(choice) - 1]
    if choice == str(len(DATASETS) + 1):
        return clean_entity(input("Enter custom dataset name: "))
    raise ValueError("Invalid dataset selection.")


def choose_destination() -> str:
    direct_prefix = os.getenv("S3_PREFIX_DIRECT", "direct_data").strip("/")
    history_prefix = os.getenv("S3_PREFIX_HISTORY", "history_data").strip("/")

    print("\nSelect S3 destination:")
    print(f"  1. {direct_prefix} (new/current incoming data)")
    print(f"  2. {history_prefix} (historical/backfill data)")
    choice = input("Enter choice (default 1): ").strip() or "1"

    if choice == "1":
        return direct_prefix
    if choice == "2":
        return history_prefix
    raise ValueError("Invalid destination selection.")


def convert_csv_to_ndjson(csv_path: Path, json_path: Path) -> int:
    """Convert CSV rows to NDJSON. Returns number of records written.

    CSV values remain strings by default to avoid guessing data types.
    Empty cells are represented as empty strings; downstream dbt/Snowflake
    transformations can safely cast them to the required business types.
    """
    records_written = 0

    with csv_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)

        if not reader.fieldnames:
            raise ValueError("The CSV file is empty or does not contain a header row.")

        # Reject blank or duplicate header names to avoid ambiguous JSON keys.
        headers = [header.strip() if header else "" for header in reader.fieldnames]
        if any(not header for header in headers):
            raise ValueError("CSV contains a blank column name in its header.")
        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column names in its header.")

        # DictReader uses original field names, so normalize them consistently.
        reader.fieldnames = headers

        with json_path.open("w", encoding="utf-8", newline="\n") as target:
            for row in reader:
                # Skip completely blank lines returned as empty rows.
                if row is None or not any(value not in (None, "") for value in row.values()):
                    continue

                # A row with more fields than the header has a None key.
                if None in row:
                    raise ValueError(
                        f"CSV row {reader.line_num} has more values than the header."
                    )

                # Missing trailing values become empty strings.
                normalized = {
                    key: (value if value is not None else "")
                    for key, value in row.items()
                }
                target.write(json.dumps(normalized, ensure_ascii=False) + "\n")
                records_written += 1

    if records_written == 0:
        raise ValueError("The CSV contains headers but no data records.")
    return records_written


def build_s3_key(entity: str, prefix: str, timestamp: datetime) -> str:
    """Build entity/year/month/day/entity_timestamp.json S3 key."""
    date_path = timestamp.strftime("%Y/%m/%d")
    timestamp_text = timestamp.strftime("%Y%m%d_%H%M%S")
    filename = f"{entity}_{timestamp_text}.json"
    return f"{prefix}/{entity}/{date_path}/{filename}"


def main() -> int:
    bucket = os.getenv("S3_BUCKET", "").strip()
    region = os.getenv("AWS_REGION", "us-east-1").strip()
    profile = os.getenv("AWS_PROFILE", "").strip()

    if not bucket:
        print("ERROR: S3_BUCKET is missing. Configure it in the .env file.")
        return 1

    try:
        entity = choose_dataset()
        raw_path = input("\nEnter the full path of the local CSV file: ").strip()
        csv_path = Path(raw_path.strip('"').strip("'")).expanduser()

        if not csv_path.exists() or not csv_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {csv_path}")
        if csv_path.suffix.lower() != ".csv":
            raise ValueError("Only CSV input files are supported. The output will be JSON.")

        destination = choose_destination()
        upload_time = datetime.now(TIMEZONE)
        s3_key = build_s3_key(entity, destination, upload_time)

        # Convert into a temporary JSON file; the original CSV remains untouched.
        with tempfile.TemporaryDirectory(prefix="salesiq_") as temp_dir:
            json_path = Path(temp_dir) / f"{entity}.json"
            record_count = convert_csv_to_ndjson(csv_path, json_path)

            session = (
                boto3.Session(profile_name=profile, region_name=region)
                if profile
                else boto3.Session(region_name=region)
            )
            s3 = session.client("s3")

            print(f"\nConverted {record_count:,} CSV records to NDJSON.")
            print("Uploading JSON file to Amazon S3...")

            s3.upload_file(
                str(json_path),
                bucket,
                s3_key,
                ExtraArgs={"ContentType": "application/x-ndjson"},
            )

        print("\nUPLOAD SUCCESSFUL")
        print(f"Input CSV : {csv_path}")
        print(f"Records   : {record_count:,}")
        print(f"S3 URI    : s3://{bucket}/{s3_key}")
        print(f"Region    : {region}")
        print("Output    : NDJSON (.json), one JSON object per line")
        print("Original local CSV file has not been changed or deleted.")
        return 0

    except (ValueError, FileNotFoundError, UnicodeDecodeError) as exc:
        print(f"INPUT / CONVERSION ERROR: {exc}")
        return 2
    except (BotoCoreError, ClientError) as exc:
        print(f"AWS UPLOAD ERROR: {exc}")
        print("Check credentials, AWS region, bucket name and S3 PutObject permissions.")
        return 3
    except KeyboardInterrupt:
        print("\nUpload cancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
