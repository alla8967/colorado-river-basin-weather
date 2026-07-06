// Purpose: Render the reliability-map guide section, keeping its long-form copy out of index.html.

// The content is static trusted markup (no artifact- or user-derived strings),
// so it is safe to inject directly. Every threshold, weight, and chart bar
// below is taken from the surface builder (weather_reconstruction_model/
// scripts/common/reliability_surface.py) and computed from the Paloma v1
// holdout master artifact (739 stations).

// Histogram of the 739 holdout station MAEs (0.5 F bins) with the four
// calibration anchors marked.
const MAE_DISTRIBUTION_SVG = `<svg viewBox="0 0 760 320" role="img" aria-label="Distribution of holdout station MAE with calibration anchors" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><line x1="52" y1="274.0" x2="742" y2="274.0" stroke="#e2e8f0"/><text x="44" y="278.0" text-anchor="end" fill="#64748b" font-size="12">0</text><line x1="52" y1="204.0" x2="742" y2="204.0" stroke="#e2e8f0"/><text x="44" y="208.0" text-anchor="end" fill="#64748b" font-size="12">60</text><line x1="52" y1="134.0" x2="742" y2="134.0" stroke="#e2e8f0"/><text x="44" y="138.0" text-anchor="end" fill="#64748b" font-size="12">120</text><line x1="52" y1="64.0" x2="742" y2="64.0" stroke="#e2e8f0"/><text x="44" y="68.0" text-anchor="end" fill="#64748b" font-size="12">180</text><rect x="88.0" y="272.8" width="31.5" height="1.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="122.5" y="211.0" width="31.5" height="63.0" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="157.0" y="86.2" width="31.5" height="187.8" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="191.5" y="83.8" width="31.5" height="190.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="226.0" y="122.3" width="31.5" height="151.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="260.5" y="166.7" width="31.5" height="107.3" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="295.0" y="199.3" width="31.5" height="74.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="329.5" y="243.7" width="31.5" height="30.3" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="364.0" y="244.8" width="31.5" height="29.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="398.5" y="267.0" width="31.5" height="7.0" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="433.0" y="265.8" width="31.5" height="8.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="467.5" y="269.3" width="31.5" height="4.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="536.5" y="269.3" width="31.5" height="4.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="640.0" y="272.8" width="31.5" height="1.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="709.0" y="272.8" width="31.5" height="1.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="52.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">0</text><text x="190.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">2</text><text x="328.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">4</text><text x="466.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">6</text><text x="604.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">8</text><text x="742.0" y="294" text-anchor="middle" fill="#64748b" font-size="12">10</text><line x1="155.5" y1="46" x2="155.5" y2="274" stroke="#16a34a" stroke-width="2" stroke-dasharray="5 4"/><text x="155.5" y="14" text-anchor="middle" fill="#16a34a" font-size="13" font-weight="bold">Strict 1.5 F</text><line x1="223.8" y1="46" x2="223.8" y2="274" stroke="#2563eb" stroke-width="2" stroke-dasharray="5 4"/><text x="223.8" y="34" text-anchor="middle" fill="#2563eb" font-size="13" font-weight="bold">Median 2.49 F</text><line x1="328.0" y1="46" x2="328.0" y2="274" stroke="#ca8a04" stroke-width="2" stroke-dasharray="5 4"/><text x="328.0" y="14" text-anchor="middle" fill="#ca8a04" font-size="13" font-weight="bold">p90 4.0 F</text><line x1="396.3" y1="46" x2="396.3" y2="274" stroke="#dc2626" stroke-width="2" stroke-dasharray="5 4"/><text x="396.3" y="34" text-anchor="middle" fill="#dc2626" font-size="13" font-weight="bold">IDW 4.99 F</text><text x="397" y="312" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">Holdout station MAE (F)</text><text x="16" y="169" text-anchor="middle" transform="rotate(-90 16 169)" fill="#475569" font-size="13" font-weight="bold">Stations</text></svg>`;

// Histogram of the 739 holdout station correlations (0.01 bins) with the
// quality-tier correlation bars marked.
const CORRELATION_DISTRIBUTION_SVG = `<svg viewBox="0 0 760 300" role="img" aria-label="Distribution of holdout station correlation with quality-tier bars" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><line x1="52" y1="254.0" x2="742" y2="254.0" stroke="#e2e8f0"/><text x="44" y="258.0" text-anchor="end" fill="#64748b" font-size="12">0</text><line x1="52" y1="188.0" x2="742" y2="188.0" stroke="#e2e8f0"/><text x="44" y="192.0" text-anchor="end" fill="#64748b" font-size="12">100</text><line x1="52" y1="122.0" x2="742" y2="122.0" stroke="#e2e8f0"/><text x="44" y="126.0" text-anchor="end" fill="#64748b" font-size="12">200</text><line x1="52" y1="56.0" x2="742" y2="56.0" stroke="#e2e8f0"/><text x="44" y="60.0" text-anchor="end" fill="#64748b" font-size="12">300</text><rect x="55.0" y="250.0" width="47.1" height="4.0" fill="#fecaca" stroke="#f87171" rx="2"/><text x="78.5" y="245.0" text-anchor="middle" fill="#64748b" font-size="11">6</text><text x="78.5" y="274" text-anchor="middle" fill="#64748b" font-size="12">&lt;0.88</text><text x="131.6" y="274" text-anchor="middle" fill="#64748b" font-size="12">0.88</text><rect x="161.2" y="253.3" width="47.1" height="0.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="184.7" y="248.3" text-anchor="middle" fill="#64748b" font-size="11">1</text><rect x="214.2" y="253.3" width="47.1" height="0.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="237.8" y="248.3" text-anchor="middle" fill="#64748b" font-size="11">1</text><text x="237.8" y="274" text-anchor="middle" fill="#64748b" font-size="12">0.90</text><rect x="267.3" y="252.7" width="47.1" height="1.3" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="290.8" y="247.7" text-anchor="middle" fill="#64748b" font-size="11">2</text><rect x="320.4" y="252.7" width="47.1" height="1.3" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="343.9" y="247.7" text-anchor="middle" fill="#64748b" font-size="11">2</text><text x="343.9" y="274" text-anchor="middle" fill="#64748b" font-size="12">0.92</text><rect x="373.5" y="250.0" width="47.1" height="4.0" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="397.0" y="245.0" text-anchor="middle" fill="#64748b" font-size="11">6</text><rect x="426.5" y="250.0" width="47.1" height="4.0" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="450.1" y="245.0" text-anchor="middle" fill="#64748b" font-size="11">6</text><text x="450.1" y="274" text-anchor="middle" fill="#64748b" font-size="12">0.94</text><rect x="479.6" y="242.8" width="47.1" height="11.2" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="503.2" y="237.8" text-anchor="middle" fill="#64748b" font-size="11">17</text><rect x="532.7" y="216.4" width="47.1" height="37.6" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="556.2" y="274" text-anchor="middle" fill="#64748b" font-size="12">0.96</text><rect x="585.8" y="195.3" width="47.1" height="58.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><rect x="638.8" y="82.4" width="47.1" height="171.6" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><text x="662.4" y="274" text-anchor="middle" fill="#64748b" font-size="12">0.98</text><rect x="691.9" y="61.3" width="47.1" height="192.7" fill="#bfdbfe" stroke="#60a5fa" rx="2"/><line x1="211.2" y1="40" x2="211.2" y2="254" stroke="#ca8a04" stroke-width="2" stroke-dasharray="5 4"/><text x="211.2" y="14" text-anchor="middle" fill="#ca8a04" font-size="13" font-weight="bold">Acceptable 0.90</text><line x1="476.6" y1="40" x2="476.6" y2="254" stroke="#14b8a6" stroke-width="2" stroke-dasharray="5 4"/><text x="476.6" y="32" text-anchor="middle" fill="#14b8a6" font-size="13" font-weight="bold">Strong 0.95</text><line x1="582.8" y1="40" x2="582.8" y2="254" stroke="#16a34a" stroke-width="2" stroke-dasharray="5 4"/><text x="582.8" y="14" text-anchor="middle" fill="#16a34a" font-size="13" font-weight="bold">Excellent 0.97</text><text x="397" y="292" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">Holdout daily correlation (r)</text><text x="16" y="155" text-anchor="middle" transform="rotate(-90 16 155)" fill="#475569" font-size="13" font-weight="bold">Stations</text></svg>`;

// The anchored usefulness curve from expected_mae_usefulness_score().
const USEFULNESS_CURVE_SVG = `<svg viewBox="0 0 760 300" role="img" aria-label="Expected MAE usefulness curve with anchor points" xmlns="http://www.w3.org/2000/svg" font-family="Arial, Helvetica, sans-serif"><line x1="52" y1="254.0" x2="742" y2="254.0" stroke="#e2e8f0"/><text x="44" y="258.0" text-anchor="end" fill="#64748b" font-size="12">0</text><line x1="52" y1="199.0" x2="742" y2="199.0" stroke="#e2e8f0"/><text x="44" y="203.0" text-anchor="end" fill="#64748b" font-size="12">25</text><line x1="52" y1="144.0" x2="742" y2="144.0" stroke="#e2e8f0"/><text x="44" y="148.0" text-anchor="end" fill="#64748b" font-size="12">50</text><line x1="52" y1="89.0" x2="742" y2="89.0" stroke="#e2e8f0"/><text x="44" y="93.0" text-anchor="end" fill="#64748b" font-size="12">75</text><line x1="52" y1="34.0" x2="742" y2="34.0" stroke="#e2e8f0"/><text x="44" y="38.0" text-anchor="end" fill="#64748b" font-size="12">100</text><text x="52.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">0</text><text x="224.5" y="274" text-anchor="middle" fill="#64748b" font-size="12">2</text><text x="397.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">4</text><text x="569.5" y="274" text-anchor="middle" fill="#64748b" font-size="12">6</text><text x="742.0" y="274" text-anchor="middle" fill="#64748b" font-size="12">8</text><line x1="482.4" y1="34" x2="482.4" y2="254" stroke="#dc2626" stroke-width="2" stroke-dasharray="5 4"/><text x="488.4" y="48" fill="#dc2626" font-size="13" font-weight="bold">IDW baseline 4.99 F</text><path d="M52.0,34.0 L181.4,45.0 L267.6,78.0 L353.9,122.0 L440.1,166.0 L569.5,210.0 L742.0,243.0" fill="none" stroke="#2563eb" stroke-width="3" stroke-linejoin="round"/><circle cx="52.0" cy="34.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><circle cx="181.4" cy="45.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><text x="191.4" y="49.0" fill="#475569" font-size="13" font-weight="bold">Strict bar: 95</text><circle cx="267.6" cy="78.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><text x="277.6" y="82.0" fill="#475569" font-size="13" font-weight="bold">Median: 80</text><circle cx="353.9" cy="122.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><circle cx="440.1" cy="166.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><text x="450.1" y="170.0" fill="#475569" font-size="13" font-weight="bold">40</text><circle cx="569.5" cy="210.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><circle cx="742.0" cy="243.0" r="5" fill="#2563eb" stroke="#ffffff" stroke-width="2"/><text x="397" y="292" text-anchor="middle" fill="#475569" font-size="13" font-weight="bold">Expected MAE (F)</text><text x="16" y="144" text-anchor="middle" transform="rotate(-90 16 144)" fill="#475569" font-size="13" font-weight="bold">Usefulness score</text></svg>`;

const RELIABILITY_GUIDE_HTML = `
    <h2>How to Read This Map</h2>
    <p class="methodology-intro">
        Everything on this tab comes from one experiment: the Paloma v1 grouped station holdout
        (739 stations, 416,892 held-out station days). If you take away one number, make it
        this: a typical station reconstructs to within about <strong>2.5 F per day</strong>. The
        cards below explain the raster, every score in the inspector, and why the scoring is
        calibrated the way it is.
    </p>

    <details class="method-card" open>
        <summary>What the raster shows</summary>
        <div class="method-body">
            <p>
                The surface is a 25 km grid (2,793 cells) clipped to the Colorado River Basin
                boundary. Each cell is scored from the holdout stations around it, so the raster is
                an interpolation between real validated stations: strongest near station
                clusters, weakest in empty terrain.
            </p>
            <ul>
                <li><strong>Layer</strong> (TAVG, TMIN, TMAX) picks which variable's holdout evidence drives the surface.</li>
                <li><strong>Map</strong> picks what the station dots show: the Overall quality tier, a single holdout metric (correlation, MAE, RMSE, bias), or the same metrics for the fully trained production model.</li>
                <li>The raster shading is <strong>relative</strong>: it ranks each cell against the 739 validated stations, showing where in the basin the model generalizes best and worst. Treat it as a ranking rather than a grade.</li>
                <li>Station dots are <strong>measured results</strong> rather than interpolation: each one is a station the model reconstructed while that station was fully held out of training.</li>
            </ul>
            <p>
                "Holdout" metrics are honest generalization evidence. "Fully Trained" metrics come
                from the production model scored on data it trained on, so they help diagnose fit
                but cannot prove accuracy.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>How a grid cell is scored</summary>
        <div class="method-body">
            <p>Click any shaded cell and the inspector breaks its score into four ingredients:</p>
            <ul>
                <li><strong>Expected MAE:</strong> a distance-weighted average of holdout station MAEs within 450 km (weight 1 / distance<sup>1.6</sup>). Thin evidence pulls the estimate toward the basin's 75th-percentile MAE, so sparse areas get conservative scores instead of optimistic ones. Small penalties apply when nearby stations disagree or the nearest one is over 120 km away.</li>
                <li><strong>Evidence strength (0&ndash;100):</strong> up to 50 points for proximity (fading to zero at 180 km) plus up to 50 for density (8 points per station within 50 km, 4 within 100 km, 1.5 within 200 km).</li>
                <li><strong>Generalization percentile (0&ndash;100):</strong> where the cell's expected MAE ranks among the 739 validated stations. A 50 means the middle of the pack for this model, and half the basin sits below 50 by definition. This rank is what the raster shading shows.</li>
                <li><strong>Expected MAE usefulness (0&ndash;100):</strong> an absolute scale that only cares about the temperature error itself:</li>
            </ul>
            <figure class="guide-figure">
                ${USEFULNESS_CURVE_SVG}
                <figcaption>
                    The usefulness curve is pinned to meaningful temperatures rather than the basin
                    average: hitting the strict validation bar (1.5 F) scores 95, matching a typical
                    station (2.5 F) scores 80, and by the time expected error approaches the dumb-baseline
                    zone near 5 F the score has fallen to about 40.
                </figcaption>
            </figure>
            <p>The headline <strong>Model helpfulness</strong> blends the three scores:</p>
            <figure class="score-weight-graphic">
                <div class="stacked-weight-bar" role="img" aria-label="Model helpfulness weights: 50% expected MAE usefulness, 30% generalization percentile, 20% evidence strength">
                    <span class="weight-segment" style="width: 50%; background: #2563eb;"></span>
                    <span class="weight-segment" style="width: 30%; background: #0891b2;"></span>
                    <span class="weight-segment" style="width: 20%; background: #16a34a;"></span>
                </div>
                <div class="weight-legend">
                    <span class="weight-legend-item"><span class="weight-swatch" style="background: #2563eb;"></span>Expected MAE usefulness<span>50%</span></span>
                    <span class="weight-legend-item"><span class="weight-swatch" style="background: #0891b2;"></span>Generalization percentile<span>30%</span></span>
                    <span class="weight-legend-item"><span class="weight-swatch" style="background: #16a34a;"></span>Evidence strength<span>20%</span></span>
                </div>
            </figure>
            <p>
                One guardrail sits on top: when evidence strength drops below 45, up to 20 points
                are subtracted. A confident-sounding estimate with little real validation nearby
                gets marked down for it.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>Why the scoring is calibrated this way</summary>
        <div class="method-body">
            <p>
                Every anchor traces back to this distribution, the actual holdout MAE of all
                739 validated stations:
            </p>
            <figure class="guide-figure">
                ${MAE_DISTRIBUTION_SVG}
                <figcaption>
                    Only 7% of stations beat the strict 1.5 F bar, half beat the 2.49 F median, 90%
                    stay under 4.0 F, and nearly all (97%) beat the 4.99 F that plain inverse-distance
                    interpolation averages on the exact same rows. The usefulness scale pins its
                    scores to these lines: 95 at the strict bar, 80 at the median, and roughly 40 as
                    expected error approaches the do-nothing baseline.
                </figcaption>
            </figure>
            <p>
                <strong>What we recalibrated.</strong> The inspector used to headline the
                generalization percentile colored as if it were a grade. Since half the basin ranks
                below 50 by definition, typical areas looked like failures. A cell with expected
                MAE 2.63 F (within 6% of the median above, and roughly twice as accurate as the IDW
                baseline) showed a red 44. The headline is now the Model helpfulness blend, which is
                pinned to the fixed temperature anchors in the chart; the percentile stays visible
                for comparing locations within the basin. No model outputs changed; both values
                were always in the published artifacts.
            </p>
            <p>The badge and score bars read on the helpfulness scale (basin-wide median is about 66):</p>
            <div class="band-chips" aria-label="Badge color bands">
                <span class="band-chip band-high">75+ strong</span>
                <span class="band-chip band-moderate">65&ndash;74 typical</span>
                <span class="band-chip band-low">50&ndash;64 below par</span>
                <span class="band-chip band-very-low">&lt;50 weak or thin evidence</span>
            </div>
        </div>
    </details>

    <details class="method-card">
        <summary>Station markers and quality tiers</summary>
        <div class="method-body">
            <p>
                In Overall mode, each station dot is tiered by all three holdout metrics together.
                A station must clear every threshold in a tier to earn it:
            </p>
            <ul>
                <li><span class="legend-dot quality-excellent"></span> <strong>Excellent:</strong> correlation &ge; 0.97, MAE &le; 1.25 F, RMSE &le; 2.0 F</li>
                <li><span class="legend-dot quality-strong"></span> <strong>Strong:</strong> correlation &ge; 0.95, MAE &le; 2.0 F, RMSE &le; 3.0 F</li>
                <li><span class="legend-dot quality-acceptable"></span> <strong>Acceptable:</strong> correlation &ge; 0.90, MAE &le; 2.5 F, RMSE &le; 3.5 F</li>
                <li><span class="legend-dot quality-weak"></span> <strong>Weak:</strong> correlation &ge; 0.80, MAE &le; 4.0 F, RMSE &le; 5.0 F</li>
                <li><span class="legend-dot quality-poor"></span> <strong>Poor:</strong> below the weak thresholds; <span class="legend-dot quality-unknown"></span> <strong>Unknown:</strong> insufficient metrics</li>
            </ul>
            <p>The correlation bars look strict until you see how correlation actually distributes:</p>
            <figure class="guide-figure">
                ${CORRELATION_DISTRIBUTION_SVG}
                <figcaption>
                    Daily temperatures follow the seasonal cycle, so correlation runs naturally
                    high: 87% of stations clear the Excellent bar of 0.97 and 97% clear 0.95.
                    Correlation mostly flags broken records (six stations sit below 0.88, one with a
                    negative correlation); the real grading work is done by MAE and RMSE.
                </figcaption>
            </figure>
            <p>
                Click any station dot to open its full holdout record, including daily
                predicted-versus-actual charts from the days it was held out.
            </p>
        </div>
    </details>

    <details class="method-card">
        <summary>Reading the inspector</summary>
        <div class="method-body">
            <p>After clicking the raster, the Reliability Inspector reports, in order of importance:</p>
            <ul>
                <li><strong>Model helpfulness</strong> (the badge): the calibrated blend above. It answers "how much should I trust a reconstruction here?"</li>
                <li><strong>Expected MAE:</strong> the interpolated daily error estimate in F. Compare it to the anchors: 2.49 F is typical, 1.5 F is excellent, near 5 F is baseline-level.</li>
                <li><strong>Evidence strength:</strong> how much real validation sits nearby. A confident-looking score with weak evidence is still a guess; the helpfulness blend already discounts it.</li>
                <li><strong>Generalization percentile:</strong> this location's rank within the basin. Useful for comparing sites rather than judging absolute quality.</li>
                <li><strong>Limiting variable:</strong> on combined layers, which of TAVG/TMIN/TMAX drags the cell down.</li>
                <li><strong>Nearby holdout stations:</strong> the actual measured stations behind the estimate, with distance and holdout MAE, plus the nearest notably-good and notably-bad stations for context.</li>
            </ul>
            <p>
                Sources: <code>reliability_surface_&lt;layer&gt;.json</code> artifacts built by
                <code>build_reliability_surfaces.py</code> from the Paloma v1 holdout master
                (score version <code>holdout-mae-spatial-reliability-v1</code>); distribution charts
                computed from the same 739-station artifact.
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
