# SESSION 28 CONTRACTS — STAGE 23 APPROVED SCOPE SPECIFICATION
## Option 1: Stage 22 Mathematical Remediation & Regular Vine Copula Architecture (R-Vine / C-Vine Decomposition & Exact Positive-Stable Gumbel Simulation)

**Project:** Quantitative Research Dashboard & Portfolio Optimization Engine  
**Session:** 28  
**Governance Stage:** Stage 23 — Regular Vine Copula Architecture, Pair-Copula Decomposition & Exact Positive-Stable Gumbel Simulation  
**Status:** Approved by User for Implementation  
**Approved Scope:** Option 1  

---

## 1. Quantitative & Mathematical Formulations

### 1.1 Remediation of DEF-28-01: Exact Positive-Stable Frailty Gumbel Generator
The Gumbel Archimedean copula has generator $\psi(t) = \exp(-t^{1/\theta})$ with $\theta \ge 1$.
The Laplace transform of a positive stable distribution $V \sim S(\alpha = 1/\theta, \beta = 1, \gamma = (\cos(\pi / (2\theta)))^\theta, \delta = 0)$ is:
$$\mathbb{E}[e^{-t V}] = \exp\left( - t^{1/\theta} \right) = \psi(t)$$

#### Chambers-Mallows-Stuck (1976) Algorithm for Positive Stable Sampling:
For $\alpha = 1/\theta \in (0, 1]$:
1. Draw standard uniform $U \sim \text{Uniform}\left(-\frac{\pi}{2}, \frac{\pi}{2}\right)$.
2. Draw independent standard exponential $W \sim \text{Exponential}(1)$.
3. When $\alpha = 1$ ($\theta = 1$, independence): $V \equiv 1$.
4. When $\alpha < 1$ ($\theta > 1$):
   $$V = \frac{\sin\left(\alpha \left(U + \frac{\pi}{2}\right)\right)}{\left(\cos U\right)^{1/\alpha}} \left( \frac{\cos\left( U - \alpha \left(U + \frac{\pi}{2}\right) \right)}{W} \right)^{\frac{1 - \alpha}{\alpha}}$$
5. For each asset $i \in \{1, \dots, N\}$, draw independent standard exponential $E_i \sim \text{Exponential}(1)$.
6. Evaluate uniform pseudo-observation:
   $$U_i = \exp\left( - \left(\frac{E_i}{V}\right)^{1/\theta} \right)$$
7. **Theoretical Tail Invariant:**
   $$\lambda_L = 0, \qquad \lambda_U = 2 - 2^{1/\theta} \in (0, 1)$$
   The simulated empirical upper tail quantile comovement recovers $\lambda_U > 0$, strictly remediating DEF-28-01.

---

### 1.2 Pair-Copula Construction (PCC) and Regular Vine Decomposition

Sklar's theorem implies that any $d$-dimensional continuous density $f(x_1, \dots, x_d)$ can be decomposed into marginal densities $f_i(x_i)$ and a product of $d(d-1)/2$ bivariate copula densities conditioned on subsets of variables (Aas, Czado, Frigessi, & Bakken 2009; Bedford & Cooke 2002):

$$f(x_1, \dots, x_d) = \prod_{k=1}^d f_k(x_k) \times \prod_{i=1}^{d-1} \prod_{e \in E_i} c_{j(e), k(e) \mid D(e)}\left( F(x_{j(e)} \mid x_{D(e)}), F(x_{k(e)} \mid x_{D(e)}) \right)$$

where $E_i$ are edges in tree $T_i$, and $D(e)$ is the conditioning set.

#### Canonical Vine (C-Vine) Structure:
In a C-Vine, each tree $T_i$ has a unique star/root node connecting to all other nodes.
The joint copula density for ordering $(1, \dots, d)$ is:
$$c(u_1, \dots, u_d) = \prod_{j=1}^{d-1} \prod_{k=1}^{d-j} c_{j, j+k \mid 1, \dots, j-1}\left( F(u_j \mid u_1, \dots, u_{j-1}), F(u_{j+k} \mid u_1, \dots, u_{j-1}) \right)$$

#### D-Vine Structure:
In a D-Vine, each tree $T_i$ is a path. The joint copula density is:
$$c(u_1, \dots, u_d) = \prod_{j=1}^{d-1} \prod_{k=1}^{d-j} c_{k, k+j \mid k+1, \dots, k+j-1}\left( F(u_k \mid u_{k+1}, \dots, u_{k+j-1}), F(u_{k+j} \mid u_{k+1}, \dots, u_{k+j-1}) \right)$$

---

### 1.3 Conditional Copula Distribution Functions ($h$-functions)

Joe (1996) proved that the conditional distribution function for a pair $(u, v)$ with copula $C(u, v)$ is given by the partial derivative:
$$h(u \mid v; \mathbf{\theta}) = F(u \mid v) = \frac{\partial C(u, v)}{\partial v}$$

#### Analytical $h$-functions and Inverse $h^{-1}$-functions:
1. **Gaussian Copula:**
   $$h_{\text{Gauss}}(u \mid v; \rho) = \Phi\left( \frac{\Phi^{-1}(u) - \rho \Phi^{-1}(v)}{\sqrt{1 - \rho^2}} \right)$$
   $$h_{\text{Gauss}}^{-1}(w \mid v; \rho) = \Phi\left( \rho \Phi^{-1}(v) + \sqrt{1 - \rho^2} \Phi^{-1}(w) \right)$$

2. **Student-t Copula:**
   $$h_t(u \mid v; \rho, \nu) = t_{\nu+1}\left( \frac{t_\nu^{-1}(u) - \rho t_\nu^{-1}(v)}{\sqrt{\frac{(\nu + (t_\nu^{-1}(v))^2)(1 - \rho^2)}{\nu + 1}}} \right)$$
   $$h_t^{-1}(w \mid v; \rho, \nu) = t_\nu\left( \rho t_\nu^{-1}(v) + t_{\nu+1}^{-1}(w) \sqrt{\frac{(\nu + (t_\nu^{-1}(v))^2)(1 - \rho^2)}{\nu + 1}} \right)$$

3. **Clayton Copula:**
   $$h_{\text{Clayton}}(u \mid v; \theta) = v^{-(\theta + 1)} \left( u^{-\theta} + v^{-\theta} - 1 \right)^{-(1 + 1/\theta)}$$
   $$h_{\text{Clayton}}^{-1}(w \mid v; \theta) = \left[ 1 + v^{-\theta} \left( w^{-\frac{\theta}{\theta+1}} - 1 \right) \right]^{-1/\theta}$$

4. **Gumbel Copula:**
   Let $\tilde{u} = -\ln u, \tilde{v} = -\ln v, A = \tilde{u}^\theta + \tilde{v}^\theta$:
   $$h_{\text{Gumbel}}(u \mid v; \theta) = C_\theta(u, v) \frac{\tilde{v}^{\theta - 1}}{v A^{1 - 1/\theta}}$$
   $h_{\text{Gumbel}}^{-1}(w \mid v; \theta)$ evaluated via root-finding (Newton-Raphson / Brent's method) on $[10^{-8}, 1 - 10^{-8}]$.

5. **Independence Copula:**
   $$h_{\text{Indep}}(u \mid v) = u, \qquad h_{\text{Indep}}^{-1}(w \mid v) = w$$

---

### 1.4 Sequential Simulation from Regular Vines

To simulate a vector of $d$ dependent uniform variables $(U_1, \dots, U_d)$ from a fitted C-Vine:
1. Draw $d$ independent uniform random variables: $W_1, \dots, W_d \sim \text{Uniform}(0, 1)$.
2. Set $U_1 = W_1$.
3. For $j = 2, \dots, d$:
   - Recursively invert the conditioned variables using $h^{-1}$:
     $$U_j = h^{-1}(W_j \mid U_{1:(j-1)}; \theta)$$
4. Transform uniforms through marginal inverse CDFs to obtain simulated asset returns:
   $$R_i = F_i^{-1}(U_i)$$

This guarantees fully heterogeneous non-linear dependence across all dimensions $d \ge 2$, overcoming DEF-28-02.

---

## 2. API Contract Specifications

### 2.1 Request Models
- `POST /api/v1/copula/vine/fit`
  ```json
  {
    "dataset_id": "string",
    "vine_type": "c_vine | d_vine",
    "marginal_method": "empirical | student_t",
    "family_set": ["clayton", "gumbel", "student_t", "gaussian", "indep"],
    "tickers": ["AAPL", "MSFT", "GOOGL"]
  }
  ```
- `POST /api/v1/copula/vine/simulate`
  ```json
  {
    "dataset_id": "string",
    "vine_type": "c_vine | d_vine",
    "marginal_method": "empirical | student_t",
    "num_simulations": 5000,
    "random_seed": 42,
    "tickers": ["AAPL", "MSFT", "GOOGL"]
  }
  ```
- `POST /api/v1/copula/vine/tail-risk-parity`
  ```json
  {
    "dataset_id": "string",
    "vine_type": "c_vine | d_vine",
    "marginal_method": "empirical | student_t",
    "confidence_level": 0.99,
    "num_simulations": 5000,
    "random_seed": 42,
    "tickers": ["AAPL", "MSFT", "GOOGL"]
  }
  ```

---

## 3. Independent Analytical Benchmarks

1. **Positive-Stable Frailty Benchmark (DEF-28-01 Remediation):**
   - For Gumbel with $\theta = 2.0$:
     $\alpha = 0.50$.
     Draw $V \sim S(0.5, 1, (\cos(\pi/4))^{0.5}, 0)$.
     $U_i = \exp(-(E_i / V)^{0.5})$.
     Theoretical upper tail dependence $\lambda_U = 2 - \sqrt{2} \approx 0.58578644$.
     Simulated empirical upper tail event frequency: $|\hat{\lambda}_U - 0.5858| < 0.05$.
2. **h-Function Inverse Identity Benchmark:**
   - For all supported copula families (Gaussian, Student-t, Clayton, Gumbel, Independence) and valid parameters:
     $$| h^{-1}(h(u \mid v; \theta) \mid v; \theta) - u | < 10^{-7} \quad \forall u, v \in (0, 1)$$
3. **C-Vine 3-Asset Analytical Benchmark:**
   - In a 3-asset C-Vine with star node 1, Tree 1 contains pairs $(1, 2)$ and $(1, 3)$. Tree 2 contains conditioned pair $(2, 3 \mid 1)$.
   - Evaluates exact sequential conditional densities without numerical overflow.
