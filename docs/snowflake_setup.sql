-- Illustrative setup only. Replace cloud/IAM identifiers and validate with your AWS/Snowflake admin.
create database if not exists SALESIQ;
create schema if not exists SALESIQ.RAW;

-- Create STORAGE INTEGRATION using your AWS IAM role ARN.
-- create or replace storage integration SALESIQ_S3_INT
--   type = external_stage
--   storage_provider = 'S3'
--   enabled = true
--   storage_aws_role_arn = '<AWS_IAM_ROLE_ARN>'
--   storage_allowed_locations = ('s3://s3-salesiq-snowflake-project-2026/direct_data/',
--                                 's3://s3-salesiq-snowflake-project-2026/history_data/');

-- After creating the integration, obtain its generated AWS IAM user/external ID
-- and update the trust relationship on the AWS role as documented by Snowflake.

-- create or replace stage SALESIQ.RAW.SALESIQ_DIRECT_STAGE
--   url = 's3://s3-salesiq-snowflake-project-2026/direct_data/'
--   storage_integration = SALESIQ_S3_INT;

-- Example landing table pattern. Repeat for each entity.
create table if not exists SALESIQ.RAW.CUSTOMERS_LANDING (
    PAYLOAD variant,
    SOURCE_FILENAME varchar,
    LOADED_AT timestamp_ntz default current_timestamp()
);

-- For JSON files, COPY INTO can load parsed JSON into a VARIANT column using a JSON file format.
-- CSV requires a deliberate row-to-object mapping (for example OBJECT_CONSTRUCT)
-- and should be loaded using a matching CSV file format and COPY transformation.
