/**
 * Institutional Vector Chart: Monthly Returns Heatmap & Discrete Compounding Table
 * Displays historical discrete monthly net returns R_M = prod(1 + r_t) - 1.
 * Clean, printable grid with clear positive (emerald) vs negative (crimson) shading and annual compounded totals.
 */

import React from 'react';
import type { MonthlyReturnCell } from '../../types/reporting';
import { formatPercent } from './formatters';

interface MonthlyReturnsGridProps {
  cells: MonthlyReturnCell[];
  showGross?: boolean;
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export const MonthlyReturnsGrid: React.FC<MonthlyReturnsGridProps> = ({
  cells,
  showGross = false,
}) => {
  if (!cells || cells.length === 0) {
    return (
      <div className="report-grid-empty" role="region" aria-label="Monthly Returns Table">
        <p className="report-empty-text">No discrete monthly return observations recorded.</p>
      </div>
    );
  }

  // Group by Year -> Month -> Cell
  const yearsMap: Record<number, Record<number, MonthlyReturnCell>> = {};
  for (const cell of cells) {
    if (!yearsMap[cell.year]) {
      yearsMap[cell.year] = {};
    }
    yearsMap[cell.year][cell.month] = cell;
  }

  const sortedYears = Object.keys(yearsMap)
    .map(Number)
    .sort((a, b) => b - a); // Descending years

  // Function to determine cell background style based on magnitude
  const getCellBg = (val: number | null | undefined): string => {
    if (val === null || val === undefined || isNaN(val)) return 'transparent';
    if (Math.abs(val) < 0.0001) return '#F8FAFC';
    if (val > 0) {
      const alpha = Math.min(0.7, 0.12 + Math.min(1.0, val / 0.1) * 0.5);
      return `rgba(16, 185, 129, ${alpha.toFixed(2)})`;
    } else {
      const alpha = Math.min(0.7, 0.12 + Math.min(1.0, Math.abs(val) / 0.1) * 0.5);
      return `rgba(239, 68, 68, ${alpha.toFixed(2)})`;
    }
  };

  const getTextColor = (val: number | null | undefined): string => {
    if (val === null || val === undefined || isNaN(val)) return '#94A3B8';
    if (Math.abs(val) < 0.0001) return '#475569';
    if (val > 0.05 || val < -0.05) return '#FFFFFF'; // High contrast text on dark cell
    return val > 0 ? '#065F46' : '#991B1B';
  };

  return (
    <div className="report-monthly-grid-container" role="region" aria-label="Monthly Returns Matrix">
      <div className="report-section-heading">Monthly Net Return Performance Matrix (% Compounded)</div>
      <table className="report-monthly-table">
        <thead>
          <tr>
            <th className="th-year">Year</th>
            {MONTH_NAMES.map((m) => (
              <th key={m} className="th-month">
                {m}
              </th>
            ))}
            <th className="th-ytd">Year / YTD</th>
          </tr>
        </thead>
        <tbody>
          {sortedYears.map((yr) => {
            const row = yearsMap[yr];
            // Compute YTD compounded return: prod(1 + r) - 1
            let compNet = 1.0;
            let countNet = 0;
            for (let m = 1; m <= 12; m++) {
              if (row[m] && row[m].return_net != null) {
                compNet *= 1.0 + row[m].return_net;
                countNet++;
              }
            }
            const ytdNet = countNet > 0 ? compNet - 1.0 : null;

            return (
              <tr key={yr}>
                <td className="td-year font-mono">{yr}</td>
                {MONTH_NAMES.map((_, idx) => {
                  const m = idx + 1;
                  const cell = row[m];
                  const val = showGross && cell?.return_gross != null ? cell.return_gross : cell?.return_net;
                  return (
                    <td
                      key={m}
                      className="td-month font-mono"
                      style={{
                        backgroundColor: getCellBg(val),
                        color: getTextColor(val),
                        fontWeight: val != null && Math.abs(val) > 0.03 ? 600 : 400,
                      }}
                    >
                      {formatPercent(val, 1)}
                    </td>
                  );
                })}
                <td
                  className="td-ytd font-mono"
                  style={{
                    backgroundColor: getCellBg(ytdNet),
                    color: getTextColor(ytdNet),
                    fontWeight: 700,
                  }}
                >
                  {formatPercent(ytdNet, 2, true)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
