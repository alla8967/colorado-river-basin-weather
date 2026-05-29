export const elements = {
    analyzeButton: document.getElementById("analyze-button"),
    resultsContainer: document.getElementById("results"),
    engineStatus: document.getElementById("engine-status"),
    confidenceLayerStatus: document.getElementById("confidence-layer-status"),
    confidenceResultsContainer: document.getElementById("confidence-results"),
    tabButtons: document.querySelectorAll("[data-tab-target]")
};

export const state = {
    engineReady: false,
    map: null,
    confidenceMap: null,
    selectedMarker: null,
    confidencePointLayer: null,
    confidencePointData: null,
    confidenceLayerLoading: false,
    confidenceSelectedMarker: null,
    resultStationLayer: null,
    resultLineLayer: null,
    proxyMarkersByRank: new Map(),
    currentMatchMode: "target_to_hub",
    currentHighCorrelationOptions: [],
    currentLowCorrelationOptions: []
};
