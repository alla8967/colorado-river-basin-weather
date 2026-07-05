// Purpose: Render the main analysis results, proxy station rankings, cards, and comparison charts.

import { attachChartSelectInteractions, cleanComparisonOptions, renderDailyComparisonChart, renderLowCorrelationExample, renderMonthlyComparisonChart } from "./charts.js?v=low-correlation-v1";
import { highlightProxyRank, plotAnalysisStations } from "./maps.js";
import { elements, state } from "./state.js";
import {
    calculateDistanceKm,
    correlationPercent,
    formatNumber,
    formatObservationPeriod,
    formatPreparedObservationPeriod,
    inversePercent,
    matchTerms,
    renderMetric,
    renderScoreItem,
    stationRoleLabel
} from "./formatters.js";

export function renderProxySummary(match, terms = matchTerms()) {
    if (!match) {
        return "";
    }

    return `
        <p class="summary">
            ${terms.summaryNoun} is ${formatNumber(match.distanceKm, 1)} km from the nearest station,
            ${formatNumber(match.elevationDifferenceM, 1)} m different in elevation,
            and is supported by ${match.pairedDays} paired daily observations.
        </p>
    `;
}

export function renderScoreBreakdown(match) {
    if (!match) {
        return "";
    }

    return `
        <div class="score-band">
            ${renderScoreItem("Daily correlation", formatNumber(match.dailyCorrelation, 3), correlationPercent(match.dailyCorrelation))}
            ${renderScoreItem("Daily MAD", `${formatNumber(match.dailyMAD, 2)} F`, inversePercent(match.dailyMAD, 2, 12))}
            ${renderScoreItem("Daily RMSE", `${formatNumber(match.dailyRMSE, 2)} F`, inversePercent(match.dailyRMSE, 2.75, 14))}
            ${renderScoreItem("Distance", `${formatNumber(match.distanceKm, 1)} km`, inversePercent(match.distanceKm, 35, 300))}
            ${renderScoreItem("Elevation", `${formatNumber(match.elevationDifferenceM, 1)} m`, inversePercent(match.elevationDifferenceM, 50, 1500))}
        </div>
    `;
}

export function attachResultInteractions() {
    document.querySelectorAll("[data-proxy-rank]").forEach(row => {
        row.addEventListener("click", function() {
            highlightProxyRank(this.dataset.proxyRank);
        });
    });
}

export function renderResults(data) {
    if (data.status !== "ok") {
        if (state.resultStationLayer) {
            state.resultStationLayer.clearLayers();
        }

        elements.resultsContainer.innerHTML = `
            <div class="card">
                <h2>Error</h2>
                <div class="error">${data.message || "Unknown error"}</div>
            </div>
        `;
        return;
    }

    plotAnalysisStations(data);

    const nearest = data.nearestStation;
    const best = data.bestProxyStation;
    const matches = data.topProxyMatches || [];
    const terms = matchTerms(data);
    const stationLoadSummary = `${data.targetStationCount ?? "N/A"} targets / ${data.hubStationCount ?? "N/A"} hubs`;
    const nearestDistanceKm = calculateDistanceKm(
        data.selectedLocation.latitude,
        data.selectedLocation.longitude,
        nearest.latitude,
        nearest.longitude
    );

    let bestProxyHtml = "";

    if (best) {
        bestProxyHtml = `
            <div class="card">
                <h2>${terms.bestHeading}</h2>
                <h3>${best.proxyStation.stationName}</h3>
                <p><strong>Station ID:</strong> ${best.proxyStation.stationID}</p>
                <p><strong>Full usable observation period:</strong> ${formatObservationPeriod(best.proxyStation)} (${best.proxyStation.fullObservationYears || "N/A"} years)</p>
                <p><strong>Prepared comparison window:</strong> ${formatPreparedObservationPeriod(best.proxyStation)} (${best.proxyStation.dailyRecords || "N/A"} daily records loaded)</p>
                ${renderProxySummary(best, terms)}
                ${renderScoreBreakdown(best)}

                <div class="metric-grid">
                    ${renderMetric("Match Score", formatNumber(best.score, 2))}
                    ${renderMetric("Distance", `${formatNumber(best.distanceKm, 1)} km`)}
                    ${renderMetric("Elevation Difference", `${formatNumber(best.elevationDifferenceM, 1)} m`)}
                    ${renderMetric("Daily Correlation", formatNumber(best.dailyCorrelation, 3))}
                    ${renderMetric("Daily MAD", formatNumber(best.dailyMAD, 2))}
                    ${renderMetric("Daily RMSE", formatNumber(best.dailyRMSE, 2))}
                    ${renderMetric("Paired Days", best.pairedDays)}
                    ${renderMetric("Paired Months", best.pairedMonths)}
                    ${renderMetric(data.matchMode === "hub_to_hub" ? "Full Similar Hub Record" : "Full Proxy Record", formatObservationPeriod(best.proxyStation))}
                    ${renderMetric("Prepared Window", formatPreparedObservationPeriod(best.proxyStation))}
                    ${renderMetric(data.matchMode === "hub_to_hub" ? "Similar Hub Daily Records" : "Proxy Daily Records", best.proxyStation.dailyRecords || "N/A")}
                </div>
            </div>
        `;
    } else {
        bestProxyHtml = `
            <div class="card">
                <h2>${terms.bestHeading}</h2>
                <p class="placeholder">${terms.emptyMessage}</p>
            </div>
        `;
    }

    const tableRows = matches.map(match => `
        <tr data-proxy-rank="${match.rank}">
            <td>${match.rank}</td>
            <td>${match.proxyStation.stationName}</td>
            <td>${formatNumber(match.score, 2)}</td>
            <td>${formatNumber(match.distanceKm, 1)} km</td>
            <td>${formatNumber(match.elevationDifferenceM, 1)} m</td>
            <td>${formatNumber(match.dailyCorrelation, 3)}</td>
            <td>${formatNumber(match.dailyMAD, 2)}</td>
            <td>${formatNumber(match.dailyRMSE, 2)}</td>
            <td>${formatObservationPeriod(match.proxyStation)}</td>
        </tr>
    `).join("");

    elements.resultsContainer.innerHTML = `
        <div class="card">
            <h2>Selected Location</h2>
            <div class="metric-grid">
                ${renderMetric("Latitude", formatNumber(data.selectedLocation.latitude, 6))}
                ${renderMetric("Longitude", formatNumber(data.selectedLocation.longitude, 6))}
                ${renderMetric("Stations Loaded", stationLoadSummary)}
            </div>
        </div>

        <div class="card">
            <h2>Nearest Station</h2>
            <h3>${nearest.stationName}</h3>
            <p><strong>Station ID:</strong> ${nearest.stationID}</p>
            <p><strong>Station type:</strong> ${stationRoleLabel(nearest)}</p>
            ${nearest.isHubStation ? `<p class="summary">This is a hub station with a full usable observation period of ${formatObservationPeriod(nearest)} (${nearest.fullObservationYears || "N/A"} years), so the matches below are the most similar other hubs.</p>` : `<p class="summary">This is a target station, so the matches below are proxy hub stations.</p>`}
            <p><strong>Distance from selected point:</strong> ${formatNumber(nearestDistanceKm, 2)} km</p>
            <div class="metric-grid">
                ${renderMetric("Latitude", formatNumber(nearest.latitude, 6))}
                ${renderMetric("Longitude", formatNumber(nearest.longitude, 6))}
                ${renderMetric("Elevation", `${formatNumber(nearest.elevation, 1)} m`)}
                ${renderMetric("Full Observation Period", formatObservationPeriod(nearest))}
                ${renderMetric("Full Observation Years", nearest.fullObservationYears || "N/A")}
                ${renderMetric("Prepared Window", formatPreparedObservationPeriod(nearest))}
                ${renderMetric("Daily Records", nearest.dailyRecords)}
                ${renderMetric("Monthly Records", nearest.monthlyRecords)}
                ${renderMetric("Seasonal Records", nearest.seasonalRecords)}
            </div>
        </div>

        ${bestProxyHtml}

        ${renderMonthlyComparisonChart(data)}
        ${renderDailyComparisonChart(data)}

        <div class="card">
            <h2>${terms.tableHeading}</h2>
            <p class="table-note">Click a match row to center and open that station on the map.</p>
            <table>
                <thead>
                    <tr>
                        <th>Rank</th>
                        <th>${terms.tableStationHeading}</th>
                        <th>Score</th>
                        <th>Distance</th>
                        <th>Elev. Diff</th>
                        <th>Daily r</th>
                        <th>MAD</th>
                        <th>RMSE</th>
                        <th>Record</th>
                    </tr>
                </thead>
                <tbody>
                    ${tableRows}
                </tbody>
            </table>
        </div>

        ${renderLowCorrelationExample(data)}
    `;

    attachResultInteractions();
    state.currentMatchMode = data.matchMode || "target_to_hub";
    state.currentHighCorrelationOptions = data.highCorrelationComparisonOptions || [];
    // Keep the same filtered list the rendered dropdown was built from, so
    // select indexes stay aligned.
    state.currentLowCorrelationOptions = cleanComparisonOptions(data.lowCorrelationComparisonOptions);
    attachChartSelectInteractions();
}
