# Engineering Methodology & Mathematical Formulation

This document details the architectural principles, mathematical formulations, and machine learning pipelines implemented in the **AI-Enabled Smart Grid Cyber-Physical System**.

---

## 1. Cyber-Physical Control Doctrine

The core operational principle of this platform resolves the danger of stochastic AI actuation in physical electrical grids:

$$\textbf{AI Predicts \& Diagnoses} \;\longrightarrow\; \textbf{Deterministic Safety Decides} \;\longrightarrow\; \textbf{ESP32 Executes}$$

* **Artificial Intelligence Layer:** Operates as an advisory forecasting and diagnostic coprocessor. It calculates lookahead electrical demands and identifies anomalous branch signatures. It is strictly prohibited from directly toggling physical contactors.
* **Deterministic Safety Engine:** A hardcoded rule-based arbiter operating on physical electrical laws (Kirchhoff's Current Law, statistical overcurrent limits, and capacity headroom). It evaluates and authorizes all switching commands.
* **Embedded Edge Execution:** The ESP32 microcontroller executes validated switching states via optocoupled relays while simultaneously running local autonomous overcurrent breakers independently of network connectivity.

---

## 2. Mathematical Formulations

### 2.1 Statistical Two-Standard-Deviation ($2\sigma$) Edge Breaker
To protect branch conductors and sensitive loads from thermal overloads without relying on cloud round-trip latency, edge tripping thresholds are derived from steady-state empirical distributions:

$$I_{\text{trip}, j} = \mu_j + 2\sigma_j$$

where $\mu_j$ and $\sigma_j$ represent the baseline mean current and standard deviation of branch $j$. 

| Sector ($j$) | Nominal Baseline ($I_{\text{nominal}}$) | 2-SD Trip Threshold ($I_{\text{trip}}$) | Edge Action |
| :--- | :---: | :---: | :---: |
| **Critical Load** | $300.0\,\text{mA}$ | $320.0\,\text{mA}$ | Visual/MQTT Alert (Non-sheddable) |
| **Hospital** | $256.0\,\text{mA}$ | $272.0\,\text{mA}$ | Instant Edge Trip ($< 1.0\,\text{s}$) |
| **Street Light** | $394.0\,\text{mA}$ | $405.0\,\text{mA}$ | Instant Edge Trip ($< 1.0\,\text{s}$) |
| **House** | $241.0\,\text{mA}$ | $256.0\,\text{mA}$ | Instant Edge Trip ($< 1.0\,\text{s}$) |
| **Industry** | $240.0\,\text{mA}$ | $264.0\,\text{mA}$ | Instant Edge Trip ($< 1.0\,\text{s}$) |

If $I_j(t) > I_{\text{trip}, j}$, the ESP32 opens the corresponding relay in **$< 1.0\,\text{second}$** locally on Core 1.

---

### 2.2 Capacity Shedding & Dynamic Hysteresis
Total busbar capacity utilization $U(t)$ is computed in real time:

$$U(t) = \left( \frac{I_{\text{total}}(t)}{I_{\text{limit}}(t)} \right) \times 100\%$$

where $I_{\text{limit}}(t)$ is dynamically arbitrated by hardware optocouplers:
* **Dual SMPS:** $I_{\text{limit}} = 5000\,\text{mA}$ ($60.0\,\text{W}$)
* **Single SMPS:** $I_{\text{limit}} = 1000\,\text{mA}$ ($12.0\,\text{W}$)
* **Battery Backup:** $I_{\text{limit}} = 800\,\text{mA}$ ($9.6\,\text{W}$)

#### Shedding Rule:
When $U(t) \ge 85.0\%$, the system sheds the lowest active priority sector:

$$\text{Shed Candidate} = \arg\min_{k \in \text{Active}} P_k$$

where priority weights are:
$$\text{Critical (5)} > \text{Hospital (4)} > \text{Street (3)} > \text{House (2)} > \text{Industry (1)}$$

**Anti-Chattering Dwell Time:** A mandatory $15.0\,\text{second}$ cooldown is enforced after any switching event:
$$\Delta t_{\text{dwell}} = t - t_{\text{last\_switch}} \ge 15.0\,\text{s}$$
preventing contact bounce and mechanical relay wear.

---

### 2.3 Opportunistic Priority-Packing Restoration (Bounded Knapsack)
When grid demand subsides and capacity headroom becomes available ($U(t) < 84.0\%$), shedded sectors are restored using a greedy approximation of the 0/1 Bounded Knapsack Problem:

$$\max \sum_{i \in \text{Off}} P_i \cdot x_i \quad \text{subject to} \quad I_{\text{total}}(t) + \sum_{i \in \text{Off}} (I_{\text{nominal}, i} \cdot x_i) \le 0.84 \times I_{\text{limit}}(t)$$

where $x_i \in \{0, 1\}$.

The algorithm evaluates shedded sectors in descending priority order (`Hospital` $\to$ `Street` $\to$ `House` $\to$ `Industry`). If restoring a high-priority load would breach the $84.0\%$ ceiling, the algorithm greedily bypasses it and attempts to pack smaller lower-priority loads into the remaining headroom. This eliminates cyclical cold-load pickup brownouts.

---

### 2.4 Stuck Relay / Welded Contactor Diagnostics
Mechanical contactors frequently suffer from contact welding under high-current inductive arcing. The system continuously evaluates:

$$\text{Fault} = \text{STUCK\_CLOSED} \quad \text{if} \quad (\text{Relay}_{\text{cmd}, j} == 0) \land (I_j(t) > 25.0\,\text{mA})$$

When detected, the sector is placed into a safety lockout state, logged in the database actuation audit trail, and dispatched via Telegram alerts.

---

## 3. Machine Learning Pipeline

### 3.1 36-Feature Rolling Temporal Window
To feed the predictive models without high disk I/O, an in-memory 35-sample circular FIFO queue maintains rolling telemetry frames. At each 2.0-second step, it extracts 36 features:

1. **Temporal Features:** Hour of day, minute, day of week, weekend indicator.
2. **Current State:** Dynamic current limit, generation source presence flags (SMPS1, SMPS2, Battery).
3. **Lag Vectors:** Multi-step lags for total current ($t-1, t-3, t-6, t-30$).
4. **Moving Averages:** 1-minute (last 6 samples) and 5-minute (last 30 samples) rolling means:
   $$\bar{I}_{1\text{min}}(t) = \frac{1}{6} \sum_{k=0}^{5} I_{\text{total}}(t - k)$$
5. **Discrete Rate of Change:** Numerical first derivative approximation:
   $$\frac{dI}{dt} \approx I_{\text{total}}(t) - I_{\text{total}}(t - 1)$$
6. **Sector Load Metrics:** Sector voltages, currents, and powers across all 5 branches.

### 3.2 Hybrid Physics-Constrained Load Forecasting
* **Architecture:** Scikit-Learn `RandomForestRegressor` with 100 estimators.
* **Physics Clamping Constraint:** Purely statistical models often predict small residual baseline currents even when a sector relay is open. The inference engine applies a post-prediction physical mask:
  $$\hat{P}_j(t + 1) = \begin{cases} f_{\text{RF}}(X_j(t)), & \text{if } \text{Relay}_j(t) == 1 \\ 0.0, & \text{if } \text{Relay}_j(t) == 0 \end{cases}$$
* **Performance:** $R^2 = 0.9404$, $\text{RMSE} = 28.4\,\text{mA}$, inference time = $8.2\,\text{ms}$ on CPU.

### 3.3 Branch Fault Classification
Dedicated Random Forest classifiers monitor each sector to detect:
* `NORMAL`: Steady-state operation within nominal limits.
* `OVERCURRENT`: Branch draw exceeding 2-SD limit.
* `UNDERCURRENT`: Branch draw $< 60\%$ of nominal rating while energized.
* `RELAY_OFF_CURRENT_DRAWN`: Physical contactor welded shut.
* `RELAY_ON_NO_CURRENT`: Open circuit or load disconnection.
* **Diagnostic Accuracy:** **$98.5\%$** on experimental fault-injection datasets.

---

## 4. Concurrency & Telemetry Storage Architecture

The persistence engine uses **SQLite in Write-Ahead Logging (WAL) mode**:
* `PRAGMA journal_mode=WAL;`
* `PRAGMA synchronous=NORMAL;`

WAL mode decouples read and write locks:
1. High-frequency MQTT threads execute inserts into `telemetry_logs` and `grid_actuation_events` concurrently.
2. Web dashboard clients execute non-blocking time-series queries via B-Tree indexes on the `timestamp` column (`CREATE INDEX idx_telemetry_ts ON telemetry_logs (timestamp)`).
3. Average historical query latency is $< 1.2\,\text{ms}$ across 3,495 logged hardware cycles.
