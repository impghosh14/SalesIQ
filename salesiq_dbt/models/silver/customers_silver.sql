-- Example JSON-object payload mapping. Adjust keys to match your source file.
select
    payload:customer_id::varchar as customer_id,
    payload:customer_name::varchar as customer_name,
    payload:email::varchar as email,
    payload:city::varchar as city,
    payload:country::varchar as country,
    loaded_at,
    source_filename
from {{ ref('customers_bronze') }}
qualify row_number() over (
    partition by payload:customer_id::varchar
    order by loaded_at desc
) = 1
