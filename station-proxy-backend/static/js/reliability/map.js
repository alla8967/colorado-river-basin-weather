// Purpose: Manage the reliability Leaflet map: raster layers, station markers, legends, and controls.

import {
    fetchReliabilitySample,
    fetchReliabilityStationDetails,
    fetchReliabilitySurface,
    fetchReliabilitySummary
} from "../api.js";
import { elements, state } from "../state.js";
import { escapeHtml, formatNumber } from "../formatters.js";
import {
    LAYER_LABELS,
    RELIABILITY_LEGENDS,
    RELIABILITY_MAP_MODES,
    activeReliabilityMapMode,
    finalModelMetricConfig,
    holdoutErrorMetricConfig,
    isStationMetricOverlayMode
} from "./config.js?v=tabs-v1";
import {
    classifyDailyTemperatureReconstructionQuality,
    classifyHoldoutBias,
    classifyHoldoutCorrelation,
    numericMetric,
    numericStationValues,
    stationHoldoutMetricBundle
} from "./metrics.js?v=tabs-v1";
import {
    renderReliabilityOverview,
    renderReliabilitySample,
    renderReliabilityStationDetails
} from "./station-details.js?v=reliability-guide-v1";

export function refreshReliabilityMapSize() {
    if (!state.reliabilityMap) {
        return;
    }

    state.reliabilityMap.invalidateSize(true);
}

function setReliabilityStatus(message) {
    if (elements.reliabilityLayerStatus) {
        elements.reliabilityLayerStatus.textContent = message;
    }
}

function reliabilityBounds(payload) {
    const bounds = payload && payload.bounds;
    if (!bounds) {
        return null;
    }

    return [
        [Number(bounds.latMin), Number(bounds.lonMin)],
        [Number(bounds.latMax), Number(bounds.lonMax)]
    ];
}

function renderReliabilityLegend() {
    if (!elements.reliabilityLegend) {
        return;
    }

    const mode = activeReliabilityMapMode();
    const legend = RELIABILITY_LEGENDS[mode] || RELIABILITY_LEGENDS.quality;
    const modeConfig = RELIABILITY_MAP_MODES[mode] || RELIABILITY_MAP_MODES.quality;
    elements.reliabilityLegend.className = `map-legend quality-legend reliability-legend mode-${mode}`;
    elements.reliabilityLegend.innerHTML = `
        <strong class="legend-title">${escapeHtml(modeConfig.label)}</strong>
        ${modeConfig.legendNote ? `<span class="legend-note">${escapeHtml(modeConfig.legendNote)}</span>` : ""}
        ${legend.map(([className, label]) => `
            <span class="legend-item"><span class="legend-dot ${escapeHtml(className)}"></span>${escapeHtml(label)}</span>
        `).join("")}
    `;
}

function updateReliabilityModeControls() {
    const mode = activeReliabilityMapMode();
    const modeConfig = RELIABILITY_MAP_MODES[mode] || RELIABILITY_MAP_MODES.quality;

    if (elements.reliabilityMapModeSelect) {
        elements.reliabilityMapModeSelect.value = mode;
    }

    if (elements.reliabilityMapHelp) {
        elements.reliabilityMapHelp.textContent = modeConfig.help;
    }

    renderReliabilityLegend();
}

function updateReliabilityRasterVisibility() {
    if (!state.reliabilityImageLayer) {
        return;
    }

    const mode = activeReliabilityMapMode();
    const modeConfig = RELIABILITY_MAP_MODES[mode] || RELIABILITY_MAP_MODES.quality;
    state.reliabilityImageLayer.setOpacity(modeConfig.rasterOpacity);
}

function updateReliabilityImageUrl(payload) {
    if (!state.reliabilityImageLayer || !payload) {
        return;
    }

    state.reliabilityImageLayer.setUrl(
        activeImageUrlForPayload(payload, state.reliabilityCurrentLayer)
    );
}

function reliabilityStatusForPayload(payload) {
    if (elements.reliabilityStationToggle && !elements.reliabilityStationToggle.checked) {
        return "Holdout station layer hidden";
    }

    const mode = activeReliabilityMapMode();
    const holdoutErrorConfig = holdoutErrorMetricConfig(mode);
    if (holdoutErrorConfig) {
        const stationCount = numericStationValues(
            payload.holdoutStations || [],
            station => station[holdoutErrorConfig.field]
        ).length;
        return `${stationCount} holdout stations with ${holdoutErrorConfig.metricLabel} plotted`;
    }

    const finalConfig = finalModelMetricConfig(mode);
    if (finalConfig) {
        const stations = payload.holdoutStations || [];
        const stationCount = numericStationValues(
            stations,
            station => station[finalConfig.field]
        ).length;
        const missingCount = Math.max(0, stations.length - stationCount);
        return `${stationCount} stations with final-model ${finalConfig.metricLabel} available; ${missingCount} missing`;
    }

    if (mode === "bias") {
        const stationCount = numericStationValues(payload.holdoutStations || [], station => station.holdoutBiasF).length;
        return `${stationCount} holdout stations with bias plotted`;
    }

    if (mode === "correlation") {
        const stationCount = numericStationValues(payload.holdoutStations || [], station => station.observedCorrelation).length;
        return `${stationCount} holdout stations with correlation plotted`;
    }

    const pointCount = payload.grid && payload.grid.maskedPointCount
        ? payload.grid.maskedPointCount
        : (payload.points || []).length;
    return `${pointCount} masked grid cells loaded`;
}

function stationVisualization(station) {
    const mode = activeReliabilityMapMode();
    const holdoutErrorConfig = holdoutErrorMetricConfig(mode);

    if (holdoutErrorConfig) {
        const value = numericMetric(station && station[holdoutErrorConfig.field]);
        const bucket = holdoutErrorConfig.classify(value);
        const valueText = value === null
            ? "N/A"
            : `${formatNumber(value, holdoutErrorConfig.digits)}${holdoutErrorConfig.suffix}`;
        return {
            className: `error-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | holdout ${holdoutErrorConfig.metricLabel} ${valueText} | r ${formatNumber(station.observedCorrelation, 3)}`
        };
    }

    const finalConfig = finalModelMetricConfig(mode);

    if (finalConfig) {
        const value = numericMetric(station && station[finalConfig.field]);
        const bucket = finalConfig.classify(value);
        const valueText = value === null
            ? "N/A"
            : `${formatNumber(value, finalConfig.digits)}${finalConfig.suffix}`;
        const rowCount = numericMetric(station && station.finalModelRowCount);
        const rowText = rowCount === null ? "rows N/A" : `${formatNumber(rowCount, 0)} rows`;
        const classPrefix = mode === "final-correlation"
            ? "correlation"
            : mode === "final-bias"
                ? "bias"
                : "error";
        return {
            className: `${classPrefix}-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | final ${finalConfig.metricLabel} ${valueText} | ${rowText}`
        };
    }

    if (mode === "bias") {
        const bias = numericMetric(station && station.holdoutBiasF);
        const bucket = classifyHoldoutBias(bias);
        const biasText = bias === null ? "N/A" : `${formatNumber(bias, 2)} F`;
        return {
            className: `bias-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | bias ${biasText} (actual - predicted) | r ${formatNumber(station.observedCorrelation, 3)}`
        };
    }

    if (mode === "correlation") {
        const bucket = classifyHoldoutCorrelation(station && station.observedCorrelation);
        return {
            className: `correlation-${bucket.id}`,
            color: bucket.color,
            title: `${station.stationId}: ${bucket.label} | holdout r ${formatNumber(station.observedCorrelation, 3)}`
        };
    }

    const quality = classifyDailyTemperatureReconstructionQuality(stationHoldoutMetricBundle(station));
    return {
        className: `quality-${quality.id}`,
        color: quality.color,
        title: `${station.stationId}: ${quality.label} | r ${formatNumber(station.observedCorrelation, 3)} | MAE ${formatNumber(station.observedMaeF, 2)} F | RMSE ${formatNumber(station.observedRmseF, 2)} F`
    };
}

function applyReliabilityMapMode(mode) {
    if (!RELIABILITY_MAP_MODES[mode]) {
        return;
    }

    state.reliabilityMapMode = mode;
    updateReliabilityModeControls();
    updateReliabilityRasterVisibility();

    const payload = state.reliabilitySurfaceData[state.reliabilityCurrentLayer];
    if (payload) {
        updateReliabilityImageUrl(payload);
        updateStationMarkers(payload);
        renderReliabilityOverview(payload);
        setReliabilityStatus(reliabilityStatusForPayload(payload));
    }

    refreshReliabilityMapSize();
}

function imageUrlForPayload(payload, layer) {
    const path = payload && payload.imageUrl
        ? payload.imageUrl
        : `/model-runs/reliability/surface.png?layer=${encodeURIComponent(layer)}`;

    const baseUrl = payload && payload.__apiBaseUrl && path.startsWith("/")
        ? payload.__apiBaseUrl
        : window.location.origin;
    const url = new URL(path, baseUrl);
    const visualization = payload && payload.visualization;
    const scaleVersion = visualization && visualization.scaleVersion
        ? visualization.scaleVersion
        : payload && payload.scoreVersion
            ? payload.scoreVersion
            : "1";
    url.searchParams.set("visual", scaleVersion);

    return url.toString();
}

function stationOverlayUrlForPayload(payload, layer, mode) {
    const overlayUrls = payload && payload.stationOverlayUrls;
    const path = overlayUrls && overlayUrls[mode]
        ? overlayUrls[mode]
        : `/model-runs/reliability/station-overlay.png?layer=${encodeURIComponent(layer)}&mode=${encodeURIComponent(mode)}`;

    const baseUrl = payload && payload.__apiBaseUrl && path.startsWith("/")
        ? payload.__apiBaseUrl
        : window.location.origin;
    const url = new URL(path, baseUrl);
    url.searchParams.set("overlay", `station-${mode}-v1`);

    return url.toString();
}

function activeImageUrlForPayload(payload, layer) {
    const mode = activeReliabilityMapMode();
    if (isStationMetricOverlayMode(mode)) {
        return stationOverlayUrlForPayload(payload, layer, mode);
    }

    return imageUrlForPayload(payload, layer);
}

function applyReliabilitySummary(summary) {
    state.reliabilitySummary = summary;
    const availableLayers = new Set(summary.availableLayers || []);
    const layerOptions = elements.reliabilityLayerSelect
        ? [...elements.reliabilityLayerSelect.options]
        : [];
    const visibleLayerValues = layerOptions.map(option => option.value);

    if (elements.reliabilityLayerSelect && availableLayers.size) {
        layerOptions.forEach(option => {
            const available = availableLayers.has(option.value);
            option.disabled = !available;
            option.title = available ? "" : "Artifact not available";
        });
    }

    const preferredLayer = visibleLayerValues.includes(state.reliabilityCurrentLayer)
        && (!availableLayers.size || availableLayers.has(state.reliabilityCurrentLayer))
        ? state.reliabilityCurrentLayer
        : visibleLayerValues.includes("tavg") && (!availableLayers.size || availableLayers.has("tavg"))
            ? "tavg"
            : visibleLayerValues.find(value => !availableLayers.size || availableLayers.has(value));

    if (preferredLayer) {
        state.reliabilityCurrentLayer = preferredLayer;
    }

    if (elements.reliabilityLayerSelect) {
        elements.reliabilityLayerSelect.value = state.reliabilityCurrentLayer;
    }
}

function updateBoundary(payload) {
    if (!state.reliabilityMap || !payload.boundaryGeoJson) {
        return;
    }

    if (state.reliabilityBoundaryLayer) {
        state.reliabilityBoundaryLayer.remove();
    }

    state.reliabilityBoundaryLayer = L.geoJSON(payload.boundaryGeoJson, {
        interactive: false,
        style: {
            color: "#0f172a",
            weight: 2,
            opacity: 0.85,
            fillOpacity: 0
        }
    }).addTo(state.reliabilityMap);
}

function updateSelectedStationMarker() {
    state.reliabilityStationMarkersById.forEach((marker, stationId) => {
        const icon = marker.getElement();
        if (!icon) {
            return;
        }

        icon.classList.toggle("selected", stationId === state.reliabilitySelectedStationId);
    });
}

async function selectReliabilityStation(station) {
    if (!elements.reliabilityResultsContainer || !station || !station.stationId) {
        return;
    }

    state.reliabilitySelectedStationId = station.stationId;
    updateSelectedStationMarker();

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>Station Detail</h2>
            <div class="loading-skeleton" aria-hidden="true">
                <span class="skeleton-line wide"></span>
                <span class="skeleton-line"></span>
                <span class="skeleton-line narrow"></span>
            </div>
            <p class="placeholder">
                Loading ${escapeHtml(station.stationName || station.stationId)} station metrics...
            </p>
        </div>
    `;

    try {
        const data = await fetchReliabilityStationDetails(
            state.reliabilityCurrentLayer,
            station.stationId
        );
        renderReliabilityStationDetails(data);
    } catch (error) {
        renderReliabilityStationDetails({
            status: "error",
            message: "Could not load station details for this marker."
        });
    }
}

function bindStationMarkerClick(marker, station) {
    const selectStation = event => {
        if (event) {
            L.DomEvent.stop(event);
        }
        selectReliabilityStation(station);
    };

    marker.on("click", event => {
        if (event.originalEvent) {
            L.DomEvent.stop(event.originalEvent);
        }
        selectReliabilityStation(station);
    });

    marker.on("add", () => {
        const icon = marker.getElement();
        if (!icon) {
            return;
        }

        L.DomEvent.disableClickPropagation(icon);
        L.DomEvent.on(icon, "click", selectStation);
    });
}

function updateStationMarkers(payload) {
    if (!state.reliabilityMap || !state.reliabilityStationLayer) {
        return;
    }

    state.reliabilityStationLayer.clearLayers();
    state.reliabilityStationMarkersById = new Map();
    if (!elements.reliabilityStationToggle || !elements.reliabilityStationToggle.checked) {
        return;
    }

    const stations = payload.holdoutStations || [];
    stations.forEach(station => {
        const latitude = Number(station.latitude);
        const longitude = Number(station.longitude);
        if (Number.isNaN(latitude) || Number.isNaN(longitude)) {
            return;
        }

        const visualization = stationVisualization(station);
        const marker = L.marker([latitude, longitude], {
            pane: "reliabilityStationPane",
            bubblingMouseEvents: false,
            icon: L.divIcon({
                className: `reliability-station-marker ${visualization.className}`,
                html: `<span style="background: ${visualization.color};"></span>`,
                iconSize: [13, 13],
                iconAnchor: [6, 6],
                popupAnchor: [0, -7]
            }),
            interactive: true,
            keyboard: true,
            riseOnHover: true,
            title: visualization.title
        });
        bindStationMarkerClick(marker, station);
        marker.addTo(state.reliabilityStationLayer);
        state.reliabilityStationMarkersById.set(station.stationId, marker);
    });
    updateSelectedStationMarker();
}

async function loadReliabilityLayer(layer) {
    if (state.reliabilityLayerLoading) {
        return;
    }

    state.reliabilityLayerLoading = true;
    state.reliabilityCurrentLayer = layer;
    setReliabilityStatus(`Loading ${LAYER_LABELS[layer] || layer}...`);

    try {
        const payload = state.reliabilitySurfaceData[layer] || await fetchReliabilitySurface(layer);
        state.reliabilitySurfaceData[layer] = payload;
        const bounds = reliabilityBounds(payload);

        if (!bounds) {
            throw new Error("Reliability surface did not include bounds.");
        }

        if (state.reliabilityImageLayer) {
            state.reliabilityImageLayer.remove();
        }

        state.reliabilityImageLayer = L.imageOverlay(
            activeImageUrlForPayload(payload, layer),
            bounds,
            {
                pane: "reliabilityRasterPane",
                opacity: (RELIABILITY_MAP_MODES[activeReliabilityMapMode()] || RELIABILITY_MAP_MODES.quality).rasterOpacity,
                interactive: false
            }
        ).addTo(state.reliabilityMap);

        updateReliabilityModeControls();
        updateReliabilityRasterVisibility();
        updateBoundary(payload);
        updateStationMarkers(payload);
        renderReliabilityOverview(payload);
        state.reliabilityMap.fitBounds(bounds, {
            padding: [20, 20],
            maxZoom: 7
        });

        setReliabilityStatus(reliabilityStatusForPayload(payload));
    } catch (error) {
        console.warn("Could not load reliability surface:", error);
        setReliabilityStatus("Reliability artifacts unavailable");
        if (elements.reliabilityResultsContainer) {
            elements.reliabilityResultsContainer.innerHTML = `
                <div class="card">
                    <h2>Reliability Inspector</h2>
                    <div class="error">
                        Reliability artifacts are not available yet. Build
                        weather_reconstruction_model/model_runs/paloma_v1_reliability first.
                    </div>
                </div>
            `;
        }
    } finally {
        state.reliabilityLayerLoading = false;
        refreshReliabilityMapSize();
    }
}

async function sampleReliabilityPoint(latitude, longitude) {
    if (!elements.reliabilityResultsContainer) {
        return;
    }

    if (state.reliabilitySelectedMarker) {
        state.reliabilitySelectedMarker.setLatLng([latitude, longitude]);
    } else {
        state.reliabilitySelectedMarker = L.circleMarker([latitude, longitude], {
            pane: "reliabilitySelectionPane",
            radius: 8,
            color: "#0f172a",
            fillColor: "#ffffff",
            fillOpacity: 0.95,
            interactive: false,
            weight: 3
        }).addTo(state.reliabilityMap);
    }

    elements.reliabilityResultsContainer.innerHTML = `
        <div class="card">
            <h2>Reliability Inspector</h2>
            <div class="loading-skeleton" aria-hidden="true">
                <span class="skeleton-line wide"></span>
                <span class="skeleton-line"></span>
                <span class="skeleton-line narrow"></span>
            </div>
            <p class="placeholder">Sampling ${LAYER_LABELS[state.reliabilityCurrentLayer]} at ${formatNumber(latitude, 6)}, ${formatNumber(longitude, 6)}...</p>
        </div>
    `;

    try {
        const data = await fetchReliabilitySample(state.reliabilityCurrentLayer, latitude, longitude);
        renderReliabilitySample(data);
    } catch (error) {
        renderReliabilitySample({
            status: "error",
            message: "Could not sample this point. It may be outside the basin mask or the backend may be unavailable."
        });
    }
}

export function bindReliabilityControls() {
    if (elements.reliabilityLayerSelect) {
        elements.reliabilityLayerSelect.addEventListener("change", event => {
            if (event.target.selectedOptions[0] && event.target.selectedOptions[0].disabled) {
                event.target.value = state.reliabilityCurrentLayer;
                return;
            }

            loadReliabilityLayer(event.target.value);
        });
    }

    if (elements.reliabilityStationToggle) {
        elements.reliabilityStationToggle.addEventListener("change", () => {
            const payload = state.reliabilitySurfaceData[state.reliabilityCurrentLayer];
            if (payload) {
                updateStationMarkers(payload);
                setReliabilityStatus(reliabilityStatusForPayload(payload));
            }
        });
    }

    if (elements.reliabilityMapModeSelect) {
        elements.reliabilityMapModeSelect.addEventListener("change", event => {
            applyReliabilityMapMode(event.target.value);
        });
    }
}

export function initializeReliabilityMap() {
    if (state.reliabilityMap || typeof L === "undefined") {
        refreshReliabilityMapSize();
        return;
    }

    const mapElement = document.getElementById("reliability-map");
    mapElement.style.height = "62vh";
    mapElement.style.width = "100%";

    state.reliabilityMap = L.map("reliability-map", {
        scrollWheelZoom: true,
        zoomControl: true
    });

    L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 18,
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, USGS, NOAA"
        }
    ).addTo(state.reliabilityMap);

    state.reliabilityMap.createPane("reliabilityRasterPane");
    state.reliabilityMap.getPane("reliabilityRasterPane").style.zIndex = 350;
    state.reliabilityMap.createPane("reliabilityStationPane");
    state.reliabilityMap.getPane("reliabilityStationPane").style.zIndex = 380;
    state.reliabilityMap.createPane("reliabilitySelectionPane");
    state.reliabilityMap.getPane("reliabilitySelectionPane").style.zIndex = 400;
    state.reliabilityMap.getPane("reliabilitySelectionPane").style.pointerEvents = "none";

    state.reliabilityStationLayer = L.layerGroup().addTo(state.reliabilityMap);
    state.reliabilityMap.setView([39.5, -107.0], 6);
    state.reliabilityMap.on("click", event => {
        if (activeReliabilityMapMode() === "quality") {
            sampleReliabilityPoint(event.latlng.lat, event.latlng.lng);
        }
    });

    updateReliabilityModeControls();
    fetchReliabilitySummary()
        .then(summary => {
            applyReliabilitySummary(summary);
            return loadReliabilityLayer(state.reliabilityCurrentLayer);
        })
        .catch(error => {
            console.warn("Could not load reliability summary:", error);
            loadReliabilityLayer(state.reliabilityCurrentLayer);
        });
    requestAnimationFrame(refreshReliabilityMapSize);
    setTimeout(refreshReliabilityMapSize, 100);
    setTimeout(refreshReliabilityMapSize, 500);
    window.addEventListener("resize", refreshReliabilityMapSize);
}
