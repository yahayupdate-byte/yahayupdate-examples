"""Exercise the real Redis gate against SQLite using three API processes."""

import json
import multiprocessing as mp
import os
import sqlite3
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import redis

from cache_gate import CacheGate

URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6380/0")
KEY = "featured-products"


def worker(db_path: str, count: int, namespace: str, start: mp.Event,
           output: mp.Queue) -> None:
    client = redis.Redis.from_url(URL, decode_responses=True)
    gate = CacheGate(client, namespace=namespace, ttl_s=30, lock_ms=5000, wait_s=15)

    def load_products():
        client.incr(f"{namespace}:origin_reads")
        with sqlite3.connect(db_path) as conn:
            # Actual database read. Query work makes concurrent misses observable.
            rows = conn.execute("""
                WITH RECURSIVE tally(n) AS (
                    SELECT 1 UNION ALL SELECT n+1 FROM tally WHERE n<100000
                )
                SELECT p.id, p.name, p.price_cents, (SELECT SUM(n) FROM tally)
                FROM products p ORDER BY p.id
            """).fetchall()
        return [{"id": r[0], "name": r[1], "price_cents": r[2]} for r in rows]

    start.wait()
    with ThreadPoolExecutor(max_workers=count) as pool:
        results = list(pool.map(lambda _: gate.get_or_load(KEY, load_products), range(count)))
    output.put((len(results), all(value == results[0] for value in results)))


def main():
    client = redis.Redis.from_url(URL, decode_responses=True)
    client.ping()
    namespace = f"yhu-integration:{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory() as tmp:
        db_path = str(Path(tmp) / "catalog.sqlite3")
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT, price_cents INTEGER)")
            conn.executemany("INSERT INTO products VALUES (?, ?, ?)",
                             [(1, "Phone case", 1499), (2, "Charger", 2499)])
        start, output = mp.Event(), mp.Queue()
        counts = (34, 33, 33)
        processes = [mp.Process(target=worker, args=(db_path, n, namespace, start, output))
                     for n in counts]
        for process in processes:
            process.start()
        start.set()
        reports = [output.get(timeout=30) for _ in processes]
        for process in processes:
            process.join(timeout=5)
        assert all(p.exitcode == 0 for p in processes), "An API process failed"
    result = {
        "stack": "Python 3 + redis-py 8.1.0 + Redis 8.2 + SQLite",
        "api_processes": len(counts),
        "concurrent_requests": sum(n for n, _ in reports),
        "responses_identical": all(ok for _, ok in reports),
        "sqlite_reads": int(client.get(f"{namespace}:origin_reads") or 0),
    }
    print(json.dumps(result, indent=2))
    assert result["concurrent_requests"] == 100
    assert result["responses_identical"]
    assert result["sqlite_reads"] == 1
    client.delete(f"{namespace}:data:{KEY}", f"{namespace}:lock:{KEY}",
                  f"{namespace}:origin_reads")


if __name__ == "__main__":
    main()
