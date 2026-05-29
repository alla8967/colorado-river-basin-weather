import { fetchConfidenceGrid, fetchConfidenceSupport } from "./api.js";
import { elements, state } from "./state.js";
import {
    clampPercent,
    confidenceColor,
    confidenceComponentLabel,
    confidenceMarkerRadius,
    confidencePointLabel,
    confidencePointPopupHtml,
    confidencePointScore,
    confidenceStrokeColor,
    confidenceTone,
    escapeHtml,
    formatNearestConfidenceStation,
    formatNumber
} from "./formatters.js";

export function setConfidenceLayerStatus(message) {
    if (elements.confidenceLayerStatus) {
        elements.confidenceLayerStatus.textContent = message;
    }
}

export function renderSupportScoreItem(label, value) {
    const numericValue = Number(value);
    const safeValue = Number.isNaN(numericValue) ? 0 : numericValue;

    return `
        <div class="score-item">
            <div class="score-label">${escapeHtml(label)}</div>
            <div class="score-bar">
                <div class="score-fill" style="width: ${clampPercent(safeValue)}%; background: ${confidenceColor(safeValue)};"></div>
            </div>
            <div class="score-value">${formatNumber(safeValue, 1)}</div>
        </div>
    `;
}

export function renderConfidenceSupportResult(data) {
    if (!elements.confidenceResultsContainer) {
        return;
    }

    if (!data || data.status !== "ok") {
        elements.confidenceResultsContainer.innerHTML = `
            <div class="card">
                <h2>Clicked Point Support Estimate</h2>
                <div class="error">${escapeHtml(data && data.message ? data.message : "Could not calculate point support.")}</div>
            </div>
        `;
        return;
    }

    const components = data.components || {};
    const componentHtml = Object.keys(components).sort().map(name => (
        renderSupportScoreItem(
            confidenceComponentLabel(name),
            components[name]
        )
    )).join("");
    const nearestStations = data.nearestStations || [];
    const nearestRows = nearestStations.length ? nearestStations.map(station => `
        <tr>
            <td>${escapeHtml(station.stationId)}</td>
            <td>${escapeHtml(station.stationRole || "N/A")}</td>
            <td>${formatNumber(station.distanceKm, 1)} km</td>
            <td>${station.elevationDifferenceM === null || station.elevationDifferenceM === undefined ? "N/A" : `${formatNumber(station.elevationDifferenceM, 1)} m`}</td>
        </tr>
    `).join("") : `
        <tr>
            <td class="support-empty-row" colspan="4">No supporting stations returned.</td>
        </tr>
    `;
    const reasonsHtml = (data.reasons || []).map(reason => `
        <li>${escapeHtml(reason)}</li>
    `).join("");
    const warningsHtml = (data.warnings || []).map(warning => `
        <li>${escapeHtml(warning)}</li>
    `).join("");
    const tone = confidenceTone(data.score);

    elements.confidenceResultsContainer.innerHTML = `
        <div class="card support-card">
            <div class="support-hero">
                <div>
                    <h2>Clicked Point Support Estimate</h2>
                    <p class="support-meta">
                        ${formatNumber(data.latitude, 6)}, ${formatNumber(data.longitude, 6)}
                        ${data.modelReference ? ` | ${escapeHtml(data.modelReference)}` : ""}
                    </p>
                </div>
                <div class="support-score-badge ${tone}">
                    <span class="support-score-number">${formatNumber(data.score, 1)}</span>
                    <span class="support-score-label">${escapeHtml(data.label)}</span>
                </div>
            </div>

            <div class="support-body">
                <section class="support-section">
                    <h3>Component Scores</h3>
                    <div class="score-band">
                        ${componentHtml}
                    </div>
                </section>

                <section class="support-section">
                    <h3>Reasons</h3>
                    <ul class="support-list">
                        ${reasonsHtml || "<li>No reasons returned.</li>"}
                    </ul>
                </section>

                ${warningsHtml ? `
                    <section class="support-section">
                        <h3>Warnings</h3>
                        <ul class="support-warning-list">
                            ${warningsHtml}
                        </ul>
                    </section>
                ` : ""}

                <section class="support-section">
                    <h3>Nearest Supporting Stations</h3>
                    <div class="support-table-wrap">
                        <table>
                            <thead>
                                <tr>
                                    <th>Station</th>
                                    <th>Role</th>
                                    <th>Distance</th>
                                    <th>Elev. Diff</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${nearestRows}
                            </tbody>
                        </table>
                    </div>
                </section>
            </div>
        </div>
    `;
}

export function renderConfidencePoints(payload) {
    if (!state.confidenceMap || !state.confidencePointLayer || !payload || !Array.isArray(payload.points)) {
        return;
    }

    state.confidencePointLayer.clearLayers();

    payload.points.forEach(point => {
        const latitude = Number(point.latitude);
        const longitude = Number(point.longitude);
        const score = confidencePointScore(point);
        const label = confidencePointLabel(point);

        if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
            return;
        }

        const marker = L.circleMarker([latitude, longitude], {
            pane: "confidencePane",
            radius: confidenceMarkerRadius(score),
            color: confidenceStrokeColor(score),
            fillColor: confidenceColor(score),
            fillOpacity: 0.72,
            opacity: 0.9,
            weight: 1
        });

        marker.bindTooltip(
            `${label}: ${formatNumber(score, 1)} | ${formatNearestConfidenceStation(point)}`,
            {
                sticky: true,
                direction: "top"
            }
        );
        marker.bindPopup(confidencePointPopupHtml(point));
        marker.addTo(state.confidencePointLayer);
    });

    if (!state.confidenceMap.hasLayer(state.confidencePointLayer)) {
        state.confidencePointLayer.addTo(state.confidenceMap);
    }
}

export async function analyzeConfidencePoint(latitude, longitude) {
    if (!elements.confidenceResultsContainer) {
        return;
    }

    if (state.confidenceSelectedMarker) {
        state.confidenceSelectedMarker.setLatLng([latitude, longitude]);
    } else if (state.confidenceMap) {
        state.confidenceSelectedMarker = L.circleMarker([latitude, longitude], {
            pane: "confidenceSelectionPane",
            radius: 9,
            color: "#0f172a",
            fillColor: "#ffffff",
            fillOpacity: 0.95,
            opacity: 1,
            weight: 3
        }).addTo(state.confidenceMap);
    }

    if (state.confidenceSelectedMarker) {
        state.confidenceSelectedMarker.bindPopup(`
            <strong>Selected support-estimate point</strong><br>
            ${formatNumber(latitude, 6)}, ${formatNumber(longitude, 6)}
        `);
        state.confidenceSelectedMarker.openPopup();
    }

    elements.confidenceResultsContainer.innerHTML = `
        <div class="card">
            <h2>Clicked Point Support Estimate</h2>
            <p class="placeholder">Calculating support-style score for ${formatNumber(latitude, 6)}, ${formatNumber(longitude, 6)}...</p>
        </div>
    `;

    try {
        const data = await fetchConfidenceSupport(latitude, longitude);
        renderConfidenceSupportResult(data);
        return;
    } catch (error) {
        renderConfidenceSupportResult({
            status: "error",
            message: "Could not connect to the support endpoint. Open the app through FastAPI to use live clicked-point scoring."
        });
    }
}

export async function loadConfidencePoints() {
    if (state.confidencePointData || state.confidenceLayerLoading) {
        return state.confidencePointData;
    }

    state.confidenceLayerLoading = true;
    setConfidenceLayerStatus("Loading calibrated confidence grid...");

    try {
        state.confidencePointData = await fetchConfidenceGrid();
        renderConfidencePoints(state.confidencePointData);
        const pointCount = state.confidencePointData.pointCount || (state.confidencePointData.points || []).length || 0;
        const pointType = state.confidencePointData.pointType === "validation_station_anchor"
            ? "calibrated confidence anchors"
            : (
                state.confidencePointData.pointType === "continuous_support_surface"
                    ? "calibrated surface points"
                    : "confidence points"
            );
        setConfidenceLayerStatus(`${pointCount} ${pointType} loaded`);
        return state.confidencePointData;
    } catch (error) {
        console.warn("Could not load calibrated confidence grid:", error);
        setConfidenceLayerStatus("Calibrated confidence layer unavailable");
        return null;
    } finally {
        state.confidenceLayerLoading = false;
    }
}
