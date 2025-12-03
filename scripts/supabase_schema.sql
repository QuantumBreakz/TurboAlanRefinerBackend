-- Enable UUID extension if not enabled
create extension if not exists "uuid-ossp";

-- 1. Jobs Table
create table if not exists public.jobs (
    id uuid primary key default uuid_generate_v4(),
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    updated_at timestamp with time zone default timezone('utc'::text, now()) not null,
    user_id uuid references auth.users(id), -- Optional link to auth.users
    status text not null check (status in ('pending', 'processing', 'completed', 'failed', 'cancelled')),
    file_name text not null,
    file_id text not null,
    total_passes int default 1,
    current_pass int default 0,
    model text default 'gpt-4',
    metadata jsonb default '{}'::jsonb
);

-- 2. Job Events Table (Detailed logs for each job)
create table if not exists public.job_events (
    id uuid primary key default uuid_generate_v4(),
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    job_id uuid references public.jobs(id) on delete cascade not null,
    event_type text not null, -- 'pass_start', 'pass_complete', 'error', etc.
    pass_number int,
    message text,
    details jsonb default '{}'::jsonb
);

-- 3. System Logs Table (Application-wide logs)
create table if not exists public.system_logs (
    id uuid primary key default uuid_generate_v4(),
    created_at timestamp with time zone default timezone('utc'::text, now()) not null,
    level text not null, -- 'INFO', 'ERROR', 'WARNING', 'DEBUG'
    logger_name text not null,
    message text not null,
    module text,
    function_name text,
    line_number int,
    traceback text,
    metadata jsonb default '{}'::jsonb
);

-- Indexes for performance
create index if not exists idx_jobs_user_id on public.jobs(user_id);
create index if not exists idx_jobs_created_at on public.jobs(created_at desc);
create index if not exists idx_job_events_job_id on public.job_events(job_id);
create index if not exists idx_system_logs_created_at on public.system_logs(created_at desc);
create index if not exists idx_system_logs_level on public.system_logs(level);

-- RLS Policies (Row Level Security)
alter table public.jobs enable row level security;
alter table public.job_events enable row level security;
alter table public.system_logs enable row level security;

-- Allow read/write for authenticated users (own jobs)
create policy "Users can view their own jobs" on public.jobs
    for select using (auth.uid() = user_id);

create policy "Users can insert their own jobs" on public.jobs
    for insert with check (auth.uid() = user_id);

create policy "Users can update their own jobs" on public.jobs
    for update using (auth.uid() = user_id);

-- Allow read for job events if user owns the job
create policy "Users can view events for their jobs" on public.job_events
    for select using (
        exists ( select 1 from public.jobs where id = job_events.job_id and user_id = auth.uid() )
    );

-- Allow service role (backend) full access
-- Note: Service role bypasses RLS, but explicit policies can be good documentation.
-- We assume the backend uses the SERVICE_ROLE_KEY for writing logs/jobs for all users.

-- Public/Anon access for System Logs (Optional: restrict to admins only in production)
-- For now, allow insert from backend (service role) and read from authenticated admins
create policy "Service role can insert logs" on public.system_logs
    for insert with check (true); -- Backend uses service key which bypasses this, but good to have.

create policy "Admins can view system logs" on public.system_logs
    for select using (
        -- Check if user is admin (you might need a custom claim or admin table)
        -- For simplicity in this MVP, allow authenticated users to view logs (or restrict)
        auth.role() = 'authenticated'
    );
