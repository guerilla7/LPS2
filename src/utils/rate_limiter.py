"""Enhanced in-memory rate limiter for Flask.

Supports both IP-based and user-based rate limiting with different tiers.
Implements fixed window + lightweight burst tracking.
Not production-grade (single-process only). For production, use Redis-based implementation.
"""
from __future__ import annotations
import time
import threading
from typing import Dict, Tuple, Optional, NamedTuple
from config import (
    RATE_LIMIT_WINDOW_SECONDS, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_BURST,
    USER_RATE_LIMIT_WINDOW, USER_RATE_LIMIT_MAX, USER_RATE_LIMIT_BURST,
    ADMIN_RATE_LIMIT_WINDOW, ADMIN_RATE_LIMIT_MAX, ADMIN_RATE_LIMIT_BURST
)

class RateLimitTier(NamedTuple):
    """Rate limit configuration for a specific user tier."""
    window_seconds: int
    max_requests: int
    burst_limit: int

# Default rate limits by tier
DEFAULT_TIERS = {
    'ip': RateLimitTier(
        window_seconds=RATE_LIMIT_WINDOW_SECONDS,
        max_requests=RATE_LIMIT_MAX_REQUESTS,
        burst_limit=RATE_LIMIT_BURST
    ),
    'user': RateLimitTier(
        window_seconds=USER_RATE_LIMIT_WINDOW,
        max_requests=USER_RATE_LIMIT_MAX,
        burst_limit=USER_RATE_LIMIT_BURST
    ),
    'admin': RateLimitTier(
        window_seconds=ADMIN_RATE_LIMIT_WINDOW,
        max_requests=ADMIN_RATE_LIMIT_MAX,
        burst_limit=ADMIN_RATE_LIMIT_BURST
    )
}

_LOCK = threading.Lock()
_STATE: Dict[str, Dict[str, float]] = {}  # key -> {timestamp -> time}
_BURST: Dict[str, Tuple[int, float]] = {}  # key -> (count, last_ts)

def check_rate(identifier: str, tier: str = 'ip') -> Tuple[bool, Optional[Dict]]:
    """
    Check if a request should be rate limited.
    
    Args:
        identifier: IP address or username to track
        tier: Rate limit tier to apply ('ip', 'user', or 'admin')
        
    Returns:
        Tuple of (allowed, limit_info) where limit_info contains rate limit headers
    """
    # Get the appropriate tier settings
    limit_config = DEFAULT_TIERS.get(tier, DEFAULT_TIERS['ip'])
    
    # Create a composite key that includes the tier
    key = f"{tier}:{identifier}"
    
    now = time.time()
    window_start = now - limit_config.window_seconds
    
    with _LOCK:
        bucket = _STATE.setdefault(key, {})
        
        # Prune old entries
        old_keys = [k for k, ts in bucket.items() if ts < window_start]
        for k in old_keys:
            del bucket[k]
            
        # Current request count in window
        current_count = len(bucket)
        
        # Add new request entry keyed by precise timestamp id
        bucket[str(now)] = now
        
        # Check window-based rate limit
        if current_count >= limit_config.max_requests:
            # Calculate reset time
            oldest_ts = min(bucket.values()) if bucket else now
            reset_after = int(limit_config.window_seconds - (now - oldest_ts))
            
            return False, {
                'X-RateLimit-Limit': limit_config.max_requests,
                'X-RateLimit-Remaining': 0,
                'X-RateLimit-Reset': reset_after,
                'X-RateLimit-Used': current_count
            }
            
        # Burst logic: collapse last second counts
        cnt, last_ts = _BURST.get(key, (0, 0.0))
        if now - last_ts <= 1.0:
            cnt += 1
        else:
            cnt = 1
        _BURST[key] = (cnt, now)
        
        if cnt > limit_config.burst_limit:
            return False, {
                'X-RateLimit-Limit': limit_config.max_requests,
                'X-RateLimit-Remaining': limit_config.max_requests - current_count,
                'X-RateLimit-Reset': limit_config.window_seconds,
                'X-RateLimit-Burst-Limit': limit_config.burst_limit,
                'X-RateLimit-Burst-Count': cnt
            }
            
    # Request allowed
    return True, {
        'X-RateLimit-Limit': limit_config.max_requests,
        'X-RateLimit-Remaining': limit_config.max_requests - current_count,
        'X-RateLimit-Reset': limit_config.window_seconds
    }
