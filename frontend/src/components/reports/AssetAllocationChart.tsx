/**
 * Institutional Vector Chart: Asset Allocation Breakdown & Holdings Table
 * Vector horizontal stacked distribution bar and high-density holdings table.
 * Preserves cash, short positions, target vs effective weights, and return contributions.
 */

import React from 'react';
import type { AssetAllocationItem } from '../../types/reporting';
import { formatPercent } from './formatters';

interface AssetAllocationChartProps {
  allocations: AssetAllocationItem[];
  compact?: boolean;
}

const PALETTE = [
  '#1E3A8A', // Deep Navy
  '#0284C7', // Slate Blue
  '#0D9488', // Teal
  '#10B981', // Emerald
  '#F59E0B', // Amber
  '#8B5CF6', // Purple
  '#EC4899', // Pink
  '#64748B', // Neutral Slate
];

export const AssetAllocationChart: React.FC<AssetAllocationChartProps> = ({
  allocations,
  compact = false,
}) => {
  if (!allocations || allocations.length === 0) {
    return (
      <div className="report-allocations-empty" role="region" aria-label="Asset Allocation">
        <p className="report-empty-text">No target or effective asset allocations resolved for this strategy.</p>
      </div>
    );
  }

  // Display top holdings (up to 6 in compact, up to 10 in full)
  const maxDisplay = compact ? 6 : 10;
  const sortedAlloc = [...allocations].sort(
    (a, b) => Math.abs(b.effective_weight) - Math.abs(a.effective_weight)
  );
  const displayItems = sortedAlloc.slice(0, maxDisplay);

  return (

    <div className="report-allocation-container" role="region" aria-label="Asset Allocation Breakdown">
      <div className="report-section-heading">
        {compact ? 'Top Portfolio Holdings & Allocations' : 'Asset Allocation & Risk Contribution Breakdown'}
      </div>

      {/* Vector Stacked Bar Representation */}
      <div className="report-alloc-stacked-bar" role="img" aria-label="Allocation distribution bar">
        {displayItems.map((item, idx) => {
          const pct = Math.max(0, item.effective_weight) * 100;
          if (pct < 0.5) return null;
          const color = PALETTE[idx % PALETTE.length];
          return (
            <div
              key={item.asset_id}
              className="report-alloc-segment"
              style={{
                width: `${pct.toFixed(1)}%`,
                backgroundColor: color,
              }}
              title={`${item.ticker}: ${formatPercent(item.effective_weight, 1)}`}
            >
              {pct >= 7 && <span className="alloc-segment-label">{item.ticker}</span>}
            </div>
          );
        })}
      </div>

      {/* Allocation Table */}
      <table className="report-alloc-table">
        <thead>
          <tr>
            <th className="th-asset">Asset / Ticker</th>
            <th className="th-market">Market</th>
            <th className="th-weight">Target Wgt</th>
            <th className="th-weight">Effective Wgt</th>
            {!compact && <th className="th-metric">Cumulative Ret</th>}
            {!compact && <th className="th-metric">Return Contrib</th>}
          </tr>
        </thead>
        <tbody>
          {displayItems.map((item, idx) => {
            const dotColor = PALETTE[idx % PALETTE.length];
            return (
              <tr key={item.asset_id}>
                <td className="td-asset">
                  <span className="alloc-color-dot" style={{ backgroundColor: dotColor }}></span>
                  <span className="alloc-ticker font-mono">{item.ticker}</span>
                  {item.name && <span className="alloc-name">{item.name}</span>}
                </td>
                <td className="td-market font-mono">{item.market || 'US'}</td>
                <td className="td-weight font-mono">{formatPercent(item.target_weight, 1)}</td>
                <td className="td-weight font-mono font-bold">{formatPercent(item.effective_weight, 1)}</td>
                {!compact && (
                  <td className="td-metric font-mono">
                    {formatPercent(item.asset_cumulative_return, 1, true)}
                  </td>
                )}
                {!compact && (
                  <td className="td-metric font-mono">
                    {formatPercent(item.total_contribution, 2, true)}
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
