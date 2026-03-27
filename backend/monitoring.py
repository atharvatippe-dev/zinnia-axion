"""
Monitoring and metrics collection for the backend.

Periodically collects and reports:
  - Database connection pool statistics
  - Redis cache statistics
  - Query performance metrics
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def collect_and_report_metrics(app) -> bool:
    """
    Collect metrics from database connection pool, cache, and report to CloudWatch.
    
    Call this periodically (e.g., from a background task or the blueprint).
    """
    try:
        from backend.cloudwatch_metrics import (
            report_db_pool_stats,
            report_cache_stats,
        )
        from backend.cache_config import get_cache_stats
        
        # ─── Database Pool Metrics ─────────────────────────────────
        engine = app.extensions['sqlalchemy'].engine
        pool = engine.pool
        
        # Get pool statistics
        pool_size = pool.size()
        pool_checked_out = pool.checkedout()
        pool_overflow = pool.overflow()
        pool_max_size = getattr(pool, '_pool_size', 10)
        pool_idle = pool_size - pool_checked_out
        
        logger.debug(
            f"DB Pool Stats: size={pool_size}, active={pool_checked_out}, "
            f"idle={pool_idle}, overflow={pool_overflow}, max={pool_max_size}"
        )
        
        report_db_pool_stats(
            active=pool_checked_out,
            idle=pool_idle,
            overflow=pool_overflow,
            max_size=pool_max_size
        )
        
        # ─── Redis Cache Metrics ───────────────────────────────────
        cache_stats = get_cache_stats()
        
        if cache_stats.get("status") == "connected":
            hits = cache_stats.get("keyspace_hits", 0)
            misses = cache_stats.get("keyspace_misses", 0)
            evicted = cache_stats.get("evicted_keys", 0)
            memory_mb = cache_stats.get("used_memory_mb", 0)
            
            logger.debug(
                f"Cache Stats: hits={hits}, misses={misses}, "
                f"evicted={evicted}, memory={memory_mb}MB, "
                f"hit_rate={cache_stats.get('hit_rate', 0):.2f}%"
            )
            
            report_cache_stats(
                hits=int(hits),
                misses=int(misses),
                evicted=int(evicted),
                memory_mb=float(memory_mb)
            )
        
        logger.info("Metrics collected and reported to CloudWatch")
        return True
        
    except Exception as e:
        logger.error(f"Error collecting metrics: {e}", exc_info=True)
        return False


def get_pool_stats(app) -> dict:
    """Get current database pool statistics."""
    try:
        engine = app.extensions['sqlalchemy'].engine
        pool = engine.pool
        
        return {
            "pool_size": pool.size(),
            "pool_checked_out": pool.checkedout(),
            "pool_overflow": pool.overflow(),
            "pool_idle": pool.size() - pool.checkedout(),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting pool stats: {e}")
        return {"error": str(e)}


def get_cache_stats_dict(app) -> dict:
    """Get current cache statistics."""
    try:
        from backend.cache_config import get_cache_stats
        return get_cache_stats()
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"error": str(e)}
