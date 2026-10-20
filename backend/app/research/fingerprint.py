"""
Canonical serialization and SHA-256 fingerprint generation for research experiment configurations.
"""

from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from typing import Any

# Semantic configuration fields included in the research experiment fingerprint.
# Any change to these fields impacts financial calculations or outputs.
SEMANTIC_CONFIG_FIELDS = {
    "strategy_type",
    "dataset_id",
    "assets",
    "weights",
    "objective",
    "constraints",
    "rebalance_frequency",
    "transaction_cost_bps",
    "slippage_bps",
    "benchmark_asset",
    "risk_free_rate",
    "seed",
    "distribution",
    "degrees_of_freedom",
    "horizon_days",
    "num_paths",
    "initial_capital",
    "rebalance_policy",
    "training_window",
    "start_date",
    "end_date",
    "custom_expected_returns",
}

# Non-semantic metadata excluded from the fingerprint
EXCLUDED_METADATA_FIELDS = {
    "id",
    "name",
    "description",
    "user_id",
    "version",
    "created_at",
    "updated_at",
    "save_report",
}


def _canonicalize_value(value: Any) -> Any:
    """
    Recursively canonicalizes arbitrary config structures:
    - Sorts dictionary keys lexicographically
    - Normalizes asset strings (uppercase, stripped)
    - Normalizes lists of assets
    - Rounds floats to 8 decimal precision
    - Converts dates/datetimes to ISO strings
    """
    if isinstance(value, dict):
        return {
            str(k): _canonicalize_value(v)
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    elif isinstance(value, list):
        # If it's a list of strings (e.g. assets), normalize and sort
        if all(isinstance(x, str) for x in value):
            normalized_strings = [x.strip().upper() for x in value]
            return sorted(normalized_strings)
        return [_canonicalize_value(item) for item in value]
    elif isinstance(value, float):
        return round(float(value), 8)
    elif isinstance(value, (int, bool)):
        return value
    elif isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")
    elif value is None:
        return None
    elif isinstance(value, str):
        return value.strip()
    return str(value)


def extract_semantic_config(config: dict[str, Any]) -> dict[str, Any]:
    """
    Filters a raw or dictionary configuration to retain only semantic research parameters.
    """
    semantic_dict: dict[str, Any] = {}
    for key, val in config.items():
        if key in SEMANTIC_CONFIG_FIELDS:
            # Normalize weights keys to uppercase if dict
            if key == "weights" and isinstance(val, dict):
                norm_w = {str(k).strip().upper(): round(float(v), 8) for k, v in val.items()}
                semantic_dict[key] = {k: norm_w[k] for k in sorted(norm_w.keys())}
            elif key == "assets" and isinstance(val, list):
                semantic_dict[key] = sorted([str(a).strip().upper() for a in val])
            elif key == "benchmark_asset" and isinstance(val, str):
                semantic_dict[key] = val.strip().upper()
            else:
                semantic_dict[key] = _canonicalize_value(val)
    return semantic_dict


def canonical_json_dumps(config: dict[str, Any]) -> str:
    """
    Serializes a semantic config into deterministic, canonical JSON with zero whitespace
    and lexicographically sorted keys.
    """
    semantic = extract_semantic_config(config)
    canonical_obj = _canonicalize_value(semantic)
    return json.dumps(canonical_obj, sort_keys=True, separators=(",", ":"))


def compute_config_fingerprint(config: dict[str, Any]) -> str:
    """
    Computes a 64-character hex SHA-256 fingerprint for a research configuration.
    """
    canonical_str = canonical_json_dumps(config)
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()
