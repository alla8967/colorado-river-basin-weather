# Deploying the Demo to Google Cloud Run

This runbook publishes the Station Proxy app at a permanent public HTTPS URL
with cost-abuse protections layered in. The app-level protections (response
caching, gzip, input clamping, path redaction) are already in the backend;
this document covers the platform side.

**Build-machine requirement:** deploy from a machine that has the full local
data (`NOAA_Inventory_Sort/*_daily_app_ready.csv`,
`weather_reconstruction_model/model_runs/`, `alpine_outputs/predictions/`).
The image bakes that data in — roughly a 340 MB upload. Without the full CSVs
the image still builds but serves the tiny fixture dataset.

## 1. One-Time Account Setup

1. Create or sign in to a Google Cloud account at <https://console.cloud.google.com>.
   New accounts get $300 in trial credit.
2. Create a project (e.g. `crb-weather-demo`) and attach a billing account.
3. Install and authenticate the gcloud CLI:

   ```bash
   brew install google-cloud-sdk
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   gcloud services enable run.googleapis.com cloudbuild.googleapis.com
   ```

## 2. Deploy

From the project root:

```bash
make deploy-cloud-run
```

That runs `gcloud run deploy --source .` (Cloud Build compiles the C++ engine
and assembles the image remotely — no local Docker needed) with the protective
flags baked in:

| Flag | Value | Why |
| --- | --- | --- |
| `--max-instances` | 1 | Hard ceiling on compute cost: floods make the demo slow, not expensive. |
| `--concurrency` | 20 | Bounds in-flight requests per instance. |
| `--timeout` | 60 | Caps how long any request can hold resources; also covers cold-start engine loading. |
| `--memory` / `--cpu` | 2Gi / 1 | Engine holds the NOAA CSVs in memory. |
| `--cpu-boost` | on | Extra CPU during startup so the engine data load finishes quickly. |
| no `--min-instances` | scale to zero | Idle time is free; first visit after idle waits ~30-60 s while the engine loads. |

The first deploy prints the service URL (`https://<service>-<hash>-uc.a.run.app`).
Redeploys reuse the same URL.

Uploading ~340 MB and building takes several minutes the first time.

## 3. Billing Guardrails (do this immediately after the first deploy)

Budget alerts warn you; they do **not** stop spending by themselves.

```bash
gcloud billing budgets create \
  --billing-account=$(gcloud billing projects describe $(gcloud config get-value project) --format="value(billingAccountName)" | sed 's|billingAccounts/||') \
  --display-name="crb-weather-demo budget" \
  --budget-amount=25USD \
  --threshold-rule=percent=0.2 \
  --threshold-rule=percent=0.4 \
  --threshold-rule=percent=1.0
```

That emails you at $5, $10, and $25 of monthly spend. Expected normal spend
with portfolio-level traffic is near zero (Cloud Run free tier covers it).

If an alert fires and you want the service offline immediately:

```bash
gcloud run services delete crb-weather-demo --region us-central1
```

Optional full kill switch (spend threshold auto-disables the service): wire the
budget to a Pub/Sub topic and a small Cloud Function that calls the command
above. Google documents the pattern as "Automated cost control responses" —
worth adding if the demo will be unattended for long stretches.

## 4. Verify the Deployment

```bash
URL=$(gcloud run services describe crb-weather-demo --region us-central1 --format='value(status.url)')
curl -s "$URL/test" | python3 -m json.tool | head
curl -s -o /dev/null -w "%{http_code}\n" "$URL/analyze-location?lat=999&lon=0"   # expect 422
curl -s -H "Accept-Encoding: gzip" -o /dev/null -w "%{size_download} bytes\n" \
  "$URL/model-runs/reliability/surface?layer=tavg"                               # expect ~533 KB, not ~9 MB
```

Then open the URL in a browser, click a preset location, and check the
Reliability Map tab.

## 5. Publish the Link

- Add the URL to the README intro as a "Live demo" link.
- Optional hardening upgrade: put Cloudflare's free tier in front via a custom
  domain. It caches the artifact responses at the edge (the backend already
  sends `Cache-Control` headers) and rate-limits abusive IPs before they reach
  Cloud Run.

## Updating and Tearing Down

- Redeploy after changes: `make deploy-cloud-run` (same URL).
- Pause/remove entirely: `gcloud run services delete crb-weather-demo --region us-central1`.
  The URL is recreated identically on the next deploy only if the service name,
  project, and region match.
