"""
MongoDB Database Client
Handles all interactions with MongoDB: Analytics, Jobs, System Logs, and Users.
Production-ready with connection pooling, error handling, and retry logic.
"""
from __future__ import annotations

import os
import logging
import json
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime, date
from pathlib import Path
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, OperationFailure, ServerSelectionTimeoutError
from pymongo.collection import Collection
from pymongo.database import Database
import threading

# Load environment variables early
try:
    from dotenv import load_dotenv
    # Try to load .env from backend directory
    backend_root = Path(__file__).parent.parent.parent
    env_path = backend_root / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        # Fallback to current directory
        load_dotenv()
except ImportError:
    # dotenv not available, continue without it
    pass

if TYPE_CHECKING:
    from pymongo import MongoClient

# We don't use the standard logger here to avoid recursion when logging to DB
# Instead, we use a basic print for critical errors in this module
def _safe_log(msg: str, always_print: bool = False):
    # Print if DEBUG is enabled or if always_print is True
    if always_print or os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        print(f"[MongoDB] {msg}")

class MongoDB:
    """
    Singleton MongoDB client with connection pooling and error handling.
    Production-ready implementation for Vercel serverless functions.
    """
    _instance = None
    _lock = threading.Lock()
    _client: Optional[MongoClient] = None
    _db: Optional[Database] = None

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(MongoDB, cls).__new__(cls)
                    cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        """Initialize MongoDB client with connection pooling."""
        try:
            mongodb_url = os.getenv("MONGODB_URL") or os.getenv("MONGO_URL") or os.getenv("MONGO_URI")
            
            if not mongodb_url:
                _safe_log("MongoDB URL not configured. Set MONGODB_URL, MONGO_URL, or MONGO_URI environment variable.", always_print=True)
                return
            
            _safe_log(f"MongoDB URL found (length: {len(mongodb_url)})", always_print=True)

            # Connection options for production
            connection_options = {
                "maxPoolSize": 50,  # Maximum number of connections in the pool
                "minPoolSize": 5,   # Minimum number of connections
                "maxIdleTimeMS": 45000,  # Close connections after 45 seconds of inactivity
                "serverSelectionTimeoutMS": 5000,  # Timeout for server selection
                "connectTimeoutMS": 10000,  # Timeout for initial connection
                "socketTimeoutMS": 30000,  # Timeout for socket operations
                "retryWrites": True,  # Enable retryable writes
                "retryReads": True,  # Enable retryable reads
            }

            self._client = MongoClient(mongodb_url, **connection_options)
            
            # Test connection
            self._client.admin.command('ping')
            
            # Get database name from URL or use default
            db_name = os.getenv("MONGODB_DB_NAME", "alan_refiner")
            self._db = self._client[db_name]
            
            # Create indexes for better performance
            self._create_indexes()
            
            _safe_log("MongoDB client initialized successfully.", always_print=True)
            
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            _safe_log(f"Failed to connect to MongoDB: {e}", always_print=True)
            self._client = None
            self._db = None
        except Exception as e:
            _safe_log(f"Failed to initialize MongoDB client: {e}", always_print=True)
            import traceback
            _safe_log(f"Traceback: {traceback.format_exc()}", always_print=True)
            self._client = None
            self._db = None

    def _create_indexes(self):
        """Create indexes for better query performance."""
        if self._db is None:
            return
        
        try:
            # Users collection indexes
            users_col = self._db.users
            users_col.create_index([("email", ASCENDING)], unique=True)
            users_col.create_index([("role", ASCENDING)])
            users_col.create_index([("is_active", ASCENDING)])
            
            # Usage stats collection indexes
            usage_stats_col = self._db.usage_stats
            usage_stats_col.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
            usage_stats_col.create_index([("user_id", ASCENDING)])
            usage_stats_col.create_index([("date", DESCENDING)])
            usage_stats_col.create_index([("job_id", ASCENDING)])
            
            # Schema usage stats collection indexes
            schema_usage_col = self._db.schema_usage_stats
            schema_usage_col.create_index([("user_id", ASCENDING), ("schema_id", ASCENDING)], unique=True)
            schema_usage_col.create_index([("user_id", ASCENDING)])
            schema_usage_col.create_index([("schema_id", ASCENDING)])
            
            # Jobs collection indexes
            jobs_col = self._db.jobs
            jobs_col.create_index([("user_id", ASCENDING)])
            jobs_col.create_index([("created_at", DESCENDING)])
            jobs_col.create_index([("status", ASCENDING)])
            jobs_col.create_index([("id", ASCENDING)], unique=True)
            
            # Job events collection indexes
            job_events_col = self._db.job_events
            job_events_col.create_index([("job_id", ASCENDING)])
            job_events_col.create_index([("created_at", ASCENDING)])
            
            # System logs collection indexes
            system_logs_col = self._db.system_logs
            system_logs_col.create_index([("user_id", ASCENDING)])
            system_logs_col.create_index([("action", ASCENDING)])
            system_logs_col.create_index([("created_at", DESCENDING)])
            system_logs_col.create_index([("level", ASCENDING)])
            
            _safe_log("MongoDB indexes created successfully.")
        except Exception as e:
            _safe_log(f"Failed to create indexes: {e}")

    @property
    def client(self) -> Optional[MongoClient]:
        """Get MongoDB client instance."""
        return self._client

    @property
    def db(self) -> Optional[Database]:
        """Get MongoDB database instance."""
        return self._db

    def is_connected(self) -> bool:
        """Check if MongoDB is connected."""
        if not self._client:
            return False
        try:
            self._client.admin.command('ping')
            return True
        except:
            return False

    # --- Analytics Methods ---

    def store_usage_stats(self, user_id: Optional[str], request_count: int = 1, 
                         tokens_in: int = 0, tokens_out: int = 0, cost: float = 0.0, 
                         model: str = "gpt-4", job_id: Optional[str] = None) -> bool:
        """Store usage statistics for a user."""
        if self._db is None:
            return False
        try:
            collection = self._db.usage_stats
            today = date.today()
            
            # Use upsert to update or insert
            collection.update_one(
                {
                    "user_id": user_id,
                    "date": today.isoformat()
                },
                {
                    "$inc": {
                        "request_count": request_count,
                        "tokens_in": tokens_in,
                        "tokens_out": tokens_out,
                        "cost": float(cost)
                    },
                    "$set": {
                        "model": model,
                        "job_id": job_id,
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            _safe_log(f"Failed to store usage stats: {e}")
            return False

    def store_schema_usage(self, user_id: str, schema_id: str) -> bool:
        """Store schema usage statistics."""
        if self._db is None:
            return False
        try:
            collection = self._db.schema_usage_stats
            collection.update_one(
                {
                    "user_id": user_id,
                    "schema_id": schema_id
                },
                {
                    "$inc": {"usage_count": 1},
                    "$set": {
                        "last_used_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    },
                    "$setOnInsert": {
                        "created_at": datetime.utcnow()
                    }
                },
                upsert=True
            )
            return True
        except Exception as e:
            _safe_log(f"Failed to store schema usage: {e}")
            return False

    def get_aggregate_analytics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get aggregated analytics for a user or all users."""
        if self._db is None:
            return {}
        try:
            collection = self._db.usage_stats
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": None,
                    "total_requests": {"$sum": "$request_count"},
                    "total_tokens_in": {"$sum": "$tokens_in"},
                    "total_tokens_out": {"$sum": "$tokens_out"},
                    "total_cost": {"$sum": "$cost"},
                    "current_model": {"$last": "$model"}  # Get the most recent model
                }}
            ]
            
            result = list(collection.aggregate(pipeline))
            if result:
                return {
                    "total_requests": result[0].get("total_requests", 0),
                    "total_tokens_in": result[0].get("total_tokens_in", 0),
                    "total_tokens_out": result[0].get("total_tokens_out", 0),
                    "total_cost": result[0].get("total_cost", 0.0),
                    "current_model": result[0].get("current_model", "gpt-4")
                }
            return {
                "total_requests": 0,
                "total_tokens_in": 0,
                "total_tokens_out": 0,
                "total_cost": 0.0,
                "current_model": "gpt-4"
            }
        except Exception as e:
            _safe_log(f"Failed to get analytics: {e}")
            return {}

    def get_last_24h_analytics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get analytics for the last 24 hours from MongoDB with hourly breakdown."""
        if self._db is None:
            return {
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "series": []
            }
        try:
            from datetime import datetime, timedelta
            collection = self._db.usage_stats
            
            # Calculate 24 hours ago
            now = datetime.utcnow()
            yesterday = now - timedelta(hours=24)
            
            query = {
                "created_at": {"$gte": yesterday}
            }
            if user_id:
                query["user_id"] = user_id
            
            # First, get total aggregated stats
            total_pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": None,
                    "requests": {"$sum": "$request_count"},
                    "tokens_in": {"$sum": "$tokens_in"},
                    "tokens_out": {"$sum": "$tokens_out"},
                    "cost": {"$sum": "$cost"}
                }}
            ]
            
            total_result = list(collection.aggregate(total_pipeline))
            
            # Get hourly breakdown using $dateToString for compatibility
            hourly_pipeline = [
                {"$match": query},
                {"$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%dT%H:00:00Z",
                            "date": "$created_at"
                        }
                    },
                    "requests": {"$sum": "$request_count"},
                    "tokens_in": {"$sum": "$tokens_in"},
                    "tokens_out": {"$sum": "$tokens_out"},
                    "cost": {"$sum": "$cost"}
                }},
                {"$sort": {"_id": 1}}
            ]
            
            # Try aggregation, fallback to manual grouping if it fails
            try:
                hourly_result = list(collection.aggregate(hourly_pipeline))
            except Exception:
                # Fallback: group by hour manually
                hourly_result = []
                all_docs = list(collection.find(query).sort("created_at", 1))
                
                # Group by hour
                hourly_data = {}
                for doc in all_docs:
                    created_at = doc.get("created_at")
                    if isinstance(created_at, datetime):
                        hour_key = created_at.replace(minute=0, second=0, microsecond=0)
                    elif isinstance(created_at, str):
                        try:
                            hour_key = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                            hour_key = hour_key.replace(minute=0, second=0, microsecond=0)
                        except:
                            continue
                    else:
                        continue
                    
                    if hour_key not in hourly_data:
                        hourly_data[hour_key] = {
                            "requests": 0,
                            "tokens_in": 0,
                            "tokens_out": 0,
                            "cost": 0.0
                        }
                    
                    hourly_data[hour_key]["requests"] += doc.get("request_count", 0)
                    hourly_data[hour_key]["tokens_in"] += doc.get("tokens_in", 0)
                    hourly_data[hour_key]["tokens_out"] += doc.get("tokens_out", 0)
                    hourly_data[hour_key]["cost"] += doc.get("cost", 0.0)
                
                # Convert to list format
                for hour_key, data in sorted(hourly_data.items()):
                    hourly_result.append({
                        "_id": hour_key.isoformat() + "Z",
                        **data
                    })
            
            # Format hourly series for frontend
            series = []
            for hour_data in hourly_result:
                hour_id = hour_data.get("_id")
                hour_dt = None
                
                # Parse the hour from various formats
                if isinstance(hour_id, datetime):
                    hour_dt = hour_id
                elif isinstance(hour_id, str):
                    try:
                        # Try parsing ISO format
                        hour_dt = datetime.fromisoformat(hour_id.replace('Z', '+00:00'))
                    except:
                        try:
                            # Try parsing other formats
                            from dateutil import parser
                            hour_dt = parser.parse(hour_id)
                        except:
                            continue
                else:
                    continue
                
                if hour_dt:
                    # Convert to timestamp (milliseconds since epoch)
                    hour_timestamp = int(hour_dt.timestamp() * 1000)
                    
                    series.append({
                        "hour": hour_timestamp,
                        "requests": hour_data.get("requests", 0),
                        "tokens_in": hour_data.get("tokens_in", 0),
                        "tokens_out": hour_data.get("tokens_out", 0)
                    })
            
            if total_result:
                return {
                    "requests": total_result[0].get("requests", 0),
                    "tokens_in": total_result[0].get("tokens_in", 0),
                    "tokens_out": total_result[0].get("tokens_out", 0),
                    "cost": total_result[0].get("cost", 0.0),
                    "series": series
                }
            
            return {
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "series": series
            }
        except Exception as e:
            _safe_log(f"Failed to get last 24h analytics: {e}")
            return {
                "requests": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost": 0.0,
                "series": []
            }

    def get_schema_usage_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get schema usage statistics."""
        if self._db is None:
            return {}
        try:
            collection = self._db.schema_usage_stats
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            results = list(collection.find(query).sort("last_used_at", DESCENDING))
            
            # Aggregate schema usage
            schema_usage = {}
            total_usages = 0
            most_used_schema = None
            most_used_count = 0
            least_used_schema = None
            least_used_count = float('inf')
            
            for result in results:
                schema_id = result.get("schema_id")
                usage_count = result.get("usage_count", 0)
                schema_usage[schema_id] = {
                    "usage_count": usage_count,
                    "last_used_at": result.get("last_used_at")
                }
                total_usages += usage_count
                
                if usage_count > most_used_count:
                    most_used_count = usage_count
                    most_used_schema = schema_id
                
                if usage_count < least_used_count:
                    least_used_count = usage_count
                    least_used_schema = schema_id
            
            # Calculate average usage
            schema_count = len(schema_usage)
            average_usage = total_usages / schema_count if schema_count > 0 else 0.0
            
            # Build schema_last_used dict from results
            schema_last_used = {}
            for result in results:
                schema_id = result.get("schema_id")
                last_used = result.get("last_used_at")
                if schema_id and last_used:
                    if hasattr(last_used, "isoformat"):
                        schema_last_used[schema_id] = last_used.isoformat()
                    else:
                        schema_last_used[schema_id] = str(last_used)
            
            return {
                "total_usages": total_usages,
                "most_used_schema": most_used_schema,
                "most_used_count": most_used_count if most_used_count > 0 else 0,
                "least_used_schema": least_used_schema,
                "least_used_count": least_used_count if least_used_count != float('inf') else 0,
                "average_usage": average_usage,
                "schema_usage": schema_usage,
                "schema_last_used": schema_last_used
            }
        except Exception as e:
            _safe_log(f"Failed to get schema stats: {e}")
            return {}

    # --- Job Management Methods ---

    def create_job(self, job_id: str, file_name: str, file_id: str, 
                   user_id: Optional[str] = None, total_passes: int = 1, 
                   model: str = "gpt-4", metadata: Dict = {}) -> bool:
        """Create a new job record."""
        if self._db is None:
            return False
        try:
            collection = self._db.jobs
            job_doc = {
                "id": job_id,
                "file_name": file_name,
                "file_id": file_id,
                "user_id": user_id,
                "status": "pending",
                "total_passes": total_passes,
                "current_pass": 0,
                "model": model,
                "metadata": metadata,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            collection.insert_one(job_doc)
            return True
        except Exception as e:
            _safe_log(f"Failed to create job {job_id}: {e}")
            return False

    def update_job_status(self, job_id: str, status: str, current_pass: Optional[int] = None, 
                          metadata_update: Optional[Dict] = None) -> bool:
        """Update job status and metadata."""
        if self._db is None:
            return False
        try:
            collection = self._db.jobs
            update_doc = {
                "status": status,
                "updated_at": datetime.utcnow()
            }
            if current_pass is not None:
                update_doc["current_pass"] = current_pass
            if metadata_update:
                # Merge metadata instead of replacing
                update_doc["$set"] = {"metadata": metadata_update}
            
            collection.update_one(
                {"id": job_id},
                {"$set": update_doc}
            )
            return True
        except Exception as e:
            _safe_log(f"Failed to update job {job_id}: {e}")
            return False

    def log_job_event(self, job_id: str, event_type: str, message: str, 
                      pass_number: Optional[int] = None, details: Dict = {}) -> bool:
        """Log a job event."""
        if self._db is None:
            return False
        try:
            collection = self._db.job_events
            event_doc = {
                "job_id": job_id,
                "event_type": event_type,
                "message": message,
                "pass_number": pass_number,
                "details": details,
                "created_at": datetime.utcnow()
            }
            collection.insert_one(event_doc)
            return True
        except Exception as e:
            _safe_log(f"Failed to log event for job {job_id}: {e}")
            return False

    def get_jobs(self, limit: int = 100, user_id: Optional[str] = None) -> List[Dict]:
        """Get list of jobs."""
        if self._db is None:
            return []
        try:
            collection = self._db.jobs
            query = {}
            if user_id:
                query["user_id"] = user_id
            
            results = list(
                collection.find(query)
                .sort("created_at", DESCENDING)
                .limit(limit)
            )
            
            # Convert ObjectId to string and format dates
            for result in results:
                if "_id" in result:
                    result["_id"] = str(result["_id"])
                if "created_at" in result:
                    result["created_at"] = result["created_at"].isoformat()
                if "updated_at" in result:
                    result["updated_at"] = result["updated_at"].isoformat()
            
            return results
        except Exception as e:
            _safe_log(f"Failed to get jobs: {e}")
            return []

    def get_job_events(self, job_id: str) -> List[Dict]:
        """Get events for a specific job."""
        if self._db is None:
            return []
        try:
            collection = self._db.job_events
            results = list(
                collection.find({"job_id": job_id})
                .sort("created_at", ASCENDING)
            )
            
            # Convert ObjectId to string and format dates
            for result in results:
                if "_id" in result:
                    result["_id"] = str(result["_id"])
                if "created_at" in result:
                    result["created_at"] = result["created_at"].isoformat()
            
            return results
        except Exception as e:
            _safe_log(f"Failed to get events for job {job_id}: {e}")
            return []

    # --- System Logging Methods ---

    def write_system_log(self, level: str, logger_name: str, message: str, 
                         module: str = None, function_name: str = None, 
                         line_number: int = None, traceback: str = None, 
                         metadata: Dict = {}, user_id: Optional[str] = None,
                         action: Optional[str] = None, details: Optional[str] = None,
                         ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> bool:
        """Write a system log entry."""
        if self._db is None:
            return False
        try:
            collection = self._db.system_logs
            log_doc = {
                "level": level,
                "logger_name": logger_name,
                "message": message,
                "module": module,
                "function_name": function_name,
                "line_number": line_number,
                "traceback": traceback,
                "metadata": metadata,
                "user_id": user_id,
                "action": action,
                "details": details,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "created_at": datetime.utcnow()
            }
            # Remove None values
            log_doc = {k: v for k, v in log_doc.items() if v is not None}
            
            collection.insert_one(log_doc)
            return True
        except Exception as e:
            # Do NOT log this error to avoid infinite recursion if this is called from the logger
            if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
                print(f"[MongoDB] Failed to write system log: {e}")
            return False

    def get_system_logs(self, limit: int = 200, level: Optional[str] = None) -> List[Dict]:
        """Get system logs."""
        if self._db is None:
            return []
        try:
            collection = self._db.system_logs
            query = {}
            if level:
                query["level"] = level
            
            results = list(
                collection.find(query)
                .sort("created_at", DESCENDING)
                .limit(limit)
            )
            
            # Convert ObjectId to string and format dates
            for result in results:
                if "_id" in result:
                    result["_id"] = str(result["_id"])
                if "created_at" in result:
                    result["created_at"] = result["created_at"].isoformat()
            
            return results
        except Exception as e:
            _safe_log(f"Failed to get system logs: {e}")
            return []

    # --- User Management Methods (for password reset) ---

    def get_user_by_email(self, email: str) -> Optional[Dict]:
        """Get user by email."""
        if self._db is None:
            return None
        try:
            collection = self._db.users
            user = collection.find_one({"email": email.lower()})
            if user and "_id" in user:
                user["_id"] = str(user["_id"])
            return user
        except Exception as e:
            _safe_log(f"Failed to get user by email: {e}")
            return None

    def update_user_password(self, email: str, password_hash: str) -> bool:
        """Update user password."""
        if self._db is None:
            return False
        try:
            collection = self._db.users
            collection.update_one(
                {"email": email.lower()},
                {
                    "$set": {
                        "password_hash": password_hash,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            return True
        except Exception as e:
            _safe_log(f"Failed to update user password: {e}")
            return False

# Global instance
db = MongoDB()

