# Local Smoke Tests

This folder contains small tests that let reviewers validate the app and C++
engine without full NOAA or model-run artifacts.

## File Map

- `test_app_shell.py` verifies the FastAPI app shell and static asset
  references.
- `test_reliability_backend.py` builds temporary reliability fixtures and checks
  backend reliability routes.
- `test_engine_fixture.py` compiles the C++ engine against tiny fixture CSVs and
  checks station matching behavior.
- `fixtures/` contains the small target and hub station CSVs used by the engine
  fixture test.

Run the main reviewer validation set from the project root:

```bash
make check
```

