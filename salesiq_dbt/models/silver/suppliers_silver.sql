select
    payload:supplier_id::varchar as supplier_id,
    payload:supplier_name::varchar as supplier_name,
    payload:country::varchar as country,
    loaded_at,
    source_filename
from {{ ref('suppliers_bronze') }}
qualify row_number() over (
    partition by payload:supplier_id::varchar
    order by loaded_at desc
) = 1
