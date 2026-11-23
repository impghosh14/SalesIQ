# SalesIQ – Sales Data Engineering Project

An extensible AWS S3 → Snowflake → dbt sales analytics project using a Bronze / Silver / Gold medallion design.

## 1. S3 layout

The uploader creates keys like:

```text
s3://s3-salesiq-snowflake-project-2026/
├── direct_data/
│   └── customers/2026/11/23/customers_20261123_101530.csv
│   └── orders/2026/11/23/orders_20261123_101530.csv
└── history_data/
    └── customers/2026/11/23/customers_20261123_101530.csv
```

`direct_data` is the default landing area for newly supplied files. `history_data` is a separate prefix for historical/backfill files. The uploader asks which destination to use; it does not move or automatically archive files.

## 2. Python local-to-S3 uploader

### Prerequisites
- Python 3.10+
- AWS credentials configured using an existing AWS profile, environment variables, or an IAM role.
- IAM permissions: `s3:PutObject` on the target bucket/prefix (and optionally `s3:ListBucket`).
- Install dependencies:

```bash
pip install -r requirements.txt
```

### Configure
Copy `.env.example` to `.env` and set the bucket, AWS region, and optionally an AWS profile. `.env` is ignored by Git.

### Run

```bash
python python_uploader/upload_to_s3.py
```

The script prompts for:
1. Dataset: customers, orders, products, suppliers, shipping (or a custom entity)
2. Local file path
3. Destination: direct_data or history_data

It creates the year/month/day folders from the current Asia/Kolkata date and uploads with a timestamped filename. It preserves the original file extension and does not delete the local file.

## 3. Snowflake ingestion design

Recommended ingestion pattern:
1. Create a Snowflake storage integration for the S3 bucket.
2. Create an external stage pointing to `direct_data/` and `history_data/`.
3. Create file formats appropriate to the incoming file types.
4. Load records into entity-specific landing tables, retaining the source filename and load timestamp.
5. Store semi-structured source records in a `VARIANT` column (`PAYLOAD`) in the Bronze layer.
6. Use dbt to transform Bronze → Silver → Gold.

Important: `VARIANT` is a Snowflake data type, not a folder command. CSV files need to be parsed into objects (for example with `OBJECT_CONSTRUCT`) before they can be stored as one VARIANT payload. JSON can be loaded as VARIANT directly. Parquet has its own conversion/mapping approach. Excel files generally need conversion to CSV/JSON before Snowflake ingestion.

## 4. dbt model layers

- `models/bronze`: thin models over raw landing tables; preserve payload and ingestion metadata.
- `models/silver`: typed, cleaned, deduplicated entity models.
- `models/gold`: business-facing dimensions, facts and reporting aggregates.
- `snapshots`: optional dbt snapshots for tracking changes over time.
- `macros`: reusable SQL helpers.
- `tests`: generic and project-specific data tests.

The sample SQL is a starter template. Update source table/column names to match your actual Snowflake landing implementation.

## 5. dbt Cloud connection

Create a dbt Cloud project connected to this Git repository. Configure the Snowflake connection in the dbt Cloud environment. The `profiles.yml` here is for local dbt Core use; dbt Cloud manages credentials in its environment settings.

Suggested job:
1. `dbt deps`
2. `dbt build --target prod`

Run only after the Snowflake landing tables and source definitions are available.

## 6. Suggested next enhancements

- Event notification from S3 to SQS/SNS or EventBridge.
- Snowpipe auto-ingest or scheduled `COPY INTO`.
- File manifest / audit table and idempotency checks.
- Quarantine prefix for invalid files.
- dbt tests for primary keys, relationships, accepted values and freshness.
- CI/CD with GitHub or Azure DevOps.

## Existing connection code

No existing Python connection script was attached with the screenshot, so this project uses `boto3`'s standard AWS credential chain. If you share your current connection code (remove access keys/secrets first), the uploader can be adapted to reuse it exactly.
