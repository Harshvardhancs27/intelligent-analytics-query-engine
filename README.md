# Intelligent Analytics Query Engine

A production-grade, dual-engine (Pandas / SQL) Analytics Engine that translates natural language business questions into secure, executable analytical code, runs it against enterprise datasets with sub-millisecond latency, and returns precise computed results accompanied by multi-factor confidence scores and transparent explainable AI summaries.

---

## 🏛️ Architecture Overview

The system is architected as an 8-stage decoupled analytical pipeline:

```
                          Natural Language Query
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 1: Linguistic Parsing & Ontology Grounding                        │
│   • SchemaCatalog & Data Dictionary (Metrics, Dimensions, Synonyms)     │
│   • Feedback Loop Matcher (Historical calibration & prior corrections) │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 2: Semantic Intent Compiler (QueryPlan AST)                      │
│   • Identifies Intent: Aggregation, Top-N, Contribution %, Window,    │
│     Target Comparison Join, YoY Growth, Multi-Level Nested Ranking      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 3: Dual Code Generation Engine                                   │
│   • PandasGenerator: Idiomatic, vectorized DataFrame operations        │
│   • SQLGenerator: ANSI/SQLite SQL with CTEs, Window Functions, JOINs   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 4: AST Security Sandbox                                          │
│   • Validates Python AST against banned built-ins & RCE exploits       │
│   • Restricts imports, file I/O, process spawning, dunder traversal    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 5: Deterministic Execution Engine                                │
│   • PandasRunner / SQLRunner (In-Memory SQLite)                        │
│   • Zero-data-mutation isolated execution context                      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 6: Multi-Factor Confidence Scorer (0.00 – 1.00)                  │
│   • Schema Alignment (30%) + Syntax Validity (25%) +                   │
│     Translation Certainty (25%) + Execution Status (20%) +/- Feedback │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 7: Explainable AI Engine                                         │
│   • Details what was understood (metrics, formulas, dimensions)        │
│   • Details how results were derived (joins, windowing, aggregations)  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│ Stage 8: Output Packaging & Feedback Loop Integration                  │
│   • Standard JSON schema output                                        │
│   • Dynamic feedback recording to feedback_log.csv                     │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Key Engineering Highlights & Edge Cases Solved

1. **North America (`"NA"`) Region Preservation vs. NaN**:
   - In standard Pandas `pd.read_csv()`, the string `"NA"` is parsed by default as `NaN` (missing value).
   - In international business datasets, `"NA"` denotes North America alongside `"APAC"` and `"EMEA"`.
   - Our `DataLoader` configures `keep_default_na=False` with selective null handling, ensuring North American regions are accurately grouped and joined.

2. **Malformed File & BOM Resilience**:
   - Automatically detects and unescapes Excel/CSV quote-wrapped files (`"\"order_id,order_date...\""`).
   - Handles UTF-8 BOM (`\ufeff`) across all JSON and CSV ingestion pipelines.

3. **Dynamic Formula Derivation**:
   - Derived business metrics defined in `data_dictionary.json` (such as `revenue = quantity * unit_price * (1 - discount)` and `AOV = revenue / orders`) are automatically compiled into working columns and SQL expressions without requiring manual pre-calculations.

4. **AST Code Sandboxing**:
   - Python code execution runs through an AST NodeVisitor (`SandboxValidator`) that intercepts and blocks unauthorized imports (`os`, `sys`, `subprocess`), banned builtins (`open`, `eval`, `exec`, `compile`, `__import__`), and dunder inspection (`__class__`, `__subclasses__`).

5. **Single-Year YoY Growth Handling**:
   - The test dataset contains FY2024 transactional data. When calculating Year-over-Year (YoY) growth, prior period (2023) baseline is mathematically absent.
   - The engine gracefully flags this boundary condition, returns the baseline FY2024 revenue ($6,134.40), and provides an explicit explanation rather than crashing with division-by-zero or unhandled `NaN`.

6. **Dual Execution Engine Parity**:
   - Every analytical query can be executed interchangeably through **Pandas** or **In-Memory SQLite SQL**, with 100% mathematical parity across results.

---

## 📊 Benchmark Suite Results (`nl_queries.json`)

The engine was evaluated against the entire benchmark test suite. Results are recorded in `output_results.json`:

| # | Natural Language Query | Generated Pandas Logic | Computed Result | Confidence |
|---|------------------------|------------------------|-----------------|:----------:|
| 1 | **Total sales in India for March** | `df[(df['country'] == 'India') & (df['month'] == '2024-03')]['revenue'].sum()` | `108.0` | **1.00** |
| 2 | **Top 2 cities by profit** | `df.groupby('city')['profit'].sum().reset_index().sort_values(by='profit', ascending=False).head(2)` | `New York: 200`<br>`San Francisco: 180` | **0.99** |
| 3 | **Average order value by region** | `(df.groupby('region')['revenue'].sum() / df.groupby('region')['order_id'].nunique()).reset_index(name='avg_order_value')` | `APAC: 118.50`<br>`EMEA: 799.33`<br>`NA: 1087.47` | **0.99** |
| 4 | **Which region missed its target in Feb?** | Target JOIN on `region`, filter `month == '2024-02'`, compare `revenue < target_revenue` | `APAC: 75.0 vs 6000`<br>`EMEA: 255.0 vs 7500`<br>`NA: 1116.0 vs 9500` | **0.99** |
| 5 | **Sales contribution % by category** | `cat_sales = df.groupby('product_category')['revenue'].sum().reset_index()`<br>`cat_sales['contribution_pct'] = (cat_sales['revenue'] / df['revenue'].sum()) * 100` | `Technology: 88.06%`<br>`Furniture: 9.44%`<br>`Office Supplies: 2.50%` | **0.99** |
| 6 | **Top product in each region** | Group by `['region', 'product_name']`, compute rank partitioned by `region`, filter `rank == 1` | `APAC: Ergo Chair (324.0)`<br>`EMEA: Samsung Galaxy (1288.0)`<br>`NA: Dell XPS (2068.0)` | **0.99** |
| 7 | **YoY growth in revenue** | `yearly_rev = df.groupby('year')['revenue'].sum()`<br>`yearly_rev.pct_change()` | `2024: $6,134.40`<br>*(Prior year absent in dataset)* | **0.97** |
| 8 | **Revenue of top 3 customers per region** | Group by `['region', 'customer_id']`, rank within `region`, filter top 3, aggregate by `region` | `APAC: 474.0`<br>`EMEA: 2398.0`<br>`NA: 3262.4` | **0.99** |

---

## 🎯 Confidence Scoring Rubric

The engine produces an objective, deterministic confidence score between `0.00` and `1.00`:

$$C = 0.30 \cdot S_{schema} + 0.25 \cdot S_{syntax} + 0.25 \cdot S_{certainty} + 0.20 \cdot S_{execution} \pm \Delta_{feedback}$$

- **Schema Alignment ($S_{schema}$, 30%)**: Verifies that 100% of target metrics, dimensions, and filter columns exist in registered table schemas.
- **Syntax Validity ($S_{syntax}$, 25%)**: Evaluates whether the generated Pandas AST or SQL statement parses with zero syntax errors.
- **Translation Certainty ($S_{certainty}$, 25%)**: Quantifies linguistic ambiguity (penalizes queries requiring heuristic defaults).
- **Execution Status ($S_{execution}$, 20%)**: Verifies runtime execution succeeded and returned non-empty, validly typed analytical outputs.
- **Feedback Adjustment ($\Delta_{feedback}$, $\pm 10\%$)**: Historical 5-star verified feedback yields $+0.05$ boost; past flagged corrections trigger calibration penalties.

---

## 🔄 Feedback Loop Integration (`feedback_log.csv`)

The feedback manager provides closed-loop active learning:
1. **Lookup**: For every query, the engine computes Jaccard token similarity against historical records in `feedback_log.csv`.
2. **Calibration**: Matches with high similarity (>0.65) and positive analyst ratings adjust confidence upwards and annotate the explainability summary.
3. **Capture**: Analysts can log real-time feedback via CLI or REST API:
   ```bash
   python main.py -q "Total sales in India for March" --feedback-rate 5 --feedback-notes "Verified by finance team"
   ```

---

## ⚖️ Architectural Tradeoffs & Decisions

| Dimension | Decision Taken | Rationale & Tradeoff |
|---|---|---|
| **Execution Dialect** | Dual Engine (Pandas + SQL) | Pandas excels at ad-hoc exploratory scripting; SQL excels at enterprise warehouse integration. Dual-engine provides portability with zero vendor lock-in. |
| **Parsing Strategy** | Hybrid Semantic Compiler + LLM Bridging | Pure LLM calls have non-deterministic latencies (1-3s) and external API dependencies. A semantic grammar compiler provides microsecond execution, 100% reliability offline, while supporting LLM escalation. |
| **Code Execution** | Isolated AST Sandbox | Raw `exec()` is an arbitrary code execution risk. AST validation prevents RCE while maintaining the power of native vectorization. |
| **Output Representation** | Strictly Typed JSON Primitives | Rather than dumping raw DataFrame strings, tables and series are converted to structured JSON dictionaries and rounded floats for automated consumption. |

---

## 💻 How to Run

### 1. Run Benchmark Suite (Default: Pandas)
```bash
python main.py
```
*Outputs evaluation summary and writes `output_results.json`.*

### 2. Run Benchmark Suite in SQL Mode
```bash
python main.py -m sql
```

### 3. Run Custom Ad-Hoc Query
```bash
python main.py -q "What is the total profit in Germany?"
python main.py -q "Top 3 products by sales"
```

### 4. Run Automated Test Suite
```bash
python -m unittest test_engine.py
```
*Executes 20 comprehensive unit and integration tests (benchmark parity, security sandbox, unseen queries, feedback loop).*

### 5. Launch FastAPI REST Server
```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```
*Interactive Swagger documentation available at: `http://127.0.0.1:8000/docs`.*

---

## 🔮 Future Improvements (If Given More Time)

1. **Vector Embedding Retriever**: Incorporate local vector embeddings (e.g. `sentence-transformers` / Faiss) for semantic schema search on 10,000+ column enterprise warehouses.
2. **Natural Language Visualization Engine**: Automatically synthesize interactive Vega-Lite / Plotly chart specifications alongside tabular results.
3. **Auto-Correction Multi-turn Agent**: If execution fails on a dirty dataset, an autonomous reflection loop iteratively inspects error tracebacks and repairs the logic.
4. **Data Drift & Anomaly Alerts**: Integrated distribution monitoring to alert analysts when query results deviate significantly from expected historical bounds.
