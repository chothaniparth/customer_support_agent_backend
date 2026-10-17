-- STEP 4 (read-only): confirm everything exists.
select table_name, row_security
from (
  select c.relname as table_name, c.relrowsecurity as row_security
  from pg_class c join pg_namespace n on n.oid = c.relnamespace
  where n.nspname = 'public' and c.relname in ('support_tickets', 'pending_actions', 'orders')
) t;

select column_name from information_schema.columns
where table_schema = 'public' and table_name = 'orders' and column_name = 'delivered_at';

select tgname from pg_trigger where tgname = 'trg_orders_delivered_at';
