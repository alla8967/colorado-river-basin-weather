// Purpose: Render the Model & Testing tab, keeping its long-form copy out of index.html.

// The content is static trusted markup (no artifact- or user-derived strings),
// so it is safe to inject directly. Every number below is measured from a run
// artifact or manifest; the sources are listed in the final section, and
// weather_reconstruction_model/MODEL_RUNS.md is the source of truth.

const MODEL_TESTING_HTML = `
    <h2>Model &amp; Testing</h2>
    <p class="methodology-intro">
        How the Paloma v1 reconstruction model was built, how it was validated, where it ran,
        and how long the runs took. Every number on this page is measured from a run artifact
        or manifest &mdash; the sources are listed at the bottom.
    </p>

    <div class="station-glance-grid testing-headline">
        <div class="station-glance-card">
            <div class="station-glance-label">Validation Stations</div>
            <div class="station-glance-value">739</div>
            <div class="station-glance-detail">Grouped station holdout &mdash; each station fully excluded from the forest that scored it.</div>
        </div>
        <div class="station-glance-card">
            <div class="station-glance-label">Held-Out Daily Rows</div>
            <div class="station-glance-value">416,892</div>
            <div class="station-glance-detail">Real observed days compared against the model's reconstruction.</div>
        </div>
        <div class="station-glance-card">
            <div class="station-glance-label">Mean Station MAE</div>
            <div class="station-glance-value">2.68 F</div>
            <div class="station-glance-detail">Median 2.49 F across the 739 held-out stations (TAVG).</div>
        </div>
        <div class="station-glance-card">
            <div class="station-glance-label">Validation Compute</div>
            <div class="station-glance-value">~13,400 core-hours</div>
            <div class="station-glance-detail">189 forest fits on 48-core high-memory HPC nodes.</div>
        </div>
    </div>

    <div class="testing-section">
        <h3>The Model</h3>
        <p>
            Paloma v1 reconstructs a target weather station's daily temperatures from surrounding
            stations and terrain. Instead of predicting temperature directly, each random forest
            predicts the <strong>offset from a regional hub baseline</strong>, then adds it back.
            That keeps the trees focused on local deviation rather than relearning the seasonal cycle.
        </p>
        <table class="spec-table">
            <tbody>
                <tr><td>Model family</td><td>Random forest regressor (scikit-learn), one model per variable (TAVG, TMIN, TMAX)</td></tr>
                <tr><td>Prediction design</td><td><code>regional_baseline + predicted_offset</code></td></tr>
                <tr><td>Features</td><td>873 inputs: 5 hub stations, 10 nearest neighbor stations, seasonality, station geometry, and DEM terrain (elevation, slope, aspect, relief)</td></tr>
                <tr><td>Production training set</td><td>2,174,509 daily rows across 761 target stations (TAVG)</td></tr>
                <tr><td>Production hyperparameters</td><td>300 trees, max depth 20, min 5 samples per leaf, fixed random seed</td></tr>
                <tr><td>Exported</td><td>2026-05-27 &mdash; serialized <code>model.joblib</code> with a model manifest and feature schema</td></tr>
            </tbody>
        </table>
    </div>

    <div class="testing-section">
        <h3>How It Was Tested</h3>
        <p>
            <strong>Grouped station holdout.</strong> The 739 validation stations were split into
            189 groups of 2&ndash;5 stations. For each group, a separate forest was trained with every
            station in that group fully excluded, then asked to reconstruct those stations' real
            daily records &mdash; 416,892 held-out rows in total. Because whole stations are held out
            rather than random rows, the score measures reconstructing a station the model has
            never seen, not memorization.
        </p>
        <p>
            Two guardrails keep the metrics honest: baseline comparisons are <strong>row-locked</strong>
            (evaluated on the exact prediction rows, failing loudly if any baseline row is missing),
            and exported prediction CSVs are independently re-scored by a separate C++ validator,
            so the headline numbers do not depend on a single implementation.
        </p>
        <table>
            <thead>
                <tr><th>Holdout Result (TAVG)</th><th>Value</th></tr>
            </thead>
            <tbody>
                <tr><td>Mean station MAE</td><td>2.68 F</td></tr>
                <tr><td>Median station MAE</td><td>2.49 F</td></tr>
                <tr><td>90th percentile station MAE</td><td>4.00 F</td></tr>
                <tr><td>Hardest station MAE</td><td>9.61 F</td></tr>
                <tr><td>Strict passes (MAE &le; 1.5 F, RMSE &le; 2.0 F, correlation &ge; 0.985)</td><td>52 / 739</td></tr>
            </tbody>
        </table>
        <p class="testing-note">
            The strict-pass bar is intentionally hard and stays visible: 52 stations meet it today.
            That frontier is reported, not hidden.
        </p>
    </div>

    <div class="testing-section">
        <h3>Against Simple Baselines</h3>
        <p>
            Same 739 stations, same 416,892 prediction rows, zero missing baseline rows
            (row-locked comparison run 2026-06-11). Lower is better:
        </p>
        <div class="mae-bars" role="img" aria-label="Mean station MAE comparison: Paloma v1 2.68 F, inverse-distance weighting of 5 hubs 4.99 F, nearest hub 5.58 F">
            <div class="mae-bar-row">
                <span class="mae-bar-label">Paloma v1</span>
                <span class="mae-bar-track"><span class="mae-bar-fill model" style="width: 48%"></span></span>
                <span class="mae-bar-value">2.68 F</span>
            </div>
            <div class="mae-bar-row">
                <span class="mae-bar-label">IDW of 5 hubs</span>
                <span class="mae-bar-track"><span class="mae-bar-fill idw" style="width: 89%"></span></span>
                <span class="mae-bar-value">4.99 F</span>
            </div>
            <div class="mae-bar-row">
                <span class="mae-bar-label">Nearest hub</span>
                <span class="mae-bar-track"><span class="mae-bar-fill nearest" style="width: 100%"></span></span>
                <span class="mae-bar-value">5.58 F</span>
            </div>
        </div>
        <ul class="support-list">
            <li>Beats inverse-distance weighting at 588 of 739 stations (80%).</li>
            <li>Beats the nearest hub at 631 of 739 stations (85%).</li>
            <li>Strict passes: model 52, IDW 9, nearest hub 8.</li>
        </ul>
    </div>

    <div class="testing-section">
        <h3>Where It Ran</h3>
        <p>
            All Paloma training and holdout validation ran on <strong>CU Boulder's Alpine
            supercomputer</strong> (CU Research Computing) as Slurm batch jobs on CPU partitions
            &mdash; no GPUs. The project keeps a durable copy in <code>/projects</code> storage and runs
            jobs from <code>/scratch</code>; every job runs an environment and cache-integrity check
            before touching the model, and results sync back to durable storage before being
            retrieved into this repository. The app you are using now runs separately on
            Google Cloud Run.
        </p>
        <table>
            <thead>
                <tr><th>Job</th><th>Alpine Partition</th><th>Resources per Job</th></tr>
            </thead>
            <tbody>
                <tr><td>Grouped holdout training (Slurm job arrays)</td><td>amem (high-memory)</td><td>48 CPU cores &middot; 900 GB RAM &middot; 24 h wall limit</td></tr>
                <tr><td>Production model export</td><td>amem (high-memory)</td><td>48 CPU cores &middot; 900 GB RAM</td></tr>
                <tr><td>Training-table builds and merges</td><td>amilan (general CPU)</td><td>4&ndash;32 CPU cores</td></tr>
            </tbody>
        </table>
    </div>

    <div class="testing-section">
        <h3>How Long the Runs Took</h3>
        <div class="station-glance-grid">
            <div class="station-glance-card">
                <div class="station-glance-label">Holdout Forest Fits</div>
                <div class="station-glance-value">189</div>
                <div class="station-glance-detail">One fit per station group, run May&ndash;June 2026.</div>
            </div>
            <div class="station-glance-card">
                <div class="station-glance-label">Median Fit Time</div>
                <div class="station-glance-value">92 min</div>
                <div class="station-glance-detail">Mean 88 min on a 48-core allocation; ~1.65M training rows per fit.</div>
            </div>
            <div class="station-glance-card">
                <div class="station-glance-label">Fastest / Longest Fit</div>
                <div class="station-glance-value">25 min / 2 h 26 min</div>
                <div class="station-glance-detail">Fit time scales with how much of the table each group leaves behind.</div>
            </div>
            <div class="station-glance-card">
                <div class="station-glance-label">Total Node Time</div>
                <div class="station-glance-value">~278 hours</div>
                <div class="station-glance-detail">~13,400 core-hours, parallelized as Slurm job arrays.</div>
            </div>
        </div>
        <p class="testing-note">
            Timings are the <code>elapsed_seconds</code> values the training script wrote into the
            holdout master artifact &mdash; measured wall time per group fit, not scheduler estimates.
        </p>
    </div>

    <div class="testing-section">
        <h3>Sources</h3>
        <p class="testing-note">Every figure above traces to one of these project artifacts:</p>
        <ul class="support-list provenance-list">
            <li><code>alpine_outputs/paloma/paloma_v1_tavg_station_holdout_master.csv</code> &mdash; per-station holdout metrics and measured fit times</li>
            <li><code>model_runs/paloma_v1/paloma_v1_tavg/model_manifest.json</code> &mdash; production model card (rows, features, hyperparameters)</li>
            <li><code>weather_reconstruction_model/MODEL_RUNS.md</code> &mdash; verified claims and the row-locked baseline comparison</li>
            <li><code>remote_jobs/*.sh</code> &mdash; Slurm job definitions (partitions, cores, memory, wall limits)</li>
        </ul>
    </div>
`;

export function renderModelTesting() {
    const section = document.getElementById("model-testing-section");
    if (!section) {
        return;
    }

    section.innerHTML = MODEL_TESTING_HTML;
}
