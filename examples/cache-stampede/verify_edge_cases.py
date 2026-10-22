"""Check lock ownership and follower timeout against a real Redis instance."""

import os

import redis

from cache_gate import CacheGate, _PUBLISH


def main() -> None:
    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0"),
        decode_responses=True,
    )
    namespace = "yhu-edge-check"
    cache_key = f"{namespace}:data:item"
    lock_key = f"{namespace}:lock:item"
    client.delete(cache_key, lock_key)
    try:
        client.set(lock_key, "new-owner", px=5000)
        published = client.eval(
            _PUBLISH, 2, lock_key, cache_key, "expired-owner", '"stale"', 30
        )
        assert published == 0
        assert client.get(lock_key) == "new-owner"
        assert client.get(cache_key) is None

        gate = CacheGate(client, namespace=namespace, wait_s=0.05)
        loader_called = False

        def loader():
            nonlocal loader_called
            loader_called = True
            return "unexpected"

        try:
            gate.get_or_load("item", loader)
        except TimeoutError:
            pass
        else:
            raise AssertionError("A follower should time out while the lock is held")
        assert not loader_called
        print("Passed: expired owner cannot publish; follower times out without loading")
    finally:
        client.delete(cache_key, lock_key)


if __name__ == "__main__":
    main()
