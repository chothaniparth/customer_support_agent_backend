-- STEP 3: record when an order becomes 'delivered' (used for return-window checks).
alter table public.orders add column if not exists delivered_at timestamptz;

create or replace function public.set_order_delivered_at()
returns trigger
language plpgsql
set search_path = public
as $$
begin
  if new.status = 'delivered' and old.status is distinct from 'delivered' then
    new.delivered_at := now();
  end if;
  return new;
end;
$$;

drop trigger if exists trg_orders_delivered_at on public.orders;
create trigger trg_orders_delivered_at
  before update of status on public.orders
  for each row
  execute function public.set_order_delivered_at();
