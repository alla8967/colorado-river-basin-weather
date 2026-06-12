// Purpose: Store shared DOM references and mutable browser state for frontend modules.

export const elements = {
    analyzeButton: document.getElementById("analyze-button"),
    resultsContainer: document.getElementById("results"),
    engineStatus: document.getElementById("engine-status"),
    reliabilityLayerStatus: document.getElementById("reliability-layer-status"),
    reliabilityResultsContainer: document.getElementById("reliability-results"),
    reliabilityLayerSelect: document.getElementById("reliability-layer-select"),
    reliabilityStationToggle: document.getElementById("reliability-station-toggle"),
    reliabilityMapModeSelect: document.getElementById("reliability-map-mode-select"),
    reliabilityMapHelp: document.getElementById("reliability-map-help"),
    reliabilityLegend: document.getElementById("reliability-legend"),
    tabButtons: document.querySelectorAll("[data-tab-target]"),
    presetButtons: document.querySelectorAll("[data-preset-lat][data-preset-lon]")
};

export const state = {
    engineReady: false,
    map: null,
    reliabilityMap: null,
    selectedMarker: null,
    reliabilitySurfaceData: {},
    reliabilityLayerLoading: false,
    reliabilityCurrentLayer: "tavg",
    reliabilityMapMode: "quality",
    reliabilityImageLayer: null,
    reliabilityBoundaryLayer: null,
    reliabilityStationLayer: null,
    reliabilitySelectedMarker: null,
    reliabilitySelectedStationId: null,
    reliabilityStationMarkersById: new Map(),
    reliabilitySummary: null,
    resultStationLayer: null,
    resultLineLayer: null,
    proxyMarkersByRank: new Map(),
    currentMatchMode: "target_to_hub",
    currentHighCorrelationOptions: [],
    currentLowCorrelationOptions: []
};
