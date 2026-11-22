CREATE or replace FILE FORMAT 
SALESIQ_CSV_FILE_FORMAT
TYPE = CSV
skip_header = 1
field_delimiter = ','
 ERROR_ON_COLUMN_COUNT_MISMATCH = false;