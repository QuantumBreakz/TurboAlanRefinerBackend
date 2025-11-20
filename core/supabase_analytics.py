"""
Supabase Analytics Storage Module
Stores analytics data to Supabase for user-specific and aggregate tracking
"""
import os
import logging
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from supabase import Client
from datetime import datetime, date

logger = logging.getLogger(__name__)

# Try to import supabase client
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
    SupabaseClient = Client
except ImportError:
    SUPABASE_AVAILABLE = False
    SupabaseClient = None  # Type placeholder when not available
    logger.warning("Supabase client not available. Install with: pip install supabase")


def get_supabase_client() -> Optional[Any]:
    """Get Supabase client if configured"""
    if not SUPABASE_AVAILABLE:
        return None
    
    supabase_url = os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_key:
        return None
    
    try:
        return create_client(supabase_url, supabase_key)
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}")
        return None


def store_usage_stats(
    user_id: Optional[str],
    request_count: int = 1,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost: float = 0.0,
    model: str = "gpt-4",
    job_id: Optional[str] = None
) -> bool:
    """
    Store usage statistics to Supabase
    
    Args:
        user_id: User UUID (can be None for anonymous usage)
        request_count: Number of requests
        tokens_in: Input tokens
        tokens_out: Output tokens
        cost: Total cost
        model: Model used
        job_id: Optional job ID
    
    Returns:
        True if stored successfully, False otherwise
    """
    client = get_supabase_client()
    if not client:
        return False
    
    # Convert user_id to UUID format if it's not already
    user_uuid = None
    if user_id and user_id != "default":
        try:
            # Try to use as-is if it's already a UUID
            if len(user_id) == 36 and user_id.count('-') == 4:
                user_uuid = user_id
            else:
                # Skip non-UUID user_ids (like "default", "user_123", etc.)
                logger.debug(f"Skipping non-UUID user_id: {user_id}")
                return False
        except Exception:
            return False
    
    try:
        # Use RPC function if available, otherwise direct insert
        result = client.rpc('update_usage_stats', {
            'p_user_id': user_uuid,
            'p_request_count': request_count,
            'p_token_count': tokens_in + tokens_out,  # Legacy field
            'p_tokens_in': tokens_in,
            'p_tokens_out': tokens_out,
            'p_cost': float(cost),
            'p_model': model,
            'p_job_id': job_id
        })
        if hasattr(result, 'execute'):
            result.execute()
        logger.info(f"✅ Stored usage stats to Supabase for user {user_uuid}: {request_count} requests, ${cost:.6f} cost")
        return True
    except Exception as e:
        # Fallback to direct insert if RPC fails
        try:
            insert_result = client.table('usage_stats').insert({
                'user_id': user_uuid,
                'request_count': request_count,
                'token_count': tokens_in + tokens_out,
                'tokens_in': tokens_in,
                'tokens_out': tokens_out,
                'cost': float(cost),
                'model': model,
                'job_id': job_id,
                'date': date.today().isoformat()
            }).execute()
            logger.info(f"✅ Stored usage stats to Supabase (direct insert) for user {user_uuid}: {request_count} requests, ${cost:.6f} cost")
            return True
        except Exception as e2:
            logger.warning(f"❌ Failed to store usage stats to Supabase: {e2}")
            return False


def store_schema_usage(
    user_id: Optional[str],
    schema_id: str
) -> bool:
    """
    Store schema usage statistics to Supabase
    
    Args:
        user_id: User UUID (can be None for anonymous usage)
        schema_id: Schema identifier
    
    Returns:
        True if stored successfully, False otherwise
    """
    client = get_supabase_client()
    if not client:
        return False
    
    # Convert user_id to UUID format if it's not already
    user_uuid = None
    if user_id and user_id != "default":
        try:
            if len(user_id) == 36 and user_id.count('-') == 4:
                user_uuid = user_id
            else:
                logger.debug(f"Skipping non-UUID user_id for schema usage: {user_id}")
                return False
        except Exception:
            return False
    
    try:
        # Use RPC function if available
        result = client.rpc('update_schema_usage_stats', {
            'p_user_id': user_uuid,
            'p_schema_id': schema_id
        })
        if hasattr(result, 'execute'):
            result.execute()
        logger.info(f"✅ Stored schema usage to Supabase for user {user_uuid}: schema={schema_id}")
        return True
    except Exception as e:
        # Fallback to direct upsert
        try:
            # Get current count and increment
            existing = client.table('schema_usage_stats').select('usage_count').eq('user_id', user_uuid).eq('schema_id', schema_id).execute()
            current_count = existing.data[0]['usage_count'] if existing.data else 0
            
            client.table('schema_usage_stats').upsert({
                'user_id': user_uuid,
                'schema_id': schema_id,
                'usage_count': current_count + 1,
                'last_used_at': datetime.now().isoformat()
            }, on_conflict='user_id,schema_id').execute()
            logger.info(f"✅ Stored schema usage to Supabase (direct upsert) for user {user_uuid}: schema={schema_id}")
            return True
        except Exception as e2:
            logger.warning(f"❌ Failed to store schema usage to Supabase: {e2}")
            return False


def get_aggregate_analytics(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get aggregated analytics from Supabase
    
    Args:
        user_id: Optional user UUID to filter by user, None for all users
    
    Returns:
        Dictionary with aggregated analytics
    """
    client = get_supabase_client()
    if not client:
        return {}
    
    try:
        query = client.table('usage_stats').select('*')
        
        if user_id:
            # Validate UUID format
            if len(user_id) == 36 and user_id.count('-') == 4:
                query = query.eq('user_id', user_id)
            else:
                return {}
        
        result = query.execute()
        
        if not result.data:
            return {
                'total_requests': 0,
                'total_tokens_in': 0,
                'total_tokens_out': 0,
                'total_cost': 0.0,
                'current_model': 'gpt-4'
            }
        
        # Aggregate the data
        total_requests = sum(row.get('request_count', 0) for row in result.data)
        total_tokens_in = sum(row.get('tokens_in', 0) for row in result.data)
        total_tokens_out = sum(row.get('tokens_out', 0) for row in result.data)
        total_cost = sum(float(row.get('cost', 0)) for row in result.data)
        
        # Get most recent model
        current_model = 'gpt-4'
        if result.data:
            sorted_data = sorted(result.data, key=lambda x: x.get('created_at', ''), reverse=True)
            current_model = sorted_data[0].get('model', 'gpt-4')
        
        return {
            'total_requests': total_requests,
            'total_tokens_in': total_tokens_in,
            'total_tokens_out': total_tokens_out,
            'total_cost': total_cost,
            'current_model': current_model
        }
    except Exception as e:
        logger.error(f"Failed to get aggregate analytics from Supabase: {e}")
        return {}


def get_schema_usage_stats(user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Get schema usage statistics from Supabase
    
    Args:
        user_id: Optional user UUID to filter by user, None for all users
    
    Returns:
        Dictionary with schema usage statistics
    """
    client = get_supabase_client()
    if not client:
        return {}
    
    try:
        query = client.table('schema_usage_stats').select('*')
        
        if user_id:
            if len(user_id) == 36 and user_id.count('-') == 4:
                query = query.eq('user_id', user_id)
            else:
                return {}
        
        result = query.execute()
        
        if not result.data:
            return {
                'total_usages': 0,
                'most_used_schema': None,
                'most_used_count': 0,
                'least_used_schema': None,
                'least_used_count': 0,
                'average_usage': 0,
                'schema_usage': {},
                'schema_last_used': {}
            }
        
        # Aggregate schema usage
        schema_counts: Dict[str, int] = {}
        schema_last_used: Dict[str, str] = {}
        
        for row in result.data:
            schema_id = row.get('schema_id')
            if schema_id:
                schema_counts[schema_id] = schema_counts.get(schema_id, 0) + row.get('usage_count', 0)
                last_used = row.get('last_used_at')
                if last_used and (schema_id not in schema_last_used or last_used > schema_last_used[schema_id]):
                    schema_last_used[schema_id] = last_used
        
        total_usages = sum(schema_counts.values())
        most_used = max(schema_counts.items(), key=lambda x: x[1]) if schema_counts else None
        least_used = min(schema_counts.items(), key=lambda x: x[1]) if schema_counts else None
        
        return {
            'total_usages': total_usages,
            'most_used_schema': most_used[0] if most_used else None,
            'most_used_count': most_used[1] if most_used else 0,
            'least_used_schema': least_used[0] if least_used else None,
            'least_used_count': least_used[1] if least_used else 0,
            'average_usage': total_usages / len(schema_counts) if schema_counts else 0,
            'schema_usage': schema_counts,
            'schema_last_used': schema_last_used
        }
    except Exception as e:
        logger.error(f"Failed to get schema usage stats from Supabase: {e}")
        return {}

