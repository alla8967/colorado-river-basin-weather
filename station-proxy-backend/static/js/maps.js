import { analyzeConfidencePoint, loadConfidencePoints } from "./confidence.js";
import { state } from "./state.js";
import {
    formatNumber,
    matchTerms,
    stationHasCoordinates,
    stationLatLng,
    stationRoleLabel
} from "./formatters.js";

export function setCoordinateInputs(latitude, longitude) {
    const latitudeInput = document.getElementById("latitude");
    const longitudeInput = document.getElementById("longitude");

    latitudeInput.value = latitude.toFixed(6);
    longitudeInput.value = longitude.toFixed(6);
}

export function refreshMapSize() {
    if (!state.map) {
        return;
    }

    state.map.invalidateSize(true);
}

export function refreshConfidenceMapSize() {
    if (!state.confidenceMap) {
        return;
    }

    state.confidenceMap.invalidateSize(true);
}

export function addStationCircleMarker(station, options) {
    if (!state.map || !state.resultStationLayer || !stationHasCoordinates(station)) {
        return null;
    }

    const marker = L.circleMarker([Number(station.latitude), Number(station.longitude)], {
        radius: options.radius || 8,
        color: options.color,
        fillColor: options.fillColor || options.color,
        fillOpacity: options.fillOpacity || 0.85,
        weight: options.weight || 2
    }).addTo(state.resultStationLayer);

    marker.bindPopup(options.popupHtml);
    return marker;
}

export function addMapLine(points, options) {
    if (!state.map || !state.resultLineLayer || points.length < 2) {
        return null;
    }

    return L.polyline(points, {
        color: options.color,
        weight: options.weight || 3,
        opacity: options.opacity || 0.75,
        dashArray: options.dashArray || null
    }).addTo(state.resultLineLayer);
}

export function plotAnalysisStations(data) {
    if (!state.map || !state.resultStationLayer || !state.resultLineLayer || !data || data.status !== "ok") {
        return;
    }

    state.resultStationLayer.clearLayers();
    state.resultLineLayer.clearLayers();
    state.proxyMarkersByRank = new Map();

    const bounds = [];
    let selectedPoint = null;

    if (data.selectedLocation && state.selectedMarker) {
        const selectedLat = Number(data.selectedLocation.latitude);
        const selectedLon = Number(data.selectedLocation.longitude);

        if (!Number.isNaN(selectedLat) && !Number.isNaN(selectedLon)) {
            selectedPoint = [selectedLat, selectedLon];
            state.selectedMarker.setLatLng(selectedPoint);
            bounds.push(selectedPoint);
        }
    }

    const nearest = data.nearestStation;
    const terms = matchTerms(data);
    if (stationHasCoordinates(nearest)) {
        const nearestPoint = stationLatLng(nearest);

        addStationCircleMarker(nearest, {
            color: "#2563eb",
            fillColor: "#60a5fa",
            radius: 9,
            popupHtml: `
                <strong>Nearest ${stationRoleLabel(nearest)}</strong><br>
                ${nearest.stationName}<br>
                ${nearest.stationID}<br>
                ${stationRoleLabel(nearest)}<br>
                Elevation: ${formatNumber(nearest.elevation, 1)} m
            `
        });

        bounds.push(nearestPoint);

        if (selectedPoint) {
            addMapLine([selectedPoint, nearestPoint], {
                color: "#2563eb",
                weight: 3,
                opacity: 0.7
            });
        }
    }

    const matches = data.topProxyMatches || [];
    matches.forEach(function(match) {
        const proxy = match.proxyStation;

        if (!stationHasCoordinates(proxy)) {
            return;
        }

        const marker = addStationCircleMarker(proxy, {
            color: "#dc2626",
            fillColor: "#f87171",
            radius: Math.max(5, 9 - (match.rank || 1)),
            popupHtml: `
                <strong>${terms.mapStationLabel} #${match.rank}</strong><br>
                ${proxy.stationName}<br>
                ${proxy.stationID}<br>
                Score: ${formatNumber(match.score, 2)}<br>
                Distance: ${formatNumber(match.distanceKm, 1)} km<br>
                Daily r: ${formatNumber(match.dailyCorrelation, 3)}
            `
        });

        if (marker) {
            state.proxyMarkersByRank.set(Number(match.rank), marker);
        }

        bounds.push(stationLatLng(proxy));
    });

    const bestProxy = data.bestProxyStation && data.bestProxyStation.proxyStation;
    if (stationHasCoordinates(nearest) && stationHasCoordinates(bestProxy)) {
        addMapLine([stationLatLng(nearest), stationLatLng(bestProxy)], {
            color: "#dc2626",
            weight: 3,
            opacity: 0.65,
            dashArray: "8 7"
        });
    }

    if (bounds.length > 1) {
        state.map.fitBounds(bounds, {
            padding: [28, 28],
            maxZoom: 8
        });
    } else if (bounds.length === 1) {
        state.map.setView(bounds[0], 8);
    }

    refreshMapSize();
}

export function initializeMap() {
    if (state.map || typeof L === "undefined") {
        return;
    }

    const mapElement = document.getElementById("map");
    mapElement.style.height = "62vh";
    mapElement.style.width = "100%";

    state.map = L.map("map", {
        scrollWheelZoom: true,
        zoomControl: true,
        preferCanvas: true
    });

    const tileLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 18,
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, USGS, NOAA"
        }
    );

    tileLayer.on("tileerror", function(error) {
        console.warn("A map tile failed to load:", error);
    });

    tileLayer.addTo(state.map);

    state.map.setView([39.5, -107.0], 6);

    state.selectedMarker = L.marker([39.75, -105.0]).addTo(state.map);
    state.selectedMarker.bindPopup("<strong>Selected Location</strong>");
    state.resultLineLayer = L.layerGroup().addTo(state.map);
    state.resultStationLayer = L.layerGroup().addTo(state.map);
    setCoordinateInputs(39.75, -105.0);

    state.map.on("click", function(event) {
        const latitude = event.latlng.lat;
        const longitude = event.latlng.lng;

        setCoordinateInputs(latitude, longitude);
        state.selectedMarker.setLatLng([latitude, longitude]);
    });

    requestAnimationFrame(refreshMapSize);
    setTimeout(refreshMapSize, 100);
    setTimeout(refreshMapSize, 500);
    setTimeout(refreshMapSize, 1000);
    setTimeout(refreshMapSize, 2000);

    window.addEventListener("resize", refreshMapSize);
}

export function fitConfidenceMapToPayload(payload) {
    if (!state.confidenceMap || !payload || !payload.bounds) {
        return;
    }

    const bounds = payload.bounds;
    const southWest = [Number(bounds.latMin), Number(bounds.lonMin)];
    const northEast = [Number(bounds.latMax), Number(bounds.lonMax)];

    if (southWest.some(value => Number.isNaN(value)) ||
        northEast.some(value => Number.isNaN(value))) {
        return;
    }

    state.confidenceMap.fitBounds([southWest, northEast], {
        padding: [20, 20],
        maxZoom: 6
    });
}

export function initializeConfidenceMap() {
    if (state.confidenceMap || typeof L === "undefined") {
        refreshConfidenceMapSize();
        return;
    }

    const mapElement = document.getElementById("confidence-map");
    mapElement.style.height = "62vh";
    mapElement.style.width = "100%";

    state.confidenceMap = L.map("confidence-map", {
        scrollWheelZoom: true,
        zoomControl: true,
        preferCanvas: true
    });

    const tileLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 18,
            attribution: "Tiles &copy; Esri &mdash; Source: Esri, USGS, NOAA"
        }
    );

    tileLayer.on("tileerror", function(error) {
        console.warn("A confidence map tile failed to load:", error);
    });

    tileLayer.addTo(state.confidenceMap);
    state.confidenceMap.createPane("confidencePane");
    state.confidenceMap.getPane("confidencePane").style.zIndex = 360;
    state.confidenceMap.getPane("confidencePane").style.pointerEvents = "auto";
    state.confidenceMap.createPane("confidenceSelectionPane");
    state.confidenceMap.getPane("confidenceSelectionPane").style.zIndex = 390;
    state.confidenceMap.getPane("confidenceSelectionPane").style.pointerEvents = "auto";
    state.confidencePointLayer = L.layerGroup().addTo(state.confidenceMap);
    state.confidenceMap.setView([39.5, -107.0], 6);

    state.confidenceMap.on("click", function(event) {
        analyzeConfidencePoint(event.latlng.lat, event.latlng.lng);
    });

    loadConfidencePoints().then(payload => {
        fitConfidenceMapToPayload(payload);
        refreshConfidenceMapSize();
    });

    requestAnimationFrame(refreshConfidenceMapSize);
    setTimeout(refreshConfidenceMapSize, 100);
    setTimeout(refreshConfidenceMapSize, 500);
    window.addEventListener("resize", refreshConfidenceMapSize);
}

export function highlightProxyRank(rank) {
    const numericRank = Number(rank);

    document.querySelectorAll("[data-proxy-rank]").forEach(row => {
        row.classList.toggle("active-row", Number(row.dataset.proxyRank) === numericRank);
    });

    const marker = state.proxyMarkersByRank.get(numericRank);
    if (marker && state.map) {
        marker.openPopup();
        state.map.panTo(marker.getLatLng(), {
            animate: true,
            duration: 0.45
        });
    }
}
