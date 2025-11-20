# Supabase Analytics Storage

## Overview

The backend automatically stores analytics data to Supabase for persistent, user-specific tracking. All analytics records are **user-specific** and linked to individual user accounts.

## What Gets Stored

### 1. Usage Statistics (`usage_stats` table)

**Stored for each API request:**
- `user_id` - UUID of the user (REQUIRED - only stores if valid UUID)
- `request_count` - Number of requests (typically 1 per call)
- `tokens_in` - Input tokens used
- `tokens_out` - Output tokens used
- `token_count` - Total tokens (legacy field: tokens_in + tokens_out)
- `cost` - Total cost in USD
- `model` - Model used (e.g., "gpt-4", "gpt-4o")
- `job_id` - Optional job identifier
- `date` - Date of the usage (auto-set to current date)
- `created_at` - Timestamp when record was created
- `updated_at` - Timestamp when record was last updated

**Storage Behavior:**
- Records are aggregated by `user_id` and `date` (one row per user per day)
- If a record exists for the same user and date, it **updates** the existing record (increments counts and costs)
- If no record exists, it **creates** a new one

### 2. Schema Usage Statistics (`schema_usage_stats` table)

**Stored when a schema is activated:**
- `user_id` - UUID of the user (REQUIRED - only stores if valid UUID)
- `schema_id` - Schema identifier (e.g., "microstructure_control", "anti_scanner_techniques")
- `usage_count` - Number of times this schema was used by this user
- `last_used_at` - Timestamp of last usage
- `created_at` - Timestamp when first used
- `updated_at` - Timestamp when last updated

**Storage Behavior:**
- One record per user per schema (unique constraint on `user_id` + `schema_id`)
- If a record exists, it **increments** the `usage_count` and updates `last_used_at`
- If no record exists, it **creates** a new one with `usage_count = 1`

## User-Specific Storage

**YES, all records are user-specific!**

- Records are only stored if `user_id` is a valid UUID format
- Non-UUID user_ids (like "default", "user_123") are **skipped** and not stored
- Each record is linked to a specific user via the `user_id` foreign key
- When querying analytics, you can filter by `user_id` to get user-specific stats

## When Records Are Stored

### Usage Stats Storage:
- **Triggered**: Every time `analytics_store.add()` is called (which happens on every OpenAI API call)
- **Location**: `backend/language_model.py` → `_Analytics.add()` method
- **Threading**: Stored in a background thread (non-blocking, won't slow down requests)
- **Error Handling**: Failures are logged but don't affect the main request

### Schema Usage Storage:
- **Triggered**: Every time a schema is activated (when `schema_level > 0`)
- **Location**: `backend/language_model.py` → `_Analytics.track_schema_usage()` method
- **Threading**: Stored in a background thread (non-blocking)
- **Error Handling**: Failures are logged but don't affect the main request

## Configuration Required

To enable Supabase storage, set these environment variables in your backend:

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your_service_role_key_here

# OR use anon key (less secure, but works)
# SUPABASE_ANON_KEY=your_anon_key_here
```

**Note**: If Supabase is not configured, the system will:
- Still calculate and track analytics in-memory
- Still return analytics data (from in-memory store)
- Just skip storing to Supabase (no errors, graceful degradation)

## Database Schema

Make sure you've run the SQL migration in `Frontend/supabase-schema.sql` which creates:
- `usage_stats` table with all required columns
- `schema_usage_stats` table with unique constraint
- RPC functions: `update_usage_stats()` and `update_schema_usage_stats()`
- Proper indexes for performance
- Row Level Security (RLS) policies

## Querying User-Specific Analytics

### From Backend API:
```bash
# Get analytics for specific user
GET /analytics/summary?user_id=<user-uuid>

# Get aggregate analytics (all users)
GET /analytics/summary
```

### From Supabase Directly:
```sql
-- Get usage stats for a specific user
SELECT * FROM usage_stats WHERE user_id = '<user-uuid>' ORDER BY date DESC;

-- Get schema usage for a specific user
SELECT * FROM schema_usage_stats WHERE user_id = '<user-uuid>' ORDER BY usage_count DESC;

-- Get total cost for a user
SELECT SUM(cost) as total_cost, SUM(tokens_in) as total_tokens_in, SUM(tokens_out) as total_tokens_out
FROM usage_stats 
WHERE user_id = '<user-uuid>';

-- Get most used schemas for a user
SELECT schema_id, usage_count, last_used_at
FROM schema_usage_stats
WHERE user_id = '<user-uuid>'
ORDER BY usage_count DESC;
```

## Logging

The system logs when records are successfully stored:
- `✅ Stored usage stats to Supabase for user {user_id}: {requests} requests, ${cost} cost`
- `✅ Stored schema usage to Supabase for user {user_id}: schema={schema_id}`

Check your backend logs to confirm records are being inserted.

## Troubleshooting

**No records appearing?**
1. Check that `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are set
2. Verify the SQL migration has been run in Supabase
3. Check backend logs for error messages
4. Ensure `user_id` is a valid UUID (36 characters with 4 hyphens)
5. Check Supabase RLS policies allow inserts

**Records not user-specific?**
- All records require a valid UUID `user_id`
- Non-UUID user_ids are automatically skipped
- Check that your frontend is passing the correct user UUID to the backend

