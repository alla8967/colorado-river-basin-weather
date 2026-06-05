// Purpose: Store shared DOM references and mutable browser state for frontend modules.

export const elements = {
    analyzeButton: document.getElementById("analyze-button"),
    resultsContainer: document.getElementById("results"),
    engineStatus: document.getElementById("engine-status"),
    confidenceLayerStatus: document.getElementById("confidence-layer-status"),
    confidenceResultsContainer: document.getElementById("confidence-results"),
    reliabilityLayerStatus: document.getElementById("reliability-layer-status"),
    reliabilityResultsContainer: document.getElementById("reliability-results"),
    reliabilityLayerSelect: document.getElementById("reliability-layer-select"),
    reliabilityStationToggle: document.getElementById("reliability-station-toggle"),
    reliabilityMapModeSelect: document.getElementById("reliability-map-mode-select"),
    reliabilityMapHelp: document.getElementById("reliability-map-help"),
    reliabilityLegend: document.getElementById("reliability-legend"),
    tabButtons: document.querySelectorAll("[data-tab-target]")
};

export const state = {
    engineReady: false,
    map: null,
    confidenceMap: null,
    reliabilityMap: null,
    selectedMarker: null,
    confidencePointLayer: null,
    confidencePointData: null,
    confidenceLayerLoading: false,
    confidenceSelectedMarker: null,
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
