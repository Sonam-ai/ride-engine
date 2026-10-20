# Performance

Measured with `simulator/load_test.py` against a locally running backend (in-memory Redis, SQLite).
Numbers depend on the machine; treat them as a baseline, not a guarantee.

## How to run

```bash
# terminal 1: backend
cd backend && python -m uvicorn app.main:app
# terminal 2
cd backend && python ../simulator/load_test.py --drivers 100 --duration 30 --rides-per-min 60
python ../simulator/load_test.py --drivers 500 --duration 30 --rides-per-min 60
python ../simulator/load_test.py --drivers 1000 --duration 30 --rides-per-min 60
```

The script resets live state first. Database writes happen only for ride lifecycle events (about 9 `trip_events` rows per completed ride) and surge changes, never per GPS ping.

## Results

Machine: _CPU / RAM / OS_

| Drivers | gps_ingest p50/p95 ms | quote p50/p95 ms | ride_request p50/p95 ms | matching (server) p50/p95 ms | websocket lag p50/p95 ms | errors |
|---:|---|---|---|---|---|---|
| 100 | | | | | | |
| 500 | | | | | | |
| 1000 | | | | | | |

## Notes

- The client is a single Python process, so at 1000 drivers (about 333 requests per second) the client itself may be the bottleneck.
- Redis operations are only meaningful with a real Redis (`redis-cli INFO commandstats`); the in-memory fake is not representative.