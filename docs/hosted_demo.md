# Hosted Demo Notes

The project has a hosted demo for portfolio and review use. The public repo
documents the app, model evidence, and safety posture, but it intentionally does
not publish the operator runbook, cloud resource names, deploy commands, billing
controls, or teardown commands.

The hosted service is treated as a public, read-only demo:

- no user accounts or cookies;
- no write API routes;
- bounded coordinate inputs;
- path-redacted JSON responses;
- explicit security headers;
- production CORS scoped to known demo origins;
- generated NOAA/model artifacts kept out of source commits.

Operational details live outside the public repository. If the hosted demo is
ever moved to a custom domain, publish only the user-facing link and keep the
cloud control plane details private.
