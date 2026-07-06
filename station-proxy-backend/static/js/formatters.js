// Purpose: Collect display formatting, numeric, station, and map-label helpers for the frontend.

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
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
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
            <div class="metric-label">${escapeHtml(label)}</div>
            <div class="metric-value">${escapeHtml(value)}</div>
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
            <div class="score-label">${escapeHtml(label)}</div>
            <div class="score-bar">
                <div class="score-fill" style="width: ${clampPercent(percent)}%;"></div>
            </div>
            <div class="score-value">${escapeHtml(value)}</div>
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
