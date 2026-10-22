/**
 * Institutional Vector Chart: Research Diagnostics Annex Visualizations
 * Vector scatter plot for In-Sample vs Out-of-Sample Sharpe performance with OLS regression fit line,
 * and PBO relative rank distribution histogram with median threshold markers.
 */

import React from 'react';
import type {
  CSCVCombinationsPoint,
  CSCVHistogramBin,
  DegradationRegression,
  PBORiskLevel,
} from '../../types/api';
import { formatPercent, formatRatio } from './formatters';

interface ResearchDiagnosticsVisualsProps {
  combinationsSample: CSCVCombinationsPoint[];
  rankDistribution: CSCVHistogramBin[];
  degradationRegression: DegradationRegression;
  pbo: number;
  pboRiskLevel: PBORiskLevel;
}

export const ResearchDiagnosticsVisuals: React.FC<ResearchDiagnosticsVisualsProps> = ({
  combinationsSample,
  rankDistribution,
  degradationRegression,
  pbo,
  pboRiskLevel,
}) => {
  // Scatter Plot geometry: 400x200
  const scatterW = 380;
  const scatterH = 180;
  const sPad = { top: 12, right: 16, bottom: 24, left: 40 };
  const sPlotW = scatterW - sPad.left - sPad.right;
  const sPlotH = scatterH - sPad.top - sPad.bottom;

  // Determine IS and OOS min/max
  let minIS = Infinity;
  let maxIS = -Infinity;
  let minOOS = Infinity;
  let maxOOS = -Infinity;

  for (const pt of combinationsSample) {
    if (pt.is_sharpe < minIS) minIS = pt.is_sharpe;
    if (pt.is_sharpe > maxIS) maxIS = pt.is_sharpe;
    if (pt.oos_sharpe < minOOS) minOOS = pt.oos_sharpe;
    if (pt.oos_sharpe > maxOOS) maxOOS = pt.oos_sharpe;
  }

  if (minIS === Infinity) {
    minIS = 0;
    maxIS = 2.0;
    minOOS = -0.5;
    maxOOS = 1.5;
  }

  // Common bounds
  const xMin = Math.min(minIS, 0);
  const xMax = Math.max(maxIS, 1.0);
  const yMin = Math.min(minOOS, -0.5);
  const yMax = Math.max(maxOOS, 1.0);

  const getScatterX = (val: number) => sPad.left + ((val - xMin) / (xMax - xMin || 1)) * sPlotW;
  const getScatterY = (val: number) => sPad.top + sPlotH - ((val - yMin) / (yMax - yMin || 1)) * sPlotH;

  // Regression line coordinates
  const regX1 = xMin;
  const regY1 = degradationRegression.intercept + degradationRegression.slope * regX1;
  const regX2 = xMax;
  const regY2 = degradationRegression.intercept + degradationRegression.slope * regX2;

  // Histogram geometry: 380x180
  const histW = 380;
  const histH = 180;
  const hPad = { top: 12, right: 16, bottom: 24, left: 40 };
  const hPlotW = histW - hPad.left - hPad.right;
  const hPlotH = histH - hPad.top - hPad.bottom;

  const maxFreq = Math.max(0.01, ...rankDistribution.map((b) => b.relative_frequency));
  const numBins = Math.max(1, rankDistribution.length);
  const barW = Math.max(2, hPlotW / numBins - 2);

  return (
    <div className="report-research-visuals-container" role="region" aria-label="Overfitting Visual Diagnostics">
      <div className="report-visual-two-col">
        {/* IS vs OOS Performance Degradation Scatter */}
        <div className="report-visual-card">
          <div className="visual-card-title">
            In-Sample vs Out-of-Sample Performance Degradation
            <span className="visual-badge">R² = {formatRatio(degradationRegression.r_squared, 2)}</span>
          </div>
          <svg
            viewBox={`0 0 ${scatterW} ${scatterH}`}
            className="report-svg-chart"
            role="img"
            aria-label="Scatter plot showing in-sample vs out-of-sample Sharpe ratios"
          >
            {/* Grid & zero lines */}
            <line
              x1={sPad.left}
              y1={getScatterY(0)}
              x2={scatterW - sPad.right}
              y2={getScatterY(0)}
              stroke="#CBD5E1"
              strokeWidth="1"
            />
            <line
              x1={getScatterX(0)}
              y1={sPad.top}
              x2={getScatterX(0)}
              y2={sPad.top + sPlotH}
              stroke="#CBD5E1"
              strokeWidth="1"
            />

            {/* Regression fit line */}
            <line
              x1={getScatterX(regX1)}
              y1={getScatterY(regY1)}
              x2={getScatterX(regX2)}
              y2={getScatterY(regY2)}
              stroke="#0284C7"
              strokeWidth="1.5"
              strokeDasharray="3,2"
            />

            {/* Data points */}
            {combinationsSample.map((pt, i) => {
              const cx = getScatterX(pt.is_sharpe);
              const cy = getScatterY(pt.oos_sharpe);
              const isOverfitted = pt.is_overfitted;
              return (
                <circle
                  key={i}
                  cx={cx}
                  cy={cy}
                  r="3"
                  fill={isOverfitted ? '#EF4444' : '#10B981'}
                  opacity="0.75"
                />
              );
            })}

            {/* Axis Labels */}
            <text x={scatterW / 2} y={scatterH - 4} textAnchor="middle" fontSize="8" fill="#64748B">
              In-Sample Sharpe (Training Subset)
            </text>
            <text
              x={10}
              y={scatterH / 2}
              textAnchor="middle"
              fontSize="8"
              fill="#64748B"
              transform={`rotate(-90 10 ${scatterH / 2})`}
            >
              OOS Sharpe
            </text>
          </svg>
          <div className="visual-card-footer">
            <span>Slope: {formatRatio(degradationRegression.slope, 2)}</span>
            <span>p-val: {formatRatio(degradationRegression.p_value, 4)}</span>
            <span>Sample size: {combinationsSample.length} trials</span>
          </div>
        </div>

        {/* CSCV Relative Rank Distribution Histogram */}
        <div className="report-visual-card">
          <div className="visual-card-title">
            Relative Rank Distribution (PBO = {formatPercent(pbo, 1)})
            <span className={`pbo-risk-badge ${pboRiskLevel}`}>{pboRiskLevel.toUpperCase()} RISK</span>
          </div>
          <svg
            viewBox={`0 0 ${histW} ${histH}`}
            className="report-svg-chart"
            role="img"
            aria-label="Histogram showing relative rank distribution of optimal strategies"
          >
            {/* Median threshold line (Rank = 0.5) */}
            <line
              x1={hPad.left + hPlotW * 0.5}
              y1={hPad.top}
              x2={hPad.left + hPlotW * 0.5}
              y2={hPad.top + hPlotH}
              stroke="#EF4444"
              strokeWidth="1.5"
              strokeDasharray="4,2"
            />

            {/* Histogram bars */}
            {rankDistribution.map((bin, i) => {
              const x = hPad.left + (i / numBins) * hPlotW;
              const h = (bin.relative_frequency / maxFreq) * hPlotH;
              const y = hPad.top + hPlotH - h;
              // If bin_start >= 0.5, it represents overfitted OOS outcomes
              const isOverfitZone = bin.bin_start >= 0.5;
              return (

                <rect
                  key={i}
                  x={x + 1}
                  y={y}
                  width={barW}
                  height={Math.max(1, h)}
                  fill={isOverfitZone ? 'rgba(239, 68, 68, 0.65)' : 'rgba(30, 58, 138, 0.75)'}
                />
              );
            })}

            {/* Labels */}
            <text x={hPad.left + hPlotW * 0.5} y={hPad.top + 10} textAnchor="middle" fontSize="8" fill="#DC2626">
              Overfit Threshold (Rank &gt; 0.5)
            </text>
            <text x={histW / 2} y={histH - 4} textAnchor="middle" fontSize="8" fill="#64748B">
              Relative Rank in OOS Test Slice (0.0 = Best, 1.0 = Worst)
            </text>
          </svg>
          <div className="visual-card-footer">
            <span>Partitions: {rankDistribution.length} bins</span>
            <span>Overfitting Probability: {formatPercent(pbo, 1)}</span>
          </div>
        </div>
      </div>
    </div>
  );
};
