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

# Import shared logging utility
from app.utils.db_logging import safe_db_log

# Convenience wrapper for backward compatibility
def _safe_log(msg: str, always_print: bool = False):
    safe_db_log(msg, module="MongoDB", always_print=always_print)

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
            
            # Stripe customers collection indexes
            customers_col = self._db.customers
            customers_col.create_index([("user_id", ASCENDING)], unique=True)
            customers_col.create_index([("stripe_customer_id", ASCENDING)], unique=True)
            customers_col.create_index([("email", ASCENDING)])
            
            # Stripe subscriptions collection indexes
            subscriptions_col = self._db.subscriptions
            subscriptions_col.create_index([("subscription_id", ASCENDING)], unique=True)
            subscriptions_col.create_index([("user_id", ASCENDING)])
            subscriptions_col.create_index([("customer_id", ASCENDING)])
            subscriptions_col.create_index([("status", ASCENDING)])
            subscriptions_col.create_index([("created_at", DESCENDING)])
            
            # Stripe payments collection indexes
            payments_col = self._db.payments
            payments_col.create_index([("payment_intent_id", ASCENDING)], unique=True)
            payments_col.create_index([("user_id", ASCENDING)])
            payments_col.create_index([("customer_id", ASCENDING)])
            payments_col.create_index([("subscription_id", ASCENDING)])
            payments_col.create_index([("status", ASCENDING)])
            payments_col.create_index([("created_at", DESCENDING)])
            
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

    def get_job_by_id(self, job_id: str) -> Optional[Dict]:
        """Get a single job by ID."""
        if self._db is None:
            return None
        try:
            collection = self._db.jobs
            result = collection.find_one({"id": job_id})
            
            if result:
                # Convert ObjectId to string and format dates
                if "_id" in result:
                    result["_id"] = str(result["_id"])
                if "created_at" in result:
                    result["created_at"] = result["created_at"].isoformat()
                if "updated_at" in result:
                    result["updated_at"] = result["updated_at"].isoformat()
                return result
            return None
        except Exception as e:
            _safe_log(f"Failed to get job {job_id}: {e}")
            return None
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Alias for get_job_by_id() for consistency with database.py interface."""
        return self.get_job_by_id(job_id)

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
    
    # --- Job Cleanup Methods ---
    
    def delete_job(self, job_id: str) -> bool:
        """Delete a job by ID from MongoDB."""
        if self._db is None:
            return False
        try:
            collection = self._db.jobs
            result = collection.delete_one({"id": job_id})
            
            # Also delete related job events
            if result.deleted_count > 0:
                self._db.job_events.delete_many({"job_id": job_id})
                _safe_log(f"Deleted job {job_id} and its events")
                return True
            return False
        except Exception as e:
            _safe_log(f"Failed to delete job {job_id}: {e}")
            return False
    
    def cleanup_old_jobs(self, days_to_keep: int = 30) -> int:
        """
        Clean up old completed/failed jobs from MongoDB.
        Returns the number of jobs deleted.
        """
        if self._db is None:
            return 0
        try:
            from datetime import datetime, timedelta
            
            collection = self._db.jobs
            cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
            
            # Delete old completed or failed jobs
            result = collection.delete_many({
                "status": {"$in": ["completed", "failed", "cancelled"]},
                "created_at": {"$lt": cutoff_date}
            })
            
            deleted_count = result.deleted_count
            
            # Also clean up orphaned job events
            if deleted_count > 0:
                # Get all remaining job IDs
                remaining_job_ids = [
                    doc["id"] for doc in collection.find({}, {"id": 1})
                ]
                
                # Delete events for non-existent jobs
                self._db.job_events.delete_many({
                    "job_id": {"$nin": remaining_job_ids}
                })
            
            _safe_log(f"Cleaned up {deleted_count} old jobs (older than {days_to_keep} days)")
            return deleted_count
        except Exception as e:
            _safe_log(f"Failed to cleanup old jobs: {e}")
            return 0
    
    # --- Chat Sessions Methods ---
    
    def create_chat_session(self, user_id: str, title: str = None, workspace_id: str = None) -> Optional[str]:
        """Create a new chat session for a user."""
        if self._db is None:
            return None
        try:
            import uuid
            session_id = str(uuid.uuid4())
            
            # Get current session count for auto-numbering
            session_count = self._db.chat_sessions.count_documents({"user_id": user_id})
            
            session = {
                "id": session_id,
                "user_id": user_id,
                "title": title or f"Chat {session_count + 1}",
                "workspace_id": workspace_id,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "message_count": 0,
                "metadata": {},
                # COLLABORATIVE FEATURES
                "is_shared": False,
                "participants": [user_id],  # Owner is always first participant
                "participant_details": []
            }
            
            self._db.chat_sessions.insert_one(session)
            _safe_log(f"Created chat session {session_id} for user {user_id}")
            return session_id
        except Exception as e:
            _safe_log(f"Failed to create chat session: {e}")
            return None
    
    def get_user_sessions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get all chat sessions for a user (owned + shared with them), sorted by updated_at descending."""
        if self._db is None:
            return []
        try:
            _safe_log(f"Fetching sessions for user_id: {user_id}")
            # Get sessions where user is owner OR participant
            sessions = list(self._db.chat_sessions.find({
                "$or": [
                    {"user_id": user_id},
                    {"participants": user_id}
                ]
            }).sort("updated_at", DESCENDING).limit(limit))
            
            _safe_log(f"Found {len(sessions)} sessions for user {user_id} (including shared)")
            
            # Convert ObjectId to string for JSON serialization
            for session in sessions:
                if "_id" in session:
                    session["_id"] = str(session["_id"])
                # Ensure collaborative fields exist (backward compatibility)
                if "is_shared" not in session:
                    session["is_shared"] = False
                if "participants" not in session:
                    session["participants"] = [session["user_id"]]
                if "participant_details" not in session:
                    session["participant_details"] = []
            
            return sessions
        except Exception as e:
            _safe_log(f"Failed to get user sessions: {e}")
            return []
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific chat session by ID."""
        if self._db is None:
            return None
        try:
            session = self._db.chat_sessions.find_one({"id": session_id})
            if session and "_id" in session:
                session["_id"] = str(session["_id"])
            return session
        except Exception as e:
            _safe_log(f"Failed to get session {session_id}: {e}")
            return None
    
    def add_chat_message(self, session_id: str, user_id: str, role: str, content: str, 
                        metadata: Dict[str, Any] = None) -> Optional[str]:
        """Add a message to a chat session."""
        if self._db is None:
            return None
        try:
            import uuid
            message_id = str(uuid.uuid4())
            
            message = {
                "id": message_id,
                "session_id": session_id,
                "user_id": user_id,
                "role": role,  # "user", "assistant", "system"
                "content": content,
                "timestamp": datetime.utcnow(),
                "metadata": metadata or {}
            }
            
            # Insert message
            self._db.chat_messages.insert_one(message)
            
            # Update session timestamp and message count
            self._db.chat_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {"updated_at": datetime.utcnow()},
                    "$inc": {"message_count": 1}
                }
            )
            
            # Update first/last message preview in metadata
            if role == "user":
                self._db.chat_sessions.update_one(
                    {"id": session_id},
                    {"$set": {
                        "metadata.last_message_preview": content[:100] if len(content) > 100 else content
                    }}
                )
                
                # Set first message preview if this is the first user message
                session = self._db.chat_sessions.find_one({"id": session_id})
                if session and not session.get("metadata", {}).get("first_message_preview"):
                    self._db.chat_sessions.update_one(
                        {"id": session_id},
                        {"$set": {
                            "metadata.first_message_preview": content[:100] if len(content) > 100 else content
                        }}
                    )
            
            return message_id
        except Exception as e:
            _safe_log(f"Failed to add chat message: {e}")
            return None
    
    def get_session_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all messages in a chat session, sorted by timestamp ascending."""
        if self._db is None:
            return []
        try:
            messages = list(self._db.chat_messages.find(
                {"session_id": session_id}
            ).sort("timestamp", ASCENDING).limit(limit))
            
            # Convert ObjectId to string
            for message in messages:
                if "_id" in message:
                    message["_id"] = str(message["_id"])
            
            return messages
        except Exception as e:
            _safe_log(f"Failed to get session messages: {e}")
            return []
    
    def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a chat session and all its messages. Verifies ownership."""
        if self._db is None:
            return False
        try:
            # Verify ownership
            session = self._db.chat_sessions.find_one({"id": session_id, "user_id": user_id})
            if not session:
                _safe_log(f"Session {session_id} not found or not owned by user {user_id}")
                return False
            
            # Delete all messages in the session
            self._db.chat_messages.delete_many({"session_id": session_id})
            
            # Delete the session
            result = self._db.chat_sessions.delete_one({"id": session_id})
            
            success = result.deleted_count > 0
            if success:
                _safe_log(f"Deleted session {session_id} and its messages")
            return success
        except Exception as e:
            _safe_log(f"Failed to delete session {session_id}: {e}")
            return False
    
    def rename_session(self, session_id: str, user_id: str, new_title: str) -> bool:
        """Rename a chat session. Verifies ownership."""
        if self._db is None:
            return False
        try:
            result = self._db.chat_sessions.update_one(
                {"id": session_id, "user_id": user_id},
                {"$set": {"title": new_title, "updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            _safe_log(f"Failed to rename session {session_id}: {e}")
            return False
    
    def clear_session_messages(self, session_id: str, user_id: str) -> bool:
        """Clear all messages in a session while keeping the session. Verifies ownership."""
        if self._db is None:
            return False
        try:
            # Verify ownership
            session = self._db.chat_sessions.find_one({"id": session_id, "user_id": user_id})
            if not session:
                return False
            
            # Delete all messages
            self._db.chat_messages.delete_many({"session_id": session_id})
            
            # Reset message count and clear previews
            self._db.chat_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "message_count": 0,
                        "updated_at": datetime.utcnow(),
                        "metadata.first_message_preview": None,
                        "metadata.last_message_preview": None
                    }
                }
            )
            
            return True
        except Exception as e:
            _safe_log(f"Failed to clear session messages: {e}")
            return False
    
    # --- Collaborative Session Methods ---
    
    def share_session(self, session_id: str, owner_id: str) -> bool:
        """Enable sharing for a session (create/link workspace)."""
        if self._db is None:
            return False
        try:
            # Get session to verify ownership
            session = self._db.chat_sessions.find_one({"id": session_id})
            if not session or session.get("user_id") != owner_id:
                _safe_log(f"Cannot share session {session_id}: not owned by {owner_id}")
                return False
            
            # Create workspace_id if doesn't exist
            workspace_id = session.get("workspace_id") or f"ws_{session_id}"
            
            # Ensure owner is in participants list
            participants = session.get("participants", [])
            if owner_id not in participants:
                participants = [owner_id] + participants  # Owner first
            
            # Ensure participant_details includes owner
            participant_details = session.get("participant_details", [])
            if not any(p.get("user_id") == owner_id for p in participant_details):
                participant_details.insert(0, {
                    "user_id": owner_id,
                    "email": "owner",
                    "name": "Owner",
                    "is_owner": True,
                    "joined_at": session.get("created_at", datetime.utcnow())
                })
            
            self._db.chat_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "is_shared": True,
                        "workspace_id": workspace_id,
                        "participants": participants,
                        "participant_details": participant_details,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            _safe_log(f"Enabled sharing for session {session_id} with workspace {workspace_id}, owner in participants")
            return True
        except Exception as e:
            _safe_log(f"Failed to share session: {e}")
            return False
    
    def unshare_session(self, session_id: str, owner_id: str) -> bool:
        """Disable sharing for a session (make private)."""
        if self._db is None:
            return False
        try:
            # Verify ownership
            session = self._db.chat_sessions.find_one({"id": session_id})
            if not session or session.get("user_id") != owner_id:
                return False
            
            # Keep owner in participants, remove others
            self._db.chat_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "is_shared": False,
                        "participants": [owner_id],
                        "participant_details": [],
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            _safe_log(f"Disabled sharing for session {session_id}")
            return True
        except Exception as e:
            _safe_log(f"Failed to unshare session: {e}")
            return False
    
    def add_session_participant(self, session_id: str, user_id: str, user_email: str = None, user_name: str = None) -> bool:
        """Add a participant to a shared session."""
        if self._db is None:
            return False
        try:
            # Verify session exists
            session = self._db.chat_sessions.find_one({"id": session_id})
            if not session:
                _safe_log(f"Session {session_id} not found")
                return False
            
            # Add to participants array
            participants = session.get("participants", [])
            if user_id in participants:
                _safe_log(f"User {user_id} already participant in session {session_id}")
                return True
            
            participants.append(user_id)
            
            # Add participant details
            participant_details = session.get("participant_details", [])
            participant_details.append({
                "user_id": user_id,
                "email": user_email or "unknown",
                "name": user_name or user_email or user_id,
                "joined_at": datetime.utcnow()
            })
            
            self._db.chat_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "participants": participants,
                        "participant_details": participant_details,
                        "is_shared": True,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            _safe_log(f"Added user {user_id} to session {session_id}")
            return True
        except Exception as e:
            _safe_log(f"Failed to add participant: {e}")
            return False
    
    def remove_session_participant(self, session_id: str, user_id: str, requester_id: str) -> bool:
        """Remove a participant from a session (owner only)."""
        if self._db is None:
            return False
        try:
            # Verify requester is owner
            session = self._db.chat_sessions.find_one({"id": session_id})
            if not session or session.get("user_id") != requester_id:
                _safe_log(f"Cannot remove participant: {requester_id} is not owner")
                return False
            
            # Cannot remove owner
            if user_id == session.get("user_id"):
                _safe_log(f"Cannot remove owner from session")
                return False
            
            # Remove from participants
            participants = [p for p in session.get("participants", []) if p != user_id]
            participant_details = [
                p for p in session.get("participant_details", []) 
                if p.get("user_id") != user_id
            ]
            
            self._db.chat_sessions.update_one(
                {"id": session_id},
                {
                    "$set": {
                        "participants": participants,
                        "participant_details": participant_details,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            _safe_log(f"Removed user {user_id} from session {session_id}")
            return True
        except Exception as e:
            _safe_log(f"Failed to remove participant: {e}")
            return False
    
    def get_session_participants(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all participants in a session."""
        if self._db is None:
            return []
        try:
            session = self._db.chat_sessions.find_one({"id": session_id})
            
            if not session:
                return []
            
            participants = session.get("participant_details", [])
            
            # Add owner info if not in details
            owner_id = session.get("user_id")
            if owner_id and not any(p.get("user_id") == owner_id for p in participants):
                participants.insert(0, {
                    "user_id": owner_id,
                    "email": "owner",
                    "name": "Owner",
                    "joined_at": session.get("created_at"),
                    "is_owner": True
                })
            else:
                # Mark owner in existing participants
                for p in participants:
                    if p.get("user_id") == owner_id:
                        p["is_owner"] = True
            
            return participants
        except Exception as e:
            _safe_log(f"Failed to get session participants: {e}")
            return []

# Global instance
mongodb = MongoDB()

# Backward compatibility alias (to be deprecated)
db = mongodb

