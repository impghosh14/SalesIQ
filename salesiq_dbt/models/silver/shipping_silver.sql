select
    payload:shipment_id::varchar as shipment_id,
    payload:order_id::varchar as order_id,
    payload:carrier::varchar as carrier,
    try_to_date(payload:ship_date::varchar) as ship_date,
    try_to_date(payload:delivery_date::varchar) as delivery_date,
    payload:shipping_status::varchar as shipping_status,
    loaded_at,
    source_filename
from {{ ref('shipping_bronze') }}
qualify row_number() over (
    partition by payload:shipment_id::varchar
    order by loaded_at desc
) = 1
