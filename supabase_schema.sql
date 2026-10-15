-- Run this once in Supabase: SQL Editor > New query > paste > Run.
create table if not exists profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  credits integer not null default 1 check (credits >= 0),
  created_at timestamptz not null default now()
);
create table if not exists payments (
  ref text primary key,
  uid uuid not null references auth.users(id) on delete cascade,
  credits integer not null,
  paid boolean not null default false,
  poll text,
  created_at timestamptz not null default now()
);
-- Row Level Security on, with no policies: browsers can never read or change these tables.
-- Only the backend (service role key) can.
alter table profiles enable row level security;
alter table payments enable row level security;

create or replace function get_credits(p_uid uuid) returns integer
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles(id, credits) values (p_uid, 1) on conflict do nothing;  -- 1 free check on first use
  return (select credits from profiles where id = p_uid);
end $$;

create or replace function use_credit(p_uid uuid) returns boolean
language plpgsql security definer set search_path = public as $$
begin
  perform get_credits(p_uid);
  update profiles set credits = credits - 1 where id = p_uid and credits > 0;
  return found;
end $$;

create or replace function refund_credit(p_uid uuid) returns void
language sql security definer set search_path = public as $$
  update profiles set credits = credits + 1 where id = p_uid;
$$;

create or replace function grant_payment(p_ref text) returns boolean
language plpgsql security definer set search_path = public as $$
declare r payments%rowtype;
begin
  update payments set paid = true where ref = p_ref and paid = false returning * into r;
  if not found then return false; end if;
  insert into profiles(id, credits) values (r.uid, 0) on conflict do nothing;
  update profiles set credits = credits + r.credits where id = r.uid;
  return true;
end $$;

-- Only the backend may call these.
revoke all on function get_credits(uuid), use_credit(uuid), refund_credit(uuid), grant_payment(text)
  from public, anon, authenticated;
