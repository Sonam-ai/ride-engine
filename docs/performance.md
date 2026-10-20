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

# Performance Test Results

## Test Environment

- CPU: 13th Gen Intel(R) Core(TM) i5-13500H — record actual CPU model
- RAM: 15.64 — record actual installed RAM
- Test duration: 30 seconds per run
- GPS update interval: 3 seconds
- Target ride generation rate: approximately 60 rides/minute
- Backend: Local development environment

## Test 1: 100 Drivers

| Metric | Samples | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Errors |
|---|---:|---:|---:|---:|---:|---:|
| gps_ingest | 1000 | 332.2 | 766.0 | 932.2 | 1016.1 | 0 |
| quote | 19 | 7.0 | 408.6 | 408.6 | 408.6 | 0 |
| ride_request | 19 | 21.5 | 420.4 | 420.4 | 420.4 | 0 |
| matching_server | 5 | 76.0 | 108.7 | 108.7 | 108.7 | 0 |
| matching_wall | 5 | 114.8 | 165.4 | 165.4 | 165.4 | 0 |
| websocket_lag | 1316 | 6.9 | 18.7 | 25.7 | 125.5 | 0 |

**Additional results**

- GPS rounds completed: 10 (target: 10)
- Assigned in matching batches: 6
- Completed trips: 1
- Pending: 6
- Average surge: 1.0x

## Test 2: 500 Drivers

| Metric | Samples | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | Errors |
|---|---:|---:|---:|---:|---:|---:|
| gps_ingest | 4000 | 1658.9 | 3825.0 | 6137.2 | 7035.7 | 0 |
| quote | 15 | 323.5 | 3228.4 | 3228.4 | 3228.4 | 0 |
| ride_request | 15 | 171.2 | 1834.7 | 1834.7 | 1834.7 | 0 |
| matching_server | 5 | 77.0 | 159.5 | 159.5 | 159.5 | 0 |
| matching_wall | 5 | 769.2 | 2396.0 | 2396.0 | 2396.0 | 0 |
| websocket_lag | 4294 | 10.5 | 27.6 | 70.2 | 797.7 | 0 |

**Additional results**

- GPS rounds completed: 8 (target: 10)
- Assigned in matching batches: 8
- Completed trips: 0
- Pending: 1
- Average surge: 1.0x

## Observations

- Both tests reported zero errors across the displayed metrics.
- Increasing the driver count from 100 to 500 increased GPS ingestion p50 latency from 332.2 ms to 1658.9 ms.
- GPS ingestion p95 latency increased from 766.0 ms to 3825.0 ms.
- Quote p95 latency increased from 408.6 ms to 3228.4 ms.
- Ride request p95 latency increased from 420.4 ms to 1834.7 ms.
- Matching wall-clock p95 latency increased from 165.4 ms to 2396.0 ms.
- WebSocket lag remained comparatively lower than GPS ingestion latency, although its maximum increased from 125.5 ms to 797.7 ms.
- The 100-driver test completed all 10 target GPS rounds. The 500-driver test completed 8 of 10 target rounds within the test duration.
- No trips were completed in the 500-driver test, compared with one completed trip in the 100-driver test.

The 500-driver results show substantial latency increases and fewer completed GPS rounds. Further profiling and testing are needed to identify bottlenecks and determine the system's sustainable capacity.

## Notes

- The client is a single Python process, so at 1000 drivers (about 333 requests per second) the client itself may be the bottleneck.
- Redis operations are only meaningful with a real Redis (`redis-cli INFO commandstats`); the in-memory fake is not representative.