export function stationHasCoordinates(station) {
    return station &&
           station.latitude !== null &&
           station.latitude !== undefined &&
           station.longitude !== null &&
           station.longitude !== undefined &&
           !Number.isNaN(Number(station.latitude)) &&
           !Number.isNaN(Number(station.longitude));
}

export function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

export function confidenceColor(score) {
    const numericScore = Number(score);

    if (numericScore >= 85) {
        return "#22c55e";
    }

    if (numericScore >= 75) {
        return "#14b8a6";
    }

    if (numericScore >= 65) {
        return "#eab308";
    }

    if (numericScore >= 50) {
        return "#f97316";
    }

    return "#ef4444";
}

export function confidenceStrokeColor(score) {
    const numericScore = Number(score);

    if (numericScore >= 85) {
        return "#15803d";
    }

    if (numericScore >= 75) {
        return "#0f766e";
    }

    if (numericScore >= 65) {
        return "#a16207";
    }

    if (numericScore >= 50) {
        return "#c2410c";
    }

    return "#b91c1c";
}

export function confidenceMarkerRadius(score) {
    const numericScore = Number(score);

    if (numericScore >= 85) {
        return 4.6;
    }

    if (numericScore >= 75) {
        return 4.2;
    }

    if (numericScore >= 65) {
        return 3.8;
    }

    return 3.5;
}

export function confidenceTone(score) {
    const numericScore = Number(score);

    if (numericScore >= 85) {
        return "very-high";
    }

    if (numericScore >= 75) {
        return "high";
    }

    if (numericScore >= 65) {
        return "moderate";
    }

    if (numericScore >= 50) {
        return "low";
    }

    return "very-low";
}

export function confidencePointScore(point) {
    const confidence = Number(point.confidence);
    if (!Number.isNaN(confidence)) {
        return confidence;
    }

    const supportScore = Number(point.score);
    return Number.isNaN(supportScore) ? 0 : supportScore;
}

export function confidencePointLabel(point) {
    const score = confidencePointScore(point);
    return point.label || (
        score >= 85 ? "Very high confidence" :
        score >= 75 ? "High confidence" :
        score >= 65 ? "Moderate confidence" :
        score >= 50 ? "Low confidence" :
        "Very low confidence"
    );
}

export function formatNearestConfidenceStation(point) {
    if (point.stationId) {
        return `Station: ${point.stationId}`;
    }

    const nearestStations = point.nearestStations || [];
    const nearest = nearestStations[0];

    if (!nearest) {
        return "Station: N/A";
    }

    return `${nearest.stationId} (${formatNumber(nearest.distanceKm, 1)} km)`;
}

export function confidencePointPopupHtml(point) {
    const score = confidencePointScore(point);
    const expectedMae = Number(point.expectedMaeF);
    const observedMae = Number(point.observedMaeF);
    const riskReasons = point.physicalRiskReasons || [];
    const riskHtml = riskReasons.length
        ? riskReasons.map(reason => `<li>${escapeHtml(reason)}</li>`).join("")
        : "<li>No physical risk reasons attached.</li>";
    const nearestStations = point.nearestStations || [];
    const nearestHtml = nearestStations.length
        ? nearestStations.map(station => `
            <li>
                ${escapeHtml(station.stationId)} ${escapeHtml(station.stationRole || "")}
                - ${formatNumber(station.distanceKm, 1)} km
            </li>
        `).join("")
        : "<li>N/A</li>";

    return `
        <strong>${escapeHtml(confidencePointLabel(point))}</strong><br>
        Calibrated confidence: ${formatNumber(score, 1)}<br>
        ${Number.isNaN(expectedMae) ? "" : `Expected MAE: ${formatNumber(expectedMae, 2)} F<br>`}
        ${point.stationId ? `Station: ${escapeHtml(point.stationName || point.stationId)} (${escapeHtml(point.stationId)})<br>` : ""}
        ${Number.isNaN(observedMae) ? "" : `Observed validation MAE: ${formatNumber(observedMae, 2)} F<br>`}
        ${formatNumber(point.latitude, 4)}, ${formatNumber(point.longitude, 4)}
        <div style="margin-top: 8px;"><strong>Risk reasons</strong></div>
        <ul style="margin: 4px 0 0 18px; padding: 0;">${riskHtml}</ul>
        ${nearestStations.length ? `
            <div style="margin-top: 8px;"><strong>Nearest supporting stations</strong></div>
            <ul style="margin: 4px 0 0 18px; padding: 0;">
                ${nearestHtml}
            </ul>
        ` : ""}
    `;
}

export function confidenceComponentLabel(name) {
    const labels = {
        stationCoverage: "Station coverage",
        hubSupport: "Hub support",
        dataQuality: "Data quality",
        elevationMatch: "Elevation match",
        terrainSimilarity: "Terrain similarity",
        terrainComplexity: "Terrain complexity",
        validationEvidence: "Validation evidence",
        extrapolationRisk: "Extrapolation risk"
    };

    return labels[name] || name;
}

export function stationLatLng(station) {
    if (!stationHasCoordinates(station)) {
        return null;
    }

    return [Number(station.latitude), Number(station.longitude)];
}

export function formatNumber(value, digits = 2) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "N/A";
    }

    return Number(value).toFixed(digits);
}

export function calculateDistanceKm(latitudeA, longitudeA, latitudeB, longitudeB) {
    const earthRadiusKm = 6371.0;
    const toRadians = degrees => degrees * Math.PI / 180.0;

    const latA = Number(latitudeA);
    const lonA = Number(longitudeA);
    const latB = Number(latitudeB);
    const lonB = Number(longitudeB);

    if ([latA, lonA, latB, lonB].some(value => Number.isNaN(value))) {
        return null;
    }

    const deltaLatitude = toRadians(latB - latA);
    const deltaLongitude = toRadians(lonB - lonA);
    const startLatitude = toRadians(latA);
    const endLatitude = toRadians(latB);

    const haversine =
        Math.sin(deltaLatitude / 2) * Math.sin(deltaLatitude / 2) +
        Math.cos(startLatitude) * Math.cos(endLatitude) *
        Math.sin(deltaLongitude / 2) * Math.sin(deltaLongitude / 2);

    return earthRadiusKm * 2 * Math.atan2(Math.sqrt(haversine), Math.sqrt(1 - haversine));
}

export function renderMetric(label, value) {
    return `
        <div class="metric">
            <div class="metric-label">${label}</div>
            <div class="metric-value">${value}</div>
        </div>
    `;
}

export function formatObservationPeriod(station) {
    if (!station ||
        !station.fullObservationStartYear ||
        !station.fullObservationEndYear ||
        Number(station.fullObservationStartYear) <= 0 ||
        Number(station.fullObservationEndYear) <= 0) {
        return "N/A";
    }

    return `${station.fullObservationStartYear}-${station.fullObservationEndYear}`;
}

export function formatPreparedObservationPeriod(station) {
    if (!station ||
        !station.preparedObservationStartYear ||
        !station.preparedObservationEndYear ||
        Number(station.preparedObservationStartYear) <= 0 ||
        Number(station.preparedObservationEndYear) <= 0) {
        return "N/A";
    }

    return `${station.preparedObservationStartYear}-${station.preparedObservationEndYear}`;
}

export function stationRoleLabel(station) {
    if (station && station.isHubStation) {
        return "Hub station";
    }

    return "Target station";
}

export function matchTerms(data) {
    const hubMode = data && data.matchMode === "hub_to_hub";

    return {
        bestHeading: hubMode ? "Most Similar Hub" : "Best Proxy Station",
        tableHeading: hubMode ? "Most Similar Hub Matches" : "Top Proxy Matches",
        tableStationHeading: hubMode ? "Similar Hub" : "Proxy Station",
        mapStationLabel: hubMode ? "Similar Hub" : "Proxy Station",
        chartProxyLabel: hubMode ? "Similar hub" : "Proxy station",
        emptyMessage: hubMode ? "No valid similar hub was found." : "No valid proxy station was found.",
        summaryNoun: hubMode ? "This similar hub" : "This proxy"
    };
}

export function clampPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return 0;
    }

    return Math.max(0, Math.min(100, Number(value)));
}

export function renderScoreItem(label, value, percent) {
    return `
        <div class="score-item">
            <div class="score-label">${label}</div>
            <div class="score-bar">
                <div class="score-fill" style="width: ${clampPercent(percent)}%;"></div>
            </div>
            <div class="score-value">${value}</div>
        </div>
    `;
}

export function correlationPercent(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return 0;
    }

    return Math.max(0, Math.min(100, Number(value) * 100));
}

export function inversePercent(value, excellent, poor) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return 0;
    }

    const numericValue = Number(value);
    if (numericValue <= excellent) {
        return 100;
    }

    if (numericValue >= poor) {
        return 0;
    }

    return 100 - ((numericValue - excellent) / (poor - excellent) * 100);
}
