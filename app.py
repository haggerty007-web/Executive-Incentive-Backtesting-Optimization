import itertools
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Incentive Backtesting & Optimization", layout="wide")

st.title("Executive Incentive Backtesting & Optimization")
st.caption("Internal pilot | Decision-support tool, not a substitute for consultant judgment")

st.info("Upload historical incentive and performance data, backtest payout formulas, and identify alternative metric weightings that would have improved alignment with shareholder value while maintaining comparable payout cost.")

# -----------------------------
# Helpers
# -----------------------------
def sample_data():
    years = list(range(2010, 2025))
    return pd.DataFrame({
        "year": years,
        "revenue": [1000, 1035, 1070, 1125, 1180, 1160, 1215, 1280, 1350, 1425, 1380, 1470, 1535, 1600, 1685],
        "ebitda": [180, 188, 197, 214, 230, 215, 238, 260, 279, 300, 272, 315, 335, 350, 375],
        "gross_margin": [0.34, 0.345, 0.35, 0.36, 0.365, 0.355, 0.37, 0.382, 0.388, 0.395, 0.381, 0.40, 0.407, 0.411, 0.42],
        "eps": [2.10, 2.18, 2.30, 2.55, 2.80, 2.45, 2.95, 3.25, 3.55, 3.85, 3.20, 4.10, 4.35, 4.60, 4.95],
        "fcf": [80, 86, 90, 100, 115, 95, 120, 135, 148, 162, 125, 170, 185, 195, 215],
        "roic": [0.095, 0.098, 0.101, 0.108, 0.113, 0.102, 0.116, 0.122, 0.128, 0.133, 0.119, 0.138, 0.142, 0.145, 0.151],
        "tsr": [0.08, 0.04, 0.12, 0.18, 0.22, -0.10, 0.16, 0.24, 0.18, 0.20, -0.18, 0.28, 0.14, 0.11, 0.19],
        "actual_payout_pct": [0.95, 1.00, 1.08, 1.22, 1.40, 0.72, 1.24, 1.45, 1.52, 1.65, 0.58, 1.78, 1.55, 1.48, 1.72],
    })

def read_file(file):
    if file is None:
        return sample_data()
    if file.name.lower().endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)

def clean_columns(df):
    df = df.copy()
    df.columns = (df.columns.astype(str).str.strip().str.lower()
                  .str.replace(" ", "_").str.replace("-", "_").str.replace(".", "_"))
    return df

def numeric_columns(df):
    return [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

def safe_corr(a, b):
    a = pd.Series(a).astype(float)
    b = pd.Series(b).astype(float)
    if len(a.dropna()) < 3 or a.std() == 0 or b.std() == 0:
        return 0.0
    val = a.corr(b)
    return 0.0 if pd.isna(val) else float(val)

def payout_curve(score, threshold=0.90, target=1.00, maximum=1.20, threshold_payout=0.50, max_payout=2.00):
    if score < threshold:
        return 0.0
    if score < target:
        return threshold_payout + ((score - threshold) / (target - threshold)) * (1.0 - threshold_payout)
    if score < maximum:
        return 1.0 + ((score - target) / (maximum - target)) * (max_payout - 1.0)
    return max_payout

def calculate_formula_payout(df, metrics, weights, threshold, target, maximum, threshold_payout, max_payout):
    # Uses period-over-period growth as performance score. 1.00 means flat/target, >1 means growth.
    growth = df[metrics].pct_change().replace([np.inf, -np.inf], np.nan)
    scores = pd.Series(0.0, index=df.index)
    for m, w in weights.items():
        scores += (1 + growth[m]) * w
    payouts = scores.apply(lambda x: np.nan if pd.isna(x) else payout_curve(x, threshold, target, maximum, threshold_payout, max_payout))
    return scores, payouts

def generate_weight_sets(metrics, step=25, max_metrics=4):
    out = []
    for r in range(1, min(max_metrics, len(metrics)) + 1):
        for combo in itertools.combinations(metrics, r):
            if r == 1:
                out.append({combo[0]: 1.0})
            else:
                for weights in itertools.product(range(step, 101, step), repeat=r):
                    if sum(weights) == 100:
                        out.append(dict(zip(combo, [w / 100 for w in weights])))
    return out

def metrics_text(weights):
    return " / ".join([f"{int(w*100)}% {m}" for m, w in weights.items()])

def score_plan(pred, actual, value, target_avg, simplicity_penalty):
    aligned = pred.dropna().index.intersection(actual.dropna().index).intersection(value.dropna().index)
    if len(aligned) < 4:
        return None
    p = pred.loc[aligned]
    a = actual.loc[aligned]
    v = value.loc[aligned]
    fit = safe_corr(p, a) ** 2
    tsr_corr = safe_corr(p, v)
    avg = p.mean()
    vol = p.std()
    cost_neutral = max(0, 1 - abs(avg - target_avg) / max(target_avg, 0.01))
    stability = max(0, 1 - vol / max(target_avg, 0.01))
    quality = (fit * 35) + (max(tsr_corr, 0) * 35) + (cost_neutral * 15) + (stability * 10) + simplicity_penalty
    return fit, tsr_corr, avg, vol, quality

# -----------------------------
# Sidebar inputs
# -----------------------------
with st.sidebar:
    st.header("1. Upload Data")
    uploaded = st.file_uploader("CSV or Excel", type=["csv", "xlsx"])
    st.caption("Required: date/year, actual payout %, shareholder value measure, and performance metrics.")

    st.header("2. Payout Curve")
    threshold = st.number_input("Threshold performance", value=0.90, step=0.01)
    target = st.number_input("Target performance", value=1.00, step=0.01)
    maximum = st.number_input("Maximum performance", value=1.20, step=0.01)
    threshold_payout = st.number_input("Threshold payout", value=0.50, step=0.05)
    max_payout = st.number_input("Maximum payout", value=2.00, step=0.05)

    st.header("3. Optimization")
    step = st.selectbox("Weighting increment", [10, 20, 25, 33, 50], index=2)
    max_metrics = st.slider("Max metrics in a plan", 1, 5, 3)

# -----------------------------
# Main workflow
# -----------------------------
df = clean_columns(read_file(uploaded))
st.subheader("Data Preview")
st.dataframe(df, use_container_width=True)

num_cols = numeric_columns(df)
if len(num_cols) < 4:
    st.error("Upload a file with at least four numeric columns: actual payout, shareholder value, and two or more performance metrics.")
    st.stop()

st.subheader("Column Mapping")
c1, c2, c3 = st.columns(3)
with c1:
    date_col = st.selectbox("Date / year column", df.columns)
with c2:
    actual_payout_col = st.selectbox("Actual STI payout column", num_cols, index=num_cols.index("actual_payout_pct") if "actual_payout_pct" in num_cols else 0)
with c3:
    value_col = st.selectbox("Shareholder value measure", num_cols, index=num_cols.index("tsr") if "tsr" in num_cols else 0)

metric_options = [c for c in num_cols if c not in [actual_payout_col, value_col]]
selected_metrics = st.multiselect("Candidate incentive metrics", metric_options, default=metric_options[:min(5, len(metric_options))])

if not selected_metrics:
    st.warning("Select at least one candidate metric.")
    st.stop()

model = df.copy()
model[date_col] = pd.to_datetime(model[date_col], errors="coerce")
if model[date_col].isna().all():
    # Allow fiscal year integers
    model[date_col] = pd.to_datetime(df[date_col].astype(str), errors="coerce")
model = model.sort_values(date_col)
for c in [actual_payout_col, value_col] + selected_metrics:
    model[c] = pd.to_numeric(model[c], errors="coerce")
model = model[[date_col, actual_payout_col, value_col] + selected_metrics].dropna()

actual = model[actual_payout_col]
value = model[value_col]
actual_avg = actual.mean()

st.subheader("Historical Diagnostics")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Years / periods", len(model))
k2.metric("Avg actual payout", f"{actual_avg:.0%}")
k3.metric("Payout volatility", f"{actual.std():.0%}")
k4.metric("Actual payout / value corr.", f"{safe_corr(actual, value):.2f}")

corr_rows = []
for m in selected_metrics:
    corr_rows.append({
        "metric": m,
        "corr_to_actual_payout": round(safe_corr(model[m].pct_change(), actual), 2),
        "corr_to_shareholder_value": round(safe_corr(model[m].pct_change(), value), 2),
    })
corr_df = pd.DataFrame(corr_rows).sort_values("corr_to_shareholder_value", ascending=False)
st.dataframe(corr_df, use_container_width=True, hide_index=True)

fig = px.bar(corr_df, x="corr_to_shareholder_value", y="metric", orientation="h", title="Metric Relationship to Shareholder Value")
st.plotly_chart(fig, use_container_width=True, key="corr_chart")

st.subheader("Define Current Plan")
st.caption("Enter the current or proposed metric weights. The weights should total 100%.")
cols = st.columns(min(4, len(selected_metrics)))
current_weights = {}
for i, m in enumerate(selected_metrics):
    with cols[i % len(cols)]:
        current_weights[m] = st.number_input(f"{m} weight", min_value=0, max_value=100, value=0, step=5, key=f"w_{m}") / 100

weight_total = sum(current_weights.values())
if abs(weight_total - 1.0) > 0.001:
    st.warning(f"Current plan weights total {weight_total:.0%}. Enter weights totaling 100% to backtest the current plan.")
else:
    current_weights = {k: v for k, v in current_weights.items() if v > 0}
    scores, current_pred = calculate_formula_payout(model, list(current_weights.keys()), current_weights, threshold, target, maximum, threshold_payout, max_payout)
    fit, tsr_corr, avg, vol, quality = score_plan(current_pred, actual, value, actual_avg, 5)

    st.markdown("### Current Plan Backtest")
    b1, b2, b3, b4, b5 = st.columns(5)
    b1.metric("Model fit R²", f"{fit:.2f}")
    b2.metric("Pay / value corr.", f"{tsr_corr:.2f}")
    b3.metric("Avg modeled payout", f"{avg:.0%}")
    b4.metric("Modeled volatility", f"{vol:.0%}")
    b5.metric("Plan quality score", f"{quality:.0f}")

    compare = model[[date_col, actual_payout_col, value_col]].copy()
    compare["modeled_current_plan"] = current_pred
    compare = compare.dropna()
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=compare[date_col], y=compare[actual_payout_col], mode="lines+markers", name="Actual payout"))
    fig2.add_trace(go.Scatter(x=compare[date_col], y=compare["modeled_current_plan"], mode="lines+markers", name="Modeled current plan"))
    fig2.update_layout(title="Actual vs. Modeled Current Plan Payout", yaxis_tickformat=".0%")
    st.plotly_chart(fig2, use_container_width=True, key="current_backtest_chart")

st.subheader("Optimize Alternative Plans")
if st.button("Run Optimization"):
    results = []
    for weights in generate_weight_sets(selected_metrics, step=step, max_metrics=max_metrics):
        _, pred = calculate_formula_payout(model, list(weights.keys()), weights, threshold, target, maximum, threshold_payout, max_payout)
        simplicity = max(0, 5 - (len(weights) - 1) * 1.5)
        scored = score_plan(pred, actual, value, actual_avg, simplicity)
        if scored is None:
            continue
        fit, tsr_corr, avg, vol, quality = scored
        results.append({
            "metric_mix": metrics_text(weights),
            "plan_quality_score": round(quality, 1),
            "model_fit_r2": round(fit, 2),
            "pay_value_correlation": round(tsr_corr, 2),
            "average_payout": round(avg, 2),
            "payout_volatility": round(vol, 2),
            "metric_count": len(weights),
        })
    results = pd.DataFrame(results).sort_values("plan_quality_score", ascending=False)
    st.session_state["opt_results"] = results

if "opt_results" in st.session_state:
    results = st.session_state["opt_results"]
    st.dataframe(results.head(25), use_container_width=True, hide_index=True)
    top = results.iloc[0]
    st.success(f"Top historical design: {top['metric_mix']}")

    fig3 = px.bar(results.head(15), x="plan_quality_score", y="metric_mix", orientation="h", title="Top Alternative Plan Designs")
    st.plotly_chart(fig3, use_container_width=True, key="optimization_chart")

    st.subheader("Board-Style Summary")
    st.write(
        f"Historical backtesting suggests **{top['metric_mix']}** would have produced the strongest overall result among the tested designs. "
        f"This structure generated a pay/value correlation of **{top['pay_value_correlation']:.2f}**, average payout of **{top['average_payout']:.0%}**, "
        f"and payout volatility of **{top['payout_volatility']:.0%}**. Results should be reviewed alongside business strategy, goal-setting rigor, market practice, and governance considerations."
    )

    st.download_button("Download optimization results", results.to_csv(index=False).encode("utf-8"), "incentive_backtesting_optimization_results.csv", "text/csv")

st.subheader("Suggested Data Format")
st.code("year, revenue, ebitda, gross_margin, eps, fcf, roic, tsr, actual_payout_pct", language="text")
