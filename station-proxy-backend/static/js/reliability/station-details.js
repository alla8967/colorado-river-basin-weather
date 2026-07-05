// Purpose: Render the reliability detail panels: station detail, grid-cell sample, and map-mode overviews.

import { elements } from "../state.js";
import { clampPercent, escapeHtml, formatNumber } from "../formatters.js";
import {
    LAYER_LABELS,
    activeReliabilityMapMode,
    finalModelMetricConfig,
    holdoutErrorMetricConfig,
    isFinalModelMetricMode,
    isHoldoutErrorMetricMode
} from "./config.js?v=tabs-v1";
import {
    classifyDailyTemperatureReconstructionQuality,
    mean,
    median,
    numericStationValues,
    reliabilityColor
} from "./metrics.js?v=tabs-v1";
import {
    renderPredictionComparisonChart,
    stationPredictionSeries
} from "./prediction-charts.js?v=tabs-v1";

function renderScoreBar(label, value) {
    const numericValue = Number(value);
    const safeValue = Number.isNaN(numericValue) ? 0 : numericValue;

    return `
        <div class="score-item">
            <div class="score-label">${escapeHtml(label)}</div>
            <div class="score-bar">
                <div class="score-fill" style="width: ${clampPercent(safeValue)}%; background: ${reliabilityColor(safeValue)};"></div>
            </div>
            <div class="score-value">${formatNumber(safeValue, 1)}</div>
        </div>
    `;
}

function renderStationList(stations) {
    if (!stations || !stations.length) {
        return `<li>No nearby holdout stations returned.</li>`;
    }

    return stations.slice(0, 5).map(station => `
        <li>
            <strong>${escapeHtml(station.stationId)}</strong>
            ${formatNumber(station.distanceKm, 1)} km,
            MAE ${formatNumber(station.observedMaeF, 2)} F
        </li>
    `).join("");
}

function metricOrUnavailable(label, value, suffix = "", digits = 2) {
    return `
        <div class="metric">
            <div class="metric-label">${escapeHtml(label)}</div>
            <div class="metric-value">${formatNumber(value, digits)}${formatNumber(value, digits) === "N/A" ? "" : suffix}</div>
        </div>
    `;
}

function textMetric(label, value) {
    return `
        <div class="metric">
            <div class="metric-label">${escapeHtml(label)}</div>
            <div class="metric-value">${escapeHtml(value || "N/A")}</div>
        </div>
    `;
}

function booleanLabel(value) {
    if (value === true) {
        return "Pass";
    }

    if (value === false) {
        return "No pass";
    }

    return "N/A";
}

function renderQualitySummary(quality) {
    return `
        <div class="quality-summary quality-${escapeHtml(quality.id)}">
            <strong>${escapeHtml(quality.label)} daily reconstruction quality</strong>
            <span>${escapeHtml(quality.description)}</span>
        </div>
    `;
}

function fullyTrainedMetricStatusMessage(status) {
    if (status === "missing_final_model_station_vs_observed_artifact") {
        return "No final-model station-vs-observed metrics artifact is available for this station yet.";
    }

    if (status === "available") {
        return "Final-model station-vs-observed metrics are available.";
    }

    return "Final-model station-vs-observed metrics are unavailable.";
}

function evaluationModeLabel(mode) {
    if (mode === "final_model_in_sample_fit") {
        return "Final model in-sample fit";
    }

    return mode || "N/A";
}

function yearRangeLabel(startYear, endYear) {
    if (startYear && endYear) {
        return `${startYear}-${endYear}`;
    }

    if (startYear) {
        return `${startYear}-present`;
    }

    if (endYear) {
        return `through ${endYear}`;
    }

    return "";
}

function dateRangeLabel(startDate, endDate) {
    if (startDate && endDate) {
        return `${startDate} to ${endDate}`;
    }

    return "";
}

function coordinatesLabel(station) {
    const latitude = formatNumber(station && station.latitude, 5);
    const longitude = formatNumber(station && station.longitude, 5);
    if (latitude === "N/A" || longitude === "N/A") {
        return "";
    }

    return `${latitude}, ${longitude}`;
}

function stationRoleLabel(profile) {
    const roles = [];
    if (profile && profile.isTargetCandidate) {
        roles.push("Target candidate");
    }
    if (profile && profile.isHubCandidate) {
        roles.push("Hub candidate");
    }

    return roles.length ? roles.join(" + ") : "Reliability station";
}

function yesNoLabel(value) {
    if (value === true) {
        return "Yes";
    }

    if (value === false) {
        return "No";
    }

    return "N/A";
}

function biasInterpretation(value) {
    const numericValue = Number(value);
    if (Number.isNaN(numericValue)) {
        return "Bias unavailable.";
    }

    if (numericValue <= -1) {
        return "Negative bias: predictions ran warm.";
    }

    if (numericValue >= 1) {
        return "Positive bias: predictions ran cool.";
    }

    return "Near zero: little average bias.";
}

function renderStationGlanceCard(label, value, detail, tone = "") {
    return `
        <div class="station-glance-card ${tone ? `station-glance-${escapeHtml(tone)}` : ""}">
            <div class="station-glance-label">${escapeHtml(label)}</div>
            <div class="station-glance-value">${escapeHtml(value || "N/A")}</div>
            <div class="station-glance-detail">${escapeHtml(detail || "")}</div>
        </div>
    `;
}

function renderStationAtAGlance(data, quality, percentile) {
    const finalMetrics = data.fullyTrainedModelVsObserved;
    const holdout = data.stationHoldoutTest || {};
    const holdoutRun = data.holdoutRun;
    const finalValue = finalMetrics
        ? `r ${formatNumber(finalMetrics.correlation, 3)}`
        : "N/A";
    const finalDetail = finalMetrics
        ? `MAE ${formatNumber(finalMetrics.maeF, 2)} F, RMSE ${formatNumber(finalMetrics.rmseF, 2)} F`
        : "Final model fit metrics unavailable.";
    const holdoutDetail = `MAE ${formatNumber(holdout.maeF, 2)} F, r ${formatNumber(holdout.correlation, 3)}`;
    const biasValue = holdoutRun && holdoutRun.biasF !== null && holdoutRun.biasF !== undefined
        ? `${formatNumber(holdoutRun.biasF, 2)} F`
        : "N/A";
    const reliabilityDetail = percentile === null
        ? "MAE percentile unavailable."
        : `MAE percentile ${formatNumber(percentile, 1)}%`;

    return `
        <section class="support-section station-overview-section">
            <h3>At a Glance</h3>
            <div class="station-glance-grid">
                ${renderStationGlanceCard("Final model fit", finalValue, finalDetail)}
                ${renderStationGlanceCard("Holdout reconstruction", quality.label, holdoutDetail, quality.id)}
                ${renderStationGlanceCard("Holdout bias", biasValue, biasInterpretation(holdoutRun && holdoutRun.biasF))}
                ${renderStationGlanceCard(
                    "Reliability surface",
                    formatNumber(holdout.observedReliability, 1),
                    reliabilityDetail
                )}
            </div>
        </section>
    `;
}

function renderStationIdentitySection(station, sourceVariable, layerLabel) {
    const profile = station.profile || null;
    const usableRange = profile
        ? yearRangeLabel(profile.usableTempStartYear, profile.usableTempEndYear)
        : "";
    const tmaxRange = profile ? yearRangeLabel(profile.tmaxStartYear, profile.tmaxEndYear) : "";
    const tminRange = profile ? yearRangeLabel(profile.tminStartYear, profile.tminEndYear) : "";

    return `
        <section class="support-section station-identity-section">
            <h3>Station Identity</h3>
            <div class="metric-grid station-identity-grid">
                ${textMetric("Name", station.stationName || station.stationId)}
                ${textMetric("Station ID", station.stationId)}
                ${textMetric("Source variable", sourceVariable)}
                ${textMetric("Surface layer", layerLabel)}
                ${metricOrUnavailable("Latitude", station.latitude, "", 5)}
                ${metricOrUnavailable("Longitude", station.longitude, "", 5)}
            </div>
            ${profile ? `
                <div class="station-metric-group">
                    <h4>Inventory & Record Coverage</h4>
                    <div class="metric-grid">
                        ${textMetric("Data role", stationRoleLabel(profile))}
                        ${textMetric("Usable temperature years", usableRange)}
                        ${metricOrUnavailable("Usable year count", profile.usableTempYears, "", 0)}
                        ${textMetric("TMAX available", yesNoLabel(profile.hasTmax))}
                        ${textMetric("TMAX years", tmaxRange)}
                        ${textMetric("TMIN available", yesNoLabel(profile.hasTmin))}
                        ${textMetric("TMIN years", tminRange)}
                    </div>
                </div>
            ` : ""}
        </section>
    `;
}

function hasTerrainFeatures(terrain) {
    return Boolean(terrain && Object.keys(terrain).some(key => key !== "source"));
}

function renderStationTerrainSection(station) {
    const terrain = station.terrainFeatures || null;
    if (!hasTerrainFeatures(terrain)) {
        return "";
    }

    return `
        <section class="support-section">
            <h3>DEM / Terrain Features</h3>
            <p class="support-note">
                DEM-derived station features used by terrain-aware model artifacts when those columns are available.
            </p>
            <div class="station-metric-group">
                <h4>Station Terrain</h4>
                <div class="metric-grid">
                    ${metricOrUnavailable("NOAA elevation", terrain.noaaElevationM, " m", 1)}
                    ${metricOrUnavailable("DEM elevation", terrain.demElevationM, " m", 1)}
                    ${metricOrUnavailable("DEM minus NOAA", terrain.demMinusNoaaElevationM, " m", 1)}
                    ${metricOrUnavailable("Slope", terrain.slopeDegrees, " deg", 1)}
                    ${metricOrUnavailable("Local relief", terrain.localReliefM, " m", 1)}
                    ${metricOrUnavailable("Terrain position", terrain.terrainPositionIndexM, " m", 1)}
                </div>
            </div>
            <div class="station-metric-group">
                <h4>Multi-scale Context</h4>
                <div class="metric-grid">
                    ${metricOrUnavailable("300 m slope", terrain.slopeDegreesR300m, " deg", 1)}
                    ${metricOrUnavailable("300 m relief", terrain.localReliefMR300m, " m", 1)}
                    ${metricOrUnavailable("300 m terrain position", terrain.terrainPositionIndexMR300m, " m", 1)}
                    ${metricOrUnavailable("990 m slope", terrain.slopeDegreesR990m, " deg", 1)}
                    ${metricOrUnavailable("990 m relief", terrain.localReliefMR990m, " m", 1)}
                    ${metricOrUnavailable("990 m terrain position", terrain.terrainPositionIndexMR990m, " m", 1)}
                    ${metricOrUnavailable("3000 m slope", terrain.slopeDegreesR3000m, " deg", 1)}
                    ${metricOrUnavailable("3000 m relief", terrain.localReliefMR3000m, " m", 1)}
                    ${metricOrUnavailable("3000 m terrain position", terrain.terrainPositionIndexMR3000m, " m", 1)}
                </div>
            </div>
        </section>
    `;
}

function renderFullyTrainedModelSection(data, sourceVariable) {
    const metrics = data.fullyTrainedModelVsObserved;
    const context = data.context || {};
    const finalSeries = stationPredictionSeries(data, "finalModel");

    if (!metrics) {
        return `
            <section class="support-section">
                <h3>Fully Trained Paloma Model vs Observed Data</h3>
                <p class="support-note">
                    Independent station-level metrics for the final fully trained Paloma model are not present in the current artifacts.
                    The available <code>station_metrics.csv</code> row for this station was prepared from station-holdout validation, so it is not shown here as final-model evidence.
                </p>
                <div class="notice">
                    <strong>Not available yet.</strong>
                    ${escapeHtml(fullyTrainedMetricStatusMessage(context.fullyTrainedMetricStatus))}
                </div>
            </section>
        `;
    }

    return `
        <section class="support-section">
            <h3>Fully Trained Paloma Model vs Observed Data</h3>
            <p class="support-note">
                ${escapeHtml(sourceVariable)} final production model compared against observed station rows.
                This is an in-sample fit check because the production estimator was trained on all eligible rows.
            </p>
            <div class="station-metric-group">
                <h4>Fit Performance</h4>
                <div class="metric-grid">
                    ${metricOrUnavailable("MAE", metrics.maeF, " F", 2)}
                    ${metricOrUnavailable("RMSE", metrics.rmseF, " F", 2)}
                    ${metricOrUnavailable("Correlation", metrics.correlation, "", 3)}
                    ${metricOrUnavailable("Bias", metrics.biasF, " F", 2)}
                </div>
            </div>
            <div class="station-metric-group">
                <h4>Rows & Averages</h4>
                <div class="metric-grid">
                    ${metricOrUnavailable("Fit rows", metrics.rowCount, "", 0)}
                    ${textMetric("Date range", dateRangeLabel(metrics.startDate, metrics.endDate))}
                    ${metricOrUnavailable("Actual mean", metrics.actualMeanF, " F", 2)}
                    ${metricOrUnavailable("Predicted mean", metrics.predictedMeanF, " F", 2)}
                    ${textMetric("Evaluation", evaluationModeLabel(metrics.evaluationMode))}
                </div>
            </div>
            ${renderPredictionComparisonChart(finalSeries, {
                modelLabel: "Fully trained model",
                variableLabel: sourceVariable,
                emptyMessage: "Daily final-model prediction rows are unavailable for this station."
            })}
        </section>
    `;
}

function renderHoldoutReconstructionSection(data, holdout, holdoutRun, layerLabel, sourceVariable) {
    const quality = classifyDailyTemperatureReconstructionQuality(holdout);
    const holdoutSeries = stationPredictionSeries(data, "holdout");

    return `
        <section class="support-section">
            <h3>Station Holdout Reconstruction Performance</h3>
            <p class="support-note">
                These metrics come from the station holdout test, where observed data for this station is withheld and reconstructed from the rest of the network.
            </p>
            ${renderQualitySummary(quality)}
            <div class="station-metric-group">
                <h4>Reconstruction Performance</h4>
                <div class="metric-grid">
                    ${metricOrUnavailable("MAE", holdout.maeF, " F", 2)}
                    ${metricOrUnavailable("RMSE", holdout.rmseF, " F", 2)}
                    ${metricOrUnavailable("Correlation", holdout.correlation, "", 3)}
                    ${metricOrUnavailable("Bias", holdoutRun && holdoutRun.biasF, " F", 2)}
                </div>
            </div>
            ${renderPredictionComparisonChart(holdoutSeries, {
                modelLabel: "Holdout model",
                variableLabel: sourceVariable,
                emptyMessage: "Daily holdout prediction rows are unavailable for this station."
            })}
            <div class="station-metric-group">
                <h4>Holdout Setup</h4>
                <div class="metric-grid">
                    ${metricOrUnavailable("Test rows", holdout.testRows, "", 0)}
                    ${textMetric("Strict pass", booleanLabel(holdoutRun && holdoutRun.strictPass))}
                    ${textMetric("Holdout group", holdoutRun && holdoutRun.holdoutGroupId)}
                    ${metricOrUnavailable("Group size", holdoutRun && holdoutRun.holdoutGroupSize, "", 0)}
                    ${metricOrUnavailable("Train rows", holdoutRun && holdoutRun.trainRows, "", 0)}
                    ${metricOrUnavailable("Elapsed", holdoutRun && holdoutRun.elapsedSeconds, " s", 1)}
                    ${textMetric("Surface role", `${layerLabel} station anchor`)}
                </div>
            </div>
        </section>
    `;
}

export function renderReliabilityStationDetails(data) {
    if (!elements.reliabilityResultsContainer) {
        return;
    }

    if (!data || data.status !== "ok") {
        elements.reliabilityResultsContainer.innerHTML = `
            <div class="card">
                <h2>Station Detail</h2>
                <div class="error">${escapeHtml(data && data.message ? data.message : "Could not load station details.")}</div>
            </div>
        `;
        return;
    }

    const station = data.station || {};
    const holdout = data.stationHoldoutTest || {};
    const holdoutRun = data.holdoutRun;
    const context = data.context || {};
    const layerLabel = LAYER_LABELS[data.layer] || data.layer;
    const sourceVariable = station.sourceVariable ? station.sourceVariable.toUpperCase() : "N/A";
    const quality = classifyDailyTemperatureReconstructionQuality(holdout);
    const stationName = station.stationName || station.stationId || "Unknown station";
    const coordinates = coordinatesLabel(station);
    const percentile = holdout.maePercentile === null || holdout.maePercentile === undefined
        ? null
        : Number(holdout.maePercentile) * 100;

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card support-card station-detail-card">
            <div class="support-hero station-detail-hero">
                <div>
                    <div class="station-eyebrow">Station Detail</div>
                    <h2>${escapeHtml(stationName)}</h2>
                    <p class="support-meta">
                        ${escapeHtml(station.stationId || "N/A")} |
                        ${escapeHtml(sourceVariable)}
                        ${coordinates ? ` | ${escapeHtml(coordinates)}` : ""}
                    </p>
                </div>
                <div class="support-score-badge quality-${escapeHtml(quality.id)}">
                    <span class="support-score-number">${escapeHtml(quality.label)}</span>
                    <span class="support-score-label">Holdout quality</span>
                </div>
            </div>

            <div class="support-body">
                ${renderStationIdentitySection(station, sourceVariable, layerLabel)}
                ${renderStationAtAGlance(data, quality, percentile)}
                ${renderFullyTrainedModelSection(data, sourceVariable)}
                ${renderHoldoutReconstructionSection(data, holdout, holdoutRun, layerLabel, sourceVariable)}
                ${renderStationTerrainSection(station)}

                <section class="support-section">
                    <h3>Reliability Context</h3>
                    <p class="support-note">
                        This is the map-side context for the selected station anchor, separate from final-model fit and station-holdout validation.
                    </p>
                    <div class="station-metric-group">
                        <h4>Surface Position</h4>
                        <div class="metric-grid">
                            ${metricOrUnavailable("Surface reliability", holdout.observedReliability, "", 1)}
                            ${metricOrUnavailable("MAE percentile", percentile, "%", 1)}
                            ${textMetric("Surface layer", layerLabel)}
                        </div>
                    </div>
                    <div class="station-metric-group">
                        <h4>Artifacts</h4>
                        <div class="metric-grid">
                            ${textMetric("Reliability run", context.reliabilityModelRunId)}
                            ${textMetric("Source model run", context.sourceModelRunId)}
                            ${textMetric("Surface artifact", context.surfaceArtifact)}
                        </div>
                    </div>
                </section>
            </div>
        </div>
    `;
}

function renderVariableBreakdown(sample) {
    const variables = sample.variables || {};
    const hasHelpfulness = Object.values(variables).some(item => item && item.modelHelpfulness !== undefined);
    const rows = Object.keys(variables).map(variable => {
        const item = variables[variable];
        const score = item.modelHelpfulness !== undefined ? item.modelHelpfulness : item.reliability;
        const generalization = item.generalizationReliability !== undefined
            ? ` / Gen ${formatNumber(item.generalizationReliability, 1)}`
            : "";
        return `
            <tr>
                <td>${escapeHtml(variable.toUpperCase())}</td>
                <td>${formatNumber(score, 1)}${generalization}</td>
                <td>${formatNumber(item.expectedMaeF, 2)} F</td>
                <td>${formatNumber(item.evidenceStrength, 1)}</td>
            </tr>
        `;
    }).join("");

    if (!rows) {
        return "";
    }

    return `
        <section class="support-section">
            <h3>Variable Breakdown</h3>
            <div class="support-table-wrap">
                <table>
                    <thead>
                        <tr>
                            <th>Layer</th>
                            <th>${hasHelpfulness ? "Helpfulness / Generalization" : "Reliability"}</th>
                            <th>Expected MAE</th>
                            <th>Evidence</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        </section>
    `;
}

export function renderReliabilitySample(data) {
    if (!elements.reliabilityResultsContainer) {
        return;
    }

    if (!data || data.status !== "ok") {
        elements.reliabilityResultsContainer.innerHTML = `
            <div class="card">
                <h2>Reliability Inspector</h2>
                <div class="error">${escapeHtml(data && data.message ? data.message : "Could not sample the reliability surface.")}</div>
            </div>
        `;
        return;
    }

    const sample = data.sample || {};
    const layerLabel = LAYER_LABELS[data.layer] || data.layer;
    // Headline the calibrated helpfulness blend, not the raw percentile rank:
    // half the basin ranks below 50 by construction, so the rank alone reads
    // like a failing grade even where the model is near its median accuracy.
    const headlineScore = sample.modelHelpfulness !== undefined
        ? sample.modelHelpfulness
        : sample.reliability;
    const scoreLabel = data.layer === "helpfulness" || sample.modelHelpfulness !== undefined
        ? "Model helpfulness"
        : "Reliability";
    const highStation = sample.nearestHighMaeStation;
    const lowStation = sample.nearestLowMaeStation;
    const generalizationMetric = sample.generalizationReliability !== undefined
        ? `
            <div class="metric">
                <div class="metric-label">Generalization percentile</div>
                <div class="metric-value">${formatNumber(sample.generalizationReliability, 1)}</div>
            </div>
        `
        : "";
    const maeUsefulnessMetric = sample.expectedMaeUsefulness !== undefined
        ? `
            <div class="metric">
                <div class="metric-label">Expected MAE usefulness</div>
                <div class="metric-value">${formatNumber(sample.expectedMaeUsefulness, 1)}</div>
            </div>
        `
        : "";

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card support-card">
            <div class="support-hero">
                <div>
                    <h2>Reliability Inspector</h2>
                    <p class="support-meta">
                        ${escapeHtml(layerLabel)} |
                        ${formatNumber(sample.latitude, 6)}, ${formatNumber(sample.longitude, 6)} |
                        nearest grid cell ${formatNumber(data.nearestSurfaceDistanceKm, 1)} km
                    </p>
                </div>
                <div class="support-score-badge ${headlineScore >= 75 ? "high" : headlineScore >= 65 ? "moderate" : headlineScore >= 50 ? "low" : "very-low"}">
                    <span class="support-score-number">${formatNumber(headlineScore, 1)}</span>
                    <span class="support-score-label">${escapeHtml(scoreLabel)}</span>
                </div>
            </div>

            <div class="support-body">
                <section class="support-section">
                    <h3>Surface Estimate</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <div class="metric-label">Expected MAE</div>
                            <div class="metric-value">${formatNumber(sample.expectedMaeF, 2)} F</div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Evidence strength</div>
                            <div class="metric-value">${formatNumber(sample.evidenceStrength, 1)}</div>
                        </div>
                        ${generalizationMetric}
                        ${maeUsefulnessMetric}
                        <div class="metric">
                            <div class="metric-label">Limiting variable</div>
                            <div class="metric-value">${escapeHtml((sample.worstVariable || data.layer || "N/A").toUpperCase())}</div>
                        </div>
                    </div>
                    <div class="score-band">
                        ${renderScoreBar(scoreLabel, headlineScore)}
                        ${renderScoreBar("Evidence strength", sample.evidenceStrength)}
                    </div>
                </section>

                ${renderVariableBreakdown(sample)}

                <section class="support-section">
                    <h3>Nearby Holdout Stations</h3>
                    <ul class="support-list">
                        ${renderStationList(sample.nearestHoldoutStations)}
                    </ul>
                </section>

                <section class="support-section">
                    <h3>High/Low MAE Context</h3>
                    <div class="metric-grid">
                        <div class="metric">
                            <div class="metric-label">Nearest high-MAE station</div>
                            <div class="metric-value">
                                ${highStation ? `${escapeHtml(highStation.stationId)} (${formatNumber(highStation.distanceKm, 1)} km)` : "N/A"}
                            </div>
                        </div>
                        <div class="metric">
                            <div class="metric-label">Nearest low-MAE station</div>
                            <div class="metric-value">
                                ${lowStation ? `${escapeHtml(lowStation.stationId)} (${formatNumber(lowStation.distanceKm, 1)} km)` : "N/A"}
                            </div>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    `;
}

export function renderReliabilityOverview(payload) {
    if (!elements.reliabilityResultsContainer || !payload) {
        return;
    }

    const mode = activeReliabilityMapMode();
    if (isFinalModelMetricMode(mode)) {
        renderFinalModelMapOverview(payload, mode);
        return;
    }

    if (isHoldoutErrorMetricMode(mode)) {
        renderHoldoutErrorMapOverview(payload, mode);
        return;
    }

    if (mode === "bias") {
        renderBiasMapOverview(payload);
        return;
    }

    if (mode === "correlation") {
        renderCorrelationMapOverview(payload);
        return;
    }

    const summary = payload.surfaceSummary || {};
    const holdoutSummary = payload.stationHoldoutSummary || {};
    const layerLabel = LAYER_LABELS[payload.layer] || payload.layer;
    const isHelpfulness = payload.layer === "helpfulness";
    const sourceVariables = (payload.sourceVariableLayers || []).map(variable => variable.toUpperCase()).join(", ");
    const missingVariables = (payload.missingVariableLayers || []).map(variable => variable.toUpperCase()).join(", ");
    const visualization = payload.visualization || {};
    const visualizationNote = visualization.note
        ? `<p class="summary">${escapeHtml(visualization.note)}</p>`
        : "";
    const maskedPointCount = payload.grid && Number(payload.grid.maskedPointCount);
    const smallArtifactNotice = maskedPointCount > 0 && maskedPointCount < 25
        ? `
            <div class="notice">
                This reliability artifact has only ${maskedPointCount} masked grid cell${maskedPointCount === 1 ? "" : "s"}.
                It is smoke-test scale, not a production Colorado Basin surface.
            </div>
        `
        : "";

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>${escapeHtml(layerLabel)}</h2>
            <p class="summary">
                Click the map to inspect expected MAE, reliability, evidence strength,
                and nearby station holdout context for a grid cell.
            </p>
            ${visualizationNote}
            ${smallArtifactNotice}
            <div class="metric-grid">
                <div class="metric">
                    <div class="metric-label">Surface median ${isHelpfulness ? "helpfulness" : "reliability"}</div>
                    <div class="metric-value">${formatNumber(summary.median, 1)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">Surface mean ${isHelpfulness ? "helpfulness" : "reliability"}</div>
                    <div class="metric-value">${formatNumber(summary.mean, 1)}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">${isHelpfulness ? "Source variables" : "Holdout stations"}</div>
                    <div class="metric-value">${isHelpfulness ? escapeHtml(sourceVariables || "N/A") : holdoutSummary.count || "N/A"}</div>
                </div>
                <div class="metric">
                    <div class="metric-label">${isHelpfulness ? "Missing variables" : "Median holdout MAE"}</div>
                    <div class="metric-value">${isHelpfulness ? escapeHtml(missingVariables || "None") : `${formatNumber(holdoutSummary.median, 2)} F`}</div>
                </div>
            </div>
        </div>
    `;
}

function renderHoldoutErrorMapOverview(payload, mode) {
    const errorConfig = holdoutErrorMetricConfig(mode);
    if (!errorConfig) {
        renderReliabilityOverview(payload);
        return;
    }

    const stations = payload.holdoutStations || [];
    const values = numericStationValues(stations, station => station[errorConfig.field]);
    const layerLabel = LAYER_LABELS[payload.layer] || payload.layer;
    const minValue = values.length ? values[0] : null;
    const maxValue = values.length ? values[values.length - 1] : null;

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>${escapeHtml(errorConfig.title)}</h2>
            <p class="summary">
                ${escapeHtml(layerLabel)} station points colored only by station-holdout ${escapeHtml(errorConfig.metricLabel)}.
                Lower values are better; this view ignores correlation and bias so absolute reconstruction error can be inspected directly.
            </p>
            <div class="metric-grid">
                ${metricOrUnavailable(`Stations with ${errorConfig.metricLabel}`, values.length, "", 0)}
                ${metricOrUnavailable(`Median holdout ${errorConfig.metricLabel}`, median(values), errorConfig.suffix, errorConfig.digits)}
                ${metricOrUnavailable(`Mean holdout ${errorConfig.metricLabel}`, mean(values), errorConfig.suffix, errorConfig.digits)}
                ${metricOrUnavailable(`Lowest holdout ${errorConfig.metricLabel}`, minValue, errorConfig.suffix, errorConfig.digits)}
                ${metricOrUnavailable(`Highest holdout ${errorConfig.metricLabel}`, maxValue, errorConfig.suffix, errorConfig.digits)}
            </div>
        </div>
    `;
}

function renderFinalModelMapOverview(payload, mode) {
    const finalConfig = finalModelMetricConfig(mode);
    if (!finalConfig) {
        renderReliabilityOverview(payload);
        return;
    }

    const stations = payload.holdoutStations || [];
    const values = numericStationValues(stations, station => station[finalConfig.field]);
    const layerLabel = LAYER_LABELS[payload.layer] || payload.layer;
    const missingCount = Math.max(0, stations.length - values.length);
    const minValue = values.length ? values[0] : null;
    const maxValue = values.length ? values[values.length - 1] : null;
    const coverageNotice = missingCount
        ? `
            <div class="notice">
                ${missingCount} of ${stations.length} station${stations.length === 1 ? "" : "s"} on this map
                do not have a final_model_station_metrics.csv row yet. Those station points are shown as missing;
                the heat surface uses only the ${values.length} available final-model metric row${values.length === 1 ? "" : "s"}.
            </div>
        `
        : "";
    const biasSpecificMetrics = mode === "final-bias"
        ? `
                ${metricOrUnavailable("Mean absolute bias", mean(values.map(value => Math.abs(value))), finalConfig.suffix, finalConfig.digits)}
                ${metricOrUnavailable("Most predicted-warm bias", minValue, finalConfig.suffix, finalConfig.digits)}
                ${metricOrUnavailable("Most predicted-cool bias", maxValue, finalConfig.suffix, finalConfig.digits)}
        `
        : `
                ${metricOrUnavailable(`Lowest final ${finalConfig.metricLabel}`, minValue, finalConfig.suffix, finalConfig.digits)}
                ${metricOrUnavailable(`Highest final ${finalConfig.metricLabel}`, maxValue, finalConfig.suffix, finalConfig.digits)}
        `;

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>${escapeHtml(finalConfig.title)}</h2>
            <p class="summary">
                ${escapeHtml(layerLabel)} station points colored by the final fully trained Paloma model's
                station-vs-observed ${escapeHtml(finalConfig.metricLabel)}. This is final-model fit evidence,
                not station-holdout validation.
            </p>
            ${coverageNotice}
            <div class="metric-grid">
                ${metricOrUnavailable("Stations with final metric", values.length, "", 0)}
                ${metricOrUnavailable("Stations missing final metric", missingCount, "", 0)}
                ${metricOrUnavailable(`Median final ${finalConfig.metricLabel}`, median(values), finalConfig.suffix, finalConfig.digits)}
                ${metricOrUnavailable(`Mean final ${finalConfig.metricLabel}`, mean(values), finalConfig.suffix, finalConfig.digits)}
                ${biasSpecificMetrics}
            </div>
        </div>
    `;
}

function renderBiasMapOverview(payload) {
    const stations = payload.holdoutStations || [];
    const biasValues = numericStationValues(stations, station => station.holdoutBiasF);
    const absoluteBiasValues = biasValues.map(value => Math.abs(value));
    const layerLabel = LAYER_LABELS[payload.layer] || payload.layer;
    const minBias = biasValues.length ? biasValues[0] : null;
    const maxBias = biasValues.length ? biasValues[biasValues.length - 1] : null;

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>Holdout Bias Map</h2>
            <p class="summary">
                ${escapeHtml(layerLabel)} station points colored by station-holdout bias.
                Bias is actual minus predicted, so positive values mean the reconstruction was too cool and negative values mean it was too warm.
            </p>
            <div class="metric-grid">
                ${metricOrUnavailable("Stations with bias", biasValues.length, "", 0)}
                ${metricOrUnavailable("Median bias", median(biasValues), " F", 2)}
                ${metricOrUnavailable("Mean absolute bias", mean(absoluteBiasValues), " F", 2)}
                ${metricOrUnavailable("Most predicted-warm bias", minBias, " F", 2)}
                ${metricOrUnavailable("Most predicted-cool bias", maxBias, " F", 2)}
            </div>
        </div>
    `;
}

function renderCorrelationMapOverview(payload) {
    const stations = payload.holdoutStations || [];
    const correlationValues = numericStationValues(stations, station => station.observedCorrelation);
    const layerLabel = LAYER_LABELS[payload.layer] || payload.layer;
    const minCorrelation = correlationValues.length ? correlationValues[0] : null;
    const maxCorrelation = correlationValues.length ? correlationValues[correlationValues.length - 1] : null;

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>Holdout Correlation Map</h2>
            <p class="summary">
                ${escapeHtml(layerLabel)} station points colored only by station-holdout correlation.
                This view ignores MAE and RMSE so spatial coherence in daily timing can be inspected directly.
            </p>
            <div class="metric-grid">
                ${metricOrUnavailable("Stations with correlation", correlationValues.length, "", 0)}
                ${metricOrUnavailable("Median holdout r", median(correlationValues), "", 3)}
                ${metricOrUnavailable("Mean holdout r", mean(correlationValues), "", 3)}
                ${metricOrUnavailable("Lowest holdout r", minCorrelation, "", 3)}
                ${metricOrUnavailable("Highest holdout r", maxCorrelation, "", 3)}
            </div>
        </div>
    `;
}
