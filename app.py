import io
import itertools
from typing import Dict, List

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Executive Incentive Design Lab", layout="wide")

# -----------------------------
# Utilities
# -----------------------------
def clean_col(c):
    return str(c).strip().replace("\n", " ").replace("  ", " ")


def normalize_year_series(s: pd.Series) -> pd.Series:
    raw = s.copy()
    txt = raw.astype(str).str.strip()
    extracted = txt.str.extract(r"((?:19|20)\d{2})", expand=False)
    extracted_num = pd.to_numeric(extracted, errors="coerce")
    numeric = pd.to_numeric(txt.str.replace(",", "", regex=False), errors="coerce")
    numeric_year = numeric.where((numeric >= 1900) & (numeric <= 2100))
    dt = pd.to_datetime(raw, errors="coerce")
    date_year = dt.dt.year.where((dt.dt.year >= 1900) & (dt.dt.year <= 2100))
    return extracted_num.combine_first(numeric_year).combine_first(date_year).astype("Int64")


def parse_pasted_table(text: str) -> pd.DataFrame:
    text = text.strip()
    if not text:
        return pd.DataFrame()
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
            height=160,
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
        st.dataframe(df.head(8), use_container_width=True)
    return df


def clean_numeric(series: pd.Series) -> pd.Series:
    raw = series.astype(str).str.strip()
    has_pct = raw.str.contains("%", regex=False).any()
    out = pd.to_numeric(
        raw.str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("x", "", regex=False),
        errors="coerce",
    )
    if has_pct:
        out = out / 100.0
    return out


def numeric_candidate_cols(df: pd.DataFrame, exclude: List[str]) -> List[str]:
    cols = []
    for c in df.columns:
        if c in exclude:
            continue
        converted = clean_numeric(df[c])
        if converted.notna().sum() >= max(3, int(len(df) * 0.5)):
            cols.append(c)
    return cols



def normalize_metric_name(x: str) -> str:
    return str(x).strip().lower().replace("_", " ").replace("-", " ").replace("  ", " ")


def build_metric_library(library_df: pd.DataFrame, metric_col: str, category_col: str | None = None, emphasis_col: str | None = None) -> Dict[str, Dict[str, float | str]]:
    """Create lookup from metric label to category and management emphasis score."""
    if library_df is None or library_df.empty or metric_col is None:
        return {}
    lib = library_df.copy()
    lib[metric_col] = lib[metric_col].astype(str).str.strip()
    if emphasis_col and emphasis_col in lib.columns:
        raw = clean_numeric(lib[emphasis_col])
        if raw.notna().sum() > 0:
            mn, mx = raw.min(), raw.max()
            if mx != mn:
                score = 40 + (raw - mn) / (mx - mn) * 60
            else:
                score = pd.Series(80, index=raw.index)
        else:
            score = pd.Series(80, index=lib.index)
    else:
        score = pd.Series(80, index=lib.index)
    lookup = {}
    for i, row in lib.iterrows():
        metric = str(row[metric_col]).strip()
        if not metric or metric.lower() == "nan":
            continue
        category = "Management priority"
        if category_col and category_col in lib.columns and pd.notna(row[category_col]):
            category = str(row[category_col]).strip() or "Management priority"
        lookup[normalize_metric_name(metric)] = {
            "display_metric": metric,
            "category": category,
            "management_priority_score": float(score.loc[i]) if pd.notna(score.loc[i]) else 80.0,
        }
    return lookup


def match_metric_library(metric_candidates: List[str], metric_lookup: Dict[str, Dict[str, float | str]]) -> List[str]:
    """Return performance columns that appear in the management metric library."""
    if not metric_lookup:
        return []
    return [m for m in metric_candidates if normalize_metric_name(m) in metric_lookup]

def safe_corr(a, b) -> float:
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    mask = x.notna() & y.notna()
    if mask.sum() < 3 or x[mask].std() == 0 or y[mask].std() == 0:
        return 0.0
    return float(np.corrcoef(x[mask], y[mask])[0, 1])


def metric_signal(series: pd.Series, direction: str) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    change = s.pct_change().replace([np.inf, -np.inf], np.nan)
    if direction == "Lower is better":
        change = -change
    elif direction == "Target range / stability":
        median = s.median()
        denom = max(abs(median), 1e-9)
        change = -abs((s - median) / denom)
    return change


def merge_data(perf, payouts, value, perf_year, payout_year, payout_col, value_year, value_col, metrics):
    p = perf[[perf_year] + metrics].copy()
    p["Year"] = normalize_year_series(p[perf_year])
    for c in metrics:
        p[c] = clean_numeric(p[c])
    p = p[["Year"] + metrics]

    pay = payouts[[payout_year, payout_col]].copy()
    pay["Year"] = normalize_year_series(pay[payout_year])
    pay["Actual Payout"] = clean_numeric(pay[payout_col])
    pay = pay[["Year", "Actual Payout"]]

    v = value[[value_year, value_col]].copy()
    v["Year"] = normalize_year_series(v[value_year])
    v["Shareholder Value"] = clean_numeric(v[value_col])
    v = v[["Year", "Shareholder Value"]]

    for d in [p, pay, v]:
        d.dropna(subset=["Year"], inplace=True)
        d["Year"] = d["Year"].astype(int)

    merged = p.merge(pay, on="Year", how="inner").merge(v, on="Year", how="inner")
    return merged.sort_values("Year").reset_index(drop=True)


def percentile_score(x: float) -> float:
    # Convert correlation-like values to 0-100, preserving positive evidence.
    return max(0.0, min(100.0, (x + 1) * 50))


def build_metric_evidence(df, metrics, directions, metric_lookup=None):
    rows = []
    metric_lookup = metric_lookup or {}
    payout_std = df["Actual Payout"].std()
    for m in metrics:
        sig = metric_signal(df[m], directions[m])
        value_corr = safe_corr(sig, df["Shareholder Value"])
        payout_corr = safe_corr(sig, df["Actual Payout"])
        metric_vol = sig.std(skipna=True)
        stability = 100 if pd.isna(metric_vol) else max(0, 100 - min(metric_vol, 1.0) * 100)
        value_score = percentile_score(value_corr)
        payout_score = percentile_score(payout_corr)
        lib = metric_lookup.get(normalize_metric_name(m), {})
        category = lib.get("category", "Uncategorized")
        priority_score = float(lib.get("management_priority_score", 50.0))
        # Value alignment gets more weight than payout alignment. Management priority is a supplement, not the main driver.
        overall = value_score * 0.45 + payout_score * 0.20 + stability * 0.15 + priority_score * 0.10 + 10
        gap = payout_corr - value_corr
        rows.append({
            "Metric": m,
            "Category": category,
            "Management Priority Score": round(priority_score, 0),
            "Value Creation Corr.": round(value_corr, 2),
            "Payout Influence Corr.": round(payout_corr, 2),
            "Alignment Gap": round(gap, 2),
            "Stability Score": round(stability, 0),
            "Metric Strength Score": round(min(overall, 100), 1),
            "Direction": directions[m],
        })
    return pd.DataFrame(rows).sort_values("Metric Strength Score", ascending=False)


def payout_curve(score, threshold=0.90, target=1.00, maximum=1.20, threshold_payout=0.50, max_payout=2.00):
    if pd.isna(score):
        return np.nan
    if score < threshold:
        return 0.0
    if score < target:
        return threshold_payout + ((score - threshold) / max(target - threshold, 1e-9)) * (1.0 - threshold_payout)
    if score < maximum:
        return 1.0 + ((score - target) / max(maximum - target, 1e-9)) * (max_payout - 1.0)
    return max_payout


def modeled_payout(df, weights, directions, threshold, target, maximum, threshold_payout, max_payout):
    score = pd.Series(0.0, index=df.index)
    for m, w in weights.items():
        score += (1 + metric_signal(df[m], directions[m])) * w
    return score.apply(lambda x: payout_curve(x, threshold, target, maximum, threshold_payout, max_payout))


def evaluate_plan(df, weights, directions, threshold, target, maximum, threshold_payout, max_payout):
    pred = modeled_payout(df, weights, directions, threshold, target, maximum, threshold_payout, max_payout)
    mask = pred.notna() & df["Actual Payout"].notna() & df["Shareholder Value"].notna()
    if mask.sum() < 3:
        return None
    actual = df.loc[mask, "Actual Payout"]
    value = df.loc[mask, "Shareholder Value"]
    pred = pred[mask]
    fit = safe_corr(pred, actual)
    value_corr = safe_corr(pred, value)
    avg_payout = pred.mean()
    vol = pred.std()
    avg_error = (pred - actual).abs().mean()
    cost_neutrality = max(0, 1 - abs(avg_payout - actual.mean()) / max(abs(actual.mean()), 0.01))
    stability = max(0, 1 - vol / max(actual.std(), 0.01)) if actual.std() > 0 else 0
    quality = max(value_corr, 0) * 45 + max(fit, 0) * 20 + cost_neutrality * 20 + stability * 15
    return {
        "Plan Quality Score": round(quality, 1),
        "Value Alignment": round(value_corr, 2),
        "Payout Fit": round(fit, 2),
        "Avg Payout": round(avg_payout, 2),
        "Volatility": round(vol, 2),
        "Avg Error": round(avg_error, 2),
    }


def generate_weight_sets(metrics, step=25, max_metrics=3):
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


def bar_stars(score):
    stars = int(round(score / 20))
    return "★" * stars + "☆" * (5 - stars)


# -----------------------------
# Samples
# -----------------------------
years = list(range(2016, 2026))
sample_perf = pd.DataFrame({
    "Year": years,
    "Adjusted EBITDA": [737, 707, 920, 978, 913, 1042, 1600, 1870, 1683, 228],
    "Cash Flow Before Debt Reduction": [232, 291, -40, 439, 63, -99, 467, 304, 69, -153],
    "Revenue": [4298, 4406, 6029, 6160, 6560, 7156, 9440, 9428, 8807, 2156],
    "Gross Margin": [0.19, 0.16, 0.16, 0.18, 0.17, 0.15, 0.19, 0.23, 0.23, 0.14],
    "ROIC": [0.0529, 0.0610, 0.0248, 0.0175, 0.0115, 0.0164, 0.0551, 0.0747, 0.0635, -0.0329],
})
sample_payout = pd.DataFrame({"Year": years, "Actual Payout": [0.55, 0.50, 1.00, 1.50, 1.00, 0.64, 2.00, 1.53, 0.26, 0.00]})
sample_value = pd.DataFrame({"Year": years, "Stock Price Return": [0.12, 0.27, -0.30, 0.60, 0.04, 0.17, 0.16, 0.13, 0.12, -0.43]})
sample_library = pd.DataFrame({
    "Metric": ["Adjusted EBITDA", "Cash Flow Before Debt Reduction", "Revenue", "Gross Margin", "ROIC"],
    "Category": ["Profitability", "Cash Flow", "Growth", "Profitability", "Returns"],
    "Management Emphasis": [95, 90, 75, 65, 70],
})

# -----------------------------
# App
# -----------------------------
st.title("Executive Incentive Design Lab")
st.caption("Company DNA. Incentive DNA. Alignment Gap. Design Lab. | Internal pilot")
st.info("This version focuses on the evidence layer: which metrics appear most linked to shareholder value, which metrics drove payouts, and what alternative weighting would have tested better historically.")

st.header("1. Import Data")
st.caption("Use the first three sections for the core analysis. The fourth section is optional and helps identify management-priority metrics from investor materials, proxy disclosure, or consultant-selected candidate metrics.")
col1, col2 = st.columns(2)
with col1:
    perf_df = get_data_block("Performance Data", "Management / FP&A metrics or Capital IQ fields. Use actual incentive-plan definitions where available.", sample_perf)
with col2:
    payout_df = get_data_block("Payout History", "Historical payouts as a percent of target. Use 1.25 or 125% for 125%.", sample_payout)
col3, col4 = st.columns(2)
with col3:
    value_df = get_data_block("Shareholder Value", "TSR, stock price return, market cap growth, or another selected outcome.", sample_value)
with col4:
    library_df = get_data_block("Management Priority Metrics", "Optional. Paste metrics emphasized in investor materials, proxy disclosure, or selected by the consultant. Columns can include Metric, Category, and Management Emphasis.", sample_library)

if perf_df.empty or payout_df.empty or value_df.empty:
    st.warning("Import Performance Data, Payout History, and Shareholder Value to continue. The Management Priority Metrics section is optional.")
    st.stop()

st.header("2. Map Data")
map1, map2, map3 = st.columns(3)
with map1:
    perf_year = st.selectbox("Performance year column", perf_df.columns, key="perf_year")
    metric_candidates = numeric_candidate_cols(perf_df, [perf_year])
with map2:
    payout_year = st.selectbox("Payout year column", payout_df.columns, key="payout_year")
    payout_candidates = numeric_candidate_cols(payout_df, [payout_year])
    payout_col = st.selectbox("Actual payout column", payout_candidates or list(payout_df.columns), key="payout_col")
with map3:
    value_year = st.selectbox("Shareholder value year column", value_df.columns, key="value_year")
    value_candidates = numeric_candidate_cols(value_df, [value_year])
    value_col = st.selectbox("Shareholder value column", value_candidates or list(value_df.columns), key="value_col")

st.subheader("Management Priority Metrics Mapping (Optional)")
metric_lookup = {}
matched_priority_metrics = []
if not library_df.empty:
    l1, l2, l3 = st.columns(3)
    with l1:
        lib_metric_col = st.selectbox("Metric name column", library_df.columns, key="lib_metric_col")
    with l2:
        category_options = ["None"] + list(library_df.columns)
        lib_category_col = st.selectbox("Category column", category_options, index=category_options.index("Category") if "Category" in category_options else 0, key="lib_category_col")
    with l3:
        emphasis_options = ["None"] + list(library_df.columns)
        default_emphasis = "Management Emphasis" if "Management Emphasis" in emphasis_options else "None"
        lib_emphasis_col = st.selectbox("Management emphasis / mention count column", emphasis_options, index=emphasis_options.index(default_emphasis), key="lib_emphasis_col")
    metric_lookup = build_metric_library(
        library_df,
        lib_metric_col,
        None if lib_category_col == "None" else lib_category_col,
        None if lib_emphasis_col == "None" else lib_emphasis_col,
    )
    matched_priority_metrics = match_metric_library(metric_candidates, metric_lookup)
    st.caption(f"Matched {len(matched_priority_metrics)} management-priority metrics to the performance data. Matching is currently based on exact metric names after basic cleanup.")

default_metrics = matched_priority_metrics[:20] if matched_priority_metrics else metric_candidates[: min(8, len(metric_candidates))]
selected_metrics = st.multiselect(
    "Candidate metrics to analyze (select up to 20)",
    metric_candidates,
    default=default_metrics,
    help="Use consultant judgment to pick the metrics that are plausible incentive-plan candidates for this company or industry.",
)
if len(selected_metrics) > 20:
    st.error("Please select no more than 20 candidate metrics. This keeps the diagnostics focused and easier to explain.")
    st.stop()
if not selected_metrics:
    st.error("Select at least one performance metric.")
    st.stop()

st.header("3. Metric Behavior")
directions = {}
cols = st.columns(3)
for i, m in enumerate(selected_metrics):
    with cols[i % 3]:
        directions[m] = st.selectbox(m, ["Higher is better", "Lower is better", "Target range / stability"], key=f"dir_{m}")

try:
    merged = merge_data(perf_df, payout_df, value_df, perf_year, payout_year, payout_col, value_year, value_col, selected_metrics)
except Exception as exc:
    st.error(f"Could not merge the data: {exc}")
    st.stop()

st.header("4. Modeling Dataset")
st.dataframe(merged, use_container_width=True)
if len(merged) < 8:
    st.warning("Small sample size. Use results directionally. Annual incentive history often has limited observations, so consultant judgment remains important.")

# Diagnostics
st.header("5. Historical Diagnostics")
evidence = build_metric_evidence(merged, selected_metrics, directions, metric_lookup)

m1, m2, m3 = st.columns(3)
strong_value = evidence.sort_values("Value Creation Corr.", ascending=False).iloc[0]
strong_payout = evidence.sort_values("Payout Influence Corr.", ascending=False).iloc[0]
strong_metric = evidence.iloc[0]
m1.metric("Company DNA", strong_value["Metric"], f"Value corr. {strong_value['Value Creation Corr.']}")
m2.metric("Incentive DNA", strong_payout["Metric"], f"Payout corr. {strong_payout['Payout Influence Corr.']}")
m3.metric("Top Metric Score", strong_metric["Metric"], f"{strong_metric['Metric Strength Score']}/100")

st.subheader("Metric Evidence Scorecard")
scorecard = evidence.copy()
scorecard["Value Creation"] = scorecard["Value Creation Corr."].apply(lambda x: bar_stars(percentile_score(x)))
scorecard["Payout Influence"] = scorecard["Payout Influence Corr."].apply(lambda x: bar_stars(percentile_score(x)))
st.dataframe(scorecard[["Metric", "Category", "Management Priority Score", "Value Creation Corr.", "Value Creation", "Payout Influence Corr.", "Payout Influence", "Alignment Gap", "Stability Score", "Metric Strength Score", "Direction"]], use_container_width=True)

if "Management Priority Score" in evidence.columns:
    with st.expander("Management Priority Metrics", expanded=False):
        st.write("This section reflects the optional metric library. Use it to compare what management emphasizes with what historically aligned with shareholder value and payouts.")
        st.dataframe(evidence[["Metric", "Category", "Management Priority Score", "Value Creation Corr.", "Payout Influence Corr.", "Metric Strength Score"]].sort_values("Management Priority Score", ascending=False), use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    figv = px.bar(evidence.sort_values("Value Creation Corr."), x="Value Creation Corr.", y="Metric", orientation="h", title=f"Metrics Most Associated with {value_col}")
    st.plotly_chart(figv, use_container_width=True, key="value_corr_chart")
with c2:
    figp = px.bar(evidence.sort_values("Payout Influence Corr."), x="Payout Influence Corr.", y="Metric", orientation="h", title="Metrics Most Associated with Actual Payouts")
    st.plotly_chart(figp, use_container_width=True, key="payout_corr_chart")

st.subheader("Alignment Gap")
gap = evidence.copy().sort_values("Alignment Gap", ascending=False)
figg = go.Figure()
figg.add_trace(go.Bar(name="Value Creation", x=gap["Metric"], y=gap["Value Creation Corr."]))
figg.add_trace(go.Bar(name="Payout Influence", x=gap["Metric"], y=gap["Payout Influence Corr."]))
figg.update_layout(barmode="group", title="What Investors Rewarded vs. What the Plan Rewarded", yaxis_title="Correlation", height=420)
st.plotly_chart(figg, use_container_width=True, key="alignment_gap_chart")

if strong_value["Metric"] != strong_payout["Metric"]:
    st.warning(f"Initial insight: {strong_value['Metric']} appears most associated with shareholder value, while {strong_payout['Metric']} appears most associated with actual payouts. That gap is worth discussing before optimizing plan design.")
else:
    st.success(f"Initial insight: {strong_value['Metric']} appears to be important for both shareholder value and payout outcomes.")

# Metric cards
st.header("6. Metric Cards")
metric_choice = st.selectbox("Select metric card", evidence["Metric"].tolist())
row = evidence[evidence["Metric"] == metric_choice].iloc[0]
k1, k2, k3, k4 = st.columns(4)
k1.metric("Value Creation", row["Value Creation Corr."])
k2.metric("Payout Influence", row["Payout Influence Corr."])
k3.metric("Alignment Gap", row["Alignment Gap"])
k4.metric("Metric Strength", f"{row['Metric Strength Score']}/100")
if row["Value Creation Corr."] > 0.5:
    st.write(f"**Consultant note:** {metric_choice} has shown a relatively strong historical relationship with the selected shareholder value measure.")
elif row["Value Creation Corr."] > 0.2:
    st.write(f"**Consultant note:** {metric_choice} has shown a moderate relationship with shareholder value. Consider it alongside strategy, controllability, and goal-setting quality.")
else:
    st.write(f"**Consultant note:** {metric_choice} has not shown a strong historical relationship with the selected shareholder value measure in this dataset.")

# Current plan and alternative design lab
st.header("7. Current Plan vs. Alternative Design Lab")
st.caption("Use this to compare a current/proposed plan against alternative metric mixes. This is still a historical test, not a definitive recommendation.")

with st.expander("Payout curve assumptions", expanded=False):
    a, b, c, d, e = st.columns(5)
    with a:
        threshold = st.number_input("Threshold performance", value=0.90, step=0.05)
    with b:
        target = st.number_input("Target performance", value=1.00, step=0.05)
    with c:
        maximum = st.number_input("Maximum performance", value=1.20, step=0.05)
    with d:
        threshold_payout = st.number_input("Threshold payout", value=0.50, step=0.05)
    with e:
        max_payout = st.number_input("Maximum payout", value=2.00, step=0.05)

st.subheader("Current / Proposed Plan Weights")
weights = {}
wcols = st.columns(3)
for i, m in enumerate(selected_metrics):
    with wcols[i % 3]:
        weights[m] = st.slider(f"Weight: {m}", 0, 100, 0, 5, key=f"weight_{m}") / 100

if sum(weights.values()) == 0:
    active_weights = {m: 1 / len(selected_metrics) for m in selected_metrics}
    st.info("No weights entered yet. Using equal weights as a preview.")
elif abs(sum(weights.values()) - 1.0) > 0.001:
    active_weights = {m: w / sum(weights.values()) for m, w in weights.items() if w > 0}
    st.warning("Weights do not total 100%. The app normalized active weights for modeling.")
else:
    active_weights = {m: w for m, w in weights.items() if w > 0}

current_stats = evaluate_plan(merged, active_weights, directions, threshold, target, maximum, threshold_payout, max_payout)
if current_stats:
    curr_pred = modeled_payout(merged, active_weights, directions, threshold, target, maximum, threshold_payout, max_payout)
    compare = merged[["Year", "Actual Payout", "Shareholder Value"]].copy()
    compare["Modeled Current Plan"] = curr_pred
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Current Plan Quality", current_stats["Plan Quality Score"])
    s2.metric("Value Alignment", current_stats["Value Alignment"])
    s3.metric("Avg Payout", f"{current_stats['Avg Payout']:.0%}")
    s4.metric("Volatility", f"{current_stats['Volatility']:.0%}")
    figc = px.line(compare, x="Year", y=["Actual Payout", "Modeled Current Plan"], markers=True, title="Actual Payout vs. Modeled Current Plan")
    st.plotly_chart(figc, use_container_width=True, key="current_plan_chart")

st.subheader("Find Better Historical Designs")
o1, o2, o3 = st.columns(3)
with o1:
    max_metrics = st.slider("Maximum metrics per plan", 1, min(5, len(selected_metrics)), min(3, len(selected_metrics)))
with o2:
    step = st.selectbox("Weight increment", [10, 20, 25, 50], index=2)
with o3:
    objective = st.selectbox("Primary objective", ["Balanced", "Maximize shareholder alignment", "Maintain payout cost", "Reduce volatility"])

required_metric = st.selectbox("Optional required metric", ["None"] + selected_metrics)

if st.button("Run Design Lab"):
    plans = []
    for wset in generate_weight_sets(selected_metrics, step, max_metrics):
        if required_metric != "None" and required_metric not in wset:
            continue
        stats = evaluate_plan(merged, wset, directions, threshold, target, maximum, threshold_payout, max_payout)
        if not stats:
            continue
        if objective == "Maximize shareholder alignment":
            rank_score = max(stats["Value Alignment"], 0) * 100
        elif objective == "Maintain payout cost":
            rank_score = 100 - abs(stats["Avg Payout"] - merged["Actual Payout"].mean()) * 100
        elif objective == "Reduce volatility":
            rank_score = 100 - stats["Volatility"] * 100
        else:
            rank_score = stats["Plan Quality Score"]
        stats["Rank Score"] = round(rank_score, 1)
        stats["Metric Mix"] = " / ".join([f"{int(v*100)}% {k}" for k, v in wset.items()])
        plans.append(stats)
    opt = pd.DataFrame(plans).sort_values("Rank Score", ascending=False)
    st.subheader("Top Alternative Designs")
    st.dataframe(opt.head(25), use_container_width=True)

    if not opt.empty:
        best = opt.iloc[0]
        st.success(f"Top design under selected objective: {best['Metric Mix']}")
        if current_stats:
            comp = pd.DataFrame([
                {"Design": "Current / Proposed", **current_stats},
                {"Design": "Top Alternative", **{k: best[k] for k in ["Plan Quality Score", "Value Alignment", "Payout Fit", "Avg Payout", "Volatility", "Avg Error"]}},
            ])
            st.subheader("Current vs. Top Alternative")
            st.dataframe(comp, use_container_width=True)

        st.subheader("Draft Consultant Takeaway")
        if strong_value["Metric"] == strong_payout["Metric"]:
            msg = f"Historical diagnostics indicate {strong_value['Metric']} has been the strongest tested metric for both shareholder value alignment and actual payout behavior. The design lab can be used to evaluate whether increasing or preserving emphasis on this metric improves alignment while maintaining a reasonable payout profile."
        else:
            msg = f"Historical diagnostics indicate {strong_value['Metric']} has shown the strongest relationship with the selected shareholder value measure, while {strong_payout['Metric']} has had the strongest relationship with actual payouts. This suggests a potential alignment gap. The top alternative design increases emphasis on the metrics that have historically shown stronger value linkage, subject to review of strategy, controllability, goal rigor, and disclosure considerations."
        st.write(msg)

        csv = opt.to_csv(index=False).encode("utf-8")
        st.download_button("Download design lab results", csv, "design_lab_results.csv", "text/csv")

st.caption("Internal pilot. Results are directional and should supplement consultant judgment, not replace it.")
