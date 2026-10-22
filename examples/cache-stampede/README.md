# Una carga por clave, incluso con varias instancias

**Stack:** Python 3.11+, redis-py 8.1.0, Redis 8.2, SQLite.

Este ejemplo implementa cache-aside para un catálogo de lectura frecuente. Si
una clave vence, una instancia obtiene un bloqueo corto con `SET NX PX`; las
demás esperan el valor en Redis. Un token y un script Lua impiden que un líder
que perdió el bloqueo publique un resultado tardío o borre el bloqueo ajeno.

## Ejecutar

```sh
docker compose up -d
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python run_integration.py
docker compose down
```

La prueba crea una tabla SQLite real, inicia tres procesos de API y envía 100
peticiones por la misma clave vacía. Cuenta las consultas ejecutadas contra
SQLite y exige 100 respuestas iguales con una sola carga. La consulta incluye
trabajo SQL para mantener el primer miss en vuelo mientras llegan los demás.
No es un benchmark de latencia ni una predicción de ahorro en producción.

## Cómo aplicarlo

1. Usa un `loader` que lea tu fuente de datos. El valor debe ser serializable
   como JSON y el trabajo debe terminar antes del TTL del bloqueo.
2. Elige un namespace y clave que identifiquen exactamente el dato. No agrupes
   parámetros distintos bajo una misma clave.
3. Tras escribir correctamente en la base de datos, llama `invalidate(key)`;
   define la tolerancia a datos antiguos antes de usar esto en tu producto.
4. Observa misses, cargas al origen, espera, timeouts y errores de Redis.

## Límites de producción

El bloqueo de Redis reduce cargas duplicadas; no garantiza exclusión absoluta
si la consulta excede su TTL. Para cargas lentas, mide y ajusta `lock_ms` o
renueva el bloqueo de forma segura. Los seguidores fallan tras `wait_s`, en
lugar de multiplicar las consultas. Maneja ese error en la API con una respuesta
acorde a tu producto. Este ejemplo no es apropiado para datos de pagos, saldos
o inventario con requisitos de consistencia fuerte. Usa autenticación y TLS
para Redis fuera del entorno local.

Fuentes: [cache-aside de Redis](https://redis.io/docs/latest/develop/use-cases/cache-aside/go/),
[SET NX PX](https://redis.io/docs/latest/commands/set/),
[redis-py async y sync](https://redis.io/docs/latest/develop/clients/redis-py/).
