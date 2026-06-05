# Station Engine Server

This folder contains the persistent stdin/stdout wrapper around the C++ station
proxy engine.

## Why It Exists

Loading decade-scale station CSVs into the C++ engine is the slow part. The
FastAPI backend starts this server once, waits for it to report `READY`, and then
sends repeated latitude/longitude requests to the already-loaded process.

## File Map

- `station_engine_server.cpp` is the persistent service wrapper.
- `station_engine_server` is the compiled binary and is ignored by git.

Build and run through project-level commands:

```bash
make server
make run-backend
```

