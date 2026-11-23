-- Thin Bronze model: preserve source payload and ingestion metadata.
select
    payload,
    source_filename,
    loaded_at
from {{ source('salesiq_raw', 'customers_landing') }}
