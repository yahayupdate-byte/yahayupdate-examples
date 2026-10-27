# Ya Hay Update · Runnable architecture examples

Code that accompanies Ya Hay Update's software architecture articles. Each
example states its stack, how to run it, what it verifies, and its limitations.

## Examples

- [Prevent a cache stampede across API processes](examples/cache-stampede/README.md)

GitHub Actions runs the cache integration checks against a Redis service on pushes
to `main` and pull requests.

When an example claims to verify behavior, it uses actual services and a
repeatable integration check. A local check is not a production benchmark.
