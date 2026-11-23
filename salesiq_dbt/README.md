# SalesIQ dbt Project Guide

This folder contains the dbt transformation project for SalesIQ. It transforms JSON records already loaded into Snowflake landing tables through three medallion layers: Bronze, Silver and Gold.

## 1. Where dbt fits

```text
Application Server
   │
   ├── Source CSV files
   ▼
Python uploader
   │  CSV → NDJSON (.json)
   ▼
Amazon S3
   │  Storage Integration / Stage / Snowpipe or COPY
   ▼
Snowflake RAW landing tables
   │  PAYLOAD VARIANT + SOURCE_FILENAME + LOADED_AT
   ▼
dbt BRONZE
   │  Preserve source payload and ingestion metadata
   ▼
dbt SILVER
   │  Extract fields, cast types, standardize, deduplicate
   ▼
dbt GOLD
   │  Business facts, dimensions and aggregates
   ▼
BI / Analytics
```

dbt does not upload local files to S3 and does not itself create the AWS-to-Snowflake connection. The Python uploader and Snowflake ingestion process handle those responsibilities. dbt starts from the Snowflake landing tables.

## 2. Folder structure

```text
salesiq_dbt/
│
├── README.md
├── dbt_project.yml
├── packages.yml
├── profiles.example.yml
│
├── models/
│   ├── sources.yml
│   │
│   ├── bronze/
│   │   ├── customers_bronze.sql
│   │   ├── orders_bronze.sql
│   │   ├── products_bronze.sql
│   │   ├── suppliers_bronze.sql
│   │   └── shipping_bronze.sql
│   │
│   ├── silver/
│   │   ├── customers_silver.sql
│   │   ├── orders_silver.sql
│   │   ├── products_silver.sql
│   │   ├── suppliers_silver.sql
│   │   └── shipping_silver.sql
│   │
│   └── gold/
│       ├── dim_customers.sql
│       ├── dim_products.sql
│       ├── fct_sales.sql
│       ├── fct_shipping.sql
│       └── schema.yml
│
├── macros/
│   └── generate_schema_name.sql
│
├── snapshots/
│   └── customers_snapshot.sql
│
└── tests/
    └── assert_positive_order_amount.sql
```

## 3. Layer responsibilities

### Bronze – raw-preserving models

Bronze models select the `VARIANT` payload and ingestion metadata from Snowflake landing tables. They should preserve the source information and avoid applying business rules.

Example:

```sql
select
    payload,
    source_filename,
    loaded_at
from {{ source('salesiq_raw', 'customers_landing') }}
```

### Silver – cleaned and standardized models

Silver models extract JSON properties using Snowflake VARIANT path expressions, cast fields to appropriate types, and apply technical rules such as deduplication.

Example:

```sql
select
    payload:customer_id::varchar as customer_id,
    payload:customer_name::varchar as customer_name,
    payload:email::varchar as email,
    payload:country::varchar as country,
    loaded_at,
    source_filename
from {{ ref('customers_bronze') }}
qualify row_number() over (
    partition by payload:customer_id::varchar
    order by loaded_at desc
) = 1
```

The JSON property names in these examples are assumptions for the sample project. Change them to match the actual source CSV headers.

### Gold – business-ready models

Gold models expose stable structures for reporting and analytics.

| Model | Purpose |
|---|---|
| `dim_customers` | Customer dimension |
| `dim_products` | Product dimension |
| `fct_sales` | Order/sales fact |
| `fct_shipping` | Shipment and delivery fact |

These are starter examples. Add supplier dimensions, date dimensions, sales aggregates and other marts as the business requirements become clear.

## 4. Source definitions and dependencies

`sources.yml` declares the Snowflake landing tables as dbt sources. The sample assumes:

- Database: `SALESIQ`
- Schema: `RAW`
- Tables: `CUSTOMERS_LANDING`, `ORDERS_LANDING`, `PRODUCTS_LANDING`, `SUPPLIERS_LANDING`, `SHIPPING_LANDING`
- Common columns: `PAYLOAD`, `SOURCE_FILENAME`, `LOADED_AT`

Update the database, schema, table and column names if your Snowflake objects differ.

Use `source()` to reference landing tables and `ref()` to reference other dbt models. These references let dbt build the dependency graph and execute models in the correct order.

## 5. Materializations and schemas

The sample `dbt_project.yml` configures:

| Layer | Schema | Materialization |
|---|---|---|
| Bronze | `BRONZE` | View |
| Silver | `SILVER` | View |
| Gold | `GOLD` | Table |

The included `generate_schema_name` macro uses the configured custom schema name directly. Review this behavior against your team's dbt environment and naming conventions before deploying to production.

## 6. Data quality

The starter Gold `schema.yml` demonstrates `not_null`, `unique` and `relationships` tests. The singular SQL test `assert_positive_order_amount.sql` returns rows where the order amount is negative; a passing test returns zero rows.

Recommended additional tests:

- Unique and not-null business keys
- Valid order statuses and shipping statuses
- Accepted values for country/category fields where governed
- Relationships between orders and customers
- Source freshness and load-latency monitoring
- Reconciliation of source row counts to loaded row counts

## 7. Snapshots and history

The sample `customers_snapshot.sql` uses a check strategy to track changes to selected customer attributes. Snapshots are useful when you need to retain previous versions of a record (often described as Type 2 history).

A snapshot is different from the S3 `history_data` prefix:
- S3 history stores historical input files or backfills.
- dbt snapshots store row-level changes over time in Snowflake.

Configure snapshot scheduling and retention according to the business requirement.

## 8. Configure dbt Cloud

1. Push this repository to GitHub, GitLab or Azure DevOps.
2. Create a dbt Cloud project and connect the repository.
3. Configure the Snowflake account identifier, user/authentication, role, warehouse, database and development schema in the dbt Cloud environment.
4. Ensure the configured role can read the RAW landing tables and create objects in the Bronze, Silver, Gold and snapshot schemas.
5. Set the project directory to `salesiq_dbt` if the repository contains multiple projects or the root is not the dbt project.
6. Test with a development target before configuring production deployment.

The `profiles.example.yml` is only an example for local dbt Core. Do not commit real passwords or credentials. dbt Cloud manages connection credentials through its environment settings.

## 9. Useful dbt commands

Run these from the `salesiq_dbt` directory in a local dbt Core environment:

```bash
dbt debug
dbt parse
dbt compile
dbt run
dbt test
dbt build
dbt snapshot
dbt docs generate
```

For a dbt Cloud job, a typical command sequence is:

```bash
dbt deps
dbt build --target prod
```

Run `dbt snapshot` as a separately scheduled step if snapshot execution is not included in the chosen job command.

## 10. Important assumptions to validate

Before running the starter models, confirm:

1. The Snowflake landing tables exist and contain one JSON object per row in `PAYLOAD`.
2. The JSON keys match the property names used in the Silver SQL.
3. `LOADED_AT` is populated consistently and is suitable for selecting the latest record.
4. The business keys used for deduplication are truly unique identifiers.
5. Date, amount and status fields follow the expected source formats.
6. Your dbt Cloud role has the required privileges.

This is a learning/portfolio starter, not a production-ready ingestion framework. Add incremental processing, robust audit logging, late-arriving-data handling, schema evolution, alerting and deployment controls as the project matures.
