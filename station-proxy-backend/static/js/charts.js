import { state } from "./state.js";
import { formatNumber, matchTerms } from "./formatters.js";

export function buildChartPath(points) {
    return points.map((point, index) => {
        const command = index === 0 ? "M" : "L";
        return `${command}${point.x.toFixed(2)},${point.y.toFixed(2)}`;
    }).join(" ");
}

export function formatComparisonDate(point, includeDay = false) {
    const year = point.year;
    const month = String(point.month).padStart(2, "0");

    if (!includeDay) {
        return `${year}-${month}`;
    }

    return `${year}-${month}-${String(point.day).padStart(2, "0")}`;
}

export function renderTemperatureComparisonChart(options) {
    const points = options.points || [];

    if (points.length < 2) {
        return `
            <div class="card">
                <h2>${options.title}</h2>
                <p class="placeholder">
                    ${options.emptyMessage}
                </p>
            </div>
        `;
    }

    const width = 900;
    const height = 320;
    const padding = {
        top: 24,
        right: 24,
        bottom: 48,
        left: 54
    };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const values = points.flatMap(point => [Number(point.targetTavg), Number(point.proxyTavg)]);
    const rawMin = Math.min(...values);
    const rawMax = Math.max(...values);
    const yMin = Math.floor((rawMin - 5) / 5) * 5;
    const yMax = Math.ceil((rawMax + 5) / 5) * 5;
    const yRange = yMax - yMin || 1;

    const toX = index => padding.left + (points.length === 1 ? 0 : index / (points.length - 1) * chartWidth);
    const toY = value => padding.top + (yMax - value) / yRange * chartHeight;

    const targetPath = buildChartPath(points.map((point, index) => ({
        x: toX(index),
        y: toY(Number(point.targetTavg))
    })));
    const proxyPath = buildChartPath(points.map((point, index) => ({
        x: toX(index),
        y: toY(Number(point.proxyTavg))
    })));

    const yTicks = [];
    for (let i = 0; i <= 4; i++) {
        const value = yMin + (yRange * i / 4);
        const y = toY(value);
        yTicks.push({ value, y });
    }

    const xTickIndexes = options.denseTicks
        ? [0, Math.floor((points.length - 1) / 3), Math.floor((points.length - 1) * 2 / 3), points.length - 1]
        : [0, Math.floor((points.length - 1) / 2), points.length - 1];
    const xTicks = [...new Set(xTickIndexes)].map(index => ({
        index,
        x: toX(index),
        label: formatComparisonDate(points[index], options.includeDay)
    }));

    const firstPoint = points[0];
    const lastPoint = points[points.length - 1];

    return `
        <div class="card ${options.cardClass || ""}">
            <h2>${options.title}</h2>
            ${options.controlHtml || ""}
            <div class="comparison-chart">
            <p class="placeholder">
                ${options.description}
                ${formatComparisonDate(firstPoint, options.includeDay)} to
                ${formatComparisonDate(lastPoint, options.includeDay)}.
            </p>
            <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${options.title}">
                <line x1="${padding.left}" y1="${padding.top}" x2="${padding.left}" y2="${height - padding.bottom}" stroke="#94a3b8" />
                <line x1="${padding.left}" y1="${height - padding.bottom}" x2="${width - padding.right}" y2="${height - padding.bottom}" stroke="#94a3b8" />
                ${yTicks.map(tick => `
                    <line x1="${padding.left}" y1="${tick.y}" x2="${width - padding.right}" y2="${tick.y}" stroke="#e2e8f0" />
                    <text x="${padding.left - 10}" y="${tick.y + 4}" text-anchor="end" fill="#64748b" font-size="12">${formatNumber(tick.value, 0)}</text>
                `).join("")}
                ${xTicks.map(tick => `
                    <line x1="${tick.x}" y1="${height - padding.bottom}" x2="${tick.x}" y2="${height - padding.bottom + 5}" stroke="#94a3b8" />
                    <text x="${tick.x}" y="${height - padding.bottom + 22}" text-anchor="middle" fill="#64748b" font-size="12">${tick.label}</text>
                `).join("")}
                <text x="18" y="${padding.top + chartHeight / 2}" text-anchor="middle" transform="rotate(-90 18 ${padding.top + chartHeight / 2})" fill="#475569" font-size="12" font-weight="bold">${options.yAxisLabel}</text>
                <text x="${padding.left + chartWidth / 2}" y="${height - 10}" text-anchor="middle" fill="#475569" font-size="12" font-weight="bold">${options.xAxisLabel}</text>
                <path d="${targetPath}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
                <path d="${proxyPath}" fill="none" stroke="#dc2626" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />
            </svg>
            <div class="chart-legend">
                <span class="chart-legend-item"><span class="chart-swatch target"></span>${options.targetLabel || "Nearest station"}</span>
                <span class="chart-legend-item"><span class="chart-swatch proxy"></span>${options.proxyLabel || "Top proxy station"}</span>
            </div>
            </div>
        </div>
    `;
}

export function comparisonOptionLabel(option, index, fallbackPrefix) {
    const match = option.match || {};
    const proxy = match.proxyStation || {};
    const stationName = proxy.stationName || `${fallbackPrefix} ${index + 1}`;
    const score = formatNumber(match.score, 1);
    const correlation = formatNumber(match.dailyCorrelation, 3);
    const distance = formatNumber(match.distanceKm, 1);
    const years = proxy.fullObservationYears ? `${proxy.fullObservationYears} yrs` : "record N/A";
    const prefix = index === 0 ? "Default - " : "";

    return `${prefix}${index + 1}. ${stationName} | ${years} | score ${score} | r ${correlation} | ${distance} km`;
}

export function renderComparisonSelect(selectId, label, options, fallbackPrefix, selectedIndex = 0) {
    if (!options || options.length < 2) {
        return "";
    }

    const optionHtml = options.map((option, index) => `
        <option value="${index}" ${index === selectedIndex ? "selected" : ""}>${comparisonOptionLabel(option, index, fallbackPrefix)}</option>
    `).join("");

    return `
        <div class="chart-control">
            <label for="${selectId}">${label}</label>
            <select id="${selectId}" data-comparison-select="${selectId}">
                ${optionHtml}
            </select>
        </div>
    `;
}

export function renderMonthlyComparisonChart(data) {
    const terms = matchTerms(data);
    return renderTemperatureComparisonChart({
        title: "One-Year Monthly Temperature Comparison",
        description: `Monthly average temperature for the nearest station and ${terms.chartProxyLabel.toLowerCase()} from`,
        emptyMessage: "Monthly comparison data is not available in this response. Restart FastAPI so it launches the rebuilt C++ engine, then run the analysis again.",
        points: data.bestProxyMonthlyComparison || [],
        includeDay: false,
        denseTicks: false,
        yAxisLabel: "Monthly Avg Temp (F)",
        xAxisLabel: "Month"
    });
}

export function renderDailyComparisonChart(data) {
    const options = data.highCorrelationComparisonOptions || [];
    const terms = matchTerms(data);
    const selectedOption = options[0];
    const match = selectedOption && selectedOption.match;
    const proxyName = match && match.proxyStation && match.proxyStation.stationName
        ? match.proxyStation.stationName
        : terms.chartProxyLabel;

    return renderTemperatureComparisonChart({
        title: "One-Year Daily Average Temperature Comparison",
        description: `Daily average temperature for the nearest station and ${proxyName} from`,
        emptyMessage: "Daily comparison data is not available in this response. Restart FastAPI so it launches the rebuilt C++ engine, then run the analysis again.",
        points: selectedOption ? selectedOption.dailyComparison : data.bestProxyDailyComparison || [],
        includeDay: true,
        denseTicks: true,
        yAxisLabel: "Daily Avg Temp (F)",
        xAxisLabel: "Date",
        proxyLabel: match ? `${proxyName} (r = ${formatNumber(match.dailyCorrelation, 3)})` : terms.chartProxyLabel,
        controlHtml: renderComparisonSelect(
            "high-correlation-select",
            data.matchMode === "hub_to_hub" ? "High-correlation similar hub result" : "High-correlation proxy result",
            options,
            data.matchMode === "hub_to_hub" ? "Similar hub" : "Proxy",
            0
        )
    });
}

export function renderLowCorrelationExample(data) {
    const options = data.lowCorrelationComparisonOptions || [];
    const terms = matchTerms(data);
    const example = options[0] || data.lowCorrelationExample;

    if (!example || !example.match) {
        return "";
    }

    const match = example.match;
    const proxyName = match.proxyStation && match.proxyStation.stationName
        ? match.proxyStation.stationName
        : `Low-correlation ${terms.chartProxyLabel.toLowerCase()}`;

    return renderTemperatureComparisonChart({
        title: "Temporary Low-Correlation Example",
        description: `Daily average temperature against ${proxyName} from`,
        emptyMessage: "Low-correlation comparison data is not available in this response.",
        points: example.dailyComparison || [],
        includeDay: true,
        denseTicks: true,
        yAxisLabel: "Daily Avg Temp (F)",
        xAxisLabel: "Date",
        cardClass: "diagnostic-card",
        proxyLabel: `${proxyName} (r = ${formatNumber(match.dailyCorrelation, 3)})`,
        controlHtml: renderComparisonSelect(
            "low-correlation-select",
            data.matchMode === "hub_to_hub" ? "Low-correlation similar hub example" : "Low-correlation example",
            options,
            data.matchMode === "hub_to_hub" ? "Low-correlation similar hub" : "Low-correlation proxy",
            0
        )
    });
}

export function updateTemperatureComparisonCard(selectElement, options, config) {
    const selectedIndex = Number(selectElement.value);
    const option = options[selectedIndex];

    if (!option || !option.match) {
        return;
    }

    const card = selectElement.closest(".card");
    if (!card) {
        return;
    }

    const proxyName = option.match.proxyStation && option.match.proxyStation.stationName
        ? option.match.proxyStation.stationName
        : config.fallbackProxyName;
    const chartHtml = renderTemperatureComparisonChart({
        title: config.title,
        description: `${config.descriptionPrefix} ${proxyName} from`,
        emptyMessage: config.emptyMessage,
        points: option.dailyComparison || [],
        includeDay: true,
        denseTicks: true,
        yAxisLabel: "Daily Avg Temp (F)",
        xAxisLabel: "Date",
        cardClass: config.cardClass || "",
        proxyLabel: `${proxyName} (r = ${formatNumber(option.match.dailyCorrelation, 3)})`,
        controlHtml: renderComparisonSelect(
            config.selectId,
            config.selectLabel,
            options,
            config.fallbackProxyName,
            selectedIndex
        )
    });

    const wrapper = document.createElement("div");
    wrapper.innerHTML = chartHtml.trim();
    card.replaceWith(wrapper.firstElementChild);
    attachChartSelectInteractions();
}

export function attachChartSelectInteractions() {
    const highSelect = document.getElementById("high-correlation-select");
    if (highSelect) {
        highSelect.addEventListener("change", function() {
            const hubMode = state.currentMatchMode === "hub_to_hub";
            updateTemperatureComparisonCard(
                this,
                state.currentHighCorrelationOptions || [],
                {
                    title: "One-Year Daily Average Temperature Comparison",
                    descriptionPrefix: "Daily average temperature for the nearest station and",
                    emptyMessage: "Daily comparison data is not available in this response.",
                    selectId: "high-correlation-select",
                    selectLabel: hubMode ? "High-correlation similar hub result" : "High-correlation proxy result",
                    fallbackProxyName: hubMode ? "Similar hub" : "Proxy"
                }
            );
        });
    }

    const lowSelect = document.getElementById("low-correlation-select");
    if (lowSelect) {
        lowSelect.addEventListener("change", function() {
            const hubMode = state.currentMatchMode === "hub_to_hub";
            updateTemperatureComparisonCard(
                this,
                state.currentLowCorrelationOptions || [],
                {
                    title: "Temporary Low-Correlation Example",
                    descriptionPrefix: "Daily average temperature against",
                    emptyMessage: "Low-correlation comparison data is not available in this response.",
                    selectId: "low-correlation-select",
                    selectLabel: hubMode ? "Low-correlation similar hub example" : "Low-correlation example",
                    fallbackProxyName: hubMode ? "Low-correlation similar hub" : "Low-correlation proxy",
                    cardClass: "diagnostic-card"
                }
            );
        });
    }
}
