-- STEP 0 (read-only): check existing columns and order statuses before changing anything.
select table_name, column_name, data_type
from information_schema.columns
where table_schema = 'public'
  and table_name in ('orders', 'conversations', 'messages', 'support_tickets', 'pending_actions')
order by table_name, ordinal_position;

select status, count(*) from public.orders group by status;

select conname, pg_get_constraintdef(oid)
from pg_constraint
where conrelid = 'public.orders'::regclass and contype = 'c';
