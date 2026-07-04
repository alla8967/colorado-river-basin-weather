// Purpose: Render daily prediction-vs-actual comparison charts for station detail panels.

import { buildChartPath } from "../charts.js";
import { escapeHtml, formatNumber } from "../formatters.js";

function predictionSeriesPoints(series) {
    return (series && Array.isArray(series.points) ? series.points : [])
        .map(point => ({
            date: String(point.date || ""),
            actualF: Number(point.actualF),
            predictedF: Number(point.predictedF)
        }))
        .filter(point => (
            point.date &&
            Number.isFinite(point.actualF) &&
            Number.isFinite(point.predictedF)
        ));
}

function seriesDateLabel(point) {
    return point && point.date ? point.date : "N/A";
}

export function stationPredictionSeries(data, key) {
    const series = data.temperaturePredictionSeries || {};
    return series[key] || null;
}

export function renderPredictionComparisonChart(series, options) {
    const points = predictionSeriesPoints(series);
    const title = `${options.modelLabel} ${options.variableLabel} vs Actual ${options.variableLabel}`;

    if (!series || series.status !== "available") {
        return `
            <div class="prediction-chart unavailable">
                <div class="prediction-chart-header">
                    <h4>${escapeHtml(title)}</h4>
                </div>
                <p class="placeholder">
                    ${escapeHtml(series && series.message ? series.message : options.emptyMessage)}
                </p>
            </div>
        `;
    }

    if (points.length < 2) {
        return `
            <div class="prediction-chart unavailable">
                <div class="prediction-chart-header">
                    <h4>${escapeHtml(title)}</h4>
                </div>
                <p class="placeholder">At least two daily prediction rows are needed to draw this chart.</p>
            </div>
        `;
    }

    const width = 900;
    const height = 300;
    const padding = {
        top: 20,
        right: 24,
        bottom: 46,
        left: 54
    };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const values = points.flatMap(point => [point.actualF, point.predictedF]);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const yMin = Math.floor((rawMin - 5) / 5) * 5;
    const yMax = Math.ceil((rawMax + 5) / 5) * 5;
    const yRange = yMax - yMin || 1;
    const toX = index => padding.left + index / (points.length - 1) * chartWidth;
    const toY = value => padding.top + (yMax - value) / yRange * chartHeight;
    const actualPath = buildChartPath(points.map((point, index) => ({
        x: toX(index),
        y: toY(point.actualF)
    })));
    const predictedPath = buildChartPath(points.map((point, index) => ({
        x: toX(index),
        y: toY(point.predictedF)
    })));
    const yTicks = [];
    for (let index = 0; index <= 4; index++) {
        const value = yMin + yRange * index / 4;
        yTicks.push({
            value,
            y: toY(value)
        });
    }
    const xTickIndexes = [
        0,
        Math.floor((points.length - 1) / 3),
        Math.floor((points.length - 1) * 2 / 3),
        points.length - 1
    ];
    const xTicks = [...new Set(xTickIndexes)].map(index => ({
        index,
        x: toX(index),
        label: seriesDateLabel(points[index])
    }));
    const firstPoint = points[0];
    const lastPoint = points[points.length - 1];
    const rowSummary = series.downsampled
        ? `${formatNumber(series.returnedRows, 0)} of ${formatNumber(series.totalRows, 0)} rows shown`
        : `${formatNumber(series.totalRows, 0)} rows`;

    return `
        <div class="prediction-chart">
            <div class="prediction-chart-header">
                <div>
                    <h4>${escapeHtml(title)}</h4>
                    <p>
                        ${escapeHtml(seriesDateLabel(firstPoint))} to ${escapeHtml(seriesDateLabel(lastPoint))}
                    </p>
                </div>
                <span>${escapeHtml(rowSummary)}</span>
            </div>
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
                <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" stroke="#94a3b8" />
                <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" stroke="#94a3b8" />
                ${yTicks.map(tick => `
                    <line x1="${padding.left}" y1="${tick.y}" x2="${width - padding.right}" y2="${tick.y}" stroke="#e2e8f0" />
                    <text x="${padding.left - 10}" y="${tick.y + 4}" text-anchor="end" fill="#64748b" font-size="12">${formatNumber(tick.value, 0)}</text>
                `).join("")}
                ${xTicks.map(tick => `
                    <line x1="${tick.x}" y1="${height - padding.bottom}" x2="${tick.x}" y2="${height - padding.bottom + 5}" stroke="#94a3b8" />
                    <text x="${tick.x}" y="${height - padding.bottom + 22}" text-anchor="middle" fill="#64748b" font-size="12">${escapeHtml(tick.label)}</text>
                `).join("")}
                <text x="18" y="${padding.top + chartHeight / 2}" text-anchor="middle" transform="rotate(-90 18 ${padding.top + chartHeight / 2})" fill="#475569" font-size="12" font-weight="bold">Daily ${escapeHtml(options.variableLabel)} (F)</text>
                <text x="${padding.left + chartWidth / 2}" y="${height - 10}" text-anchor="middle" fill="#475569" font-size="12" font-weight="bold">Date</text>
                <path d="${actualPath}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
                <path d="${predictedPath}" fill="none" stroke="#dc2626" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
            </svg>
            <div class="chart-legend">
                <span class="chart-legend-item"><span class="chart-swatch target"></span>Actual recorded ${escapeHtml(options.variableLabel)}</span>
                <span class="chart-legend-item"><span class="chart-swatch proxy"></span>${escapeHtml(options.modelLabel)} ${escapeHtml(options.variableLabel)}</span>
            </div>
        </div>
    `;
}
