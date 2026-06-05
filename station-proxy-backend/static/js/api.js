// Purpose: Wrap backend fetch calls for engine status, analysis, confidence, reliability, and model-run data.

export async function fetchEngineStatus() {
    const response = await fetch("/test");
    return response.json();
}

export async function fetchLocationAnalysis(latitude, longitude) {
    const query = `lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`;
    const response = await fetch(`/analyze-location?${query}`);
    return response.json();
}

export async function fetchConfidenceGrid() {
    const response = await fetch("/model-runs/current/confidence-grid");
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }

    return response.json();
}

export function confidenceAnalysisUrls(latitude, longitude) {
    const query = `lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`;
    const urls = [`/analyze-confidence?${query}`];

    if (window.location.hostname === "127.0.0.1" && window.location.port !== "8000") {
        urls.push(`http://127.0.0.1:8000/analyze-confidence?${query}`);
    }

    return urls;
}

export async function fetchConfidenceSupport(latitude, longitude) {
    let lastError = null;

    for (const url of confidenceAnalysisUrls(latitude, longitude)) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            if (data && typeof data === "object" && url.startsWith("http://")) {
                data.__apiBaseUrl = new URL(url).origin;
            }

            return data;
        } catch (error) {
            lastError = error;
        }
    }

    throw lastError;
}

function backendUrls(path) {
    const urls = [path];

    if (window.location.hostname === "127.0.0.1" && window.location.port !== "8000") {
        urls.push(`http://127.0.0.1:8000${path}`);
    }

    return urls;
}

async function fetchFirstJson(path) {
    let lastError = null;

    for (const url of backendUrls(path)) {
        try {
            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            return response.json();
        } catch (error) {
            lastError = error;
        }
    }

    throw lastError;
}

export async function fetchReliabilitySummary() {
    return fetchFirstJson("/model-runs/reliability/summary");
}

export async function fetchReliabilitySurface(layer = "overall") {
    const query = `layer=${encodeURIComponent(layer)}`;
    return fetchFirstJson(`/model-runs/reliability/surface?${query}`);
}

export async function fetchReliabilitySample(layer, latitude, longitude) {
    const query = [
        `layer=${encodeURIComponent(layer)}`,
        `lat=${encodeURIComponent(latitude)}`,
        `lon=${encodeURIComponent(longitude)}`
    ].join("&");
    return fetchFirstJson(`/model-runs/reliability/sample?${query}`);
}

export async function fetchReliabilityStationDetails(layer, stationId) {
    const query = [
        `layer=${encodeURIComponent(layer)}`,
        `station_id=${encodeURIComponent(stationId)}`
    ].join("&");
    return fetchFirstJson(`/model-runs/reliability/station?${query}`);
}
