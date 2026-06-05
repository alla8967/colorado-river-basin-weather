# Shared Script Helpers

This package contains reusable helpers for the reconstruction scripts.

## What Belongs Here

Use `common/` for behavior that is not specific to one pipeline stage:

- CSV, JSON, number, and HTML-report helpers,
- geographic distance and validation metrics,
- weather-cache access,
- model-run artifact loading and manifest helpers,
- confidence-support scoring and input loading,
- pairwise station skill calculations,
- reliability-surface payload builders.

If two command-line scripts need the same utility, it usually belongs here
before it gets copied.

