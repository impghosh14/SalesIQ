import pandas as pd
import boto3
import json

from datetime import datetime
from pathlib import Path


# --------------------------------
# 1. PROJECT CONFIGURATION
# --------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

CSV_FILE = BASE_DIR / "input" / "customers.csv"
OUTPUT_DIR = BASE_DIR / "output"

BUCKET_NAME = "YOUR_BUCKET_NAME"
OBJECT_NAME = "customer"

OUTPUT_DIR.mkdir(exist_ok=True)


# --------------------------------
# 2. CSV TO JSON CONVERSION
# --------------------------------

def convert_csv_to_json():

    now = datetime.now()

    timestamp = now.strftime("%Y%m%d_%H%M%S")

    filename = f"customers_{timestamp}.JSON"

    json_file = OUTPUT_DIR / filename

    df = pd.read_csv(
        CSV_FILE,
        dtype=str,
        keep_default_na=False
    )

    records = df.to_dict(orient="records")

    with open(json_file, "w", encoding="utf-8") as file:

        json.dump(
            records,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("CSV successfully converted into JSON")

    print(f"Total records: {len(records)}")

    return json_file, timestamp, now


# --------------------------------
# 3. UPLOAD JSON TO AWS S3
# --------------------------------

def upload_to_s3(json_file, timestamp, now):

    s3 = boto3.client("s3")

    year = now.strftime("%Y")
    month = now.strftime("%m")
    day = now.strftime("%d")

    filename = f"customers_{timestamp}.JSON"

    s3_key = (
        f"{OBJECT_NAME}/"
        f"{year}/{month}/{day}/{filename}"
    )

    s3.upload_file(
        str(json_file),
        BUCKET_NAME,
        s3_key,
        ExtraArgs={
            "ContentType": "application/json"
        }
    )

    print("JSON file uploaded successfully!")

    print(f"S3 Location: s3://{BUCKET_NAME}/{s3_key}")


# --------------------------------
# 4. MAIN EXECUTION
# --------------------------------

def main():

    try:

        print("Starting Customer Data Pipeline")

        json_file, timestamp, now = convert_csv_to_json()

        upload_to_s3(json_file, timestamp, now)

        print("Pipeline completed successfully!")

    except Exception as error:

        print(f"Pipeline failed: {error}")


if __name__ == "__main__":

    main()