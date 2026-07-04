// Purpose: Classify station holdout and final-model metrics into color-coded quality buckets.

export const QUALITY_UNKNOWN = {
    id: "unknown",
    label: "Unknown",
    color: "#94a3b8",
    description: "Insufficient daily reconstruction metrics for a confident quality class."
};

export function reliabilityColor(score) {
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

export function numericMetric(value) {
    if (value === null || value === undefined || value === "") {
        return null;
    }

    const number = Number(value);
    return Number.isFinite(number) ? number : null;
}

export function classifyDailyTemperatureReconstructionQuality(metrics) {
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

export function classifyHoldoutBias(biasValue, missingDescription = "No station holdout bias metric is available.") {
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

export function classifyHoldoutCorrelation(
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

export function classifyErrorMetric(
    errorValue,
    metricName,
    missingLabel = "Unknown",
    missingDescription = `No station ${metricName} metric is available.`
) {
    const error = numericMetric(errorValue);
    const isRmse = metricName === "RMSE";
    const thresholds = isRmse
        ? { excellent: 2.0, strong: 3.0, acceptable: 3.5, weak: 5.0 }
        : { excellent: 1.25, strong: 2.0, acceptable: 2.5, weak: 4.0 };

    if (error === null) {
        return {
            id: "unknown",
            label: missingLabel,
            color: "#94a3b8",
            description: missingDescription
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

export function classifyFinalModelError(errorValue, metricName) {
    return classifyErrorMetric(
        errorValue,
        metricName,
        "Missing final metric",
        "No final-model station metric row is available."
    );
}

export function stationHoldoutMetricBundle(station) {
    return {
        maeF: station && station.observedMaeF,
        rmseF: station && station.observedRmseF,
        correlation: station && station.observedCorrelation,
        testRows: station && station.testRows
    };
}

export function numericStationValues(stations, valueGetter) {
    return (stations || [])
        .map(station => numericMetric(valueGetter(station)))
        .filter(value => value !== null)
        .sort((a, b) => a - b);
}

export function median(values) {
    if (!values.length) {
        return null;
    }

    const middle = Math.floor(values.length / 2);
    if (values.length % 2) {
        return values[middle];
    }

    return (values[middle - 1] + values[middle]) / 2;
}

export function mean(values) {
    if (!values.length) {
        return null;
    }

    return values.reduce((total, value) => total + value, 0) / values.length;
}
