{{ config(materialized='table') }}

select
    o.order_id,
    o.customer_id,
    o.order_date,
    o.order_amount,
    o.order_status,
    c.country as customer_country
from {{ ref('orders_silver') }} o
left join {{ ref('customers_silver') }} c
    on o.customer_id = c.customer_id
