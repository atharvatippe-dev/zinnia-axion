"""
CloudWatch metrics integration for Zinnia Axion.

Provides centralized metrics for:
  - Database connection pool statistics
  - Query performance (latency, cache hit/miss)
  - Application-level metrics (API calls, errors)
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class CloudWatchConfig:
    """CloudWatch configuration loaded from environment."""

    CLOUDWATCH_ENABLED: bool = os.getenv("CLOUDWATCH_ENABLED", "true").lower() in (
        "true",
        "1",
        "yes",
    )
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    CLOUDWATCH_NAMESPACE: str = os.getenv("CLOUDWATCH_NAMESPACE", "ZinniaAxion/Backend")
    CLOUDWATCH_ENVIRONMENT: str = os.getenv("CLOUDWATCH_ENVIRONMENT", "development")


# Global CloudWatch client instance
_cloudwatch_client = None


def get_cloudwatch_client():
    """
    Get or create a CloudWatch client instance.
    Returns None if CloudWatch is unavailable or disabled.
    """
    global _cloudwatch_client

    if not CloudWatchConfig.CLOUDWATCH_ENABLED or not BOTO3_AVAILABLE:
        return None

    if _cloudwatch_client is not None:
        return _cloudwatch_client

    try:
        kwargs = {
            "region_name": CloudWatchConfig.AWS_REGION,
        }
        if CloudWatchConfig.AWS_ACCESS_KEY_ID and CloudWatchConfig.AWS_SECRET_ACCESS_KEY:
            kwargs["aws_access_key_id"] = CloudWatchConfig.AWS_ACCESS_KEY_ID
            kwargs["aws_secret_access_key"] = CloudWatchConfig.AWS_SECRET_ACCESS_KEY

        _cloudwatch_client = boto3.client("cloudwatch", **kwargs)
        logger.info("CloudWatch client initialized")
        return _cloudwatch_client
    except Exception as e:
        logger.warning(f"CloudWatch initialization failed: {e}")
        _cloudwatch_client = None
        return None


def put_metric(
    metric_name: str,
    value: float,
    unit: str = "None",
    dimensions: Optional[Dict[str, str]] = None,
) -> bool:
    """
    Put a custom metric to CloudWatch.

    Args:
        metric_name: Name of the metric (e.g., "DBPoolActive")
        value: Numeric value
        unit: Unit (Count, Seconds, Bytes, Percent, etc.)
        dimensions: Optional dimensions dict (e.g., {"Environment": "production"})

    Returns:
        True if successful, False otherwise
    """
    client = get_cloudwatch_client()
    if client is None:
        return False

    try:
        metric_data = {
            "MetricName": metric_name,
            "Value": value,
            "Unit": unit,
            "Timestamp": datetime.utcnow(),
        }

        # Add default dimensions
        dims = [
            {"Name": "Environment", "Value": CloudWatchConfig.CLOUDWATCH_ENVIRONMENT}
        ]
        if dimensions:
            for k, v in dimensions.items():
                dims.append({"Name": k, "Value": str(v)})
        metric_data["Dimensions"] = dims

        client.put_metric_data(
            Namespace=CloudWatchConfig.CLOUDWATCH_NAMESPACE,
            MetricData=[metric_data],
        )
        return True
    except Exception as e:
        logger.error(f"Error putting metric {metric_name}: {e}")
        return False


def put_metrics_batch(metrics: list[dict]) -> bool:
    """
    Put multiple metrics to CloudWatch in a single request.

    Args:
        metrics: List of metric dicts, each with keys:
                 - metric_name: str
                 - value: float
                 - unit: str (default "None")
                 - dimensions: Optional[Dict[str, str]]

    Returns:
        True if successful, False otherwise
    """
    client = get_cloudwatch_client()
    if client is None:
        return False

    try:
        metric_data = []
        for metric in metrics:
            metric_dict = {
                "MetricName": metric["metric_name"],
                "Value": metric["value"],
                "Unit": metric.get("unit", "None"),
                "Timestamp": datetime.utcnow(),
            }

            # Add default dimensions
            dims = [
                {
                    "Name": "Environment",
                    "Value": CloudWatchConfig.CLOUDWATCH_ENVIRONMENT,
                }
            ]
            if metric.get("dimensions"):
                for k, v in metric["dimensions"].items():
                    dims.append({"Name": k, "Value": str(v)})
            metric_dict["Dimensions"] = dims

            metric_data.append(metric_dict)

        client.put_metric_data(
            Namespace=CloudWatchConfig.CLOUDWATCH_NAMESPACE,
            MetricData=metric_data,
        )
        return True
    except Exception as e:
        logger.error(f"Error putting batch metrics: {e}")
        return False


# ─── Specific Metric Helpers ────────────────────────────────────────


def report_db_pool_stats(
    active: int, idle: int, overflow: int, max_size: int
) -> bool:
    """Report database connection pool statistics."""
    metrics = [
        {
            "metric_name": "DBPoolActive",
            "value": active,
            "unit": "Count",
        },
        {
            "metric_name": "DBPoolIdle",
            "value": idle,
            "unit": "Count",
        },
        {
            "metric_name": "DBPoolOverflow",
            "value": overflow,
            "unit": "Count",
        },
        {
            "metric_name": "DBPoolUtilization",
            "value": (active / max_size * 100) if max_size > 0 else 0,
            "unit": "Percent",
        },
    ]
    return put_metrics_batch(metrics)


def report_query_performance(
    query_name: str,
    latency_ms: float,
    from_cache: bool = False,
) -> bool:
    """Report query performance metrics."""
    metrics = [
        {
            "metric_name": "QueryLatency",
            "value": latency_ms,
            "unit": "Milliseconds",
            "dimensions": {"QueryName": query_name, "CacheHit": str(from_cache)},
        },
        {
            "metric_name": "CacheHitRate" if from_cache else "CacheMissRate",
            "value": 1,
            "unit": "Count",
            "dimensions": {"QueryName": query_name},
        },
    ]
    return put_metrics_batch(metrics)


def report_api_call(
    endpoint: str,
    method: str,
    status_code: int,
    latency_ms: float,
) -> bool:
    """Report API call metrics."""
    metrics = [
        {
            "metric_name": "APICallCount",
            "value": 1,
            "unit": "Count",
            "dimensions": {
                "Endpoint": endpoint,
                "Method": method,
                "StatusCode": str(status_code),
            },
        },
        {
            "metric_name": "APILatency",
            "value": latency_ms,
            "unit": "Milliseconds",
            "dimensions": {"Endpoint": endpoint, "Method": method},
        },
    ]
    return put_metrics_batch(metrics)


def report_error(error_type: str, endpoint: str = "unknown") -> bool:
    """Report application errors."""
    return put_metric(
        "ApplicationError",
        1,
        "Count",
        dimensions={"ErrorType": error_type, "Endpoint": endpoint},
    )


def report_cache_stats(
    hits: int, misses: int, evicted: int, memory_mb: float
) -> bool:
    """Report cache statistics."""
    total = hits + misses
    hit_rate = (hits / total * 100) if total > 0 else 0

    metrics = [
        {
            "metric_name": "CacheHits",
            "value": hits,
            "unit": "Count",
        },
        {
            "metric_name": "CacheMisses",
            "value": misses,
            "unit": "Count",
        },
        {
            "metric_name": "CacheHitRate",
            "value": hit_rate,
            "unit": "Percent",
        },
        {
            "metric_name": "CacheEvictions",
            "value": evicted,
            "unit": "Count",
        },
        {
            "metric_name": "CacheMemoryUsage",
            "value": memory_mb,
            "unit": "Megabytes",
        },
    ]
    return put_metrics_batch(metrics)
