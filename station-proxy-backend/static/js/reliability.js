// Purpose: Re-export the reliability map's public API from the reliability/ modules.
//
// The implementation lives in reliability/: config.js (modes, legends),
// metrics.js (quality classification), prediction-charts.js (SVG series
// charts), station-details.js (detail panels), and map.js (Leaflet map,
// markers, controls).

export {
    bindReliabilityControls,
    initializeReliabilityMap,
    refreshReliabilityMapSize
} from "./reliability/map.js?v=tabs-v1";
