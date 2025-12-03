"""
Supabase Database Client
Handles all interactions with Supabase: Analytics, Jobs, and System Logs.
"""
import os
import logging
import json
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime, date

if TYPE_CHECKING:
    from supabase import Client

# Try to import supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

# We don't use the standard logger here to avoid recursion when logging to DB
# Instead, we use a basic print for critical errors in this module
def _safe_log(msg: str):
    # Only print if DEBUG is enabled to avoid noise
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        print(f"[SupabaseDB] {msg}")

class SupabaseDB:
    _instance = None
    _client: Optional[Client] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupabaseDB, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        if not SUPABASE_AVAILABLE:
            _safe_log("Supabase client library not installed.")
            return

        url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")

        if not url or not key:
            _safe_log("Supabase credentials missing.")
            return

        try:
            self._client = create_client(url, key)
            _safe_log("Supabase client initialized.")
        except Exception as e:
            _safe_log(f"Failed to initialize Supabase client: {e}")

    @property
    def client(self) -> Optional[Client]:
        return self._client

    # --- Analytics Methods ---

    def store_usage_stats(self, user_id: Optional[str], request_count: int = 1, 
                         tokens_in: int = 0, tokens_out: int = 0, cost: float = 0.0, 
                         model: str = "gpt-4", job_id: Optional[str] = None) -> bool:
        if not self.client: return False
        try:
            data = {
                'user_id': user_id,
                'request_count': request_count,
                'tokens_in': tokens_in,
                'tokens_out': tokens_out,
                'cost': float(cost),
                'model': model,
                'job_id': job_id,
                'date': date.today().isoformat()
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            self.client.table('usage_stats').insert(data).execute()
            return True
        except Exception as e:
            _safe_log(f"Failed to store usage stats: {e}")
            return False

    def store_schema_usage(self, user_id: str, schema_id: str) -> bool:
        if not self.client: return False
        try:
            data = {
                'user_id': user_id,
                'schema_id': schema_id,
                'used_at': datetime.utcnow().isoformat()
            }
            self.client.table('schema_usage_stats').insert(data).execute()
            return True
        except Exception as e:
            _safe_log(f"Failed to store schema usage: {e}")
            return False

    def get_aggregate_analytics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.client: return {}
        try:
            query = self.client.table('usage_stats').select('*')
            if user_id:
                query = query.eq('user_id', user_id)
            
            result = query.execute()
            data = result.data
            
            return {
                'total_requests': sum(r.get('request_count', 0) for r in data),
                'total_tokens_in': sum(r.get('tokens_in', 0) for r in data),
                'total_tokens_out': sum(r.get('tokens_out', 0) for r in data),
                'total_cost': sum(r.get('cost', 0.0) for r in data),
            }
        except Exception as e:
            _safe_log(f"Failed to get analytics: {e}")
            return {}

    def get_schema_usage_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.client: return {}
        try:
            query = self.client.table('schema_usage_stats').select('*')
            if user_id:
                query = query.eq('user_id', user_id)
            result = query.execute()
            # (Simplification: just returning raw data for now, aggregation logic can be added if needed)
            return {"schema_usage": result.data}
        except Exception as e:
            _safe_log(f"Failed to get schema stats: {e}")
            return {}

    # --- Job Management Methods ---

    def create_job(self, job_id: str, file_name: str, file_id: str, 
                   user_id: Optional[str] = None, total_passes: int = 1, 
                   model: str = "gpt-4", metadata: Dict = {}) -> bool:
        if not self.client: return False
        try:
            data = {
                'id': job_id,
                'file_name': file_name,
                'file_id': file_id,
                'user_id': user_id,
                'status': 'pending',
                'total_passes': total_passes,
                'model': model,
                'metadata': metadata,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            self.client.table('jobs').insert(data).execute()
            return True
        except Exception as e:
            _safe_log(f"Failed to create job {job_id}: {e}")
            return False

    def update_job_status(self, job_id: str, status: str, current_pass: Optional[int] = None, 
                          metadata_update: Optional[Dict] = None) -> bool:
        if not self.client: return False
        try:
            data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat()
            }
            if current_pass is not None:
                data['current_pass'] = current_pass
            if metadata_update:
                # Note: Supabase doesn't support deep merge on update easily, 
                # so we might overwrite metadata if not careful. 
                # Ideally, fetch first then update, or use a stored procedure.
                # For now, we'll just update the field.
                data['metadata'] = metadata_update

            self.client.table('jobs').update(data).eq('id', job_id).execute()
            return True
        except Exception as e:
            _safe_log(f"Failed to update job {job_id}: {e}")
            return False

    def log_job_event(self, job_id: str, event_type: str, message: str, 
                      pass_number: Optional[int] = None, details: Dict = {}) -> bool:
        if not self.client: return False
        try:
            data = {
                'job_id': job_id,
                'event_type': event_type,
                'message': message,
                'pass_number': pass_number,
                'details': details,
                'created_at': datetime.utcnow().isoformat()
            }
            self.client.table('job_events').insert(data).execute()
            return True
        except Exception as e:
            _safe_log(f"Failed to log event for job {job_id}: {e}")
            return False

    def get_jobs(self, limit: int = 100, user_id: Optional[str] = None) -> List[Dict]:
        if not self.client: return []
        try:
            query = self.client.table('jobs').select('*').order('created_at', desc=True).limit(limit)
            if user_id:
                query = query.eq('user_id', user_id)
            result = query.execute()
            return result.data
        except Exception as e:
            _safe_log(f"Failed to get jobs: {e}")
            return []

    def get_job_events(self, job_id: str) -> List[Dict]:
        if not self.client: return []
        try:
            result = self.client.table('job_events').select('*')\
                .eq('job_id', job_id).order('created_at', desc=False).execute()
            return result.data
        except Exception as e:
            _safe_log(f"Failed to get events for job {job_id}: {e}")
            return []

    # --- System Logging Methods ---

    def write_system_log(self, level: str, logger_name: str, message: str, 
                         module: str = None, function_name: str = None, 
                         line_number: int = None, traceback: str = None, 
                         metadata: Dict = {}) -> bool:
        if not self.client: return False
        try:
            data = {
                'level': level,
                'logger_name': logger_name,
                'message': message,
                'module': module,
                'function_name': function_name,
                'line_number': line_number,
                'traceback': traceback,
                'metadata': metadata,
                'created_at': datetime.utcnow().isoformat()
            }
            # Remove None values
            data = {k: v for k, v in data.items() if v is not None}
            
            self.client.table('system_logs').insert(data).execute()
            return True
        except Exception as e:
            # Do NOT log this error to avoid infinite recursion if this is called from the logger
            if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
                print(f"[SupabaseDB] Failed to write system log: {e}")
            return False

    def get_system_logs(self, limit: int = 200, level: Optional[str] = None) -> List[Dict]:
        if not self.client: return []
        try:
            query = self.client.table('system_logs').select('*').order('created_at', desc=True).limit(limit)
            if level:
                query = query.eq('level', level)
            result = query.execute()
            return result.data
        except Exception as e:
            _safe_log(f"Failed to get system logs: {e}")
            return []

# Global instance
db = SupabaseDB()
