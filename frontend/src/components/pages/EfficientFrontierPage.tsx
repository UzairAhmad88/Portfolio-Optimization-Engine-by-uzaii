import React, { useState } from 'react';
import {
  TrendingUp,
  RefreshCw,
  XCircle,
  Info,
  Award,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  EfficientFrontierRequest,
  EfficientFrontierResponse,
  FrontierPointModel,
  PortfolioDefinition,
} from '../../types/api';

interface EfficientFrontierPageProps {
  initialPortfolio?: PortfolioDefinition | null;
}

export const EfficientFrontierPage: React.FC<EfficientFrontierPageProps> = ({ initialPortfolio }) => {
  const { currentDataset, availableAssets } = useDataset();

  const [targetCount, setTargetCount] = useState<number>(20);
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.02);
  const [annualized, setAnnualized] = useState<boolean>(true);
  const [periodsPerYear, setPeriodsPerYear] = useState<number>(252);

  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [frontierResult, setFrontierResult] = useState<EfficientFrontierResponse | null>(null);
  const [frontierError, setFrontierError] = useState<string | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<FrontierPointModel | null>(null);

  const handleGenerateFrontier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!currentDataset) {
      setFrontierError('No active dataset found.');
      return;
    }

    const assetsToUse =
      initialPortfolio?.assets && initialPortfolio.assets.length > 0
        ? initialPortfolio.assets
        : availableAssets.map((a) => a.ticker);

    if (assetsToUse.length === 0) {
      setFrontierError('No assets available for frontier computation.');
      return;
    }

    setIsGenerating(true);
    setFrontierError(null);
    setSelectedPoint(null);

    const portfolioDef: PortfolioDefinition = initialPortfolio || {
      name: 'Markowitz Frontier Universe',
      dataset_id: currentDataset.dataset_id,
      assets: assetsToUse,
      constraints: {
        default_min_weight: 0.0,
        default_max_weight: 1.0,
        target_total_weight: 1.0,
        allow_short: false,
      },
    };

    const request: EfficientFrontierRequest = {
      portfolio: portfolioDef,
      target_count: Number(targetCount),
      risk_free_rate: Number(riskFreeRate),
      annualized,
      periods_per_year: Number(periodsPerYear),
    };

    try {
      const res = await apiClient.generateEfficientFrontier(request);
      setFrontierResult(res);
      if (res.global_minimum_variance) {
        setSelectedPoint(res.global_minimum_variance);
      } else if (res.points.length > 0) {
        setSelectedPoint(res.points[0]);
      }
    } catch (err: any) {
      setFrontierError(err.message || 'Frontier generation failed.');
      setFrontierResult(null);
    } finally {
      setIsGenerating(false);
    }
  };

  if (!currentDataset) {
    return (
      <div className="workspace-container">
        <div className="alert alert-info">
          <Info size={18} style={{ flexShrink: 0 }} />
          <div>
            <strong>No Dataset Selected</strong>
            <p style={{ marginTop: '4px', fontSize: '13px' }}>
              Upload and register a dataset in <strong>Market Data</strong> to compute the Markowitz Efficient Frontier.
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Calculate SVG plot dimensions and bounds
  const renderFrontierChart = () => {
    if (!frontierResult || frontierResult.points.length === 0) return null;

    const allPoints = [...frontierResult.points];
    if (frontierResult.global_minimum_variance) {
      allPoints.push(frontierResult.global_minimum_variance);
    }

    const validPoints = allPoints.filter(
      (p) => isFinite(p.volatility) && isFinite(p.actual_return) && p.classification !== 'failed'
    );

    if (validPoints.length === 0) {
      return (
        <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
          No feasible points could be computed for the requested constraints.
        </div>
      );
    }

    const volatilities = validPoints.map((p) => p.volatility);
    const returns = validPoints.map((p) => p.actual_return);

    const minVol = Math.max(0, Math.min(...volatilities) * 0.9);
    const maxVol = Math.max(...volatilities) * 1.1;
    const minRet = Math.min(...returns) < 0 ? Math.min(...returns) * 1.1 : Math.min(...returns) * 0.9;
    const maxRet = Math.max(...returns) * 1.1;

    const width = 720;
    const height = 400;
    const padLeft = 60;
    const padRight = 30;
    const padTop = 30;
    const padBottom = 50;

    const plotW = width - padLeft - padRight;
    const plotH = height - padTop - padBottom;

    const scaleX = (vol: number) => padLeft + ((vol - minVol) / (maxVol - minVol || 1)) * plotW;
    const scaleY = (ret: number) => padTop + plotH - ((ret - minRet) / (maxRet - minRet || 1)) * plotH;

    // Separate into efficient and dominated points
    const efficientPoints = validPoints.filter((p) => p.classification === 'efficient');
    const dominatedPoints = validPoints.filter((p) => p.classification === 'dominated_inefficient');
    const gmv = frontierResult.global_minimum_variance;

    return (
      <div style={{ position: 'relative', width: '100%', overflowX: 'auto' }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: '100%', height: 'auto', maxHeight: '460px', backgroundColor: 'var(--bg-input)', borderRadius: 'var(--radius-md)' }}
        >
          {/* Grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const y = padTop + plotH * pct;
            const retVal = maxRet - pct * (maxRet - minRet);
            return (
              <g key={`y-grid-${i}`}>
                <line x1={padLeft} y1={y} x2={width - padRight} y2={y} stroke="var(--border-subtle)" strokeDasharray="3 3" />
                <text x={padLeft - 8} y={y + 4} fill="var(--text-dim)" fontSize="10" textAnchor="end" fontFamily="var(--font-mono)">
                  {(retVal * 100).toFixed(1)}%
                </text>
              </g>
            );
          })}

          {[0, 0.25, 0.5, 0.75, 1].map((pct, i) => {
            const x = padLeft + plotW * pct;
            const volVal = minVol + pct * (maxVol - minVol);
            return (
              <g key={`x-grid-${i}`}>
                <line x1={x} y1={padTop} x2={x} y2={height - padBottom} stroke="var(--border-subtle)" strokeDasharray="3 3" />
                <text x={x} y={height - padBottom + 16} fill="var(--text-dim)" fontSize="10" textAnchor="middle" fontFamily="var(--font-mono)">
                  {(volVal * 100).toFixed(1)}%
                </text>
              </g>
            );
          })}

          {/* Axes labels */}
          <text x={width / 2} y={height - 12} fill="var(--text-secondary)" fontSize="12" textAnchor="middle" fontWeight="500">
            Portfolio Volatility (σ_p)
          </text>
          <text
            x={-height / 2}
            y={16}
            fill="var(--text-secondary)"
            fontSize="12"
            textAnchor="middle"
            fontWeight="500"
            transform="rotate(-90)"
          >
            Expected Return (E[R_p])
          </text>

          {/* Dominated Points (Lower Branch) */}
          {dominatedPoints.map((pt, idx) => {
            const cx = scaleX(pt.volatility);
            const cy = scaleY(pt.actual_return);
            const isSel = selectedPoint === pt;
            return (
              <circle
                key={`dom-${idx}`}
                cx={cx}
                cy={cy}
                r={isSel ? 6 : 4}
                fill={isSel ? 'var(--text-primary)' : 'var(--text-dim)'}
                stroke={isSel ? 'var(--accent)' : 'var(--border-medium)'}
                strokeWidth={isSel ? 2 : 1}
                style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                onClick={() => setSelectedPoint(pt)}
              />
            );
          })}

          {/* Efficient Frontier Points (Upper Branch) */}
          {efficientPoints.map((pt, idx) => {
            const cx = scaleX(pt.volatility);
            const cy = scaleY(pt.actual_return);
            const isSel = selectedPoint === pt;
            return (
              <circle
                key={`eff-${idx}`}
                cx={cx}
                cy={cy}
                r={isSel ? 7 : 5}
                fill={isSel ? 'var(--accent)' : '#38BDF8'}
                stroke={isSel ? '#FFFFFF' : 'var(--border-subtle)'}
                strokeWidth={isSel ? 2 : 1}
                style={{ cursor: 'pointer', transition: 'all 0.15s ease' }}
                onClick={() => setSelectedPoint(pt)}
              />
            );
          })}

          {/* Global Minimum-Variance (GMV) Anchor */}
          {gmv && (
            <g onClick={() => setSelectedPoint(gmv)} style={{ cursor: 'pointer' }}>
              <polygon
                points={`
                  ${scaleX(gmv.volatility)},${scaleY(gmv.actual_return) - 8}
                  ${scaleX(gmv.volatility) + 7},${scaleY(gmv.actual_return) + 6}
                  ${scaleX(gmv.volatility) - 7},${scaleY(gmv.actual_return) + 6}
                `}
                fill="#10B981"
                stroke="#FFFFFF"
                strokeWidth="1.5"
              />
            </g>
          )}
        </svg>

        {/* Legend */}
        <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', marginTop: '10px', fontSize: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--accent)' }} />
            <span style={{ color: 'var(--text-primary)' }}>Efficient Frontier (Upper Branch)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: 'var(--text-dim)' }} />
            <span style={{ color: 'var(--text-muted)' }}>Dominated / Inefficient</span>
          </div>
          {gmv && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span style={{ width: '10px', height: '10px', backgroundColor: 'var(--success)' }} />
              <span style={{ color: 'var(--success)', fontWeight: 600 }}>Global Minimum-Variance (GMV)</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="workspace-container">
      {/* Controls Card */}
      <form onSubmit={handleGenerateFrontier}>
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <div className="card-title">
              <TrendingUp size={18} style={{ color: 'var(--accent)' }} />
              <span>Markowitz Continuous Efficient Frontier Generator</span>
            </div>
            <span className="badge badge-neutral">
              Quadratic Solver (SLSQP)
            </span>
          </div>

          {frontierError && (
            <div className="alert alert-danger">
              <XCircle size={18} style={{ flexShrink: 0 }} />
              <div>{frontierError}</div>
            </div>
          )}

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
            <div className="form-group">
              <label className="form-label">Target Return Steps</label>
              <input
                type="number"
                min={2}
                max={100}
                className="input font-mono"
                value={targetCount}
                onChange={(e) => setTargetCount(parseInt(e.target.value, 10) || 20)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label">
                <span>Annual Risk-Free Rate (r_f)</span>
                <span className="font-mono">{(riskFreeRate * 100).toFixed(1)}%</span>
              </label>
              <input
                type="number"
                step="0.005"
                className="input font-mono"
                value={riskFreeRate}
                onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Periods Per Year</label>
              <input
                type="number"
                className="input font-mono"
                value={periodsPerYear}
                onChange={(e) => setPeriodsPerYear(parseInt(e.target.value, 10) || 252)}
              />
            </div>

            <div className="form-group" style={{ justifyContent: 'center' }}>
              <label className="form-label">Annualization Mode</label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', height: '36px' }}>
                <input
                  type="checkbox"
                  id="frontier-annualized-checkbox"
                  checked={annualized}
                  onChange={(e) => setAnnualized(e.target.checked)}
                  style={{ cursor: 'pointer' }}
                />
                <label htmlFor="frontier-annualized-checkbox" style={{ fontSize: '13px', cursor: 'pointer', color: 'var(--text-secondary)' }}>
                  Annualize Points
                </label>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              type="submit"
              disabled={isGenerating}
              className="btn btn-primary"
            >
              {isGenerating ? <RefreshCw size={15} className="spin" /> : <TrendingUp size={15} />}
              <span>{isGenerating ? 'Generating Frontier Spectrum...' : 'Compute Markowitz Frontier'}</span>
            </button>
          </div>
        </div>
      </form>

      {/* Frontier Results & Chart */}
      {frontierResult && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '24px', marginBottom: '24px' }}>
          {/* Chart Card */}
          <div className="card" style={{ gridColumn: 'span 2' }}>
            <div className="card-header">
              <div className="card-title">
                <Award size={18} style={{ color: 'var(--accent)' }} />
                <span>Markowitz Efficient Frontier Curve</span>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-success font-mono">
                  {frontierResult.successful_count} Feasible Points
                </span>
                {frontierResult.failed_count > 0 && (
                  <span className="badge badge-warning font-mono">
                    {frontierResult.failed_count} Infeasible
                  </span>
                )}
              </div>
            </div>

            {renderFrontierChart()}
          </div>

          {/* Point Inspector Card */}
          <div className="card" style={{ gridColumn: 'span 1' }}>
            <div className="card-header">
              <div className="card-title">
                <span>Selected Portfolio Point</span>
              </div>
              {selectedPoint && (
                <span className={`badge ${selectedPoint.classification === 'efficient' ? 'badge-info' : 'badge-neutral'}`}>
                  {selectedPoint.classification}
                </span>
              )}
            </div>

            {selectedPoint ? (
              <div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
                  <div style={{ padding: '8px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>EXPECTED RETURN</div>
                    <div className="font-mono" style={{ fontSize: '16px', fontWeight: 600, color: 'var(--success)' }}>
                      {(selectedPoint.actual_return * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div style={{ padding: '8px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>VOLATILITY (σ)</div>
                    <div className="font-mono" style={{ fontSize: '16px', fontWeight: 600 }}>
                      {(selectedPoint.volatility * 100).toFixed(2)}%
                    </div>
                  </div>

                  <div style={{ padding: '8px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>SHARPE RATIO</div>
                    <div className="font-mono" style={{ fontSize: '16px', fontWeight: 600, color: 'var(--accent)' }}>
                      {selectedPoint.sharpe_ratio != null ? selectedPoint.sharpe_ratio.toFixed(3) : 'N/A'}
                    </div>
                  </div>

                  <div style={{ padding: '8px', backgroundColor: 'var(--bg-elevated)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>TARGET RESIDUAL</div>
                    <div className="font-mono" style={{ fontSize: '16px', fontWeight: 600 }}>
                      {selectedPoint.target_residual.toExponential(2)}
                    </div>
                  </div>
                </div>

                <h5 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '8px' }}>
                  Allocation Weights Breakdown
                </h5>

                <div className="table-container" style={{ maxHeight: '200px' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Ticker</th>
                        <th className="num-cell">Weight</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(selectedPoint.weights).map(([ticker, w]) => (
                        <tr key={ticker}>
                          <td className="font-mono" style={{ fontWeight: 600 }}>{ticker}</td>
                          <td className="num-cell font-mono" style={{ color: w > 0 ? 'var(--accent)' : 'var(--text-dim)' }}>
                            {(w * 100).toFixed(2)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                Click on any point along the curve to inspect its weight allocation and risk metrics.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
