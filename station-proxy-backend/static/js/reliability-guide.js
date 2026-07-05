// Purpose: Render the reliability-map guide section, keeping its long-form copy out of index.html.

// The content is static trusted markup (no artifact- or user-derived strings),
// so it is safe to inject directly. Every threshold and weight below is taken
// from the surface builder (weather_reconstruction_model/scripts/common/
// reliability_surface.py) and the Paloma v1 grouped-holdout artifacts.

const RELIABILITY_GUIDE_HTML = `
    <h2>How to Read This Map</h2>
    <p class="methodology-intro">
        Everything on this tab is derived from one experiment: the Paloma v1 grouped station
        holdout (739 stations, 416,892 held-out daily observations). The raster spreads that
        station evidence across the basin; the scores below explain exactly how.
    </p>

    <details class="method-card" open>
        <summary>What the raster shows</summary>
        <div class="method-body">
            <p>
                The surface is a 25 km grid (2,793 cells) clipped to the Colorado River Basin
                boundary. Each cell is scored from the holdout stations around it, so the raster
                is an interpolation between real validated stations &mdash; strongest near station
                clusters, weakest in empty terrain.
            </p>
            <ul>
                <li><strong>Layer</strong> (TAVG, TMIN, TMAX) picks which variable's holdout evidence drives the surface.</li>
                <li><strong>Map</strong> picks what the station dots show: the Overall quality tier, a single holdout metric (correlation, MAE, RMSE, bias), or the same metrics for the fully trained production model.</li>
                <li>The raster shading is <strong>relative</strong>: it ranks each cell's expected error against the 739 validated stations, so it shows where in the basin the model generalizes best and worst &mdash; it is not an absolute grade.</li>
                <li>Station dots are <strong>measured results</strong>, not interpolation: each one is a station the model reconstructed while that station was fully held out of training.</li>
            </ul>
            <p>
                "Holdout" metrics are honest generalization evidence. "Fully Trained" metrics are
                the production model scored on data it trained on &mdash; useful as a fit diagnostic,
                never as proof of accuracy.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>How a grid cell is scored</summary>
        <div class="method-body">
            <p>Clicking the raster samples the nearest grid cell. Its numbers are built in four steps:</p>
            <ul>
                <li>
                    <strong>Expected MAE</strong> &mdash; a distance-weighted average of holdout station MAEs
                    within 450 km (weight 1 / distance<sup>1.6</sup>, distances under 8 km capped so one
                    station cannot dominate). Where evidence is thin, the estimate is pulled toward the
                    basin's 75th-percentile MAE &mdash; sparse areas are scored conservatively, not optimistically.
                    Small penalties are added when nearby stations disagree with each other and when the
                    nearest station is more than 120 km away.
                </li>
                <li>
                    <strong>Evidence strength (0&ndash;100)</strong> &mdash; up to 50 points for proximity (fading to
                    zero when the nearest holdout station is 180 km away) plus up to 50 points for density
                    (8 points per station within 50 km, 4 within 100 km, 1.5 within 200 km).
                </li>
                <li>
                    <strong>Generalization percentile (0&ndash;100)</strong> &mdash; where the cell's expected MAE ranks
                    among the 739 validated stations. 50 means "middle of the pack for this model", not
                    "50% correct". Half the basin is below 50 by definition. This rank is what the raster shading shows.
                </li>
                <li>
                    <strong>Expected MAE usefulness (0&ndash;100)</strong> &mdash; an absolute scale anchored to fixed
                    temperatures: 1.5 F scores 95, 2.5 F scores 80, 3.5 F scores 60, 4.5 F scores 40,
                    8 F scores 5.
                </li>
            </ul>
            <p>
                The headline <strong>Model helpfulness</strong> score blends them:
                50% usefulness + 30% generalization percentile + 20% evidence strength, minus a
                penalty of up to 20 points when evidence strength drops below 45.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>How the scoring is calibrated</summary>
        <div class="method-body">
            <p>Every anchor in the scoring traces to the holdout experiment and its baselines:</p>
            <ul>
                <li><strong>1.5 F</strong> is the strict-pass bar a reconstruction must beat (with RMSE &le; 2.0 F and correlation &ge; 0.985) &mdash; only 52 of 739 stations reach it, so scores near 95 are rare by design.</li>
                <li><strong>2.5 F</strong> sits at the holdout median (2.49 F): a typical station for this model scores about 80 on usefulness.</li>
                <li><strong>4.0 F</strong> is the holdout 90th percentile &mdash; the model's weakest decile.</li>
                <li><strong>5.0 F</strong> territory means the model adds little over dumb interpolation: the row-locked IDW baseline averages 4.99 F on the same rows.</li>
            </ul>
            <p>
                <strong>Calibration note:</strong> this inspector previously headlined the generalization
                percentile colored as if it were a grade, so an area with expected MAE 2.63 F &mdash; within
                6% of the model's median and roughly twice as accurate as the IDW baseline &mdash; could show
                a red "44". The headline is now the Model helpfulness blend, which anchors to those fixed
                temperature thresholds; the percentile stays visible as "Generalization percentile" for
                comparing locations within the basin. No model outputs changed &mdash; both values were always
                in the published artifacts.
            </p>
            <p>
                The badge and bars turn teal at 75+, yellow at 65, orange at 50, and red below 50 on the
                helpfulness scale, where the basin-wide median is about 66.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>Station markers and quality tiers</summary>
        <div class="method-body">
            <p>
                In Overall mode, each station dot is tiered by all three holdout metrics together
                &mdash; a station must clear every threshold in a tier to earn it:
            </p>
            <ul>
                <li><strong>Excellent:</strong> correlation &ge; 0.97, MAE &le; 1.25 F, RMSE &le; 2.0 F</li>
                <li><strong>Strong:</strong> correlation &ge; 0.95, MAE &le; 2.0 F, RMSE &le; 3.0 F</li>
                <li><strong>Acceptable:</strong> correlation &ge; 0.90, MAE &le; 2.5 F, RMSE &le; 3.5 F</li>
                <li><strong>Weak:</strong> correlation &ge; 0.80, MAE &le; 4.0 F, RMSE &le; 5.0 F</li>
                <li><strong>Poor:</strong> below the weak thresholds; <strong>Unknown:</strong> insufficient metrics</li>
            </ul>
            <p>
                Click any station dot to open its full holdout record: per-metric results, and daily
                predicted-versus-actual charts from the days it was held out.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>Reading the inspector</summary>
        <div class="method-body">
            <p>After clicking the raster, the Reliability Inspector reports, in order of importance:</p>
            <ul>
                <li><strong>Model helpfulness</strong> (the badge) &mdash; the calibrated blend above. It answers "how much should I trust a reconstruction here?"</li>
                <li><strong>Expected MAE</strong> &mdash; the interpolated daily error estimate in F. Compare it to the anchors: 2.49 F is typical, 1.5 F is excellent, near 5 F is baseline-level.</li>
                <li><strong>Evidence strength</strong> &mdash; how much real validation sits nearby. A confident-looking score with weak evidence is still a guess; the helpfulness blend already discounts it.</li>
                <li><strong>Generalization percentile</strong> &mdash; this location's rank within the basin. Useful for comparing sites, not for judging absolute quality.</li>
                <li><strong>Limiting variable</strong> &mdash; on combined layers, which of TAVG/TMIN/TMAX drags the cell down.</li>
                <li><strong>Nearby holdout stations</strong> &mdash; the actual measured stations behind the estimate, with distance and holdout MAE, plus the nearest notably-good and notably-bad stations for context.</li>
            </ul>
            <p>
                Sources: <code>reliability_surface_&lt;layer&gt;.json</code> artifacts built by
                <code>build_reliability_surfaces.py</code> from the Paloma v1 holdout master
                (score version <code>holdout-mae-spatial-reliability-v1</code>).
            </p>
        </div>
    </details>
`;

export function renderReliabilityGuide() {
    const section = document.getElementById("reliability-guide-section");
    if (!section) {
        return;
    }

    section.innerHTML = RELIABILITY_GUIDE_HTML;
}
