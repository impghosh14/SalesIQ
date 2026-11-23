select *
from {{ ref('orders_silver') }}
where order_amount < 0
