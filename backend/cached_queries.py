"""
Caching layer for common database queries.

Provides @cached decorator and helper functions for:
  - User lookups
  - Team hierarchy traversal
  - Dashboard aggregations
"""

import logging
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Optional, Any, Callable, List

from backend.cache_config import (
    cache_get, cache_set, cache_delete, cache_delete_pattern,
    CacheConfig
)
from backend.cloudwatch_metrics import report_query_performance
import time

logger = logging.getLogger(__name__)


def _measure_query_time(func: Callable) -> Callable:
    """Decorator to measure query execution time and report to CloudWatch."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed_ms = (time.time() - start_time) * 1000
        
        # Report to CloudWatch
        from_cache = getattr(wrapper, '_from_cache', False)
        report_query_performance(func.__name__, elapsed_ms, from_cache)
        
        return result
    return wrapper


class CachedQueries:
    """Helper class for cached database queries."""

    @staticmethod
    def get_user_by_id(db, user_id: int, ttl: int = None):
        """Get user by ID with caching."""
        if ttl is None:
            ttl = CacheConfig.CACHE_TTL_USER_DATA

        cache_key = f"user:id:{user_id}"
        
        # Try cache
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached

        # Cache miss: query database
        from backend.models import User
        user = User.query.get(user_id)
        
        if user:
            user_dict = user.to_dict()
            cache_set(cache_key, user_dict, ttl=ttl)
            logger.debug(f"Cache SET: {cache_key}")
            return user_dict
        
        return None

    @staticmethod
    def get_user_by_lan_id(db, lan_id: str, ttl: int = None):
        """Get user by LAN ID with caching."""
        if ttl is None:
            ttl = CacheConfig.CACHE_TTL_USER_DATA

        cache_key = f"user:lan_id:{lan_id}"
        
        # Try cache
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached

        # Cache miss: query database
        from backend.models import User
        user = User.query.filter_by(lan_id=lan_id).first()
        
        if user:
            user_dict = user.to_dict()
            cache_set(cache_key, user_dict, ttl=ttl)
            logger.debug(f"Cache SET: {cache_key}")
            return user_dict
        
        return None

    @staticmethod
    def get_team_by_id(db, team_id: int, ttl: int = None):
        """Get team by ID with caching."""
        if ttl is None:
            ttl = CacheConfig.CACHE_TTL_TEAM_HIERARCHY

        cache_key = f"team:id:{team_id}"
        
        # Try cache
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached

        # Cache miss: query database
        from backend.models import Team
        team = Team.query.get(team_id)
        
        if team:
            team_dict = team.to_dict()
            cache_set(cache_key, team_dict, ttl=ttl)
            logger.debug(f"Cache SET: {cache_key}")
            return team_dict
        
        return None

    @staticmethod
    def get_team_hierarchy(db, team_id: int, ttl: int = None):
        """Get team hierarchy (team + descendants) with caching."""
        if ttl is None:
            ttl = CacheConfig.CACHE_TTL_TEAM_HIERARCHY

        cache_key = f"team:hierarchy:{team_id}"
        
        # Try cache
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached

        # Cache miss: query database
        from backend.models import Team
        
        def _get_descendants(team):
            result = [team.id]
            for child in team.children:
                result.extend(_get_descendants(child))
            return result

        team = Team.query.get(team_id)
        if team:
            hierarchy = _get_descendants(team)
            cache_set(cache_key, hierarchy, ttl=ttl)
            logger.debug(f"Cache SET: {cache_key}")
            return hierarchy
        
        return []

    @staticmethod
    def get_user_teams(db, user_id: int, ttl: int = None):
        """Get all teams for a user with caching."""
        if ttl is None:
            ttl = CacheConfig.CACHE_TTL_TEAM_HIERARCHY

        cache_key = f"user:teams:{user_id}"
        
        # Try cache
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached

        # Cache miss: query database
        from backend.models import Membership
        
        memberships = Membership.query.filter_by(user_id=user_id, active=True).all()
        team_ids = [m.team_id for m in memberships]
        
        cache_set(cache_key, team_ids, ttl=ttl)
        logger.debug(f"Cache SET: {cache_key}")
        return team_ids

    @staticmethod
    def get_dashboard_summary(
        db,
        user_id: str,
        days: int = 1,
        ttl: int = None
    ):
        """Get dashboard summary with caching (aggressive: 1 min)."""
        if ttl is None:
            ttl = CacheConfig.CACHE_TTL_DASHBOARD

        cache_key = f"dashboard:summary:{user_id}:{days}d"
        
        # Try cache
        cached = cache_get(cache_key)
        if cached is not None:
            logger.debug(f"Cache HIT: {cache_key}")
            return cached

        # Cache miss: this would be computed from telemetry_events
        # (actual implementation depends on your dashboard logic)
        logger.debug(f"Cache MISS (expected): {cache_key}")
        return None

    @staticmethod
    def invalidate_user_cache(user_id: int):
        """Invalidate all cache entries for a user."""
        cache_delete(f"user:id:{user_id}")
        cache_delete(f"user:teams:{user_id}")
        logger.debug(f"Invalidated cache for user {user_id}")

    @staticmethod
    def invalidate_team_cache(team_id: int):
        """Invalidate all cache entries for a team."""
        cache_delete(f"team:id:{team_id}")
        cache_delete(f"team:hierarchy:{team_id}")
        # Invalidate all descendant team cache entries
        cache_delete_pattern(f"team:hierarchy:{team_id}:*")
        logger.debug(f"Invalidated cache for team {team_id}")

    @staticmethod
    def invalidate_dashboard_cache(user_id: str = None):
        """Invalidate dashboard cache (either for a specific user or all)."""
        if user_id:
            cache_delete_pattern(f"dashboard:summary:{user_id}:*")
            logger.debug(f"Invalidated dashboard cache for user {user_id}")
        else:
            cache_delete_pattern("dashboard:summary:*")
            logger.debug("Invalidated all dashboard cache entries")
