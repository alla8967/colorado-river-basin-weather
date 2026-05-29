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

            return response.json();
        } catch (error) {
            lastError = error;
        }
    }

    throw lastError;
}
