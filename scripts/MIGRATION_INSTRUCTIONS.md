# Supabase Migration Instructions

To enable job history and detailed logs, you need to create/update tables in your Supabase project.

## 1. Open Supabase SQL Editor
Go to your Supabase project dashboard, navigate to the **SQL Editor**, and create a new query.

## 2. Run the following SQL
Copy and paste the code below into the SQL Editor and click **Run**.

```sql
-- 1. Create jobs table
CREATE TABLE IF NOT EXISTS public.jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT,
    file_name TEXT,
    file_id TEXT,
    status TEXT DEFAULT 'pending',
    current_stage TEXT,
    current_pass INTEGER DEFAULT 0,
    total_passes INTEGER,
    model TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    result JSONB,
    metadata JSONB
);

-- 2. Create job_events table
CREATE TABLE IF NOT EXISTS public.job_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID REFERENCES public.jobs(id),
    event_type TEXT,
    message TEXT,
    pass_number INTEGER,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. Create or Update system_logs table
CREATE TABLE IF NOT EXISTS public.system_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    level TEXT,
    message TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add columns to system_logs if they are missing (safe to run if they exist)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_logs' AND column_name = 'level') THEN
        ALTER TABLE public.system_logs ADD COLUMN level TEXT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'system_logs' AND column_name = 'metadata') THEN
        ALTER TABLE public.system_logs ADD COLUMN metadata JSONB;
    END IF;
END $$;

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.system_logs ENABLE ROW LEVEL SECURITY;

-- 5. Create policies (allow all for now for simplicity)
CREATE POLICY "Enable read access for all users" ON public.jobs FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON public.jobs FOR INSERT WITH CHECK (true);
CREATE POLICY "Enable update access for all users" ON public.jobs FOR UPDATE USING (true);

CREATE POLICY "Enable read access for all users" ON public.job_events FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON public.job_events FOR INSERT WITH CHECK (true);

CREATE POLICY "Enable read access for all users" ON public.system_logs FOR SELECT USING (true);
CREATE POLICY "Enable insert access for all users" ON public.system_logs FOR INSERT WITH CHECK (true);
```

## 3. Restart Backend
After running the SQL, **restart your backend server** (Ctrl+C and run `uvicorn` again) to pick up the changes and start saving data.
