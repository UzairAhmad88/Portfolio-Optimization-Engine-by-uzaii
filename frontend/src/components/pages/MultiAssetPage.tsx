import React, { useState, useEffect } from 'react';
import {
  Layers,
  Sliders,
  Play,
  PlayCircle,
  TrendingUp,
  CheckCircle2,
  XCircle,
  Shield,
  Activity,
  History,
  Coins,
  Globe,
} from 'lucide-react';
import { apiClient } from '../../api/client';
import { useDataset } from '../../context/DatasetContext';
import type {
  AssetClassType,
  MultiAssetClassMetadata,
  MultiAssetBacktestRequest,
  MultiAssetBacktestResponse,
  MultiAssetOptimizeRequest,
  MultiAssetOptimizeResponse,
} from '../../types/api';

type ActiveTab = 'optimization' | 'backtest';

export const MultiAssetPage: React.FC = () => {
  const { currentDataset, availableAssets } = useDataset();

  // Tab State
  const [activeTab, setActiveTab] = useState<ActiveTab>('optimization');

  // Multi-Asset Configurations
  const [baseCurrency, setBaseCurrency] = useState<string>('USD');
  const [riskFreeRate, setRiskFreeRate] = useState<number>(0.03);
  const [minCashWeight, setMinCashWeight] = useState<number>(0.05);
  const [maxCashWeight, setMaxCashWeight] = useState<number>(0.25);
  const [objective, setObjective] = useState<'max_sharpe' | 'min_variance' | 'risk_parity'>('max_sharpe');

  // Asset Metadata (Class & Currency per Asset)
  const [assetMeta, setAssetMeta] = useState<Record<string, { asset_class: AssetClassType; currency: string }>>({});

  // Class Limits
  const [classLimits, setClassLimits] = useState<Record<string, { min: string; max: string }>>({
    Equity: { min: '0.20', max: '0.70' },
    'Fixed Income': { min: '0.10', max: '0.50' },
    Commodity: { min: '0.00', max: '0.20' },
    'Real Estate': { min: '0.00', max: '0.20' },
  });

  // Currency Hedge Ratios
  const [hedgeRatios, setHedgeRatios] = useState<Record<string, number>>({
    EUR: 1.0,
    PKR: 0.5,
    GBP: 1.0,
  });

  // Optimization Execution State
  const [isOptimizing, setIsOptimizing] = useState<boolean>(false);
  const [optError, setOptError] = useState<string | null>(null);
  const [optResult, setOptResult] = useState<MultiAssetOptimizeResponse | null>(null);

  // Backtest Parameters & State
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'daily' | 'weekly' | 'biweekly' | 'monthly' | 'quarterly'>('monthly');
  const [estimationWindow, setEstimationWindow] = useState<number>(60);
  const [transactionCostBps, setTransactionCostBps] = useState<number>(10.0);
  const [slippageBps, setSlippageBps] = useState<number>(5.0);
  const [initialCapital, setInitialCapital] = useState<number>(100000);

  const [isBacktesting, setIsBacktesting] = useState<boolean>(false);
  const [backtestError, setBacktestError] = useState<string | null>(null);
  const [backtestResult, setBacktestResult] = useState<MultiAssetBacktestResponse | null>(null);

  // Initialize asset metadata when available assets update
  useEffect(() => {
    if (availableAssets.length > 0) {
      const initial: Record<string, { asset_class: AssetClassType; currency: string }> = {};
      availableAssets.forEach((a) => {
        const upper = a.ticker.toUpperCase();
        let cls: AssetClassType = 'Equity';
        if (['BND', 'AGG', 'TLT', 'IEF', 'SHY', 'LQD', 'HYG', 'PIB'].some((k) => upper.includes(k))) {
          cls = 'Fixed Income';
        } else if (['GLD', 'SLV', 'USO', 'DBC', 'GSG'].some((k) => upper.includes(k))) {
          cls = 'Commodity';
        } else if (['VNQ', 'IYR', 'XLRE'].some((k) => upper.includes(k))) {
          cls = 'Real Estate';
        }
        initial[a.ticker] = {
          asset_class: cls,
          currency: a.market === 'PSX' ? 'PKR' : 'USD',
        };
      });
      setAssetMeta(initial);
    }
  }, [availableAssets]);

  const handleAssetClassChange = (ticker: string, cls: AssetClassType) => {
    setAssetMeta((prev) => ({
      ...prev,
      [ticker]: { ...prev[ticker], asset_class: cls },
    }));
  };

  const handleAssetCurrencyChange = (ticker: string, curr: string) => {
    setAssetMeta((prev) => ({
      ...prev,
      [ticker]: { ...prev[ticker], currency: curr.toUpperCase() },
    }));
  };

  const buildAssetMetadataList = (): MultiAssetClassMetadata[] => {
    return availableAssets.map((a) => ({
      ticker: a.ticker,
      asset_class: assetMeta[a.ticker]?.asset_class || 'Equity',
      currency: assetMeta[a.ticker]?.currency || (a.market === 'PSX' ? 'PKR' : 'USD'),
    }));
  };

  const buildClassLimitsPayload = () => {
    const limits: Record<string, { min_weight?: number; max_weight?: number }> = {};
    Object.entries(classLimits).forEach(([cls, b]) => {
      const minVal = parseFloat(b.min);
      const maxVal = parseFloat(b.max);
      if (!isNaN(minVal) || !isNaN(maxVal)) {
        limits[cls] = {};
        if (!isNaN(minVal)) limits[cls].min_weight = minVal;
        if (!isNaN(maxVal)) limits[cls].max_weight = maxVal;
      }
    });
    return limits;
  };

  const handleRunOptimization = async () => {
    if (!currentDataset) {
      setOptError('Please select a dataset to optimize.');
      return;
    }
    setIsOptimizing(true);
    setOptError(null);

    try {
      const payload: MultiAssetOptimizeRequest = {
        dataset_id: currentDataset.dataset_id,
        base_currency: baseCurrency,
        assets_metadata: buildAssetMetadataList(),
        hedge_ratios: hedgeRatios,
        asset_class_limits: buildClassLimitsPayload(),
        min_cash_weight: minCashWeight,
        max_cash_weight: maxCashWeight,
        objective: objective,
        risk_free_rate: riskFreeRate,
      };

      const res = await apiClient.optimizeMultiAsset(payload);
      setOptResult(res);
    } catch (err: any) {
      setOptError(err.message || 'Failed to execute multi-asset optimization.');
    } finally {
      setIsOptimizing(false);
    }
  };

  const handleRunBacktest = async () => {
    if (!currentDataset) {
      setBacktestError('Please select a dataset to backtest.');
      return;
    }
    setIsBacktesting(true);
    setBacktestError(null);

    try {
      const payload: MultiAssetBacktestRequest = {
        dataset_id: currentDataset.dataset_id,
        base_currency: baseCurrency,
        assets_metadata: buildAssetMetadataList(),
        hedge_ratios: hedgeRatios,
        asset_class_limits: buildClassLimitsPayload(),
        min_cash_weight: minCashWeight,
        max_cash_weight: maxCashWeight,
        rebalance_frequency: rebalanceFrequency,
        estimation_window: estimationWindow,
        objective: objective,
        risk_free_rate: riskFreeRate,
        transaction_cost_bps: transactionCostBps,
        slippage_bps: slippageBps,
        initial_capital: initialCapital,
      };

      const res = await apiClient.backtestMultiAsset(payload);
      setBacktestResult(res);
    } catch (err: any) {
      setBacktestError(err.message || 'Failed to execute multi-asset backtest.');
    } finally {
      setIsBacktesting(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Workspace Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-slate-900/60 backdrop-blur-md p-6 rounded-2xl border border-slate-800 shadow-xl">
        <div className="flex items-center gap-4">
          <div className="p-3 bg-indigo-500/10 border border-indigo-500/20 rounded-xl text-indigo-400">
            <Layers className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight flex items-center gap-2">
              Multi-Asset Allocation & FX Hedging
              <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 border border-indigo-500/30 font-medium">
                Stage 18
              </span>
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Hierarchical asset class allocation, cash yield & drag modeling, and multi-currency FX risk decomposition.
            </p>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex bg-slate-950/80 p-1 rounded-xl border border-slate-800 text-sm">
          <button
            onClick={() => setActiveTab('optimization')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === 'optimization'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Sliders className="w-4 h-4" />
            Allocation & FX Risk
          </button>
          <button
            onClick={() => setActiveTab('backtest')}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === 'backtest'
                ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-600/30'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <History className="w-4 h-4" />
            Walk-Forward Backtesting
          </button>
        </div>
      </div>

      {/* Dataset Warning */}
      {!currentDataset && (
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4 flex items-center gap-3 text-amber-300 text-sm">
          <Coins className="w-5 h-5 flex-shrink-0" />
          <span>No dataset selected. Please select a multi-asset dataset from the top navigation to begin.</span>
        </div>
      )}

      {/* Tab 1: Multi-Asset Allocation & FX Hedging */}
      {activeTab === 'optimization' && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Configuration Sidebar */}
          <div className="lg:col-span-4 space-y-6">
            <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 p-6 space-y-5">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Sliders className="w-4 h-4 text-indigo-400" />
                Multi-Asset Parameters
              </h3>

              {/* Base Currency & Objective */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Base Currency</label>
                  <select
                    value={baseCurrency}
                    onChange={(e) => setBaseCurrency(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="USD">USD ($)</option>
                    <option value="PKR">PKR (₨)</option>
                    <option value="EUR">EUR (€)</option>
                    <option value="GBP">GBP (£)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Objective</label>
                  <select
                    value={objective}
                    onChange={(e) => setObjective(e.target.value as any)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="max_sharpe">Max Sharpe</option>
                    <option value="min_variance">Min Variance</option>
                    <option value="risk_parity">Risk Parity</option>
                  </select>
                </div>
              </div>

              {/* Cash Buffer Bounds */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Cash Weight (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="0.5"
                    value={minCashWeight}
                    onChange={(e) => setMinCashWeight(parseFloat(e.target.value) || 0)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Max Cash Weight (%)</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.05"
                    max="1.0"
                    value={maxCashWeight}
                    onChange={(e) => setMaxCashWeight(parseFloat(e.target.value) || 0.25)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
              </div>

              {/* Risk-Free Rate */}
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1.5">Cash Yield / Risk-Free Rate (%)</label>
                <input
                  type="number"
                  step="0.005"
                  min="0"
                  max="0.2"
                  value={riskFreeRate}
                  onChange={(e) => setRiskFreeRate(parseFloat(e.target.value) || 0.03)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
                />
              </div>

              {/* Asset Class Limits */}
              <div className="pt-2 border-t border-slate-800">
                <span className="text-xs font-medium text-slate-300 block mb-2">Asset Class Allocation Limits:</span>
                <div className="space-y-2 text-xs">
                  {Object.entries(classLimits).map(([cls, bounds]) => (
                    <div key={cls} className="flex items-center justify-between gap-2 bg-slate-950/40 p-2 rounded-lg border border-slate-800/80">
                      <span className="font-medium text-slate-300">{cls}</span>
                      <div className="flex items-center gap-1.5">
                        <input
                          type="number"
                          placeholder="Min"
                          step="0.05"
                          value={bounds.min}
                          onChange={(e) =>
                            setClassLimits((prev) => ({
                              ...prev,
                              [cls]: { ...prev[cls], min: e.target.value },
                            }))
                          }
                          className="w-14 bg-slate-900 border border-slate-750 rounded px-1.5 py-1 text-slate-200 text-center"
                        />
                        <span className="text-slate-500">-</span>
                        <input
                          type="number"
                          placeholder="Max"
                          step="0.05"
                          value={bounds.max}
                          onChange={(e) =>
                            setClassLimits((prev) => ({
                              ...prev,
                              [cls]: { ...prev[cls], max: e.target.value },
                            }))
                          }
                          className="w-14 bg-slate-900 border border-slate-750 rounded px-1.5 py-1 text-slate-200 text-center"
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Currency Hedge Ratios */}
              <div className="pt-2 border-t border-slate-800">
                <span className="text-xs font-medium text-slate-300 block mb-2">Currency Hedge Overlay:</span>
                <div className="space-y-2 text-xs">
                  {['EUR', 'PKR', 'GBP'].map((curr) => (
                    <div key={curr} className="flex items-center justify-between bg-slate-950/40 p-2 rounded-lg border border-slate-800/80">
                      <span className="font-medium text-slate-300 flex items-center gap-1.5">
                        <Globe className="w-3.5 h-3.5 text-indigo-400" />
                        {curr} Hedge Ratio
                      </span>
                      <input
                        type="number"
                        step="0.1"
                        min="0"
                        max="1"
                        value={hedgeRatios[curr] ?? 1.0}
                        onChange={(e) =>
                          setHedgeRatios((prev) => ({
                            ...prev,
                            [curr]: parseFloat(e.target.value) || 0.0,
                          }))
                        }
                        className="w-16 bg-slate-900 border border-slate-750 rounded px-2 py-1 text-slate-200 text-center"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* Run Optimization Button */}
              <button
                onClick={handleRunOptimization}
                disabled={isOptimizing || !currentDataset}
                className="w-full mt-2 py-3 px-4 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/25 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
              >
                {isOptimizing ? (
                  <>
                    <Activity className="w-4 h-4 animate-spin" />
                    Solving Multi-Asset Allocation...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Solve Multi-Asset Portfolio
                  </>
                )}
              </button>

              {optError && (
                <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-start gap-2">
                  <XCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                  <span>{optError}</span>
                </div>
              )}
            </div>
          </div>

          {/* Asset Classification & Optimization Tear-Sheet */}
          <div className="lg:col-span-8 space-y-6">
            {/* Asset Classification Editor */}
            <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 p-6 space-y-4">
              <h3 className="text-base font-semibold text-white flex items-center gap-2">
                <Coins className="w-4 h-4 text-indigo-400" />
                Asset Universe Classification & Currency Denomination
              </h3>
              <p className="text-xs text-slate-400">
                Configure the asset class taxonomy and local trading currency for each security in the active dataset.
              </p>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950/80 text-slate-400 border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Ticker</th>
                      <th className="py-2.5 px-3">Asset Class</th>
                      <th className="py-2.5 px-3">Local Currency</th>
                      <th className="py-2.5 px-3">Hedge Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {availableAssets.map((asset) => {
                      const curr = assetMeta[asset.ticker]?.currency || (asset.market === 'PSX' ? 'PKR' : 'USD');
                      const cls = assetMeta[asset.ticker]?.asset_class || 'Equity';
                      const isDomestic = curr.toUpperCase() === baseCurrency.toUpperCase();
                      const hRatio = isDomestic ? 1.0 : (hedgeRatios[curr] ?? 0.0);

                      return (
                        <tr key={asset.asset_id} className="hover:bg-slate-800/30">
                          <td className="py-2.5 px-3 font-semibold text-white">{asset.ticker}</td>
                          <td className="py-2.5 px-3">
                            <select
                              value={cls}
                              onChange={(e) => handleAssetClassChange(asset.ticker, e.target.value as AssetClassType)}
                              className="bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 text-xs"
                            >
                              <option value="Equity">Equity</option>
                              <option value="Fixed Income">Fixed Income</option>
                              <option value="Commodity">Commodity</option>
                              <option value="Real Estate">Real Estate</option>
                              <option value="Other">Other</option>
                            </select>
                          </td>
                          <td className="py-2.5 px-3">
                            <input
                              type="text"
                              value={curr}
                              onChange={(e) => handleAssetCurrencyChange(asset.ticker, e.target.value)}
                              className="w-16 bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 text-xs uppercase"
                            />
                          </td>
                          <td className="py-2.5 px-3">
                            {isDomestic ? (
                              <span className="text-emerald-400 font-medium">Domestic (Zero FX)</span>
                            ) : hRatio === 1.0 ? (
                              <span className="text-indigo-400 font-medium">100% Hedged</span>
                            ) : hRatio === 0.0 ? (
                              <span className="text-amber-400 font-medium">Unhedged</span>
                            ) : (
                              <span className="text-sky-400 font-medium">{(hRatio * 100).toFixed(0)}% Hedged</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Optimization Results Tear-Sheet */}
            {optResult && (
              <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    Multi-Asset Optimal Allocation & Risk Profile
                  </h3>
                  <div className="flex items-center gap-2">
                    {optResult.is_feasible ? (
                      <span className="flex items-center gap-1 text-xs px-2.5 py-1 bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 rounded-full">
                        <CheckCircle2 className="w-3 h-3" />
                        Optimal Converged
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs px-2.5 py-1 bg-amber-500/10 text-amber-400 border border-amber-500/20 rounded-full">
                        Relaxed Constraints
                      </span>
                    )}
                  </div>
                </div>

                {/* KPI Metrics */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                    <span className="text-xs text-slate-400 block mb-1">Expected Return</span>
                    <span className="text-xl font-bold text-emerald-400">
                      {(optResult.expected_annual_return * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                    <span className="text-xs text-slate-400 block mb-1">Annual Volatility</span>
                    <span className="text-xl font-bold text-slate-200">
                      {(optResult.annual_volatility * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                    <span className="text-xs text-slate-400 block mb-1">Sharpe Ratio</span>
                    <span className="text-xl font-bold text-indigo-400">{optResult.sharpe_ratio.toFixed(2)}</span>
                  </div>
                  <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800">
                    <span className="text-xs text-slate-400 block mb-1">Cash Buffer</span>
                    <span className="text-xl font-bold text-amber-400">
                      {(optResult.cash_weight * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                {/* Asset Class Distribution Breakdown */}
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Asset Class Weight Allocation
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                    {Object.entries(optResult.asset_class_allocations).map(([cls, weight]) => (
                      <div key={cls} className="bg-slate-950/40 p-3 rounded-xl border border-slate-800 text-center">
                        <span className="text-xs text-slate-400 block">{cls}</span>
                        <span className="text-base font-bold text-white">{(weight * 100).toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* FX Risk Decomposition Card */}
                <div className="bg-slate-950/60 p-5 rounded-xl border border-slate-800 space-y-4">
                  <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-2">
                    <Shield className="w-4 h-4 text-sky-400" />
                    FX Currency Risk Attribution
                  </h4>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <div className="flex justify-between text-xs text-slate-400 mb-1">
                        <span>Asset Price Risk: {optResult.fx_risk_decomposition.asset_risk_share_pct}%</span>
                        <span>FX Currency Risk: {optResult.fx_risk_decomposition.fx_risk_share_pct}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-3 rounded-full overflow-hidden flex">
                        <div
                          className="bg-indigo-500 h-full"
                          style={{ width: `${optResult.fx_risk_decomposition.asset_risk_share_pct}%` }}
                        />
                        <div
                          className="bg-sky-400 h-full"
                          style={{ width: `${optResult.fx_risk_decomposition.fx_risk_share_pct}%` }}
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-xs">
                      <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                        <span className="text-slate-400 block">Local Volatility</span>
                        <span className="font-semibold text-slate-200">
                          {(optResult.fx_risk_decomposition.local_asset_volatility * 100).toFixed(2)}%
                        </span>
                      </div>
                      <div className="bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                        <span className="text-slate-400 block">Unhedged Volatility</span>
                        <span className="font-semibold text-slate-200">
                          {(optResult.fx_risk_decomposition.unhedged_volatility * 100).toFixed(2)}%
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Individual Asset Weights Table */}
                <div className="space-y-3">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                    Individual Asset Allocations
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs text-slate-300">
                      <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                        <tr>
                          <th className="py-2 px-3">Asset</th>
                          <th className="py-2 px-3">Class</th>
                          <th className="py-2 px-3">Currency</th>
                          <th className="py-2 px-3">Weight (%)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800/60">
                        {Object.entries(optResult.risky_weights).map(([ticker, w]) => (
                          <tr key={ticker} className="hover:bg-slate-800/20">
                            <td className="py-2 px-3 font-semibold text-white">{ticker}</td>
                            <td className="py-2 px-3">{assetMeta[ticker]?.asset_class || 'Equity'}</td>
                            <td className="py-2 px-3">{assetMeta[ticker]?.currency || 'USD'}</td>
                            <td className="py-2 px-3 font-bold text-indigo-400">{(w * 100).toFixed(2)}%</td>
                          </tr>
                        ))}
                        <tr className="bg-amber-500/5 font-semibold">
                          <td className="py-2 px-3 text-amber-300">CASH BUFFER</td>
                          <td className="py-2 px-3 text-amber-300">Cash / T-Bills</td>
                          <td className="py-2 px-3 text-amber-300">{baseCurrency}</td>
                          <td className="py-2 px-3 text-amber-300">{(optResult.cash_weight * 100).toFixed(2)}%</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Walk-Forward Backtesting & Cash Drag */}
      {activeTab === 'backtest' && (
        <div className="space-y-6">
          {/* Backtest Parameter Bar */}
          <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 p-6 shadow-xl space-y-4">
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
              <div>
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <PlayCircle className="w-5 h-5 text-indigo-400" />
                  Multi-Asset Walk-Forward Simulation Controls
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Chronological walk-forward rebalancing modeling dynamic cash drag, currency conversion, and weight drift.
                </p>
              </div>

              <button
                onClick={handleRunBacktest}
                disabled={isBacktesting || !currentDataset}
                className="py-2.5 px-6 bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-medium rounded-xl shadow-lg shadow-indigo-600/30 flex items-center gap-2 transition-all disabled:opacity-50"
              >
                {isBacktesting ? (
                  <>
                    <Activity className="w-4 h-4 animate-spin" />
                    Simulating Walk-Forward...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Execute Multi-Asset Backtest
                  </>
                )}
              </button>
            </div>

            {/* Parameter Inputs */}
            <div className="grid grid-cols-2 sm:grid-cols-5 gap-4 pt-4 border-t border-slate-800 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Rebalance Frequency</label>
                <select
                  value={rebalanceFrequency}
                  onChange={(e) => setRebalanceFrequency(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
                >
                  <option value="weekly">Weekly</option>
                  <option value="biweekly">Biweekly</option>
                  <option value="monthly">Monthly</option>
                  <option value="quarterly">Quarterly</option>
                </select>
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Estimation Window (Days)</label>
                <input
                  type="number"
                  min="20"
                  max="120"
                  value={estimationWindow}
                  onChange={(e) => setEstimationWindow(parseInt(e.target.value) || 60)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Transaction Fees (bps)</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="50"
                  value={transactionCostBps}
                  onChange={(e) => setTransactionCostBps(parseFloat(e.target.value) || 10)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Execution Slippage (bps)</label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="50"
                  value={slippageBps}
                  onChange={(e) => setSlippageBps(parseFloat(e.target.value) || 5)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
                />
              </div>
              <div>
                <label className="block text-slate-400 mb-1">Initial Capital ($)</label>
                <input
                  type="number"
                  step="10000"
                  value={initialCapital}
                  onChange={(e) => setInitialCapital(parseFloat(e.target.value) || 100000)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1.5 text-slate-200"
                />
              </div>
            </div>

            {backtestError && (
              <div className="p-3 bg-rose-500/10 border border-rose-500/20 rounded-xl text-rose-400 text-xs flex items-start gap-2">
                <XCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                <span>{backtestError}</span>
              </div>
            )}
          </div>

          {/* Backtest Results View */}
          {backtestResult && (
            <div className="space-y-6">
              {/* Summary KPIs */}
              <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-4">
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 block mb-1">Total Return</span>
                  <span
                    className={`text-xl font-bold ${
                      backtestResult.summary.total_return >= 0 ? 'text-emerald-400' : 'text-rose-400'
                    }`}
                  >
                    {(backtestResult.summary.total_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 block mb-1">CAGR (Annualized)</span>
                  <span className="text-xl font-bold text-slate-200">
                    {(backtestResult.summary.cagr * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 block mb-1">Sharpe Ratio</span>
                  <span className="text-xl font-bold text-indigo-400">
                    {backtestResult.summary.sharpe_ratio.toFixed(2)}
                  </span>
                </div>
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 block mb-1">Max Drawdown</span>
                  <span className="text-xl font-bold text-rose-400">
                    {(backtestResult.summary.max_drawdown * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 block mb-1">Active Alpha (vs BM)</span>
                  <span className="text-xl font-bold text-sky-400">
                    {(backtestResult.summary.active_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
                  <span className="text-xs text-slate-400 block mb-1">Total Cash Drag</span>
                  <span className="text-xl font-bold text-amber-400">
                    {(backtestResult.summary.total_cash_drag * 100).toFixed(3)}%
                  </span>
                </div>
              </div>

              {/* Interactive Dual-Series SVG Chart */}
              <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-white flex items-center gap-2">
                    <TrendingUp className="w-4 h-4 text-emerald-400" />
                    Multi-Asset Wealth Compounding Curve (vs Balanced Benchmark)
                  </h3>
                  <div className="flex items-center gap-4 text-xs font-medium">
                    <span className="flex items-center gap-1.5 text-indigo-400">
                      <span className="w-3 h-0.5 bg-indigo-500 rounded-full" />
                      Multi-Asset Strategy
                    </span>
                    <span className="flex items-center gap-1.5 text-slate-400">
                      <span className="w-3 h-0.5 bg-slate-500 rounded-full" />
                      Equal/Balanced Benchmark
                    </span>
                  </div>
                </div>

                {/* SVG Curve */}
                {backtestResult.equity_curve.length > 1 && (
                  <div className="h-64 w-full bg-slate-950/40 rounded-xl p-3 border border-slate-800">
                    <svg className="w-full h-full" viewBox="0 0 800 220" preserveAspectRatio="none">
                      {(() => {
                        const pts = backtestResult.equity_curve;
                        const minEq = Math.min(...pts.map((p) => Math.min(p.portfolio_equity, p.benchmark_equity)));
                        const maxEq = Math.max(...pts.map((p) => Math.max(p.portfolio_equity, p.benchmark_equity)));
                        const range = maxEq - minEq || 1;

                        const getX = (i: number) => (i / (pts.length - 1)) * 780 + 10;
                        const getY = (val: number) => 200 - ((val - minEq) / range) * 180;

                        const stratPath = pts
                          .map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.portfolio_equity)}`)
                          .join(' ');
                        const bmPath = pts
                          .map((p, i) => `${i === 0 ? 'M' : 'L'} ${getX(i)} ${getY(p.benchmark_equity)}`)
                          .join(' ');

                        return (
                          <>
                            {/* Benchmark line */}
                            <path d={bmPath} fill="none" stroke="#64748b" strokeWidth="1.5" strokeDasharray="4 4" />
                            {/* Strategy line */}
                            <path d={stratPath} fill="none" stroke="#6366f1" strokeWidth="2.5" />
                          </>
                        );
                      })()}
                    </svg>
                  </div>
                )}
              </div>

              {/* Rebalance History Table */}
              <div className="bg-slate-900/60 backdrop-blur-md rounded-2xl border border-slate-800 p-6 space-y-4">
                <h3 className="text-base font-semibold text-white flex items-center gap-2">
                  <History className="w-4 h-4 text-indigo-400" />
                  Chronological Rebalance Audit Log
                </h3>

                <div className="overflow-x-auto max-h-96">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-slate-400 sticky top-0 border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3">Date</th>
                        <th className="py-2.5 px-3">Cash Weight</th>
                        <th className="py-2.5 px-3">Class Distribution</th>
                        <th className="py-2.5 px-3">Turnover</th>
                        <th className="py-2.5 px-3">Cost ($)</th>
                        <th className="py-2.5 px-3">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {backtestResult.rebalance_history.map((ev, idx) => (
                        <tr key={idx} className="hover:bg-slate-800/20">
                          <td className="py-2.5 px-3 font-semibold text-white">{ev.date}</td>
                          <td className="py-2.5 px-3 font-medium text-amber-400">
                            {(ev.cash_weight * 100).toFixed(1)}%
                          </td>
                          <td className="py-2.5 px-3">
                            <div className="flex gap-2">
                              {Object.entries(ev.asset_class_allocations).map(([c, w]) => (
                                <span key={c} className="text-slate-400">
                                  {c}: <b className="text-slate-200">{(w * 100).toFixed(0)}%</b>
                                </span>
                              ))}
                            </div>
                          </td>
                          <td className="py-2.5 px-3 font-medium text-slate-200">
                            {(ev.turnover * 100).toFixed(1)}%
                          </td>
                          <td className="py-2.5 px-3 font-medium text-slate-400">${ev.cost_incurred.toFixed(2)}</td>
                          <td className="py-2.5 px-3">
                            {ev.is_feasible ? (
                              <span className="text-emerald-400 flex items-center gap-1">
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                Optimal
                              </span>
                            ) : (
                              <span className="text-amber-400">Relaxed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
