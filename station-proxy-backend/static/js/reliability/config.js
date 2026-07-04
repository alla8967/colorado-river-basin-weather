// Purpose: Define reliability map modes, layer labels, legends, and per-mode metric configs.

import { state } from "../state.js";
import {
    classifyErrorMetric,
    classifyFinalModelError,
    classifyHoldoutBias,
    classifyHoldoutCorrelation
} from "./metrics.js?v=tabs-v1";

export const LAYER_LABELS = {
    helpfulness: "Model Helpfulness",
    overall: "Overall Reliability",
    tavg: "TAVG Reliability",
    tmin: "TMIN Reliability",
    tmax: "TMAX Reliability"
};

export const RELIABILITY_MAP_MODES = {
    quality: {
        label: "Overall Reconstruction Quality",
        rasterOpacity: 0.72,
        help: "Overall combines station-holdout correlation, MAE, and RMSE. Green means the daily reconstruction was strong; red means the station failed one or more quality thresholds. Click the raster for a grid cell or a station point for station detail.",
        legendNote: "Overall quality uses all three holdout metrics together: correlation, MAE, and RMSE."
    },
    correlation: {
        label: "Station Holdout Correlation",
        rasterOpacity: 0.68,
        help: "Holdout Correlation shows only daily timing/shape agreement. High correlation is green, low correlation is red; this view intentionally ignores MAE, RMSE, and bias.",
        legendNote: "Correlation is plotted alone: green is high agreement, red is low agreement."
    },
    mae: {
        label: "Station Holdout MAE",
        rasterOpacity: 0.68,
        help: "Holdout MAE shows mean absolute reconstruction error when each station was withheld. Green means lower daily error and red means higher daily error.",
        legendNote: "Holdout MAE is plotted alone: green is low average absolute error, red is high average absolute error."
    },
    rmse: {
        label: "Station Holdout RMSE",
        rasterOpacity: 0.68,
        help: "Holdout RMSE shows root mean squared reconstruction error when each station was withheld. Green means lower daily error; red highlights stations with larger misses and outlier-sensitive error.",
        legendNote: "Holdout RMSE is plotted alone: green is low squared-error magnitude, red is high squared-error magnitude."
    },
    bias: {
        label: "Station Holdout Bias",
        rasterOpacity: 0.68,
        help: "Holdout Bias shows whether the reconstruction was generally hot, cold, or just right. Bias is actual minus predicted: red means the model predicted too hot, green means near unbiased, and blue means the model predicted too cold.",
        legendNote: "Bias = actual - predicted. Negative values mean the model was too hot; positive values mean it was too cold."
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
    }
};

export const RELIABILITY_LEGENDS = {
    quality: [
        ["quality-excellent", "Excellent: r >= 0.97, MAE <= 1.25 F, RMSE <= 2.0 F"],
        ["quality-strong", "Strong: r >= 0.95, MAE <= 2.0 F, RMSE <= 3.0 F"],
        ["quality-acceptable", "Acceptable: r >= 0.90, MAE <= 2.5 F, RMSE <= 3.5 F"],
        ["quality-weak", "Weak: r >= 0.80, MAE <= 4.0 F, RMSE <= 5.0 F"],
        ["quality-poor", "Poor: below weak thresholds"],
        ["quality-unknown", "Unknown: insufficient metrics"]
    ],
    correlation: [
        ["correlation-excellent", "Green, excellent: r >= 0.995"],
        ["correlation-very-strong", "Green-teal, very strong: r >= 0.990"],
        ["correlation-strong", "Light green, strong: r >= 0.980"],
        ["correlation-moderate", "Yellow, moderate: r >= 0.950"],
        ["correlation-weak", "Orange, weak: r >= 0.900"],
        ["correlation-poor", "Red, low: r < 0.900"],
        ["correlation-unknown", "Unknown: no correlation metric"]
    ],
    mae: [
        ["error-excellent", "Green, very low error: MAE <= 1.25 F"],
        ["error-strong", "Green-teal, low error: MAE <= 2.0 F"],
        ["error-acceptable", "Yellow, moderate error: MAE <= 2.5 F"],
        ["error-weak", "Orange, high error: MAE <= 4.0 F"],
        ["error-poor", "Red, very high error: MAE > 4.0 F"],
        ["error-unknown", "Unknown: no holdout MAE metric"]
    ],
    rmse: [
        ["error-excellent", "Green, very low error: RMSE <= 2.0 F"],
        ["error-strong", "Green-teal, low error: RMSE <= 3.0 F"],
        ["error-acceptable", "Yellow, moderate error: RMSE <= 3.5 F"],
        ["error-weak", "Orange, high error: RMSE <= 5.0 F"],
        ["error-poor", "Red, very high error: RMSE > 5.0 F"],
        ["error-unknown", "Unknown: no holdout RMSE metric"]
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
    ]
};

export const HOLDOUT_ERROR_METRIC_CONFIGS = {
    mae: {
        title: "Holdout MAE Map",
        metricLabel: "MAE",
        field: "observedMaeF",
        suffix: " F",
        digits: 2,
        classify: value => classifyErrorMetric(
            value,
            "MAE",
            "Unknown",
            "No station holdout MAE metric is available."
        )
    },
    rmse: {
        title: "Holdout RMSE Map",
        metricLabel: "RMSE",
        field: "observedRmseF",
        suffix: " F",
        digits: 2,
        classify: value => classifyErrorMetric(
            value,
            "RMSE",
            "Unknown",
            "No station holdout RMSE metric is available."
        )
    }
};

export const FINAL_MODEL_METRIC_CONFIGS = {
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

export function activeReliabilityMapMode() {
    return RELIABILITY_MAP_MODES[state.reliabilityMapMode]
        ? state.reliabilityMapMode
        : "quality";
}

export function finalModelMetricConfig(mode) {
    return FINAL_MODEL_METRIC_CONFIGS[mode] || null;
}

export function holdoutErrorMetricConfig(mode) {
    return HOLDOUT_ERROR_METRIC_CONFIGS[mode] || null;
}

export function isFinalModelMetricMode(mode) {
    return Boolean(finalModelMetricConfig(mode));
}

export function isHoldoutErrorMetricMode(mode) {
    return Boolean(holdoutErrorMetricConfig(mode));
}

export function isStationMetricOverlayMode(mode) {
    return mode === "bias" || mode === "correlation" || isHoldoutErrorMetricMode(mode) || isFinalModelMetricMode(mode);
}
