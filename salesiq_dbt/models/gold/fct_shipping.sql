{{ config(materialized='table') }}

select
    shipment_id,
    order_id,
    carrier,
    ship_date,
    delivery_date,
    shipping_status,
    datediff('day', ship_date, delivery_date) as delivery_days
from {{ ref('shipping_silver') }}
