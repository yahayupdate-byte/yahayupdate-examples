"""Cache-aside with one Redis-backed leader per key across API processes.

For read-mostly, recomputable values. Do not use as the source of truth.
"""

import json
import secrets
import time
from typing import Callable, TypeVar

import redis

T = TypeVar("T")

_PUBLISH = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('SET', KEYS[2], ARGV[2], 'EX', ARGV[3])
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
"""
_RELEASE = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""


class CacheGate:
    def __init__(self, client: redis.Redis, namespace: str = "catalog", ttl_s: int = 30,
                 lock_ms: int = 5000, wait_s: float = 6.0):
        if ttl_s < 1 or lock_ms < 1 or wait_s <= 0:
            raise ValueError("TTL and wait limits must be positive")
        self.client, self.namespace = client, namespace
        self.ttl_s, self.lock_ms, self.wait_s = ttl_s, lock_ms, wait_s

    def get_or_load(self, key: str, loader: Callable[[], T]) -> T:
        cache_key = f"{self.namespace}:data:{key}"
        lock_key = f"{self.namespace}:lock:{key}"
        deadline = time.monotonic() + self.wait_s
        while time.monotonic() < deadline:
            cached = self.client.get(cache_key)
            if cached is not None:
                return json.loads(cached)

            token = secrets.token_hex(16)
            if self.client.set(lock_key, token, nx=True, px=self.lock_ms):
                try:
                    # The old leader may have filled the key before this lock was acquired.
                    cached = self.client.get(cache_key)
                    if cached is not None:
                        return json.loads(cached)
                    value = loader()
                    payload = json.dumps(value, separators=(",", ":"))
                    # A timed-out leader must not overwrite its successor's value.
                    published = self.client.eval(_PUBLISH, 2, lock_key, cache_key,
                                                 token, payload, self.ttl_s)
                    if published:
                        return value
                finally:
                    self.client.eval(_RELEASE, 1, lock_key, token)
            # A follower waits for the leader or retries if the lock expires.
            time.sleep(0.02)
        raise TimeoutError(f"No cached value for {key} within {self.wait_s}s")

    def invalidate(self, key: str) -> None:
        """Call after a successful write to the source database."""
        self.client.delete(f"{self.namespace}:data:{key}")
