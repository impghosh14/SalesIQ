# SalesIQ – End-to-End Sales Data Engineering Platform

SalesIQ is a sample sales-data platform that accepts CSV files from an application server, converts each file into JSON, lands the JSON data in Amazon S3, and transforms it in Snowflake using dbt.

The project is organized around a **Bronze → Silver → Gold medallion architecture**.

## 1. Business scope

SalesIQ manages these business domains:

- **Customers** – customer profile and contact information
- **Orders** – order headers, dates, amounts and statuses
- **Products** – product catalogue, category and price
- **Suppliers** – supplier details and sourcing information
- **Shipping** – shipment, carrier and delivery information

The initial ingestion contract is: **CSV is the input format; JSON is the S3 landing format.** The Python uploader converts the CSV into newline-delimited JSON (NDJSON), with one JSON object per input row. The source CSV is retained and is not modified.

## 2. Overall solution architecture

```text
┌───────────────────────────────────────────────────────────────┐
│                    APPLICATION SERVER                         │
│                                                               │
│  Source CSV files                                              │
│  customers.csv | orders.csv | products.csv | ...              │
│                                                               │
│  Python ingestion application                                  │
│  • Select dataset and local CSV file                           │
│  • Validate CSV headers and rows                               │
│  • Convert each CSV row into a JSON object                     │
│  • Add upload timestamp and build S3 object key                │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                │ AWS SDK / Boto3
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                    AMAZON S3 – SALESIQ                         │
│                                                               │
│  direct_data/                         history_data/            │
│  • New/current files                  • Historical/backfill   │
│  • Entity/date partitioning           • Entity/date partition  │
│  • JSON / NDJSON objects               • JSON / NDJSON objects  │
└───────────────────────────────┬───────────────────────────────┘
                                │
                                │ Snowflake Storage Integration
                                │ External Stage / Snowpipe or COPY
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                       SNOWFLAKE                                │
│                                                               │
│  RAW / LANDING                                                 │
│  • JSON records loaded into VARIANT                            │
│  • Source filename and load timestamp retained                 │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ BRONZE LAYER                                             │  │
│  │ Raw-preserving models; minimal transformations          │  │
│  └──────────────────────────────┬──────────────────────────┘  │
│                                 ▼                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ SILVER LAYER                                             │  │
│  │ Type casting, cleansing, standardization, deduplication  │  │
│  └──────────────────────────────┬──────────────────────────┘  │
│                                 ▼                             │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │ GOLD LAYER                                               │  │
│  │ Business logic, dimensions, facts and aggregates         │  │
│  └──────────────────────────────┬──────────────────────────┘  │
└─────────────────────────────────┼─────────────────────────────┘
                                  │
                                  ▼
┌───────────────────────────────────────────────────────────────┐
│                    CONSUMPTION / BI                            │
│  Sales dashboards • Customer insights • Product performance   │
│  Order analysis • Supplier analysis • Delivery performance     │
└───────────────────────────────────────────────────────────────┘

                 dbt Cloud: build, test, document and schedule
                 Bronze → Silver → Gold transformations
```

### Component responsibilities

| Component | Responsibility |
|---|---|
| Application server | Hosts/runs the Python ingestion application and has access to source CSV files |
| Python uploader | Validates CSV, converts rows to JSON, creates dated S3 keys and uploads |
| Amazon S3 | Stores JSON landing files, partitioned by dataset and upload date |
| Snowflake storage integration | Provides Snowflake access to the permitted S3 locations without embedding AWS keys in SQL |
| Snowflake stage / Snowpipe / COPY | Reads S3 JSON files and loads records into landing tables |
| Bronze | Preserves source payload and ingestion metadata |
| Silver | Applies technical data quality and standardization rules |
| Gold | Publishes business-ready facts, dimensions and reporting models |
| dbt Cloud | Executes model builds, tests, documentation and scheduled jobs |
| BI layer | Consumes Gold models for analytics and dashboards |

**Important:** The diagram shows the target architecture. The Python uploader currently implements CSV-to-JSON conversion and S3 upload. Snowflake ingestion orchestration (Snowpipe, event notifications or scheduled COPY) must be configured separately.

## 3. Amazon S3 bucket and folder structure

Bucket:

`s3-salesiq-snowflake-project-2026`

Recommended object-key layout:

```text
s3://s3-salesiq-snowflake-project-2026/
│
├── direct_data/
│   ├── customers/
│   │   └── 2026/
│   │       └── 11/
│   │           └── 23/
│   │               └── customers_20261123_101530.json
│   │
│   ├── orders/
│   │   └── 2026/11/23/orders_20261123_102015.json
│   │
│   ├── products/
│   │   └── 2026/11/23/products_20261123_103000.json
│   │
│   ├── suppliers/
│   │   └── 2026/11/23/suppliers_20261123_104500.json
│   │
│   └── shipping/
│       └── 2026/11/23/shipping_20261123_110000.json
│
└── history_data/
    ├── customers/
    │   └── 2025/12/31/customers_20251231_090000.json
    ├── orders/
    │   └── 2025/12/31/orders_20251231_091000.json
    ├── products/
    ├── suppliers/
    └── shipping/
```

### S3 partitioning convention

The key pattern is:

```text
<prefix>/<dataset>/<YYYY>/<MM>/<DD>/<dataset>_<YYYYMMDD_HHMMSS>.json
```

For example:

```text
direct_data/customers/2026/11/23/customers_20261123_101530.json
```

- `direct_data`: newly supplied/current data
- `history_data`: historical or backfill data
- `customers`: dataset/entity name
- `2026/11/23`: upload date in Asia/Kolkata
- `customers_20261123_101530.json`: dataset name plus upload timestamp

S3 presents these prefixes as folders in the console. They are object-key prefixes, not physical directories, and are created automatically when an object is uploaded.

### Why separate direct and history prefixes?

The prefixes make it easier to distinguish normal incoming loads from historical backfills. They can have separate Snowflake stages, load jobs, retention policies and operational controls. The uploader asks which prefix to use; it does not automatically archive or move files.

## 4. CSV-to-JSON conversion

The application server receives a CSV file, but **only JSON files are written to the S3 landing prefixes**.

Example input CSV:

```csv
customer_id,customer_name,email,country
C001,Alice,alice@example.com,India
C002,Bob,bob@example.com,USA
```

Example uploaded NDJSON content:

```json
{"customer_id": "C001", "customer_name": "Alice", "email": "alice@example.com", "country": "India"}
{"customer_id": "C002", "customer_name": "Bob", "email": "bob@example.com", "country": "USA"}
```

This is newline-delimited JSON: every line is an independent JSON object. The file has a `.json` extension and is suitable for Snowflake JSON file-format ingestion.

**Data type handling:** The starter converter keeps CSV values as strings rather than guessing whether a value is an ID, decimal, date or text. This avoids accidentally changing identifiers such as `000123`. Type casting is handled explicitly in the dbt Silver layer. Empty CSV cells remain empty strings in this starter version; define a separate null-handling rule if the source contract requires it.

## 5. Python ingestion application

Main file:

`python_uploader/upload_to_s3.py`

### Runtime flow

1. Read configuration from `.env`.
2. Prompt the operator to select a dataset: customers, orders, products, suppliers or shipping.
3. Prompt for the local CSV file path.
4. Validate that the file exists and has a `.csv` extension.
5. Validate the header row and reject blank/duplicate column names.
6. Convert each non-empty CSV record into one JSON object.
7. Generate the upload date and timestamp using the `Asia/Kolkata` timezone.
8. Build the S3 object key under the selected prefix and dataset.
9. Upload the temporary JSON file using Boto3.
10. Print the S3 URI and record count. Keep the original CSV unchanged.

### Run the uploader

```bash
# Create and activate a virtual environment (Windows PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env

# Run from the project root
python python_uploader/upload_to_s3.py
```

### Configuration

Set these values in `.env`:

```dotenv
AWS_REGION=us-east-1
S3_BUCKET=s3-salesiq-snowflake-project-2026
AWS_PROFILE=
S3_PREFIX_DIRECT=direct_data
S3_PREFIX_HISTORY=history_data
```

If `AWS_PROFILE` is blank, Boto3 uses its standard credential chain (environment variables, shared AWS credentials/config, or an attached IAM role). Do not put AWS access keys or secrets in source code or commit `.env` to Git.

### Required AWS permissions

The identity used by the application needs permission to upload objects to the intended bucket prefixes, typically `s3:PutObject`. Add `s3:ListBucket` only if the application needs to list bucket contents. Use least-privilege IAM policies and the correct AWS account/region.

## 6. Snowflake ingestion design

Recommended logical flow:

1. Create a Snowflake storage integration for the S3 bucket prefixes.
2. Configure the AWS IAM role trust relationship using the values Snowflake provides for the integration.
3. Create an external stage for `direct_data/` and, if required, a separate stage for `history_data/`.
4. Create a Snowflake JSON file format.
5. Load JSON records into entity-specific landing tables with a `VARIANT` payload column.
6. Retain source filename and load timestamp for traceability.
7. Make the landing tables available as dbt sources.

Example landing table pattern:

```sql
create table if not exists SALESIQ.RAW.CUSTOMERS_LANDING (
    PAYLOAD variant,
    SOURCE_FILENAME varchar,
    LOADED_AT timestamp_ntz default current_timestamp()
);
```

For NDJSON, each line is a JSON object. Configure the Snowflake JSON file format and COPY mapping to load each parsed record into `PAYLOAD`. Capture file metadata such as the source filename in the landing table. The exact COPY statement depends on the selected stage, file format and ingestion method.

Do not embed AWS access keys in Snowflake SQL. Use a Snowflake storage integration.

## 7. dbt transformation strategy

The dbt project lives in `salesiq_dbt/`. It separates models by medallion layer:

- `models/bronze`: source-preserving models over raw landing tables
- `models/silver`: typed, standardized and deduplicated entity models
- `models/gold`: facts, dimensions and business-facing outputs
- `macros`: reusable Jinja/SQL logic
- `snapshots`: optional change-history tracking
- `tests`: data quality assertions

The starter project includes models for customers, orders, products, suppliers and shipping, plus Gold examples for customer/product dimensions and sales/shipping facts.

Read `salesiq_dbt/README.md` for the dbt-specific explanation and setup steps.

## 8. Suggested dbt Cloud job

A production job can run:

```bash
dbt deps
dbt build --target prod
```

`dbt build` builds selected models and runs their applicable tests. Configure Snowflake credentials, role, warehouse, database and schema in the dbt Cloud environment. Connect the dbt project to the Git repository and set the required deployment environment.

The included `profiles.example.yml` is a reference for local dbt Core only. dbt Cloud credentials should be managed in dbt Cloud environment settings.

## 9. Repository structure

```text
SalesIQ_Project/
│
├── python_uploader/
│   ├── __init__.py
│   └── upload_to_s3.py
│
├── salesiq_dbt/
│   ├── README.md
│   ├── dbt_project.yml
│   ├── packages.yml
│   ├── profiles.example.yml
│   ├── models/
│   │   ├── sources.yml
│   │   ├── bronze/
│   │   ├── silver/
│   │   └── gold/
│   ├── macros/
│   ├── snapshots/
│   └── tests/
│
├── docs/
│   └── snowflake_setup.sql
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## 10. Implementation roadmap

| Phase | Deliverable |
|---|---|
| 1 | Configure application-server AWS identity and test S3 upload |
| 2 | Validate CSV-to-NDJSON conversion and S3 date partitioning |
| 3 | Create Snowflake storage integration, stages, file format and landing tables |
| 4 | Implement reliable S3-to-Snowflake loading and load audit |
| 5 | Configure dbt sources and Bronze models |
| 6 | Build Silver transformations and data quality tests |
| 7 | Build Gold dimensions, facts and reporting models |
| 8 | Configure dbt Cloud deployment job, scheduling and monitoring |

### Current starter-project boundaries

This repository provides the Python CSV-to-JSON uploader and dbt starter models. It does not yet configure AWS event notifications, Snowpipe auto-ingest, Snowflake objects in your account, dbt Cloud credentials, or a BI dashboard. Those are subsequent implementation steps and must be configured and tested in the relevant accounts.
