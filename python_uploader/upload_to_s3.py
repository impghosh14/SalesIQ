"""Interactive local-file uploader for the SalesIQ S3 landing bucket."""
from __future__ import annotations

import mimetypes
import os
import re
import sys
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
    """Return a safe lowercase S3 entity folder name."""
    value = value.strip().lower().replace(" ", "_")
    value = re.sub(r"[^a-z0-9_-]", "", value)
    if not value:
        raise ValueError("Dataset name cannot be empty.")
    return value


def choose_dataset() -> str:
    print("\nAvailable datasets:")
    for index, name in enumerate(DATASETS, start=1):
        print(f"  {index}. {name}")
    print("  6. custom dataset")
    choice = input("Choose dataset (1-6): ").strip()

    if choice in {str(i) for i in range(1, len(DATASETS) + 1)}:
        return DATASETS[int(choice) - 1]
    if choice == "6":
        return clean_entity(input("Enter custom dataset name: "))
    raise ValueError("Invalid dataset selection.")


def choose_destination() -> str:
    print("\nUpload destination:")
    print("  1. direct_data (new/current incoming data)")
    print("  2. history_data (historical/backfill data)")
    choice = input("Choose destination (1-2, default 1): ").strip() or "1"
    if choice == "1":
        return os.getenv("S3_PREFIX_DIRECT", "direct_data").strip("/")
    if choice == "2":
        return os.getenv("S3_PREFIX_HISTORY", "history_data").strip("/")
    raise ValueError("Invalid destination selection.")


def build_s3_key(file_path: Path, entity: str, prefix: str) -> str:
    now = datetime.now(TIMEZONE)
    # Keep the user's requested hierarchy: entity/year/month/day/file.
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    extension = file_path.suffix.lower()
    filename = f"{entity}_{timestamp}{extension}"
    return (
        f"{prefix}/{entity}/{now:%Y}/{now:%m}/{now:%d}/{filename}"
    )


def main() -> int:
    bucket = os.getenv("S3_BUCKET", "").strip()
    region = os.getenv("AWS_REGION", "us-east-1").strip()
    profile = os.getenv("AWS_PROFILE", "").strip()

    if not bucket:
        print("ERROR: S3_BUCKET is missing. Set it in the project .env file.")
        return 1

    try:
        entity = choose_dataset()
        raw_path = input("\nEnter the full local file path: ").strip().strip('"').strip("'")
        file_path = Path(raw_path).expanduser()

        if not file_path.exists() or not file_path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        destination = choose_destination()
        key = build_s3_key(file_path, entity, destination)

        # Use a named profile only when explicitly configured.
        session = (
            boto3.Session(profile_name=profile, region_name=region)
            if profile
            else boto3.Session(region_name=region)
        )
        s3 = session.client("s3")
        content_type, _ = mimetypes.guess_type(file_path.name)

        print("\nUploading...")
        extra_args = {"ContentType": content_type} if content_type else {}
        s3.upload_file(
            str(file_path),
            bucket,
            key,
            ExtraArgs=extra_args or None,
        )

        print("\nUPLOAD SUCCESSFUL")
        print(f"Bucket : {bucket}")
        print(f"S3 URI : s3://{bucket}/{key}")
        print(f"Region : {region}")
        print("Local file has been retained.")
        return 0

    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}")
        return 2
    except (BotoCoreError, ClientError) as exc:
        print(f"AWS UPLOAD ERROR: {exc}")
        print("Check the AWS profile/credentials, region, bucket name and S3 permissions.")
        return 3
    except KeyboardInterrupt:
        print("\nUpload cancelled.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
