select
    payload:product_id::varchar as product_id,
    payload:product_name::varchar as product_name,
    payload:category::varchar as category,
    try_to_decimal(payload:unit_price::varchar, 18, 2) as unit_price,
    loaded_at,
    source_filename
from {{ ref('products_bronze') }}
qualify row_number() over (
    partition by payload:product_id::varchar
    order by loaded_at desc
) = 1
