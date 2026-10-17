-- STEP 2: actions the AI proposes (place / cancel order) that wait for the customer's Confirm click.
create table if not exists public.pending_actions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  conversation_id text not null,
  action_type text not null check (action_type in ('place_order', 'cancel_order')),
  payload jsonb not null,
  preview jsonb not null,
  status text not null default 'pending'
    check (status in ('pending', 'processing', 'confirmed', 'rejected', 'failed')),
  result jsonb,
  created_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '15 minutes'),
  resolved_at timestamptz
);

create index if not exists pending_actions_user_status_idx
  on public.pending_actions (user_id, status);

-- RLS on with NO policies: only the backend's service-role key can read or write this table.
alter table public.pending_actions enable row level security;
