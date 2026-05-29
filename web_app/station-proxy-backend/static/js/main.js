import { fetchEngineStatus, fetchLocationAnalysis } from "./api.js";
import { initializeConfidenceMap, initializeMap, refreshConfidenceMapSize, refreshMapSize } from "./maps.js";
import { renderResults } from "./results.js";
import { elements, state } from "./state.js";

function activateTab(tabId) {
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === tabId);
    });

    elements.tabButtons.forEach(button => {
        button.classList.toggle("active", button.dataset.tabTarget === tabId);
    });

    if (tabId === "model-support-tab") {
        initializeConfidenceMap();
        setTimeout(refreshConfidenceMapSize, 100);
        return;
    }

    refreshMapSize();
}

async function checkEngineStatus() {
    try {
        const data = await fetchEngineStatus();

        if (data.engineRunning) {
            state.engineReady = true;
            elements.analyzeButton.disabled = false;
            elements.engineStatus.className = "engine-status ready";
            elements.engineStatus.innerHTML = `
                <strong>Engine Status</strong>
                Ready. The persistent C++ station engine is running and loaded.
            `;
        } else {
            state.engineReady = false;
            elements.analyzeButton.disabled = true;
            elements.engineStatus.className = "engine-status loading";
            elements.engineStatus.innerHTML = `
                <strong>Engine Status</strong>
                Backend is reachable, but the C++ station engine is still starting or unavailable.
            `;
        }
    } catch (error) {
        state.engineReady = false;
        elements.analyzeButton.disabled = true;
        elements.engineStatus.className = "engine-status offline";
        elements.engineStatus.innerHTML = `
            <strong>Engine Status</strong>
            Backend offline. Start FastAPI first, then wait for the C++ engine to finish loading.
        `;
    }
}

async function analyzeLocation() {
    if (!state.engineReady) {
        elements.resultsContainer.innerHTML = `
            <div class="card">
                <h2>Engine Not Ready</h2>
                <p class="placeholder">The backend or persistent C++ station engine is not ready yet. Start FastAPI and wait for the engine status to turn green.</p>
            </div>
        `;
        return;
    }

    const latitude = document.getElementById("latitude").value;
    const longitude = document.getElementById("longitude").value;

    elements.analyzeButton.disabled = true;
    elements.analyzeButton.textContent = "Running C++ Engine...";

    elements.resultsContainer.innerHTML = `
        <div class="card">
            <h2>Running Analysis</h2>
            <p class="placeholder">Calling FastAPI and running the C++ station-matching engine...</p>
        </div>
    `;

    try {
        const data = await fetchLocationAnalysis(latitude, longitude);
        renderResults(data);
    } catch (error) {
        elements.resultsContainer.innerHTML = `
            <div class="card">
                <h2>Error</h2>
                <div class="error">Could not connect to the backend. Make sure FastAPI is running.</div>
            </div>
        `;
    } finally {
        elements.analyzeButton.disabled = false;
        elements.analyzeButton.textContent = "Analyze Location";
    }
}

function bindEvents() {
    elements.analyzeButton.addEventListener("click", analyzeLocation);
    elements.tabButtons.forEach(button => {
        button.addEventListener("click", function() {
            activateTab(this.dataset.tabTarget);
        });
    });

    window.addEventListener("DOMContentLoaded", initializeMap);
    window.addEventListener("load", function() {
        initializeMap();
        setTimeout(refreshMapSize, 250);
        setTimeout(refreshMapSize, 750);
    });
}

function startApp() {
    bindEvents();
    initializeMap();
    checkEngineStatus();
    setInterval(checkEngineStatus, 3000);
}

startApp();
