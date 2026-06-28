import io
import itertools
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Executive Incentive Design Lab", layout="wide")

# -----------------------------
# Helpers
# -----------------------------
def clean_col(c):
    return str(c).strip().replace("\n", " ").replace("  ", " ")


def normalize_year_series(s: pd.Series) -> pd.Series:
    """Return a clean calendar/fiscal year from common Excel inputs.

    Handles:
    - 2024
    - "2024"
    - "FY2024"
    - "12/31/2024"
    - true Excel/Pandas date values

    Important: do NOT send a numeric year directly to pd.to_datetime first.
    Pandas can interpret 2024 as 2024 nanoseconds after 1970, which creates
    the 1970 bug you saw in the app.
    """
    raw = s.copy()
    as_text = raw.astype(str).str.strip()

    # First, extract a clear 4-digit year from strings such as FY2024 or 12/31/2024.
    extracted = as_text.str.extract(r"((?:19|20)\d{2})", expand=False)
    extracted_num = pd.to_numeric(extracted, errors="coerce")

    # Next, handle numeric year values such as 2024.
    numeric = pd.to_numeric(as_text.str.replace(",", "", regex=False), errors="coerce")
    numeric_year = numeric.where((numeric >= 1900) & (numeric <= 2100))

    # Finally, handle actual date values that did not contain an obvious 4-digit year.
    dt = pd.to_datetime(raw, errors="coerce")
    date_year = dt.dt.year.where((dt.dt.year >= 1900) & (dt.dt.year <= 2100))

    result = extracted_num.combine_first(numeric_year).combine_first(date_year)
    return result.astype("Int64")


def parse_pasted_table(text: str) -> pd.DataFrame:
    text = text.strip()
    if not text:
        return pd.DataFrame()
    # Excel copy/paste is usually tab-delimited. Fall back to comma if needed.
    sep = "\t" if "\t" in text else ","
    df = pd.read_csv(io.StringIO(text), sep=sep)
    df.columns = [clean_col(c) for c in df.columns]
    return df


def read_upload(file) -> pd.DataFrame:
    if file is None:
        return pd.DataFrame()
    if file.name.lower().endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
    df.columns = [clean_col(c) for c in df.columns]
    return df


def get_data_block(label: str, help_text: str, sample: pd.DataFrame) -> pd.DataFrame:
    st.subheader(label)
    st.caption(help_text)
    mode = st.radio(
        f"Input method for {label}",
        ["Paste from Excel", "Upload file", "Use sample"],
        horizontal=True,
        key=f"mode_{label}",
    )
    if mode == "Paste from Excel":
        text = st.text_area(
            f"Paste {label.lower()} here",
            height=180,
            key=f"paste_{label}",
            placeholder="Copy a range from Excel, including headers, then paste here.",
        )
        df = parse_pasted_table(text) if text.strip() else pd.DataFrame()
    elif mode == "Upload file":
        file = st.file_uploader(f"Upload {label.lower()}", type=["csv", "xlsx"], key=f"upload_{label}")
        df = read_upload(file)
    else:
        df = sample.copy()
    if not df.empty:
        st.success(f"Detected {len(df):,} rows and {len(df.columns):,} columns.")
        st.dataframe(df.head(10), use_container_width=True)
    return df


def numeric_candidate_cols(df: pd.DataFrame, exclude: List[str]) -> List[str]:
    cols = []
    for c in df.columns:
        if c in exclude:
            continue
        converted = pd.to_numeric(
            df[c].astype(str).str.replace("$", "", regex=False).str.replace(",", "", regex=False).str.replace("%", "", regex=False),
            errors="coerce",
        )
        if converted.notna().sum() >= max(3, int(len(df) * 0.5)):
            cols.append(c)
    return cols


def clean_numeric(series: pd.Series) -> pd.Series:
    raw = series.astype(str).str.strip()
    has_pct = raw.str.contains("%", regex=False).any()
    out = pd.to_numeric(
        raw.str.replace("$", "", regex=False).str.replace(",", "", regex=False).str.replace("%", "", regex=False),
        errors="coerce",
    )
    if has_pct:
        out = out / 100.0
    return out


def merge_by_year(perf: pd.DataFrame, payouts: pd.DataFrame, value: pd.DataFrame, perf_year: str, payout_year: str, payout_col: str, value_year: str, value_col: str, metrics: List[str]) -> pd.DataFrame:
    # Use a temporary normalized year column so we do not accidentally drop Year
    # when the selected source column is already named Year.
    p = perf[[perf_year] + metrics].copy()
    p["__Year__"] = normalize_year_series(p[perf_year])
    for c in metrics:
        p[c] = clean_numeric(p[c])
    p = p[["__Year__"] + metrics].rename(columns={"__Year__": "Year"})

    pay = payouts[[payout_year, payout_col]].copy()
    pay["__Year__"] = normalize_year_series(pay[payout_year])
    pay["Actual Payout"] = clean_numeric(pay[payout_col])
    pay = pay[["__Year__", "Actual Payout"]].rename(columns={"__Year__": "Year"})

    v = value[[value_year, value_col]].copy()
    v["__Year__"] = normalize_year_series(v[value_year])
    v["Shareholder Value"] = clean_numeric(v[value_col])
    v = v[["__Year__", "Shareholder Value"]].rename(columns={"__Year__": "Year"})

    p = p.dropna(subset=["Year"])
    pay = pay.dropna(subset=["Year"])
    v = v.dropna(subset=["Year"])

    p["Year"] = p["Year"].astype(int)
    pay["Year"] = pay["Year"].astype(int)
    v["Year"] = v["Year"].astype(int)

    merged = p.merge(pay, on="Year", how="inner").merge(v, on="Year", how="inner")
    return merged.sort_values("Year").dropna(subset=["Year"])


def safe_corr(a, b) -> float:
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    mask = x.notna() & y.notna()
    if mask.sum() < 3 or x[mask].std() == 0 or y[mask].std() == 0:
        return 0.0
    return float(np.corrcoef(x[mask], y[mask])[0, 1])


def metric_score(series: pd.Series, direction: str) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    change = s.pct_change().replace([np.inf, -np.inf], np.nan)
    if direction == "Lower is better":
        change = -change
    # target range will be treated as stability around history for now
    if direction == "Target range / stability":
        change = -abs((s - s.median()) / max(abs(s.median()), 1e-9))
    return change


def payout_curve(score: float, threshold: float, target: float, maximum: float, threshold_payout: float, maximum_payout: float) -> float:
    if pd.isna(score):
        return np.nan
    if score < threshold:
        return 0.0
    if score < target:
        return threshold_payout + ((score - threshold) / (target - threshold)) * (1.0 - threshold_payout)
    if score < maximum:
        return 1.0 + ((score - target) / (maximum - target)) * (maximum_payout - 1.0)
    return maximum_payout


def generate_weight_sets(metrics: List[str], step: int, max_metrics: int) -> List[Dict[str, float]]:
    values = list(range(step, 101, step))
    out = []
    for r in range(1, min(max_metrics, len(metrics)) + 1):
        for combo in itertools.combinations(metrics, r):
            if r == 1:
                out.append({combo[0]: 1.0})
            else:
                for weights in itertools.product(values, repeat=r):
                    if sum(weights) == 100:
                        out.append({m: w / 100 for m, w in zip(combo, weights)})
    return out


def modeled_payout(df: pd.DataFrame, weights: Dict[str, float], directions: Dict[str, str], threshold: float, target: float, maximum: float, threshold_payout: float, maximum_payout: float) -> pd.Series:
    parts = []
    for m, w in weights.items():
        parts.append((1 + metric_score(df[m], directions.get(m, "Higher is better"))) * w)
    perf_score = sum(parts)
    return perf_score.apply(lambda x: payout_curve(x, threshold, target, maximum, threshold_payout, maximum_payout))


def evaluate_plan(df: pd.DataFrame, weights: Dict[str, float], directions: Dict[str, str], threshold: float, target: float, maximum: float, threshold_payout: float, maximum_payout: float) -> Dict[str, float]:
    pred = modeled_payout(df, weights, directions, threshold, target, maximum, threshold_payout, maximum_payout)
    actual = df["Actual Payout"]
    value = df["Shareholder Value"]
    mask = pred.notna() & actual.notna() & value.notna()
    if mask.sum() < 3:
        return {"fit_corr": 0, "value_corr": 0, "avg_payout": 0, "volatility": 0, "avg_error": 0, "score": 0}
    fit_corr = safe_corr(pred[mask], actual[mask])
    value_corr = safe_corr(pred[mask], value[mask])
    avg_payout = float(pred[mask].mean())
    volatility = float(pred[mask].std())
    avg_error = float((pred[mask] - actual[mask]).abs().mean())
    cost_score = max(0, 1 - abs(avg_payout - actual[mask].mean()) / max(actual[mask].mean(), 0.01))
    stability_score = max(0, 1 - volatility / max(actual[mask].std(), 0.01)) if actual[mask].std() > 0 else 0
    score = max(fit_corr, 0) * 30 + max(value_corr, 0) * 40 + cost_score * 20 + stability_score * 10
    return {
        "fit_corr": round(fit_corr, 2),
        "value_corr": round(value_corr, 2),
        "avg_payout": round(avg_payout, 2),
        "volatility": round(volatility, 2),
        "avg_error": round(avg_error, 2),
        "score": round(score, 1),
    }


# -----------------------------
# Sample data
# -----------------------------
years = list(range(2011, 2025))
sample_perf = pd.DataFrame({
    "Year": years,
    "Adjusted EBITDA": [188,197,214,230,215,238,260,282,302,315,345,390,420,400],
    "Cash Flow Before Debt Reduction": [86,90,100,115,95,120,132,148,165,162,175,210,225,190],
    "Revenue": [1035,1070,1125,1180,1160,1215,1280,1350,1425,1480,1560,1660,1740,1700],
    "ROIC": [0.098,0.101,0.108,0.113,0.102,0.116,0.123,0.130,0.138,0.135,0.145,0.152,0.160,0.150],
})
sample_payout = pd.DataFrame({"Year": years, "Actual Payout": [0.95,1.05,1.20,1.35,0.70,1.25,1.45,1.60,1.55,1.00,0.64,2.00,1.53,0.26]})
sample_value = pd.DataFrame({"Year": years, "TSR": [0.04,0.12,0.18,0.22,-0.10,0.16,0.20,0.24,0.18,0.04,0.16,0.11,0.13,-0.08]})

# -----------------------------
# App
# -----------------------------
st.title("Executive Incentive Design Lab")
st.caption("Backtest. Optimize. Validate. | Internal pilot")
st.info("Paste directly from Excel or upload files. The app merges performance, payout, and shareholder value data by year.")

with st.expander("Download / copy template format", expanded=False):
    st.write("Performance data can contain any company-specific metrics. Payout and shareholder value data only need Year plus one value column.")
    st.dataframe(sample_perf.head(), use_container_width=True)
    st.dataframe(sample_payout.head(), use_container_width=True)
    st.dataframe(sample_value.head(), use_container_width=True)

st.header("1. Import Data")
colA, colB, colC = st.columns(3)
with colA:
    perf_df = get_data_block("Performance Data", "Use adjusted management metrics from FP&A or comp plan workbooks.", sample_perf)
with colB:
    payout_df = get_data_block("Payout History", "Use actual incentive payouts as a percent of target. Example: 1.25 = 125%.", sample_payout)
with colC:
    value_df = get_data_block("Shareholder Value", "Use TSR, stock price return, market cap growth, or other selected outcome measure.", sample_value)

if perf_df.empty or payout_df.empty or value_df.empty:
    st.warning("Import all three datasets to continue. You can paste from Excel, upload files, or use the samples.")
    st.stop()

st.header("2. Map Columns")
map1, map2, map3 = st.columns(3)
with map1:
    perf_year = st.selectbox("Performance year column", perf_df.columns, key="perf_year")
    metric_cols = numeric_candidate_cols(perf_df, [perf_year])
    selected_metrics = st.multiselect("Candidate performance metrics", metric_cols, default=metric_cols[: min(6, len(metric_cols))])
with map2:
    payout_year = st.selectbox("Payout year column", payout_df.columns, key="payout_year")
    payout_candidates = numeric_candidate_cols(payout_df, [payout_year])
    payout_col = st.selectbox("Actual payout column", payout_candidates or payout_df.columns, key="payout_col")
with map3:
    value_year = st.selectbox("Shareholder value year column", value_df.columns, key="value_year")
    value_candidates = numeric_candidate_cols(value_df, [value_year])
    value_col = st.selectbox("Shareholder value column", value_candidates or value_df.columns, key="value_col")

if not selected_metrics:
    st.error("Select at least one performance metric.")
    st.stop()

st.header("3. Define Metric Behavior")
directions = {}
cols = st.columns(3)
for i, m in enumerate(selected_metrics):
    with cols[i % 3]:
        directions[m] = st.selectbox(m, ["Higher is better", "Lower is better", "Target range / stability"], key=f"dir_{m}")

try:
    merged = merge_by_year(perf_df, payout_df, value_df, perf_year, payout_year, payout_col, value_year, value_col, selected_metrics)
except Exception as exc:
    st.error(f"Could not merge the data: {exc}")
    st.stop()

st.header("4. Merged Modeling Dataset")
st.dataframe(merged, use_container_width=True)
if len(merged) < 5:
    st.warning("Fewer than 5 matched years were found. Results may not be reliable.")

# Diagnostics
st.header("5. Historical Diagnostics")
diag_rows = []
for m in selected_metrics:
    metric_perf = metric_score(merged[m], directions[m])
    diag_rows.append({
        "Metric": m,
        "Correlation to Payout": round(safe_corr(metric_perf, merged["Actual Payout"]), 2),
        "Correlation to Shareholder Value": round(safe_corr(metric_perf, merged["Shareholder Value"]), 2),
    })
diag = pd.DataFrame(diag_rows).sort_values("Correlation to Shareholder Value", ascending=False)
st.dataframe(diag, use_container_width=True)
fig = px.bar(diag, x="Correlation to Shareholder Value", y="Metric", orientation="h", title="Which metrics were most associated with shareholder value?")
st.plotly_chart(fig, use_container_width=True, key="diag_value_chart")

# Plan inputs
st.header("6. Current Plan Backtest")
st.caption("Enter the current or proposed plan weights. Leave weights at 0% for metrics that are not in the plan.")
threshold = st.number_input("Threshold performance", value=0.90, step=0.05)
target = st.number_input("Target performance", value=1.00, step=0.05)
maximum = st.number_input("Maximum performance", value=1.20, step=0.05)
threshold_payout = st.number_input("Threshold payout", value=0.50, step=0.05)
maximum_payout = st.number_input("Maximum payout", value=2.00, step=0.05)

weights = {}
wcols = st.columns(3)
for i, m in enumerate(selected_metrics):
    with wcols[i % 3]:
        weights[m] = st.slider(f"Weight: {m}", 0, 100, 0, 5) / 100

weight_sum = sum(weights.values())
if weight_sum == 0:
    # default to equal weights for convenience
    equal = 1 / len(selected_metrics)
    current_weights = {m: equal for m in selected_metrics}
    st.info("No plan weights entered yet. Using equal weights for preview.")
elif abs(weight_sum - 1) > 0.001:
    current_weights = {m: w / weight_sum for m, w in weights.items() if w > 0}
    st.warning(f"Weights total {weight_sum:.0%}; the app normalized them to 100% for modeling.")
else:
    current_weights = {m: w for m, w in weights.items() if w > 0}

current_stats = evaluate_plan(merged, current_weights, directions, threshold, target, maximum, threshold_payout, maximum_payout)
pred = modeled_payout(merged, current_weights, directions, threshold, target, maximum, threshold_payout, maximum_payout)
compare = merged[["Year", "Actual Payout", "Shareholder Value"]].copy()
compare["Modeled Payout"] = pred
compare["Error"] = compare["Modeled Payout"] - compare["Actual Payout"]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Payout Fit", current_stats["fit_corr"])
c2.metric("Value Alignment", current_stats["value_corr"])
c3.metric("Avg Payout", f"{current_stats['avg_payout']:.0%}")
c4.metric("Avg Error", f"{current_stats['avg_error']:.0%}")
st.dataframe(compare, use_container_width=True)
fig2 = px.line(compare, x="Year", y=["Actual Payout", "Modeled Payout"], markers=True, title="Actual vs. Modeled Payout")
st.plotly_chart(fig2, use_container_width=True, key="actual_vs_modeled_chart")

# Optimization
st.header("7. Optimization")
colx, coly = st.columns(2)
with colx:
    max_metrics = st.slider("Maximum metrics per plan", 1, min(5, len(selected_metrics)), min(3, len(selected_metrics)))
with coly:
    step = st.selectbox("Weighting increment", [10, 20, 25, 50], index=2)

if st.button("Run Optimization"):
    plans = []
    for wset in generate_weight_sets(selected_metrics, step, max_metrics):
        stats = evaluate_plan(merged, wset, directions, threshold, target, maximum, threshold_payout, maximum_payout)
        stats["Metric Mix"] = " / ".join([f"{int(v*100)}% {k}" for k, v in wset.items()])
        plans.append(stats)
    opt = pd.DataFrame(plans).sort_values("score", ascending=False)
    st.subheader("Top Alternative Designs")
    st.dataframe(opt.head(25), use_container_width=True)
    best = opt.iloc[0]
    st.success(f"Top design: {best['Metric Mix']}")

    st.subheader("8. Draft Consultant Takeaway")
    strongest_value = diag.iloc[0]["Metric"]
    strongest_payout = diag.sort_values("Correlation to Payout", ascending=False).iloc[0]["Metric"]
    if strongest_value == strongest_payout:
        msg = f"Historical analysis indicates {strongest_value} was the strongest tested metric for both shareholder value alignment and historical payout behavior. This suggests the plan direction is broadly aligned, subject to further review of goal rigor, payout curves, and business context."
    else:
        msg = f"Historical analysis indicates shareholder value was most closely associated with {strongest_value}, while actual payouts were more closely associated with {strongest_payout}. This may indicate an opportunity to revisit metric weighting or plan design to strengthen alignment with shareholder value creation."
    st.write(msg)
