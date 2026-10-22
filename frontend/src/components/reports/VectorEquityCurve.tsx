/**
 * Institutional Vector Chart: Synchronized Portfolio Equity / Wealth Curve
 * Supports Dual Portfolio (Net/Gross) and Benchmark Curve, plus underwater drawdown overlay.
 * Clean, lightweight, zero-dependency SVG with print-stable geometry and accessible tabular context.
 */

import React from 'react';
import type { TimeSeriesPoint } from '../../types/reporting';
import { formatCurrency, formatPercent } from './formatters';

interface VectorEquityCurveProps {
  data: TimeSeriesPoint[];
  baseCurrency?: string;
  height?: number;
  showDrawdown?: boolean;
  benchmarkName?: string | null;
  compact?: boolean;
}

export const VectorEquityCurve: React.FC<VectorEquityCurveProps> = ({
  data,
  baseCurrency = 'USD',
  height = 240,
  showDrawdown = false,
  benchmarkName = 'Benchmark',
  compact = false,
}) => {
  if (!data || data.length === 0) {
    return (
      <div className="report-chart-empty" role="region" aria-label="Equity Curve">
        <p className="report-empty-text">No time-series observations available for this reporting window.</p>
      </div>
    );
  }

  const width = 800;
  const padding = compact
    ? { top: 12, right: 16, bottom: 24, left: 56 }
    : { top: 16, right: 24, bottom: 32, left: 64 };

  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  // Extract min/max values for NAV
  let minVal = Infinity;
  let maxVal = -Infinity;

  for (const pt of data) {
    if (pt.portfolio_value_net != null && isFinite(pt.portfolio_value_net)) {
      if (pt.portfolio_value_net < minVal) minVal = pt.portfolio_value_net;
      if (pt.portfolio_value_net > maxVal) maxVal = pt.portfolio_value_net;
    }
    if (pt.portfolio_value_gross != null && isFinite(pt.portfolio_value_gross)) {
      if (pt.portfolio_value_gross < minVal) minVal = pt.portfolio_value_gross;
      if (pt.portfolio_value_gross > maxVal) maxVal = pt.portfolio_value_gross;
    }
    if (pt.benchmark_value != null && isFinite(pt.benchmark_value)) {
      if (pt.benchmark_value < minVal) minVal = pt.benchmark_value;
      if (pt.benchmark_value > maxVal) maxVal = pt.benchmark_value;
    }
  }

  if (minVal === Infinity || maxVal === -Infinity) {
    minVal = 100000;
    maxVal = 100000;
  }

  // Add 4% vertical buffer
  const valRange = maxVal - minVal || maxVal * 0.1 || 1.0;
  const yMin = Math.max(0, minVal - valRange * 0.04);
  const yMax = maxVal + valRange * 0.04;
  const ySpan = yMax - yMin;

  const n = data.length;
  const getX = (i: number) => padding.left + (i / Math.max(1, n - 1)) * plotW;
  const getY = (val: number) => padding.top + plotH - ((val - yMin) / ySpan) * plotH;

  // Build SVG Paths
  const netPoints: string[] = [];
  const grossPoints: string[] = [];
  const bmPoints: string[] = [];
  let hasGross = false;
  let hasBm = false;

  data.forEach((pt, i) => {
    const x = getX(i);
    if (pt.portfolio_value_net != null) {
      netPoints.push(`${x.toFixed(1)},${getY(pt.portfolio_value_net).toFixed(1)}`);
    }
    if (pt.portfolio_value_gross != null) {
      hasGross = true;
      grossPoints.push(`${x.toFixed(1)},${getY(pt.portfolio_value_gross).toFixed(1)}`);
    }
    if (pt.benchmark_value != null) {
      hasBm = true;
      bmPoints.push(`${x.toFixed(1)},${getY(pt.benchmark_value).toFixed(1)}`);
    }
  });

  const netPath = netPoints.length > 0 ? `M ${netPoints.join(' L ')}` : '';
  const grossPath = grossPoints.length > 0 ? `M ${grossPoints.join(' L ')}` : '';
  const bmPath = bmPoints.length > 0 ? `M ${bmPoints.join(' L ')}` : '';

  // Area under Net NAV
  const netAreaPath =
    netPoints.length > 0
      ? `M ${getX(0)},${(padding.top + plotH).toFixed(1)} L ${netPoints.join(' L ')} L ${getX(
          n - 1
        )},${(padding.top + plotH).toFixed(1)} Z`
      : '';

  // Drawdown overlay path if requested
  let ddPath = '';
  if (showDrawdown) {
    const ddPoints: string[] = [];
    const maxDd = 0.5; // Scale drawdown up to 50%
    data.forEach((pt, i) => {
      const x = getX(i);
      const dd = Math.min(maxDd, Math.max(0, pt.drawdown_net || 0));
      // Render drawdown hanging down from top of an underwater strip or bottom
      const y = padding.top + plotH - (dd / maxDd) * (plotH * 0.35);
      ddPoints.push(`${x.toFixed(1)},${y.toFixed(1)}`);
    });
    if (ddPoints.length > 0) {
      ddPath = `M ${getX(0)},${(padding.top + plotH).toFixed(1)} L ${ddPoints.join(' L ')} L ${getX(
        n - 1
      )},${(padding.top + plotH).toFixed(1)} Z`;
    }
  }

  // Y-axis ticks (4 ticks)
  const yTicks = [0, 0.33, 0.66, 1.0].map((pct) => {
    const val = yMin + pct * ySpan;
    const y = padding.top + plotH - pct * plotH;
    return { val, y };
  });

  // X-axis date labels (3 to 5 evenly spaced labels)
  const xLabelsCount = compact ? 3 : 5;
  const xIndices = [0];
  for (let k = 1; k < xLabelsCount - 1; k++) {
    xIndices.push(Math.round((k / (xLabelsCount - 1)) * (n - 1)));
  }
  if (n > 1) xIndices.push(n - 1);

  const startVal = data[0].portfolio_value_net;
  const endVal = data[n - 1].portfolio_value_net;
  const totalReturn = startVal > 0 ? (endVal - startVal) / startVal : 0;

  return (
    <div className="report-vector-chart-container" role="region" aria-label="Portfolio Wealth & Equity Curve">
      <div className="report-chart-header">
        <div className="report-chart-title">
          Portfolio Cumulative Wealth Curve ({baseCurrency})
          <span className="report-chart-badge">{n} daily observations</span>
        </div>
        <div className="report-chart-legend">
          <span className="legend-item">
            <span className="legend-line net"></span> Portfolio Net NAV
          </span>
          {hasGross && (
            <span className="legend-item">
              <span className="legend-line gross"></span> Portfolio Gross NAV
            </span>
          )}
          {hasBm && (
            <span className="legend-item">
              <span className="legend-line benchmark"></span> {benchmarkName || 'Benchmark'}
            </span>
          )}
        </div>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="report-svg-chart"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label={`Equity curve showing portfolio growth from ${formatCurrency(startVal, baseCurrency)} to ${formatCurrency(endVal, baseCurrency)}`}
      >
        <defs>
          <linearGradient id="netNavGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1E3A8A" stopOpacity="0.25" />
            <stop offset="100%" stopColor="#1E3A8A" stopOpacity="0.01" />
          </linearGradient>
          <linearGradient id="ddGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#DC2626" stopOpacity="0.2" />
            <stop offset="100%" stopColor="#DC2626" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Horizontal grid lines */}
        {yTicks.map((tick, idx) => (
          <g key={idx}>
            <line
              x1={padding.left}
              y1={tick.y}
              x2={width - padding.right}
              y2={tick.y}
              stroke="#E2E8F0"
              strokeDasharray={idx === 0 ? 'none' : '3,3'}
              strokeWidth="0.75"
            />
            <text
              x={padding.left - 8}
              y={tick.y + 3}
              textAnchor="end"
              fontSize="9"
              fontFamily="var(--report-font-mono, monospace)"
              fill="#64748B"
            >
              {formatCurrency(tick.val, baseCurrency, 0)}
            </text>
          </g>
        ))}

        {/* X-axis ticks & labels */}
        {xIndices.map((idxVal, k) => {
          const x = getX(idxVal);
          const dt = data[idxVal]?.date || '';
          return (
            <g key={k}>
              <line x1={x} y1={padding.top + plotH} x2={x} y2={padding.top + plotH + 4} stroke="#CBD5E1" strokeWidth="1" />
              <text
                x={x}
                y={padding.top + plotH + 16}
                textAnchor={k === 0 ? 'start' : k === xIndices.length - 1 ? 'end' : 'middle'}
                fontSize="9"
                fontFamily="var(--report-font-mono, monospace)"
                fill="#64748B"
              >
                {dt}
              </text>
            </g>
          );
        })}

        {/* Drawdown overlay */}
        {showDrawdown && ddPath && (
          <path d={ddPath} fill="url(#ddGradient)" stroke="none" />
        )}

        {/* Net NAV Area Fill */}
        {netAreaPath && (
          <path d={netAreaPath} fill="url(#netNavGradient)" stroke="none" />
        )}

        {/* Benchmark line */}
        {hasBm && bmPath && (
          <path
            d={bmPath}
            fill="none"
            stroke="#94A3B8"
            strokeWidth="1.5"
            strokeDasharray="4,3"
          />
        )}

        {/* Gross NAV line */}
        {hasGross && grossPath && (
          <path
            d={grossPath}
            fill="none"
            stroke="#0284C7"
            strokeWidth="1.25"
            strokeDasharray="2,2"
          />
        )}

        {/* Net NAV line (Primary) */}
        {netPath && (
          <path
            d={netPath}
            fill="none"
            stroke="#1E3A8A"
            strokeWidth="2.25"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        )}
      </svg>

      <div className="report-chart-footer-meta">
        <span>Initial Capital: {formatCurrency(startVal, baseCurrency)}</span>
        <span>Ending Value: {formatCurrency(endVal, baseCurrency)}</span>
        <span>Net Compounded Change: {formatPercent(totalReturn, 2, true)}</span>
      </div>
    </div>
  );
};
