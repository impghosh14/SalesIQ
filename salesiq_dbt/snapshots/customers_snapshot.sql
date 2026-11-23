{% snapshot customers_snapshot %}
{{
    config(
      target_schema='SNAPSHOTS',
      unique_key='customer_id',
      strategy='check',
      check_cols=['customer_name', 'email', 'city', 'country']
    )
}}
select customer_id, customer_name, email, city, country
from {{ ref('customers_silver') }}
{% endsnapshot %}
