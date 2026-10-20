# SESSION 25 CONTRACTS — STAGE 21: MULTI-ASSET PERFORMANCE ATTRIBUTION, BRINSON-FACHLER DECOMPOSITION & FACTOR RISK ATTRIBUTION

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 25  
**Stage:** Stage 21 — Multi-Asset Performance Attribution, Brinson-Fachler Decomposition & Systematic Factor Risk Attribution  
**Status:** AUTHORIZED CONTRACT  
**Date:** 2026-10-19  

---

## 1. Problem Statement & Scope Exclusions

### Problem Statement
Institutional investment allocators, portfolio managers, and risk committees require mathematical decomposition explaining the exact sources of active portfolio return ($R_p - R_b$) relative to a strategic benchmark. Naive single-number excess return hides critical structural questions:
1. Did excess performance originate from superior sector/asset-class weighting decisions (**Allocation Effect**), or from picking superior individual securities within those sectors (**Selection Effect**)?
2. How do multi-period compounded returns link over time without accumulating unexplained residual drift?
3. How much of active performance is attributable to systematic factor tilts (Size, Value, Momentum, Quality) versus pure idiosyncratic manager alpha?
4. In multi-currency portfolios, what portion of excess return is attributable to foreign currency fluctuations vs active currency hedging overlays?

### Explicit Exclusions
- Execution trade venue routing and FIX protocol messaging (deferred to Stage 22).
- Non-linear machine learning price prediction (deferred to Stage 23).
- Subjective return forecasting without historical data.

---

## 2. Mathematical Definitions & Analytical Formulations

### A. Single-Period Brinson-Fachler (1985) Attribution
For $N$ segments/sectors $i \in \{1, \dots, N\}$:
- $w_{p,i}$: Portfolio segment weight ($\sum w_{p,i} = 1.0$)
- $w_{b,i}$: Benchmark segment weight ($\sum w_{b,i} = 1.0$)
- $R_{p,i}$: Portfolio segment return
- $R_{b,i}$: Benchmark segment return
- Total portfolio return: $R_p = \sum_{i=1}^N w_{p,i} R_{p,i}$
- Total benchmark return: $R_b = \sum_{i=1}^N w_{b,i} R_{b,i}$
- Total active excess return: $\Delta R = R_p - R_b$

#### Brinson-Fachler Components:
1. **Allocation Effect ($A_i$):**
   $$A_i = (w_{p,i} - w_{b,i})(R_{b,i} - R_b)$$
2. **Selection Effect ($S_i$):**
   $$S_i = w_{b,i}(R_{p,i} - R_{b,i})$$
3. **Interaction Effect ($I_i$):**
   $$I_i = (w_{p,i} - w_{b,i})(R_{p,i} - R_{b,i})$$
4. **Total Active Segment Contribution ($C_i$):**
   $$C_i = A_i + S_i + I_i = w_{p,i} R_{p,i} - w_{b,i} R_{b,i} - (w_{p,i} - w_{b,i}) R_b$$
5. **Exact Single-Period Reconciliation Identity:**
   $$\sum_{i=1}^N A_i + \sum_{i=1}^N S_i + \sum_{i=1}^N I_i \equiv R_p - R_b$$

### B. Multi-Period Cariño (1999) Logarithmic Linking
Let $t \in \{1, \dots, T\}$ denote discrete evaluation periods.
- Periodic active return: $\Delta R_t = R_{p,t} - R_{b,t}$
- Cumulative compounded returns:
  $$R_p^{\text{cum}} = \prod_{t=1}^T (1 + R_{p,t}) - 1, \quad R_b^{\text{cum}} = \prod_{t=1}^T (1 + R_{b,t}) - 1$$
- Cumulative active return:
  $$\Delta R^{\text{cum}} = R_p^{\text{cum}} - R_b^{\text{cum}}$$
- **Cariño Logarithmic Factor:**
  $$a_t = \begin{cases} \frac{\ln(1 + R_{p,t}) - \ln(1 + R_{b,t})}{R_{p,t} - R_{b,t}}, & R_{p,t} \ne R_{b,t} \\ \frac{1}{1 + R_{b,t}}, & R_{p,t} = R_{b,t} \end{cases}$$
  $$a^{\text{cum}} = \begin{cases} \frac{\ln(1 + R_p^{\text{cum}}) - \ln(1 + R_b^{\text{cum}})}{R_p^{\text{cum}} - R_b^{\text{cum}}}, & R_p^{\text{cum}} \ne R_b^{\text{cum}} \\ \frac{1}{1 + R_b^{\text{cum}}}, & R_p^{\text{cum}} = R_b^{\text{cum}} \end{cases}$$
  $$k_t = \frac{a_t}{a^{\text{cum}}}$$
- **Multi-Period Linked Attribution Components:**
  $$\tilde{A}_i = \sum_{t=1}^T k_t A_{i,t}, \quad \tilde{S}_i = \sum_{t=1}^T k_t S_{i,t}, \quad \tilde{I}_i = \sum_{t=1}^T k_t I_{i,t}$$
- **Exact Multi-Period Reconciliation Identity:**
  $$\sum_{i=1}^N (\tilde{A}_i + \tilde{S}_i + \tilde{I}_i) \equiv R_p^{\text{cum}} - R_b^{\text{cum}}$$

### C. Systematic Multi-Factor Active Return & Risk Attribution
Using the Stage 16/17 structural Barra factor model:
- Active factor exposure: $\Delta \beta_k = \beta_{p,k} - \beta_{b,k} = \sum_i w_{p,i} B_{i,k} - \sum_i w_{b,i} B_{i,k}$
- Factor active return contribution: $\text{FactorReturn}_k = \Delta \beta_k \cdot F_k$
- Specific (stock-picking) active return: $\alpha_{\text{specific}} = \Delta R - \sum_{k=1}^K \text{FactorReturn}_k$
- Systematic active tracking variance:
  $$\sigma_{\text{active}}^2 = \Delta \beta^\top \mathbf{\Sigma}_F \Delta \beta + \Delta w^\top \mathbf{\Sigma}_\epsilon \Delta w$$

---

## 3. Hand-Calculated 2-Asset 2-Period Analytical Benchmark

### Inputs
- **Segment 1 (Equity):**
  - $t=1$: $w_{p,1} = 0.60, w_{b,1} = 0.50$, $R_{p,1} = +0.04, R_{b,1} = +0.03$
  - $t=2$: $w_{p,1} = 0.70, w_{b,1} = 0.50$, $R_{p,1} = -0.02, R_{b,1} = -0.01$
- **Segment 2 (Bonds):**
  - $t=1$: $w_{p,2} = 0.40, w_{b,2} = 0.50$, $R_{p,2} = +0.01, R_{b,2} = +0.01$
  - $t=2$: $w_{p,2} = 0.30, w_{b,2} = 0.50$, $R_{p,2} = +0.005, R_{b,2} = +0.005$

### Period 1 Derivation ($t=1$)
- Portfolio return: $R_p^{(1)} = 0.60(0.04) + 0.40(0.01) = 0.0280$ ($+2.80\%$)
- Benchmark return: $R_b^{(1)} = 0.50(0.03) + 0.50(0.01) = 0.0200$ ($+2.00\%$)
- Active return: $\Delta R^{(1)} = 0.0280 - 0.0200 = +0.0080$ ($+80\text{ bps}$)
- **Brinson-Fachler Decomposition:**
  - Equity Allocation: $A_1^{(1)} = (0.60 - 0.50)(0.03 - 0.02) = +0.0010$ ($+10\text{ bps}$)
  - Equity Selection: $S_1^{(1)} = 0.50(0.04 - 0.03) = +0.0050$ ($+50\text{ bps}$)
  - Equity Interaction: $I_1^{(1)} = (0.60 - 0.50)(0.04 - 0.03) = +0.0010$ ($+10\text{ bps}$)
  - Bonds Allocation: $A_2^{(1)} = (0.40 - 0.50)(0.01 - 0.02) = +0.0010$ ($+10\text{ bps}$)
  - Bonds Selection: $S_2^{(1)} = 0.50(0.01 - 0.01) = 0.0000$
  - Bonds Interaction: $I_2^{(1)} = (0.40 - 0.50)(0.01 - 0.01) = 0.0000$
- **Total Period 1 Effects:**
  - Total Allocation: $A^{(1)} = +0.0020$ ($+20\text{ bps}$)
  - Total Selection: $S^{(1)} = +0.0050$ ($+50\text{ bps}$)
  - Total Interaction: $I^{(1)} = +0.0010$ ($+10\text{ bps}$)
  - Sum: $0.0020 + 0.0050 + 0.0010 = +0.0080 \equiv \Delta R^{(1)}$

### Period 2 Derivation ($t=2$)
- Portfolio return: $R_p^{(2)} = 0.70(-0.02) + 0.30(0.005) = -0.0125$ ($-1.25\%$)
- Benchmark return: $R_b^{(2)} = 0.50(-0.01) + 0.50(0.005) = -0.0025$ ($-0.25\%$)
- Active return: $\Delta R^{(2)} = -0.0125 - (-0.0025) = -0.0100$ ($-100\text{ bps}$)
- **Brinson-Fachler Decomposition:**
  - Equity Allocation: $A_1^{(2)} = (0.70 - 0.50)(-0.01 - (-0.0025)) = -0.0015$ ($-15\text{ bps}$)
  - Equity Selection: $S_1^{(2)} = 0.50(-0.02 - (-0.01)) = -0.0050$ ($-50\text{ bps}$)
  - Equity Interaction: $I_1^{(2)} = (0.70 - 0.50)(-0.02 - (-0.01)) = -0.0020$ ($-20\text{ bps}$)
  - Bonds Allocation: $A_2^{(2)} = (0.30 - 0.50)(0.005 - (-0.0025)) = -0.0015$ ($-15\text{ bps}$)
  - Bonds Selection: $S_2^{(2)} = 0.50(0.005 - 0.005) = 0.0000$
  - Bonds Interaction: $I_2^{(2)} = -0.20 \times 0.0 = 0.0000$
- **Total Period 2 Effects:**
  - Total Allocation: $A^{(2)} = -0.0030$ ($-30\text{ bps}$)
  - Total Selection: $S^{(2)} = -0.0050$ ($-50\text{ bps}$)
  - Total Interaction: $I^{(2)} = -0.0020$ ($-20\text{ bps}$)
  - Sum: $-0.0030 - 0.0050 - 0.0020 = -0.0100 \equiv \Delta R^{(2)}$

### Multi-Period Compounded Linking
- Cumulative Portfolio Return: $R_p^{\text{cum}} = (1 + 0.0280)(1 - 0.0125) - 1 = +0.01515000$
- Cumulative Benchmark Return: $R_b^{\text{cum}} = (1 + 0.0200)(1 - 0.0025) - 1 = +0.01745000$
- Cumulative Active Return: $\Delta R^{\text{cum}} = 0.01515000 - 0.01745000 = -0.00230000$ ($-23.00\text{ bps}$)
- Cariño multi-period linking factors $k_t$:
  $$\sum_{t=1}^2 k_t (A_t + S_t + I_t) \equiv -0.00230000$$
  Precision threshold: $< 10^{-12}$.

---

## 4. API Request & Response Contracts

### Endpoint 1: Single & Multi-Period Brinson-Fachler Attribution
- **Route:** `POST /api/v1/attribution/brinson`
- **Request Schema:**
  ```json
  {
    "dataset_id": "string",
    "portfolio_weights": { "ticker": 0.5 },
    "benchmark_weights": { "ticker": 0.5 },
    "segment_mapping": { "AAPL": "Technology", "MSFT": "Technology", "JNJ": "Healthcare" },
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "frequency": "monthly"
  }
  ```
- **Response Schema:**
  ```json
  {
    "dataset_id": "string",
    "summary": {
      "portfolio_cumulative_return": 0.152,
      "benchmark_cumulative_return": 0.125,
      "active_cumulative_return": 0.027,
      "total_allocation_effect": 0.012,
      "total_selection_effect": 0.011,
      "total_interaction_effect": 0.004
    },
    "segment_attribution": [
      {
        "segment": "Technology",
        "portfolio_weight": 0.60,
        "benchmark_weight": 0.50,
        "portfolio_return": 0.22,
        "benchmark_return": 0.18,
        "allocation_effect": 0.008,
        "selection_effect": 0.006,
        "interaction_effect": 0.002,
        "total_contribution": 0.016
      }
    ],
    "time_series": [
      {
        "date": "2024-01-31",
        "portfolio_return": 0.028,
        "benchmark_return": 0.020,
        "active_return": 0.008,
        "allocation_effect": 0.002,
        "selection_effect": 0.005,
        "interaction_effect": 0.001
      }
    ]
  }
  ```

### Endpoint 2: Systematic Factor Risk & Return Attribution
- **Route:** `POST /api/v1/attribution/factor`
- **Request Schema:**
  ```json
  {
    "dataset_id": "string",
    "portfolio_weights": { "ticker": 0.5 },
    "benchmark_weights": { "ticker": 0.5 },
    "factor_model": "fama_french_3",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31"
  }
  ```
- **Response Schema:**
  ```json
  {
    "dataset_id": "string",
    "total_active_return": 0.027,
    "systematic_active_return": 0.019,
    "specific_active_return": 0.008,
    "factor_contributions": [
      {
        "factor": "MKT",
        "active_beta": 0.15,
        "factor_return": 0.10,
        "contribution": 0.015
      }
    ],
    "active_risk_decomposition": {
      "total_tracking_error": 0.045,
      "systematic_tracking_error": 0.035,
      "specific_tracking_error": 0.028
    }
  }
  ```

---

## 5. Security, Multi-Tenant & Numerical Acceptance Criteria

1. **Authentication:** Valid JWT bearer token or researcher session cookie required on all routes.
2. **Tenant Isolation:** Access to `dataset_id` must be validated against `user_id` and organization permissions.
3. **Mathematical Identity:** $\sum (A_i + S_i + I_i) = \Delta R$ must reconcile within $< 10^{-10}$ across all calculation modes.
4. **Cariño Consistency:** Cumulative linked multi-period active return must equal $R_p^{\text{cum}} - R_b^{\text{cum}}$ within $< 10^{-10}$.
5. **Zero Look-Ahead Bias:** Attribution in historical period $t$ strictly uses weights and returns up to $t$.
6. **Frontend Integration:** Institutional React 19 / TypeScript workspace with Brinson waterfall charts, sector scatter plots, and factor attribution breakdown.
