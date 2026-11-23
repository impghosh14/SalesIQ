select payload, source_filename, loaded_at
from {{ source('salesiq_raw', 'orders_landing') }}
