{{ config(materialized='table') }}

select product_id, product_name, category, unit_price
from {{ ref('products_silver') }}
