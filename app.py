import itertools
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Executive Incentive Design Lab", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def sample_data():
    return pd.DataFrame({
        "year": list(range(2010, 2025)),
        "revenue": [1000, 1035, 1070, 1125, 1180, 1160, 1215, 1280, 1350, 1425, 1320, 1460, 1550, 1625, 1710],
        "ebitda": [180, 188, 197, 214, 230, 215, 238, 260, 282, 302, 250, 315, 344, 370, 398],
        "gross_margin": [0.340, 0.345, 0.350, 0.360, 0.365, 0.355, 0.370, 0.378, 0.385, 0.392, 0.360, 0.400, 0.410, 0.420, 0.430],
        "eps": [2.10, 2.18, 2.30, 2.55, 2.80, 2.45, 2.95, 3.30, 3.70, 4.05, 3.10, 4.40, 4.85, 5.20, 5.65],
        "fcf": [80, 86, 90, 100, 115, 95, 120, 132, 148, 165, 110, 172, 190, 210, 228],
        "roic": [0.095, 0.098, 0.101, 0.108, 0.113, 0.102, 0.116, 0.123, 0.130, 0.138, 0.110, 0.142, 0.150, 0.158, 0.166],
        "tsr": [0.08, 0.04, 0.12, 0.18, 0.22, -0.10, 0.16, 0.20, 0.24, 0.18, -0.22, 0.28, 0.19, 0.15, 0.21],
        "actual_payout_pct": [0.90, 0.95, 1.05, 1.20, 1.35, 0.70, 1.25, 1.45, 1.60, 1.55, 0.55, 1.70, 1.50, 1.40, 1.65],
    })


def is_excel(uploaded_file):
    return uploaded_file is not None and uploaded_file.name.lower().endswith((".xlsx", ".xls"))


def excel_sheet_names(uploaded_file):
    if uploaded_file is None:
        return []
    uploaded_file.seek(0)
    xls = pd.ExcelFile(uploaded_file)
    return xls.sheet_names


def header_score(row):
    score = 0
    for val in row:
        if pd.isna(val):
            continue
        txt = str(val).strip()
        if not txt:
            continue
        # Penalize long encoded/cache-looking values.
        if len(txt) > 60:
            score -= 3
        # Reward likely column labels.
        if any(ch.isalpha() for ch in txt):
            score += 2
        if any(key in txt.lower() for key in ["year", "fye", "payout", "revenue", "ebitda", "eps", "tsr", "market", "metric", "weight"]):
            score += 4
    return score


def detect_excel_layout(uploaded_file):
    """Return a reasonable default sheet and header row for messy workbooks."""
    if not is_excel(uploaded_file):
        return None, 0
    names = excel_sheet_names(uploaded_file)
    best_sheet = names[0] if names else None
    best_header = 0
    best_score = -10**9
    for sheet in names:
        uploaded_file.seek(0)
        try:
            preview = pd.read_excel(uploaded_file, sheet_name=sheet, header=None, nrows=30)
        except Exception:
            continue
        for idx in range(len(preview)):
            row_score = header_score(preview.iloc[idx])
            below = preview.iloc[idx+1:idx+8] if idx + 1 < len(preview) else pd.DataFrame()
            numeric_count = 0
            if not below.empty:
                numeric_count = below.apply(pd.to_numeric, errors="coerce").notna().sum().sum()
            total = row_score + numeric_count * 0.25
            if total > best_score:
                best_score = total
                best_sheet = sheet
                best_header = idx
    return best_sheet, int(best_header)


def read_data(uploaded_file, sheet_name=None, header_row=0):
    if uploaded_file is None:
        return sample_data()
    name = uploaded_file.name.lower()
    uploaded_file.seek(0)
    if name.endswith(".csv"):
        return pd.read_csv(uploaded_file, header=header_row)
    return pd.read_excel(uploaded_file, sheet_name=sheet_name, header=header_row)


def clean_columns(df):
    df = df.copy()
    df.columns = (
        df.columns.astype(str)
        .str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace(".", "_", regex=False)
    )
    return df


def numeric_cols(df):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]


def safe_corr(a, b):
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 3 or d.iloc[:,0].std() == 0 or d.iloc[:,1].std() == 0:
        return 0.0
    return float(d.iloc[:,0].corr(d.iloc[:,1]))


def normalize_metric(series, direction):
    s = pd.to_numeric(series, errors="coerce")
    if direction == "Lower is better":
        s = -s
    # target range uses closeness to median as a first-pass proxy
    if direction == "Target range":
        target = s.median()
        s = -abs(s - target)
    if s.std() == 0 or pd.isna(s.std()):
        return pd.Series(np.ones(len(s)), index=s.index)
    z = (s - s.mean()) / s.std()
    # convert to payout-like score centered around 1.0
    score = 1 + (z * 0.15)
    return score.clip(lower=0.0, upper=2.0)


def payout_curve(performance, threshold_perf, target_perf, max_perf, threshold_payout, max_payout):
    if performance < threshold_perf:
        return 0.0
    if performance < target_perf:
        return threshold_payout + ((performance - threshold_perf) / (target_perf - threshold_perf)) * (1.0 - threshold_payout)
    if performance < max_perf:
        return 1.0 + ((performance - target_perf) / (max_perf - target_perf)) * (max_payout - 1.0)
    return max_payout


def modeled_payout(df, weights, directions, threshold_perf, target_perf, max_perf, threshold_payout, max_payout):
    score = pd.Series(0.0, index=df.index)
    total_weight = sum(weights.values())
    if total_weight == 0:
        return pd.Series(np.nan, index=df.index)
    for m, w in weights.items():
        score += normalize_metric(df[m], directions.get(m, "Higher is better")) * (w / total_weight)
    return score.apply(lambda x: payout_curve(x, threshold_perf, target_perf, max_perf, threshold_payout, max_payout))


def fit_stats(actual, predicted, value_measure):
    d = pd.DataFrame({"actual": actual, "predicted": predicted, "value": value_measure}).dropna()
    if len(d) < 3:
        return {"corr_actual_value": 0, "corr_pred_value": 0, "mae": 0, "avg_actual": 0, "avg_pred": 0, "vol_actual": 0, "vol_pred": 0, "r2_like": 0}
    mae = float((d["actual"] - d["predicted"]).abs().mean())
    ss_res = float(((d["actual"] - d["predicted"]) ** 2).sum())
    ss_tot = float(((d["actual"] - d["actual"].mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    return {
        "corr_actual_value": safe_corr(d["actual"], d["value"]),
        "corr_pred_value": safe_corr(d["predicted"], d["value"]),
        "mae": mae,
        "avg_actual": float(d["actual"].mean()),
        "avg_pred": float(d["predicted"].mean()),
        "vol_actual": float(d["actual"].std()),
        "vol_pred": float(d["predicted"].std()),
        "r2_like": max(float(r2), -1.0),
    }


def generate_weight_sets(metrics, step=25, max_metrics=4):
    out = []
    for r in range(1, min(max_metrics, len(metrics)) + 1):
        for combo in itertools.combinations(metrics, r):
            if r == 1:
                out.append({combo[0]: 100})
            else:
                for vals in itertools.product(range(step, 101, step), repeat=r):
                    if sum(vals) == 100:
                        out.append(dict(zip(combo, vals)))
    return out


def plan_quality(stats, avg_actual, max_metrics_count):
    alignment = max(stats["corr_pred_value"], 0) * 35
    fit = max(min(stats["r2_like"], 1), 0) * 25
    cost = max(0, 1 - abs(stats["avg_pred"] - avg_actual) / max(avg_actual, 0.01)) * 15
    stability = max(0, 1 - stats["vol_pred"] / 1.0) * 15
    simplicity = max(0, 1 - (max_metrics_count - 1) / 5) * 10
    return alignment + fit + cost + stability + simplicity


def optimize_plans(df, metrics, directions, actual_col, value_col, threshold_perf, target_perf, max_perf, threshold_payout, max_payout, max_metrics=4, step=25):
    results = []
    actual = df[actual_col]
    value = df[value_col]
    avg_actual = float(pd.to_numeric(actual, errors="coerce").mean())
    for weights in generate_weight_sets(metrics, step=step, max_metrics=max_metrics):
        pred = modeled_payout(df, weights, directions, threshold_perf, target_perf, max_perf, threshold_payout, max_payout)
        stats = fit_stats(actual, pred, value)
        quality = plan_quality(stats, avg_actual, len(weights))
        mix = " / ".join([f"{w}% {m}" for m, w in weights.items()])
        results.append({
            "plan_quality_score": round(quality, 1),
            "metric_mix": mix,
            "value_alignment": round(stats["corr_pred_value"], 2),
            "historical_fit_r2": round(stats["r2_like"], 2),
            "average_payout": round(stats["avg_pred"], 2),
            "payout_volatility": round(stats["vol_pred"], 2),
            "average_error": round(stats["mae"], 2),
        })
    return pd.DataFrame(results).sort_values("plan_quality_score", ascending=False)

# -----------------------------
# UI
# -----------------------------
st.title("Executive Incentive Design Lab")
st.caption("Internal pilot | Historical diagnostics, backtesting, and incentive design optimization")
st.info("Start with the company's own history. The tool identifies what drove value, what drove payouts, and which alternative designs would have produced stronger alignment.")

with st.sidebar:
    st.header("1. Upload Data")
    uploaded = st.file_uploader("CSV or Excel", type=["csv", "xlsx", "xls"])
    st.caption("Use annual data where possible. At minimum: period, actual payout %, shareholder value measure, and candidate performance metrics.")

    selected_sheet = None
    header_row = 0
    if uploaded is not None and is_excel(uploaded):
        default_sheet, default_header = detect_excel_layout(uploaded)
        sheets = excel_sheet_names(uploaded)
        default_index = sheets.index(default_sheet) if default_sheet in sheets else 0
        selected_sheet = st.selectbox("Excel worksheet", sheets, index=default_index)
        header_row = st.number_input("Header row number", min_value=1, max_value=50, value=int(default_header) + 1, step=1) - 1
        st.caption("For your GPK file, the real data is on Sheet1 with headers on row 3. The hidden CIQ cache sheet should be ignored.")
    elif uploaded is not None:
        header_row = st.number_input("Header row number", min_value=1, max_value=50, value=1, step=1) - 1

    st.header("2. Payout Curve")
    threshold_perf = st.number_input("Threshold performance", value=0.90, step=0.05)
    target_perf = st.number_input("Target performance", value=1.00, step=0.05)
    max_perf = st.number_input("Maximum performance", value=1.20, step=0.05)
    threshold_payout = st.number_input("Threshold payout", value=0.50, step=0.05)
    max_payout = st.number_input("Maximum payout", value=2.00, step=0.10)

    st.header("3. Optimization")
    max_metrics = st.slider("Maximum metrics per plan", 1, 5, 4)
    step = st.selectbox("Weighting increment", [10, 20, 25, 50], index=2)

raw = clean_columns(read_data(uploaded, selected_sheet, header_row))

st.subheader("Data Preview")
st.dataframe(raw, use_container_width=True)

nums = numeric_cols(raw)
if len(nums) < 3:
    st.error("Upload a file with at least three numeric columns: actual payout, shareholder value, and at least one performance metric.")
    st.stop()

st.subheader("Step 1: Map the Data")
col1, col2, col3 = st.columns(3)
with col1:
    period_col = st.selectbox("Period / year column", raw.columns, index=0)
with col2:
    actual_col = st.selectbox("Actual payout column", nums, index=nums.index("actual_payout_pct") if "actual_payout_pct" in nums else 0)
with col3:
    value_col = st.selectbox("Shareholder value measure", nums, index=nums.index("tsr") if "tsr" in nums else min(1, len(nums)-1))

metric_candidates = [c for c in nums if c not in [actual_col, value_col]]
default_metrics = [m for m in ["revenue", "ebitda", "gross_margin", "eps", "fcf", "roic"] if m in metric_candidates]
selected_metrics = st.multiselect("Candidate incentive metrics", metric_candidates, default=default_metrics if default_metrics else metric_candidates[:5])

if not selected_metrics:
    st.warning("Select at least one candidate incentive metric.")
    st.stop()

st.subheader("Step 2: Define Metric Behavior")
directions = {}
cols = st.columns(3)
for i, metric in enumerate(selected_metrics):
    with cols[i % 3]:
        directions[metric] = st.selectbox(f"{metric}", ["Higher is better", "Lower is better", "Target range"], key=f"dir_{metric}")

work = raw.copy()
# Period handling: allow true dates, fiscal years, or Excel serial dates.
period_numeric = pd.to_numeric(work[period_col], errors="coerce")
if period_numeric.notna().sum() >= max(3, len(work) // 2):
    # Excel serial dates are commonly above 20,000. Fiscal years are commonly 1900-2100.
    if period_numeric.median() > 20000:
        work[period_col] = pd.to_datetime(period_numeric, unit="D", origin="1899-12-30", errors="coerce")
    else:
        work[period_col] = period_numeric
else:
    work[period_col] = pd.to_datetime(work[period_col], errors="coerce")
if work[period_col].notna().sum() > 0:
    work = work.sort_values(period_col)
for c in [actual_col, value_col] + selected_metrics:
    work[c] = pd.to_numeric(work[c], errors="coerce")
work = work.dropna(subset=[actual_col, value_col] + selected_metrics)

if len(work) < 5:
    st.warning("The model will run, but backtesting is more credible with at least 8-10 historical observations.")

# Tabs
summary_tab, diagnostics_tab, current_tab, optimize_tab, report_tab = st.tabs([
    "Executive Summary", "Historical Diagnostics", "Current Plan Backtest", "Optimization", "Committee Takeaway"
])

with diagnostics_tab:
    st.subheader("What Drove Shareholder Value?")
    rows = []
    for m in selected_metrics:
        rows.append({
            "metric": m,
            "correlation_to_value": safe_corr(work[m], work[value_col]),
            "correlation_to_actual_payout": safe_corr(work[m], work[actual_col]),
        })
    corr_df = pd.DataFrame(rows).sort_values("correlation_to_value", ascending=False)
    st.dataframe(corr_df.round(3), use_container_width=True, hide_index=True)

    fig = px.bar(corr_df, x="correlation_to_value", y="metric", orientation="h", title="Metric Relationship to Shareholder Value")
    st.plotly_chart(fig, use_container_width=True, key="value_corr_chart")

    fig2 = px.bar(corr_df.sort_values("correlation_to_actual_payout", ascending=False), x="correlation_to_actual_payout", y="metric", orientation="h", title="Metric Relationship to Actual Payouts")
    st.plotly_chart(fig2, use_container_width=True, key="payout_corr_chart")

    trend_df = work[[period_col, actual_col, value_col]].copy()
    st.subheader("Payout and Shareholder Value History")
    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(x=trend_df[period_col], y=trend_df[actual_col], mode="lines+markers", name="Actual payout"))
    fig3.add_trace(go.Scatter(x=trend_df[period_col], y=trend_df[value_col], mode="lines+markers", name="Shareholder value measure", yaxis="y2"))
    fig3.update_layout(title="Actual Payout vs. Shareholder Value", yaxis_title="Actual payout", yaxis2=dict(title="Shareholder value", overlaying="y", side="right"), height=450)
    st.plotly_chart(fig3, use_container_width=True, key="history_trend_chart")

with current_tab:
    st.subheader("Enter Current Plan Weights")
    st.caption("Enter the current plan weights for the selected metrics. The model uses the payout curve in the sidebar.")
    weights = {}
    wcols = st.columns(3)
    equal = int(round(100 / len(selected_metrics)))
    for i, m in enumerate(selected_metrics):
        with wcols[i % 3]:
            weights[m] = st.number_input(f"Weight: {m}", min_value=0, max_value=100, value=equal, step=5, key=f"w_{m}")
    total_w = sum(weights.values())
    if total_w != 100:
        st.warning(f"Weights currently sum to {total_w}%. The model will normalize them to 100% for calculation.")

    current_pred = modeled_payout(work, weights, directions, threshold_perf, target_perf, max_perf, threshold_payout, max_payout)
    stats = fit_stats(work[actual_col], current_pred, work[value_col])
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Historical Fit", f"{stats['r2_like']:.2f}")
    c2.metric("Value Alignment", f"{stats['corr_pred_value']:.2f}")
    c3.metric("Avg Modeled Payout", f"{stats['avg_pred']:.2f}x")
    c4.metric("Avg Error", f"{stats['mae']:.2f}")

    bt = work[[period_col, actual_col, value_col]].copy()
    bt["modeled_payout"] = current_pred
    bt["error"] = bt["modeled_payout"] - bt[actual_col]
    st.dataframe(bt, use_container_width=True)

    fig4 = go.Figure()
    fig4.add_trace(go.Scatter(x=bt[period_col], y=bt[actual_col], mode="lines+markers", name="Actual payout"))
    fig4.add_trace(go.Scatter(x=bt[period_col], y=bt["modeled_payout"], mode="lines+markers", name="Modeled payout"))
    fig4.update_layout(title="Actual vs. Modeled Payout", yaxis_title="Payout multiple", height=450)
    st.plotly_chart(fig4, use_container_width=True, key="current_backtest_chart")

with optimize_tab:
    st.subheader("Optimize Alternative Designs")
    st.caption("The optimizer tests practical metric combinations and ranks them using value alignment, historical fit, cost neutrality, payout stability, and simplicity.")
    if st.button("Run Optimization", type="primary"):
        results = optimize_plans(work, selected_metrics, directions, actual_col, value_col, threshold_perf, target_perf, max_perf, threshold_payout, max_payout, max_metrics=max_metrics, step=step)
        st.session_state["opt_results"] = results

    if "opt_results" in st.session_state:
        results = st.session_state["opt_results"]
        st.dataframe(results.head(25), use_container_width=True, hide_index=True)
        top = results.iloc[0]
        st.success(f"Top design: {top['metric_mix']}")
        fig5 = px.bar(results.head(15), x="plan_quality_score", y="metric_mix", orientation="h", title="Top Alternative Designs")
        st.plotly_chart(fig5, use_container_width=True, key="optimization_chart")
        st.download_button("Download optimization results", results.to_csv(index=False).encode("utf-8"), "optimization_results.csv", "text/csv")

with summary_tab:
    rows = []
    for m in selected_metrics:
        rows.append({"metric": m, "value_corr": safe_corr(work[m], work[value_col]), "payout_corr": safe_corr(work[m], work[actual_col])})
    corr_df = pd.DataFrame(rows)
    best_value = corr_df.sort_values("value_corr", ascending=False).iloc[0]
    best_payout = corr_df.sort_values("payout_corr", ascending=False).iloc[0]

    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Historical periods", len(work))
    s2.metric("Metrics tested", len(selected_metrics))
    s3.metric("Strongest value metric", str(best_value["metric"]))
    s4.metric("Strongest payout metric", str(best_payout["metric"]))

    st.subheader("Initial Read")
    if best_value["metric"] != best_payout["metric"]:
        st.warning(f"The metric most associated with shareholder value is **{best_value['metric']}**, while the metric most associated with actual payouts is **{best_payout['metric']}**. That difference may indicate an opportunity to revisit incentive design alignment.")
    else:
        st.success(f"The same metric, **{best_value['metric']}**, is most associated with both shareholder value and historical payouts. That suggests the plan may be directionally aligned, subject to further backtesting.")

    st.write("Use the tabs above to review diagnostics, enter the current plan, backtest historical payouts, and optimize alternative designs.")

with report_tab:
    rows = []
    for m in selected_metrics:
        rows.append({"metric": m, "value_corr": safe_corr(work[m], work[value_col]), "payout_corr": safe_corr(work[m], work[actual_col])})
    corr_df = pd.DataFrame(rows)
    best_value = corr_df.sort_values("value_corr", ascending=False).iloc[0]
    best_payout = corr_df.sort_values("payout_corr", ascending=False).iloc[0]

    text = f"Historical analysis indicates that {best_value['metric']} has had the strongest relationship with the selected shareholder value measure over the period reviewed. Historical payouts were most closely associated with {best_payout['metric']}. "
    if best_value["metric"] != best_payout["metric"]:
        text += "This suggests a potential disconnect between the outcomes most rewarded by the incentive plan and the outcomes most associated with shareholder value. The next step is to backtest the current plan design and compare it with alternative metric weightings that maintain comparable payout cost while improving alignment."
    else:
        text += "This suggests that historical payout outcomes have been directionally aligned with the company's value drivers. The next step is to test whether alternative weightings could improve alignment or reduce payout volatility without materially changing average payout cost."
    st.text_area("Draft committee takeaway", text, height=220)
    st.caption("Use as a starting point only. Consultant judgment, business strategy, goal rigor, market practice, and governance context should be incorporated before client use.")
