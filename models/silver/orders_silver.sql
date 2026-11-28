select
    payload:order_id::varchar as order_id,
    payload:customer_id::varchar as customer_id,
    try_to_date(payload:order_date::varchar) as order_date,
    try_to_decimal(payload:order_amount::varchar, 18, 2) as order_amount,
    payload:order_status::varchar as order_status,
    loaded_at,
    source_filename
from {{ ref('orders_bronze') }}
qualify row_number() over (
    partition by payload:order_id::varchar
    order by loaded_at desc
) = 1
