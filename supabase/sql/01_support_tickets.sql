-- STEP 1: support tickets created by the escalate_to_human tool.
create table if not exists public.support_tickets (
  id uuid primary key default gen_random_uuid(),
  ticket_number text not null unique
    default ('TCK-' || to_char(now(), 'YYYYMMDD') || '-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 6))),
  user_id uuid not null references auth.users (id) on delete cascade,
  conversation_id text,
  order_number text,
  category text not null check (category in ('order', 'refund', 'product', 'technical', 'other')),
  priority text not null default 'normal' check (priority in ('low', 'normal', 'high')),
  summary text not null check (char_length(summary) between 5 and 2000),
  status text not null default 'open' check (status in ('open', 'in_progress', 'resolved', 'closed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists support_tickets_user_created_idx
  on public.support_tickets (user_id, created_at desc);

alter table public.support_tickets enable row level security;

-- Customers may read only their own tickets. Writes go through the backend (service role).
drop policy if exists "customers read own tickets" on public.support_tickets;
create policy "customers read own tickets"
  on public.support_tickets for select
  to authenticated
  using (auth.uid() = user_id);
