// Purpose: Wire page controls, tabs, map initialization, and location-analysis form behavior.

import { fetchEngineStatus, fetchLocationAnalysis } from "./api.js";
import { initializeMap, refreshMapSize } from "./maps.js";
import { renderMethodology } from "./methodology.js?v=tabs-v1";
import { renderModelTesting } from "./model-testing.js?v=model-testing-v3";
import { renderReliabilityGuide } from "./reliability-guide.js?v=reliability-guide-v2";
import { bindReliabilityControls, initializeReliabilityMap, refreshReliabilityMapSize } from "./reliability.js?v=reliability-guide-v1";
import { renderResults } from "./results.js?v=low-correlation-v1";
import { elements, state } from "./state.js";

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function activateTab(tabId) {
    document.querySelectorAll(".tab-panel").forEach(panel => {
        panel.classList.toggle("active", panel.id === tabId);
    });

    elements.tabButtons.forEach(button => {
        const isActive = button.dataset.tabTarget === tabId;
        button.classList.toggle("active", isActive);
        button.setAttribute("aria-selected", isActive ? "true" : "false");
    });

    if (tabId === "model-reliability-tab") {
        initializeReliabilityMap();
        setTimeout(refreshReliabilityMapSize, 100);
        return;
    }

    if (tabId === "proxy-tab") {
        refreshMapSize();
    }
}

function missingFilesHtml(files) {
    if (!Array.isArray(files) || files.length === 0) {
        return "";
    }

    const rows = files.map(file => `<li><code>${escapeHtml(file)}</code></li>`).join("");
    return `
        <p>Missing required runtime files:</p>
        <ul>${rows}</ul>
    `;
}

function engineDetailsHtml(data) {
    if (!data.engineDetails) {
        return "";
    }

    return `<p><small>${escapeHtml(data.engineDetails)}</small></p>`;
}

function stationDataNoticeHtml(data) {
    if (!data.stationDataNotice) {
        return "";
    }

    return `<p><small>${escapeHtml(data.stationDataNotice)}</small></p>`;
}

function renderEngineStatus(data) {
    const message = escapeHtml(data.engineMessage || "Station Proxy engine status is unavailable.");

    if (data.engineRunning) {
        state.engineReady = true;
        elements.analyzeButton.disabled = false;
        elements.engineStatus.className = "engine-status ready";
        elements.engineStatus.innerHTML = `
            <strong>Engine Status</strong>
            ${message}
            ${stationDataNoticeHtml(data)}
        `;
        return;
    }

    state.engineReady = false;
    elements.analyzeButton.disabled = true;

    if (data.engineState === "missing-runtime-files") {
        elements.engineStatus.className = "engine-status offline";
        elements.engineStatus.innerHTML = `
            <strong>Engine Status</strong>
            ${message}
            ${missingFilesHtml(data.missingFiles)}
            <p>Generate or point the backend at the app-ready NOAA files, then restart FastAPI.</p>
            ${stationDataNoticeHtml(data)}
            ${engineDetailsHtml(data)}
        `;
        return;
    }

    if (data.engineState === "exited") {
        elements.engineStatus.className = "engine-status offline";
        elements.engineStatus.innerHTML = `
            <strong>Engine Status</strong>
            ${message}
            ${engineDetailsHtml(data)}
        `;
        return;
    }

    elements.engineStatus.className = "engine-status loading";
    elements.engineStatus.innerHTML = `
        <strong>Engine Status</strong>
        ${message}
        ${stationDataNoticeHtml(data)}
        ${engineDetailsHtml(data)}
    `;
}

async function checkEngineStatus() {
    try {
        const data = await fetchEngineStatus();
        renderEngineStatus(data);
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

function analyzePresetLocation(button) {
    document.getElementById("latitude").value = button.dataset.presetLat;
    document.getElementById("longitude").value = button.dataset.presetLon;
    analyzeLocation();
}

function bindEvents() {
    elements.analyzeButton.addEventListener("click", analyzeLocation);
    elements.presetButtons.forEach(button => {
        button.addEventListener("click", function() {
            analyzePresetLocation(this);
        });
    });
    bindReliabilityControls();
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
    renderMethodology();
    renderModelTesting();
    renderReliabilityGuide();
    bindEvents();
    initializeMap();
    checkEngineStatus();
    setInterval(checkEngineStatus, 3000);
}

startApp();
