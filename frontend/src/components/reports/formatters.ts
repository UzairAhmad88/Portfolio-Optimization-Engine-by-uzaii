/**
 * Institutional Financial Reporting Formatters & Utilities.
 * Strictly preserves null/undefined values without coercing to zero.
 * Handles currencies, basis points, percentages, ratios, and dates.
 */

export function formatPercent(
  val: number | null | undefined,
  decimals: number = 2,
  includeSign: boolean = false
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '—';
  }
  const pct = val * 100;
  const sign = includeSign && pct > 0 ? '+' : '';
  return `${sign}${pct.toFixed(decimals)}%`;
}

export function formatCurrency(
  val: number | null | undefined,
  currency: string = 'USD',
  decimals: number = 0
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '—';
  }
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: currency || 'USD',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(val);
  } catch {
    return `${currency} ${val.toLocaleString('en-US', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    })}`;
  }
}

export function formatRatio(
  val: number | null | undefined,
  decimals: number = 2
): string {
  if (val === null || val === undefined || isNaN(val) || !isFinite(val)) {
    return '—';
  }
  return val.toFixed(decimals);
}

export function formatBps(
  val: number | null | undefined,
  decimals: number = 1
): string {
  if (val === null || val === undefined || isNaN(val)) {
    return '—';
  }
  return `${val.toFixed(decimals)} bps`;
}

export function formatDate(
  val: string | null | undefined,
  includeTime: boolean = false
): string {
  if (!val) return '—';
  try {
    const d = new Date(val);
    if (isNaN(d.getTime())) return val;
    if (includeTime) {
      return d.toISOString().replace('T', ' ').substring(0, 19) + ' UTC';
    }
    return d.toISOString().substring(0, 10);
  } catch {
    return val;
  }
}

export function getReturnColorClass(val: number | null | undefined): string {
  if (val === null || val === undefined || isNaN(val)) return 'text-neutral';
  if (val > 0.00001) return 'text-positive';
  if (val < -0.00001) return 'text-negative';
  return 'text-neutral';
}
