// Purpose: Wrap backend fetch calls for engine status, analysis, confidence, reliability, and model-run data.

export async function fetchEngineStatus() {
    return fetchFirstJson("/test");
}

export async function fetchLocationAnalysis(latitude, longitude) {
    const query = `lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`;
    return fetchFirstJson(`/analyze-location?${query}`);
}

export async function fetchConfidenceGrid() {
    return fetchFirstJson("/model-runs/current/confidence-grid");
}

export function confidenceAnalysisUrls(latitude, longitude) {
    const query = `lat=${encodeURIComponent(latitude)}&lon=${encodeURIComponent(longitude)}`;
    return backendUrls(`/analyze-confidence?${query}`);
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
    const urls = [];
    const localBackendOrigins = [
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8001",
    ];
    const localContext = (
        window.location.protocol === "file:" ||
        window.location.hostname === "127.0.0.1" ||
        window.location.hostname === "localhost"
    );

    if (window.location.protocol !== "file:") {
        urls.push(path);
    }

    if (localContext) {
        localBackendOrigins.forEach(origin => {
            if (window.location.origin !== origin) {
                urls.push(`${origin}${path}`);
            }
        });
    }

    return Array.from(new Set(urls));
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
