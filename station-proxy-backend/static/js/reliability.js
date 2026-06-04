import {
    fetchReliabilitySample,
    fetchReliabilityStationDetails,
    fetchReliabilitySurface,
    fetchReliabilitySummary
} from "./api.js?v=station-details-v1";
import { elements, state } from "./state.js";
import {
    clampPercent,
    escapeHtml,
    formatNumber
} from "./formatters.js";


const LAYER_LABELS = {
    helpfulness: "Model Helpfulness",
    overall: "Overall Reliability",
    tavg: "TAVG Reliability",
    tmin: "TMIN Reliability",
    tmax: "TMAX Reliability"
};

const QUALITY_UNKNOWN = {
    id: "unknown",
    label: "Unknown",
    color: "#94a3b8",
    description: "Insufficient daily reconstruction metrics for a confident quality class."
};

const RELIABILITY_MAP_MODES = {
    quality: {
        label: "Overall Reconstruction Quality",
        rasterOpacity: 0.72,
        help: "Overall combines station-holdout correlation, MAE, and RMSE. Green means the daily reconstruction was strong; red means the station failed one or more quality thresholds. Click the raster for a grid cell or a station point for station detail.",
        legendNote: "Overall quality uses all three holdout metrics together: correlation, MAE, and RMSE."
    },
    "final-correlation": {
        label: "Fully Trained Model Correlation",
        rasterOpacity: 0.68,
        help: "Fully Trained Correlation shows the final Paloma model's station-level fit against observed station values. High correlation is green and low correlation is red. This is final-model fit evidence, not station-holdout validation.",
        legendNote: "Final-model correlation is plotted only where final_model_station_metrics.csv has a station row."
    },
    "final-mae": {
        label: "Fully Trained Model MAE",
        rasterOpacity: 0.68,
        help: "Fully Trained MAE shows the final Paloma model's mean absolute error against observed station values. Green means lower error and red means higher error. This is final-model fit evidence, not station-holdout validation.",
        legendNote: "Final-model MAE is plotted only where final_model_station_metrics.csv has a station row."
    },
    "final-rmse": {
        label: "Fully Trained Model RMSE",
        rasterOpacity: 0.68,
        help: "Fully Trained RMSE shows the final Paloma model's root mean squared error against observed station values. Green means lower error and red means higher error. This is final-model fit evidence, not station-holdout validation.",
        legendNote: "Final-model RMSE is plotted only where final_model_station_metrics.csv has a station row."
    },
    "final-bias": {
        label: "Fully Trained Model Bias",
        rasterOpacity: 0.68,
        help: "Fully Trained Bias shows whether the final Paloma model was generally hot, cold, or just right at each station. Bias is actual minus predicted: red means the model predicted too hot, green means near unbiased, and blue means the model predicted too cold.",
        legendNote: "Final-model bias = actual - predicted. Negative values mean too hot; positive values mean too cold."
    },
    bias: {
        label: "Station Holdout Bias",
        rasterOpacity: 0.68,
        help: "Holdout Bias shows whether the reconstruction was generally hot, cold, or just right. Bias is actual minus predicted: red means the model predicted too hot, green means near unbiased, and blue means the model predicted too cold.",
        legendNote: "Bias = actual - predicted. Negative values mean the model was too hot; positive values mean it was too cold."
    },
    correlation: {
        label: "Station Holdout Correlation",
        rasterOpacity: 0.68,
        help: "Holdout Correlation shows only daily timing/shape agreement. High correlation is green, low correlation is red; this view intentionally ignores MAE, RMSE, and bias.",
        legendNote: "Correlation is plotted alone: green is high agreement, red is low agreement."
    }
};

const RELIABILITY_LEGENDS = {
    quality: [
        ["quality-excellent", "Excellent: r >= 0.97, MAE <= 1.25 F, RMSE <= 2.0 F"],
        ["quality-strong", "Strong: r >= 0.95, MAE <= 2.0 F, RMSE <= 3.0 F"],
        ["quality-acceptable", "Acceptable: r >= 0.90, MAE <= 2.5 F, RMSE <= 3.5 F"],
        ["quality-weak", "Weak: r >= 0.80, MAE <= 4.0 F, RMSE <= 5.0 F"],
        ["quality-poor", "Poor: below weak thresholds"],
        ["quality-unknown", "Unknown: insufficient metrics"]
    ],
    "final-correlation": [
        ["correlation-excellent", "Green, excellent: r >= 0.995"],
        ["correlation-very-strong", "Green-teal, very strong: r >= 0.990"],
        ["correlation-strong", "Light green, strong: r >= 0.980"],
        ["correlation-moderate", "Yellow, moderate: r >= 0.950"],
        ["correlation-weak", "Orange, weak: r >= 0.900"],
        ["correlation-poor", "Red, low: r < 0.900"],
        ["correlation-unknown", "Missing: no final-model metric row"]
    ],
    "final-mae": [
        ["error-excellent", "Green, very low error: MAE <= 1.25 F"],
        ["error-strong", "Green-teal, low error: MAE <= 2.0 F"],
        ["error-acceptable", "Yellow, moderate error: MAE <= 2.5 F"],
        ["error-weak", "Orange, high error: MAE <= 4.0 F"],
        ["error-poor", "Red, very high error: MAE > 4.0 F"],
        ["error-unknown", "Missing: no final-model metric row"]
    ],
    "final-rmse": [
        ["error-excellent", "Green, very low error: RMSE <= 2.0 F"],
        ["error-strong", "Green-teal, low error: RMSE <= 3.0 F"],
        ["error-acceptable", "Yellow, moderate error: RMSE <= 3.5 F"],
        ["error-weak", "Orange, high error: RMSE <= 5.0 F"],
        ["error-poor", "Red, very high error: RMSE > 5.0 F"],
        ["error-unknown", "Missing: no final-model metric row"]
    ],
    "final-bias": [
        ["bias-very-warm", "Hot model, very strong: bias <= -4 F"],
        ["bias-warm", "Hot model: -4 to -2 F"],
        ["bias-slight-warm", "Slightly hot model: -2 to -1 F"],
        ["bias-neutral", "Just right / near zero: -1 to +1 F"],
        ["bias-slight-cool", "Slightly cold model: +1 to +2 F"],
        ["bias-cool", "Cold model: +2 to +4 F"],
        ["bias-very-cool", "Cold model, very strong: bias >= +4 F"],
        ["bias-unknown", "Missing: no final-model metric row"]
    ],
    bias: [
        ["bias-very-warm", "Hot model, very strong: bias <= -4 F"],
        ["bias-warm", "Hot model: -4 to -2 F"],
        ["bias-slight-warm", "Slightly hot model: -2 to -1 F"],
        ["bias-neutral", "Just right / near zero: -1 to +1 F"],
        ["bias-slight-cool", "Slightly cold model: +1 to +2 F"],
        ["bias-cool", "Cold model: +2 to +4 F"],
        ["bias-very-cool", "Cold model, very strong: bias >= +4 F"],
        ["bias-unknown", "Unknown: no bias metric"]
    ],
    correlation: [
        ["correlation-excellent", "Green, excellent: r >= 0.995"],
        ["correlation-very-strong", "Green-teal, very strong: r >= 0.990"],
        ["correlation-strong", "Light green, strong: r >= 0.980"],
        ["correlation-moderate", "Yellow, moderate: r >= 0.950"],
        ["correlation-weak", "Orange, weak: r >= 0.900"],
        ["correlation-poor", "Red, low: r < 0.900"],
        ["correlation-unknown", "Unknown: no correlation metric"]
    ]
};

export function refreshReliabilityMapSize() {
    if (!state.reliabilityMap) {
        return;
    }

    state.reliabilityMap.invalidateSize(true);
}

function reliabilityColor(score) {
    const numericScore = Number(score);

    if (numericScore >= 85) {
        return "#16a34a";
    }

    if (numericScore >= 75) {
        return "#14b8a6";
    }

    if (numericScore >= 65) {
        return "#facc15";
    }

    if (numericScore >= 50) {
        return "#f97316";
    }

    return "#b91c1c";
}

function numericMetric(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

function classifyDailyTemperatureReconstructionQuality(metrics) {
    const correlation = numericMetric(metrics && metrics.correlation);
    const mae = numericMetric(metrics && metrics.maeF);
    const rmse = numericMetric(metrics && metrics.rmseF);

    if ([correlation, mae, rmse].some(value => value === null)) {
        return QUALITY_UNKNOWN;
    }

    if (correlation >= 0.97 && mae <= 1.25 && rmse <= 2.0) {
        return {
            id: "excellent",
            label: "Excellent",
            color: "#16a34a",
            description: "r >= 0.97, MAE <= 1.25 F, RMSE <= 2.0 F"
        };
    }

    if (correlation >= 0.95 && mae <= 2.0 && rmse <= 3.0) {
        return {
            id: "strong",
            label: "Strong",
            color: "#14b8a6",
            description: "r >= 0.95, MAE <= 2.0 F, RMSE <= 3.0 F"
        };
    }

    if (correlation >= 0.90 && mae <= 2.5 && rmse <= 3.5) {
        return {
            id: "acceptable",
            label: "Acceptable",
            color: "#facc15",
            description: "r >= 0.90, MAE <= 2.5 F, RMSE <= 3.5 F"
        };
    }

    if (correlation >= 0.80 && mae <= 4.0 && rmse <= 5.0) {
        return {
            id: "weak",
            label: "Weak",
            color: "#f97316",
            description: "r >= 0.80, MAE <= 4.0 F, RMSE <= 5.0 F"
        };
    }

    return {
        id: "poor",
        label: "Poor",
        color: "#b91c1c",
        description: "Below weak daily reconstruction thresholds."
    };
}

function classifyHoldoutBias(biasValue, missingDescription = "No station holdout bias metric is available.") {
    const bias = numericMetric(biasValue);

    if (bias === null) {
        return {
            id: "unknown",
            label: "Unknown",
            color: "#94a3b8",
            description: missingDescription
        };
    }

    if (bias <= -4) {
        return {
            id: "very-warm",
            label: "Predicted very warm",
            color: "#b91c1c",
            description: "actual - predicted <= -4 F"
        };
    }

    if (bias <= -2) {
        return {
            id: "warm",
            label: "Predicted warm",
            color: "#ef4444",
            description: "-4 F < actual - predicted <= -2 F"
        };
    }

    if (bias <= -1) {
        return {
            id: "slight-warm",
            label: "Slight warm bias",
            color: "#fb923c",
            description: "-2 F < actual - predicted <= -1 F"
        };
    }

    if (bias < 1) {
        return {
            id: "neutral",
            label: "Near zero bias",
            color: "#16a34a",
            description: "-1 F < actual - predicted < +1 F"
        };
    }

    if (bias < 2) {
        return {
            id: "slight-cool",
            label: "Slight cool bias",
            color: "#38bdf8",
            description: "+1 F <= actual - predicted < +2 F"
        };
    }

    if (bias < 4) {
        return {
            id: "cool",
            label: "Predicted cool",
            color: "#0284c7",
            description: "+2 F <= actual - predicted < +4 F"
        };
    }

    return {
        id: "very-cool",
        label: "Predicted very cool",
        color: "#1d4ed8",
        description: "actual - predicted >= +4 F"
    };
}

function classifyHoldoutCorrelation(
    correlationValue,
    missingDescription = "No station holdout correlation metric is available."
) {
    const correlation = numericMetric(correlationValue);

    if (correlation === null) {
        return {
            id: "unknown",
            label: "Unknown",
            color: "#94a3b8",
            description: missingDescription
        };
    }

    if (correlation >= 0.995) {
        return {
            id: "excellent",
            label: "Excellent",
            color: "#16a34a",
            description: "r >= 0.995"
        };
    }

    if (correlation >= 0.99) {
        return {
            id: "very-strong",
            label: "Very strong",
            color: "#14b8a6",
            description: "r >= 0.990"
        };
    }

    if (correlation >= 0.98) {
        return {
            id: "strong",
            label: "Strong",
            color: "#84cc16",
            description: "r >= 0.980"
        };
    }

    if (correlation >= 0.95) {
        return {
            id: "moderate",
            label: "Moderate",
            color: "#facc15",
            description: "r >= 0.950"
        };
    }

    if (correlation >= 0.90) {
        return {
            id: "weak",
            label: "Weak",
            color: "#f97316",
            description: "r >= 0.900"
        };
    }

    return {
        id: "poor",
        label: "Poor",
        color: "#b91c1c",
        description: "r < 0.900"
    };
}

function classifyFinalModelError(errorValue, metricName) {
    const error = numericMetric(errorValue);
    const isRmse = metricName === "RMSE";
    const thresholds = isRmse
        ? { excellent: 2.0, strong: 3.0, acceptable: 3.5, weak: 5.0 }
        : { excellent: 1.25, strong: 2.0, acceptable: 2.5, weak: 4.0 };

    if (error === null) {
        return {
            id: "unknown",
            label: "Missing final metric",
            color: "#94a3b8",
            description: "No final-model station metric row is available."
        };
    }

    if (error <= thresholds.excellent) {
        return {
            id: "excellent",
            label: "Very low error",
            color: "#16a34a",
            description: `${metricName} <= ${thresholds.excellent} F`
        };
    }

    if (error <= thresholds.strong) {
        return {
            id: "strong",
            label: "Low error",
            color: "#14b8a6",
            description: `${metricName} <= ${thresholds.strong} F`
        };
    }

    if (error <= thresholds.acceptable) {
        return {
            id: "acceptable",
            label: "Moderate error",
            color: "#facc15",
            description: `${metricName} <= ${thresholds.acceptable} F`
        };
    }

    if (error <= thresholds.weak) {
        return {
            id: "weak",
            label: "High error",
            color: "#f97316",
            description: `${metricName} <= ${thresholds.weak} F`
        };
    }

    return {
        id: "poor",
        label: "Very high error",
        color: "#b91c1c",
        description: `${metricName} > ${thresholds.weak} F`
    };
}

const FINAL_MODEL_METRIC_CONFIGS = {
    "final-correlation": {
        title: "Fully Trained Model Correlation",
        metricLabel: "Correlation",
        field: "finalModelCorrelation",
        suffix: "",
        digits: 3,
        classify: value => classifyHoldoutCorrelation(
            value,
            "No final-model station metric row is available."
        )
    },
    "final-mae": {
        title: "Fully Trained Model MAE",
        metricLabel: "MAE",
        field: "finalModelMaeF",
        suffix: " F",
        digits: 2,
        classify: value => classifyFinalModelError(value, "MAE")
    },
    "final-rmse": {
        title: "Fully Trained Model RMSE",
        metricLabel: "RMSE",
        field: "finalModelRmseF",
        suffix: " F",
        digits: 2,
        classify: value => classifyFinalModelError(value, "RMSE")
    },
    "final-bias": {
        title: "Fully Trained Model Bias",
        metricLabel: "Bias",
        field: "finalModelBiasF",
        suffix: " F",
        digits: 2,
        classify: value => classifyHoldoutBias(
            value,
            "No final-model station metric row is available."
        )
    }
};

function stationHoldoutMetricBundle(station) {
    return {
        maeF: station && station.observedMaeF,
        rmseF: station && station.observedRmseF,
        correlation: station && station.observedCorrelation,
        testRows: station && station.testRows
    };
}

function activeReliabilityMapMode() {
    return RELIABILITY_MAP_MODES[state.reliabilityMapMode]
        ? state.reliabilityMapMode
        : "quality";
}

function finalModelMetricConfig(mode) {
    return FINAL_MODEL_METRIC_CONFIGS[mode] || null;
}

function isFinalModelMetricMode(mode) {
    return Boolean(finalModelMetricConfig(mode));
}

function isStationMetricOverlayMode(mode) {
    return mode === "bias" || mode === "correlation" || isFinalModelMetricMode(mode);
}

function numericStationValues(stations, valueGetter) {
    return (stations || [])
        .map(station => numericMetric(valueGetter(station)))
        .filter(value => value !== null)
        .sort((a, b) => a - b);
}

function median(values) {
    if (!values.length) {
        return null;
    }

    const middle = Math.floor(values.length / 2);
    if (values.length % 2) {
        return values[middle];
    }

    return (values[middle - 1] + values[middle]) / 2;
}

function mean(values) {
    if (!values.length) {
        return null;
    }

    return values.reduce((total, value) => total + value, 0) / values.length;
}

function setReliabilityStatus(message) {
    if (elements.reliabilityLayerStatus) {
        elements.reliabilityLayerStatus.textContent = message;
    }
}

function reliabilityBounds(payload) {
    const bounds = payload && payload.bounds;
    if (!bounds) {
        return null;
    }

    return [
        [Number(bounds.latMin), Number(bounds.lonMin)],
        [Number(bounds.latMax), Number(bounds.lonMax)]
    ];
}

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

function renderReliabilityLegend() {
    if (!elements.reliabilityLegend) {
        return;
    }

    const mode = activeReliabilityMapMode();
    const legend = RELIABILITY_LEGENDS[mode] || RELIABILITY_LEGENDS.quality;
    const modeConfig = RELIABILITY_MAP_MODES[mode] || RELIABILITY_MAP_MODES.quality;
    elements.reliabilityLegend.className = `map-legend quality-legend reliability-legend mode-${mode}`;
    elements.reliabilityLegend.innerHTML = `
        <strong class="legend-title">${escapeHtml(modeConfig.label)}</strong>
        ${modeConfig.legendNote ? `<span class="legend-note">${escapeHtml(modeConfig.legendNote)}</span>` : ""}
        ${legend.map(([className, label]) => `
            <span class="legend-item"><span class="legend-dot ${escapeHtml(className)}"></span>${escapeHtml(label)}</span>
        `).join("")}
    `;
}

function updateReliabilityModeControls() {
    const mode = activeReliabilityMapMode();
    const modeConfig = RELIABILITY_MAP_MODES[mode] || RELIABILITY_MAP_MODES.quality;

    if (elements.reliabilityMapModeSelect) {
        elements.reliabilityMapModeSelect.value = mode;
    }

    if (elements.reliabilityMapHelp) {
        elements.reliabilityMapHelp.textContent = modeConfig.help;
    }

    renderReliabilityLegend();
}

function updateReliabilityRasterVisibility() {
    if (!state.reliabilityImageLayer) {
        return;
    }

    const mode = activeReliabilityMapMode();
    const modeConfig = RELIABILITY_MAP_MODES[mode] || RELIABILITY_MAP_MODES.quality;
    state.reliabilityImageLayer.setOpacity(modeConfig.rasterOpacity);
}

function updateReliabilityImageUrl(payload) {
    if (!state.reliabilityImageLayer || !payload) {
        return;
    }

    state.reliabilityImageLayer.setUrl(
        activeImageUrlForPayload(payload, state.reliabilityCurrentLayer)
    );
}

function reliabilityStatusForPayload(payload) {
    if (elements.reliabilityStationToggle && !elements.reliabilityStationToggle.checked) {
        return "Holdout station layer hidden";
    }

    const mode = activeReliabilityMapMode();
    const finalConfig = finalModelMetricConfig(mode);
    if (finalConfig) {
        const stations = payload.holdoutStations || [];
        const stationCount = numericStationValues(
            stations,
            station => station[finalConfig.field]
        ).length;
        const missingCount = Math.max(0, stations.length - stationCount);
        return `${stationCount} stations with final-model ${finalConfig.metricLabel} available; ${missingCount} missing`;
    }

    if (mode === "bias") {
        const stationCount = numericStationValues(payload.holdoutStations || [], station => station.holdoutBiasF).length;
        return `${stationCount} holdout stations with bias plotted`;
    }

    if (mode === "correlation") {
        const stationCount = numericStationValues(payload.holdoutStations || [], station => station.observedCorrelation).length;
        return `${stationCount} holdout stations with correlation plotted`;
    }

    const pointCount = payload.grid && payload.grid.maskedPointCount
        ? payload.grid.maskedPointCount
        : (payload.points || []).length;
    return `${pointCount} masked grid cells loaded`;
}

function stationVisualization(station) {
    const mode = activeReliabilityMapMode();
    const finalConfig = finalModelMetricConfig(mode);

    if (finalConfig) {
        const value = numericMetric(station && station[finalConfig.field]);
        const bucket = finalConfig.classify(value);
        const valueText = value === null
            ? "N/A"
            : `${formatNumber(value, finalConfig.digits)}${finalConfig.suffix}`;
        const rowCount = numericMetric(station && station.finalModelRowCount);
        const rowText = rowCount === null ? "rows N/A" : `${formatNumber(rowCount, 0)} rows`;
        const classPrefix = mode === "final-correlation"
            ? "correlation"
            : mode === "final-bias"
                ? "bias"
                : "error";
        return {
            className: `${classPrefix}-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | final ${finalConfig.metricLabel} ${valueText} | ${rowText}`
        };
    }

    if (mode === "bias") {
        const bias = numericMetric(station && station.holdoutBiasF);
        const bucket = classifyHoldoutBias(bias);
        const biasText = bias === null ? "N/A" : `${formatNumber(bias, 2)} F`;
        return {
            className: `bias-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | bias ${biasText} (actual - predicted) | r ${formatNumber(station.observedCorrelation, 3)}`
        };
    }

    if (mode === "correlation") {
        const bucket = classifyHoldoutCorrelation(station && station.observedCorrelation);
        return {
            className: `correlation-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | holdout r ${formatNumber(station.observedCorrelation, 3)}`
        };
    }

    const quality = classifyDailyTemperatureReconstructionQuality(stationHoldoutMetricBundle(station));
    return {
        className: `quality-${quality.id}`,
        color: quality.color,
        title: `${station.stationId}: ${quality.label} | r ${formatNumber(station.observedCorrelation, 3)} | MAE ${formatNumber(station.observedMaeF, 2)} F | RMSE ${formatNumber(station.observedRmseF, 2)} F`
    };
}

function applyReliabilityMapMode(mode) {
    if (!RELIABILITY_MAP_MODES[mode]) {
        return;
    }

    state.reliabilityMapMode = mode;
    updateReliabilityModeControls();
    updateReliabilityRasterVisibility();

    const payload = state.reliabilitySurfaceData[state.reliabilityCurrentLayer];
    if (payload) {
        updateReliabilityImageUrl(payload);
        updateStationMarkers(payload);
        renderReliabilityOverview(payload);
        setReliabilityStatus(reliabilityStatusForPayload(payload));
    }

    refreshReliabilityMapSize();
}

function renderMetricSet(title, metrics, options = {}) {
    if (!metrics) {
        return `
            <section class="support-section">
                <h3>${escapeHtml(title)}</h3>
                <p class="placeholder">${escapeHtml(options.emptyMessage || "Metrics are not available for this station.")}</p>
            </section>
        `;
    }

    return `
        <section class="support-section">
            <h3>${escapeHtml(title)}</h3>
            ${options.note ? `<p class="support-note">${escapeHtml(options.note)}</p>` : ""}
            <div class="metric-grid">
                ${metricOrUnavailable("MAE", metrics.maeF, " F", 2)}
                ${metricOrUnavailable("RMSE", metrics.rmseF, " F", 2)}
                ${metricOrUnavailable("Correlation", metrics.correlation, "", 3)}
                ${metricOrUnavailable("Test rows", metrics.testRows, "", 0)}
            </div>
        </section>
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
        </section>
    `;
}

function renderHoldoutReconstructionSection(holdout, holdoutRun, layerLabel) {
    const quality = classifyDailyTemperatureReconstructionQuality(holdout);

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

function renderHoldoutRunStatistics(holdoutRun) {
    if (!holdoutRun) {
        return `
            <section class="support-section">
                <h3>Holdout Run Statistics</h3>
                <p class="placeholder">Detailed Alpine holdout-run context is not available for this station.</p>
            </section>
        `;
    }

    return `
        <section class="support-section">
            <h3>Holdout Run Statistics</h3>
            <p class="support-note">
                These are run-level and group-level details for the holdout validation process, not separate final-model station metrics.
            </p>
            <div class="metric-grid">
                ${textMetric("Model id", holdoutRun.modelId)}
                ${textMetric("Variable", String(holdoutRun.variable || "").toUpperCase())}
                ${textMetric("Holdout group", holdoutRun.holdoutGroupId)}
                ${metricOrUnavailable("Group size", holdoutRun.holdoutGroupSize, "", 0)}
                ${metricOrUnavailable("Train rows", holdoutRun.trainRows, "", 0)}
                ${metricOrUnavailable("Elapsed", holdoutRun.elapsedSeconds, " s", 1)}
            </div>
        </section>
    `;
}

function renderReliabilityStationDetails(data) {
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
                ${renderHoldoutReconstructionSection(holdout, holdoutRun, layerLabel)}
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

function renderReliabilitySample(data) {
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
    const scoreLabel = data.layer === "helpfulness" ? "Helpfulness" : "Reliability";
    const highStation = sample.nearestHighMaeStation;
    const lowStation = sample.nearestLowMaeStation;
    const generalizationMetric = sample.generalizationReliability !== undefined
        ? `
            <div class="metric">
                <div class="metric-label">Generalization reliability</div>
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
                <div class="support-score-badge ${sample.reliability >= 75 ? "high" : sample.reliability >= 65 ? "moderate" : sample.reliability >= 50 ? "low" : "very-low"}">
                    <span class="support-score-number">${formatNumber(sample.reliability, 1)}</span>
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
                        ${renderScoreBar(scoreLabel, sample.reliability)}
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

function renderReliabilityOverview(payload) {
    if (!elements.reliabilityResultsContainer || !payload) {
        return;
    }

    const mode = activeReliabilityMapMode();
    if (isFinalModelMetricMode(mode)) {
        renderFinalModelMapOverview(payload, mode);
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

function imageUrlForPayload(payload, layer) {
    const path = payload && payload.imageUrl
        ? payload.imageUrl
        : `/model-runs/reliability/surface.png?layer=${encodeURIComponent(layer)}`;

    const baseUrl = payload && payload.__apiBaseUrl && path.startsWith("/")
        ? payload.__apiBaseUrl
        : window.location.origin;
    const url = new URL(path, baseUrl);
    const visualization = payload && payload.visualization;
    const scaleVersion = visualization && visualization.scaleVersion
        ? visualization.scaleVersion
        : payload && payload.scoreVersion
            ? payload.scoreVersion
            : "1";
    url.searchParams.set("visual", scaleVersion);

    return url.toString();
}

function stationOverlayUrlForPayload(payload, layer, mode) {
    const overlayUrls = payload && payload.stationOverlayUrls;
    const path = overlayUrls && overlayUrls[mode]
        ? overlayUrls[mode]
        : `/model-runs/reliability/station-overlay.png?layer=${encodeURIComponent(layer)}&mode=${encodeURIComponent(mode)}`;

    const baseUrl = payload && payload.__apiBaseUrl && path.startsWith("/")
        ? payload.__apiBaseUrl
        : window.location.origin;
    const url = new URL(path, baseUrl);
    url.searchParams.set("overlay", `station-${mode}-v1`);

    return url.toString();
}

function activeImageUrlForPayload(payload, layer) {
    const mode = activeReliabilityMapMode();
    if (isStationMetricOverlayMode(mode)) {
        return stationOverlayUrlForPayload(payload, layer, mode);
    }

    return imageUrlForPayload(payload, layer);
}

function applyReliabilitySummary(summary) {
    state.reliabilitySummary = summary;
    const availableLayers = new Set(summary.availableLayers || []);
    const layerOptions = elements.reliabilityLayerSelect
        ? [...elements.reliabilityLayerSelect.options]
        : [];
    const visibleLayerValues = layerOptions.map(option => option.value);

    if (elements.reliabilityLayerSelect && availableLayers.size) {
        layerOptions.forEach(option => {
            const available = availableLayers.has(option.value);
            option.disabled = !available;
            option.title = available ? "" : "Artifact not available";
        });
    }

    const preferredLayer = visibleLayerValues.includes(state.reliabilityCurrentLayer)
        && (!availableLayers.size || availableLayers.has(state.reliabilityCurrentLayer))
        ? state.reliabilityCurrentLayer
        : visibleLayerValues.includes("tavg") && (!availableLayers.size || availableLayers.has("tavg"))
            ? "tavg"
            : visibleLayerValues.find(value => !availableLayers.size || availableLayers.has(value));

    if (preferredLayer) {
        state.reliabilityCurrentLayer = preferredLayer;
    }

    if (elements.reliabilityLayerSelect) {
        elements.reliabilityLayerSelect.value = state.reliabilityCurrentLayer;
    }
}

function updateBoundary(payload) {
    if (!state.reliabilityMap || !payload.boundaryGeoJson) {
        return;
    }

    if (state.reliabilityBoundaryLayer) {
        state.reliabilityBoundaryLayer.remove();
    }

    state.reliabilityBoundaryLayer = L.geoJSON(payload.boundaryGeoJson, {
        interactive: false,
        style: {
            color: "#0f172a",
            weight: 2,
            opacity: 0.85,
            fillOpacity: 0
        }
    }).addTo(state.reliabilityMap);
}

function updateSelectedStationMarker() {
    state.reliabilityStationMarkersById.forEach((marker, stationId) => {
        const icon = marker.getElement();
        if (!icon) {
            return;
        }

        icon.classList.toggle("selected", stationId === state.reliabilitySelectedStationId);
    });
}

async function selectReliabilityStation(station) {
    if (!elements.reliabilityResultsContainer || !station || !station.stationId) {
        return;
    }

    state.reliabilitySelectedStationId = station.stationId;
    updateSelectedStationMarker();

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>Station Detail</h2>
            <p class="placeholder">
                Loading ${escapeHtml(station.stationName || station.stationId)} station metrics...
            </p>
        </div>
    `;

    try {
        const data = await fetchReliabilityStationDetails(
            state.reliabilityCurrentLayer,
            station.stationId
        );
        renderReliabilityStationDetails(data);
    } catch (error) {
        renderReliabilityStationDetails({
            status: "error",
            message: "Could not load station details for this marker."
        });
    }
}

function bindStationMarkerClick(marker, station) {
    const selectStation = event => {
        if (event) {
            L.DomEvent.stop(event);
        }
        selectReliabilityStation(station);
    };

    marker.on("click", event => {
        if (event.originalEvent) {
            L.DomEvent.stop(event.originalEvent);
        }
        selectReliabilityStation(station);
    });

    marker.on("add", () => {
        const icon = marker.getElement();
        if (!icon) {
            return;
        }

        L.DomEvent.disableClickPropagation(icon);
        L.DomEvent.on(icon, "click", selectStation);
    });
}

function updateStationMarkers(payload) {
    if (!state.reliabilityMap || !state.reliabilityStationLayer) {
        return;
    }

    state.reliabilityStationLayer.clearLayers();
    state.reliabilityStationMarkersById = new Map();
    if (!elements.reliabilityStationToggle || !elements.reliabilityStationToggle.checked) {
        return;
    }

    const stations = payload.holdoutStations || [];
    stations.forEach(station => {
        const latitude = Number(station.latitude);
        const longitude = Number(station.longitude);
        if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
            return;
        }

        const visualization = stationVisualization(station);
        const marker = L.marker([latitude, longitude], {
            pane: "reliabilityStationPane",
            bubblingMouseEvents: false,
            icon: L.divIcon({
                className: `reliability-station-marker ${visualization.className}`,
                html: `<span style="background: ${visualization.color};"></span>`,
                iconSize: [13, 13],
                iconAnchor: [6, 6],
                popupAnchor: [0, -7]
            }),
            interactive: true,
            keyboard: true,
            riseOnHover: true,
            title: visualization.title
        });
        bindStationMarkerClick(marker, station);
        marker.addTo(state.reliabilityStationLayer);
        state.reliabilityStationMarkersById.set(station.stationId, marker);
    });
    updateSelectedStationMarker();
}

async function loadReliabilityLayer(layer) {
    if (state.reliabilityLayerLoading) {
        return;
    }

    state.reliabilityLayerLoading = true;
    state.reliabilityCurrentLayer = layer;
    setReliabilityStatus(`Loading ${LAYER_LABELS[layer] || layer}...`);

    try {
        const payload = state.reliabilitySurfaceData[layer] || await fetchReliabilitySurface(layer);
        state.reliabilitySurfaceData[layer] = payload;
        const bounds = reliabilityBounds(payload);

        if (!bounds) {
            throw new Error("Reliability surface did not include bounds.");
        }

        if (state.reliabilityImageLayer) {
            state.reliabilityImageLayer.remove();
        }

        state.reliabilityImageLayer = L.imageOverlay(
            activeImageUrlForPayload(payload, layer),
            bounds,
            {
                pane: "reliabilityRasterPane",
                opacity: (RELIABILITY_MAP_MODES[activeReliabilityMapMode()] || RELIABILITY_MAP_MODES.quality).rasterOpacity,
                interactive: false
            }
        ).addTo(state.reliabilityMap);

        updateReliabilityModeControls();
        updateReliabilityRasterVisibility();
        updateBoundary(payload);
        updateStationMarkers(payload);
        renderReliabilityOverview(payload);
        state.reliabilityMap.fitBounds(bounds, {
            padding: [20, 20],
            maxZoom: 7
        });

        setReliabilityStatus(reliabilityStatusForPayload(payload));
    } catch (error) {
        console.warn("Could not load reliability surface:", error);
        setReliabilityStatus("Reliability artifacts unavailable");
        if (elements.reliabilityResultsContainer) {
            elements.reliabilityResultsContainer.innerHTML = `
                <div class="card">
                    <h2>Reliability Inspector</h2>
                    <div class="error">
                        Reliability artifacts are not available yet. Build
                        weather_reconstruction_model/model_runs/paloma_v1_reliability first.
                    </div>
                </div>
            `;
        }
    } finally {
        state.reliabilityLayerLoading = false;
        refreshReliabilityMapSize();
    }
}

async function sampleReliabilityPoint(latitude, longitude) {
    if (!elements.reliabilityResultsContainer) {
        return;
    }

    if (state.reliabilitySelectedMarker) {
        state.reliabilitySelectedMarker.setLatLng([latitude, longitude]);
    } else {
        state.reliabilitySelectedMarker = L.circleMarker([latitude, longitude], {
            pane: "reliabilitySelectionPane",
            radius: 8,
            color: "#0f172a",
            fillColor: "#ffffff",
            fillOpacity: 0.95,
            interactive: false,
            weight: 3
        }).addTo(state.reliabilityMap);
    }

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>Reliability Inspector</h2>
            <p class="placeholder">Sampling ${LAYER_LABELS[state.reliabilityCurrentLayer]} at ${formatNumber(latitude, 6)}, ${formatNumber(longitude, 6)}...</p>
        </div>
    `;

    try {
        const data = await fetchReliabilitySample(state.reliabilityCurrentLayer, latitude, longitude);
        renderReliabilitySample(data);
    } catch (error) {
        renderReliabilitySample({
            status: "error",
            message: "Could not sample this point. It may be outside the basin mask or the backend may be unavailable."
        });
    }
}

export function bindReliabilityControls() {
    if (elements.reliabilityLayerSelect) {
        elements.reliabilityLayerSelect.addEventListener("change", event => {
            if (event.target.selectedOptions[0] && event.target.selectedOptions[0].disabled) {
                event.target.value = state.reliabilityCurrentLayer;
                return;
            }

            loadReliabilityLayer(event.target.value);
        });
    }

    if (elements.reliabilityStationToggle) {
        elements.reliabilityStationToggle.addEventListener("change", () => {
            const payload = state.reliabilitySurfaceData[state.reliabilityCurrentLayer];
            if (payload) {
                updateStationMarkers(payload);
                setReliabilityStatus(reliabilityStatusForPayload(payload));
            }
        });
    }

    if (elements.reliabilityMapModeSelect) {
        elements.reliabilityMapModeSelect.addEventListener("change", event => {
            applyReliabilityMapMode(event.target.value);
        });
    }
}

export function initializeReliabilityMap() {
    if (state.reliabilityMap || typeof L === "undefined") {
        refreshReliabilityMapSize();
        return;
    }

    const mapElement = document.getElementById("reliability-map");
    mapElement.style.height = "62vh";
    mapElement.style.width = "100%";

    state.reliabilityMap = L.map("reliability-map", {
        scrollWheelZoom: true,
        zoomControl: true
    });

    L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 18,
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, USGS, NOAA"
        }
    ).addTo(state.reliabilityMap);

    state.reliabilityMap.createPane("reliabilityRasterPane");
    state.reliabilityMap.getPane("reliabilityRasterPane").style.zIndex = 350;
    state.reliabilityMap.createPane("reliabilityStationPane");
    state.reliabilityMap.getPane("reliabilityStationPane").style.zIndex = 380;
    state.reliabilityMap.createPane("reliabilitySelectionPane");
    state.reliabilityMap.getPane("reliabilitySelectionPane").style.zIndex = 400;
    state.reliabilityMap.getPane("reliabilitySelectionPane").style.pointerEvents = "none";

    state.reliabilityStationLayer = L.layerGroup().addTo(state.reliabilityMap);
    state.reliabilityMap.setView([39.5, -107.0], 6);
    state.reliabilityMap.on("click", event => {
        if (activeReliabilityMapMode() === "quality") {
            sampleReliabilityPoint(event.latlng.lat, event.latlng.lng);
        }
    });

    updateReliabilityModeControls();
    fetchReliabilitySummary()
        .then(summary => {
            applyReliabilitySummary(summary);
            return loadReliabilityLayer(state.reliabilityCurrentLayer);
        })
        .catch(error => {
            console.warn("Could not load reliability summary:", error);
            loadReliabilityLayer(state.reliabilityCurrentLayer);
        });
    requestAnimationFrame(refreshReliabilityMapSize);
    setTimeout(refreshReliabilityMapSize, 100);
    setTimeout(refreshReliabilityMapSize, 500);
    window.addEventListener("resize", refreshReliabilityMapSize);
}
