# One load per key across API processes

**Stack:** Python 3.11+, redis-py 8.1.0, Redis 8.2, SQLite, Docker Compose.

- **Python + redis-py** implement the API's cache-aside path.
- **Redis** stores the temporary result and coordinates a short lock per key.
- **SQLite** holds a real product catalog and records origin queries.
- **Docker Compose** starts Redis locally for a repeatable integration run.

On a cache miss, one process acquires a short lock with `SET NX PX`; other
processes wait for the cached value. An ownership token and Lua script prevent
an expired leader from publishing late or deleting another leader's lock.

## Run

```sh
docker compose up -d
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_integration.py
python verify_edge_cases.py
docker compose down
```

The integration check creates SQLite `products` and `order_items` tables with
generated fixture rows (5,000 products and 250,000 order items). Its source
query returns the 20 best-selling active products from the last 30 days. It
starts three API processes and sends 100 requests for the same empty cache
key. It asserts 100 identical responses and one SQLite load. The fixture data
is synthetic; Redis and SQLite are real services. This is not a latency
benchmark or a claim about production traffic.
The edge check confirms that an expired owner cannot publish over a new lock
and that a follower times out without querying the source.

## Adapt it to an API

1. Replace the example loader with your source query. It must return a
   JSON-serializable value and finish within the lock TTL under normal load.
2. Include every result-changing input in the cache key. Do not share one
   key between users or query variants that require different data.
3. After a successful source write, call `invalidate(key)`. For strict
   freshness, also address the race between an in-flight read and invalidation
   with versioned keys, generation checks, or an appropriate transaction design.
4. Observe cache misses, origin loads, follower wait time, timeouts, and Redis
   errors. Define the API response when a follower times out.

## Production limits

The Redis lock reduces duplicate loads; it does not guarantee exactly one
origin read if a load exceeds the lock TTL. Measure load duration and adjust
the TTL or use safe renewal. Followers fail after `wait_s` instead of fanning
out to the source. A fallback that lets every request query the database can
recreate the stampede. This pattern targets recomputable, read-heavy data; it
is not a drop-in consistency strategy for balances, payments, or inventory.
Use Redis authentication and TLS outside a local development environment.
This sample uses a single Redis node. On Redis Cluster, the lock and data keys
must share a hash slot for the Lua operation; adapt the key format before use.

Sources: [Redis cache-aside](https://redis.io/docs/latest/develop/use-cases/cache-aside/go/),
[SET NX PX](https://redis.io/docs/latest/commands/set/),
[redis-py](https://redis.io/docs/latest/develop/clients/redis-py/).
