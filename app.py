import itertools
import re
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Executive Incentive Design Lab", layout="wide")

st.title("Executive Incentive Design Lab")
st.caption("Historical diagnostics, backtesting, and incentive plan optimization using client-specific performance data.")

st.info("Internal pilot. Results are intended to supplement consultant judgment, not replace business context, market practice, or committee discretion.")


def clean_col(c):
    c = str(c).strip()
    c = re.sub(r"\s+", "_", c)
    c = c.replace("%", "pct")
    return c


def normalize_year(s):
    out = pd.to_datetime(s, errors="coerce")
    if out.notna().sum() > 0:
        return out.dt.year
    return pd.to_numeric(s, errors="coerce").astype("Int64")


def clean_numeric(series):
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.strip()
    is_pct = s.str.contains("%", regex=False, na=False)
    s = s.str.replace("$", "", regex=False)
    s = s.str.replace(",", "", regex=False)
    s = s.str.replace("%", "", regex=False)
    s = s.str.replace("(", "-", regex=False).str.replace(")", "", regex=False)
    out = pd.to_numeric(s, errors="coerce")
    # Convert columns that appear to be expressed as percentages into decimals only if they are mostly <= 300.
    if is_pct.mean() > 0.2:
        out = out / 100.0
    return out


def read_any(uploaded_file, sheet_name=None, header_row=0):
    if uploaded_file is None:
        return None
    if uploaded_file.name.lower().endswith(".csv"):
        df = pd.read_csv(uploaded_file, header=header_row)
    else:
        df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=header_row)
    df.columns = [clean_col(c) for c in df.columns]
    df = df.dropna(how="all")
    return df


def get_excel_sheets(uploaded_file):
    if uploaded_file is None or uploaded_file.name.lower().endswith(".csv"):
        return []
    return pd.ExcelFile(uploaded_file).sheet_names


def sample_performance():
    return pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "Adjusted_EBITDA": [737, 707, 920, 978, 913, 1042, 1600, 1870, 1683, 228],
        "Cash_Flow_Before_Debt_Reduction": [232, 291, -40, 439, 63, -99, 467, 304, 69, -153],
        "Revenue": [4298, 4406, 6029, 6160, 6560, 7156, 9440, 9428, 8807, 2156],
        "Gross_Margin": [.19, .16, .16, .18, .17, .15, .19, .23, .23, .14],
        "ROIC": [.0529, .0610, .0248, .0175, .0115, .0164, .0551, .0747, .0635, -.0329],
    })


def sample_payouts():
    return pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "Actual_Payout_pct_of_Target": [.55, .50, 1.00, 1.50, 1.00, .64, 2.00, 1.53, .26, 0.00],
    })


def sample_value():
    return pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "Market_Cap": [3963, 4785, 3302, 4833, 4587, 5988, 6833, 7544, 8152, 4445],
        "Stock_Price": [10.30, 13.04, 9.18, 14.67, 15.25, 17.83, 20.66, 23.28, 26.01, 14.74],
    })


def prepare_merge(perf, payouts, value, perf_year, payout_year, payout_col, value_year, value_col):
    p = perf.copy()
    p["Year"] = normalize_year(p[perf_year])
    p = p.drop(columns=[perf_year]) if perf_year != "Year" and perf_year in p.columns else p

    po = payouts[[payout_year, payout_col]].copy()
    po["Year"] = normalize_year(po[payout_year])
    po["Actual_Payout"] = clean_numeric(po[payout_col])
    po = po[["Year", "Actual_Payout"]]

    v = value[[value_year, value_col]].copy()
    v["Year"] = normalize_year(v[value_year])
    v["Shareholder_Value"] = clean_numeric(v[value_col])
    v = v[["Year", "Shareholder_Value"]]

    for col in p.columns:
        if col != "Year":
            p[col] = clean_numeric(p[col])

    merged = p.merge(po, on="Year", how="inner").merge(v, on="Year", how="inner")
    merged = merged.sort_values("Year").dropna(subset=["Year", "Actual_Payout", "Shareholder_Value"])
    return merged


def payout_curve(attainment, threshold=.90, target=1.00, maximum=1.20):
    if pd.isna(attainment):
        return np.nan
    if attainment < threshold:
        return 0.0
    if attainment < target:
        return 0.5 + (attainment - threshold) / (target - threshold) * 0.5
    if attainment < maximum:
        return 1.0 + (attainment - target) / (maximum - target) * 1.0
    return 2.0


def metric_attainment(series, direction):
    s = pd.to_numeric(series, errors="coerce")
    base = s.shift(1)
    if direction == "Lower is better":
        return base / s.replace(0, np.nan)
    return s / base.replace(0, np.nan)


def modeled_payout(df, metric_weights, metric_directions, threshold, target, maximum):
    score = pd.Series(0.0, index=df.index)
    total_weight = sum(metric_weights.values())
    if total_weight == 0:
        return pd.Series(np.nan, index=df.index)
    for metric, weight in metric_weights.items():
        attain = metric_attainment(df[metric], metric_directions.get(metric, "Higher is better"))
        score += attain * (weight / total_weight)
    return score.apply(lambda x: payout_curve(x, threshold, target, maximum))


def safe_corr(a, b):
    x = pd.to_numeric(a, errors="coerce")
    y = pd.to_numeric(b, errors="coerce")
    d = pd.concat([x, y], axis=1).dropna()
    if len(d) < 3 or d.iloc[:, 0].std() == 0 or d.iloc[:, 1].std() == 0:
        return np.nan
    return float(d.iloc[:, 0].corr(d.iloc[:, 1]))


def r2(actual, predicted):
    d = pd.concat([actual, predicted], axis=1).dropna()
    if len(d) < 3:
        return np.nan
    ss_res = ((d.iloc[:,0] - d.iloc[:,1]) ** 2).sum()
    ss_tot = ((d.iloc[:,0] - d.iloc[:,0].mean()) ** 2).sum()
    return np.nan if ss_tot == 0 else 1 - ss_res / ss_tot


def generate_weight_sets(metrics, step=25, max_metrics=4):
    out = []
    for r in range(1, min(max_metrics, len(metrics)) + 1):
        for combo in itertools.combinations(metrics, r):
            if r == 1:
                out.append({combo[0]: 1.0})
            else:
                for weights in itertools.product(range(step, 101, step), repeat=r):
                    if sum(weights) == 100:
                        out.append({m: w / 100 for m, w in zip(combo, weights)})
    return out


def optimize_plans(df, metrics, directions, threshold, target, maximum, max_metrics, step):
    rows = []
    value_return = df["Shareholder_Value"].pct_change()
    for weights in generate_weight_sets(metrics, step=step, max_metrics=max_metrics):
        pred = modeled_payout(df, weights, directions, threshold, target, maximum)
        fit = r2(df["Actual_Payout"], pred)
        val_corr = safe_corr(pred, value_return)
        avg_payout = pred.mean()
        vol = pred.std()
        cost_neutrality = max(0, 1 - abs(avg_payout - df["Actual_Payout"].mean()))
        simplicity = max(0, 1 - (len(weights)-1) * .12)
        score = (
            max(val_corr if not pd.isna(val_corr) else 0, 0) * 35
            + max(fit if not pd.isna(fit) else 0, 0) * 25
            + max(0, 1 - (vol if not pd.isna(vol) else 0)) * 15
            + cost_neutrality * 15
            + simplicity * 10
        )
        rows.append({
            "Metric Mix": " / ".join([f"{int(w*100)}% {m}" for m, w in weights.items()]),
            "Plan Quality Score": round(score, 1),
            "Payout Fit R2": None if pd.isna(fit) else round(fit, 2),
            "Pay/Value Correlation": None if pd.isna(val_corr) else round(val_corr, 2),
            "Average Payout": round(avg_payout, 2),
            "Payout Volatility": round(vol, 2),
        })
    return pd.DataFrame(rows).sort_values("Plan Quality Score", ascending=False)


def to_excel_template():
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        sample_performance().to_excel(writer, sheet_name="Performance", index=False)
        sample_payouts().to_excel(writer, sheet_name="Payouts", index=False)
        sample_value().to_excel(writer, sheet_name="Shareholder_Value", index=False)
    return output.getvalue()


with st.sidebar:
    st.header("Data Upload")
    mode = st.radio("How is your data organized?", ["Three separate files", "One workbook with three tabs", "Use sample data"])

    st.download_button(
        "Download Excel template",
        data=to_excel_template(),
        file_name="incentive_design_lab_template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

perf = payouts = value = None

if mode == "Use sample data":
    perf = sample_performance()
    payouts = sample_payouts()
    value = sample_value()
else:
    if mode == "Three separate files":
        c1, c2, c3 = st.columns(3)
        with c1:
            perf_file = st.file_uploader("1. Performance history", type=["xlsx", "csv"], key="perf")
        with c2:
            payout_file = st.file_uploader("2. Actual payout history", type=["xlsx", "csv"], key="payout")
        with c3:
            value_file = st.file_uploader("3. Shareholder value history", type=["xlsx", "csv"], key="value")
        perf = read_any(perf_file)
        payouts = read_any(payout_file)
        value = read_any(value_file)
    else:
        wb = st.file_uploader("Upload workbook", type=["xlsx"], key="workbook")
        if wb is not None:
            sheets = get_excel_sheets(wb)
            c1, c2, c3 = st.columns(3)
            with c1:
                perf_sheet = st.selectbox("Performance tab", sheets, key="perf_sheet")
                perf_header = st.number_input("Performance header row", min_value=1, value=1, key="perf_hdr") - 1
            with c2:
                payout_sheet = st.selectbox("Payout tab", sheets, key="payout_sheet")
                payout_header = st.number_input("Payout header row", min_value=1, value=1, key="payout_hdr") - 1
            with c3:
                value_sheet = st.selectbox("Shareholder value tab", sheets, key="value_sheet")
                value_header = st.number_input("Value header row", min_value=1, value=1, key="value_hdr") - 1
            perf = read_any(wb, perf_sheet, perf_header)
            wb.seek(0)
            payouts = read_any(wb, payout_sheet, payout_header)
            wb.seek(0)
            value = read_any(wb, value_sheet, value_header)

if perf is None or payouts is None or value is None:
    st.subheader("Upload three data sources")
    st.write("Use separate files or one workbook with three tabs: Performance, Payouts, and Shareholder Value.")
    st.stop()

st.subheader("1. Preview Uploaded Data")
with st.expander("Performance data", expanded=True):
    st.dataframe(perf, use_container_width=True)
with st.expander("Payout data"):
    st.dataframe(payouts, use_container_width=True)
with st.expander("Shareholder value data"):
    st.dataframe(value, use_container_width=True)

st.subheader("2. Map Columns")
col1, col2, col3 = st.columns(3)
with col1:
    perf_year = st.selectbox("Performance year column", perf.columns)
    metric_cols = [c for c in perf.columns if c != perf_year]
    selected_metrics = st.multiselect("Candidate incentive metrics", metric_cols, default=metric_cols[:min(6, len(metric_cols))])
with col2:
    payout_year = st.selectbox("Payout year column", payouts.columns)
    payout_candidates = [c for c in payouts.columns if c != payout_year]
    payout_col = st.selectbox("Actual payout column", payout_candidates)
with col3:
    value_year = st.selectbox("Shareholder value year column", value.columns)
    value_candidates = [c for c in value.columns if c != value_year]
    value_col = st.selectbox("Shareholder value column", value_candidates)

if not selected_metrics:
    st.warning("Select at least one candidate incentive metric.")
    st.stop()

metric_directions = {}
st.subheader("3. Define Metric Behavior")
for metric in selected_metrics:
    metric_directions[metric] = st.selectbox(
        f"{metric}",
        ["Higher is better", "Lower is better"],
        key=f"dir_{metric}",
    )

merged = prepare_merge(perf, payouts, value, perf_year, payout_year, payout_col, value_year, value_col)

st.subheader("4. Merged Modeling Dataset")
st.dataframe(merged, use_container_width=True)

if len(merged) < 5:
    st.error("The merged dataset has fewer than 5 periods. Check that the year columns align across the three uploads.")
    st.stop()

value_return = merged["Shareholder_Value"].pct_change()

st.subheader("5. Historical Diagnostics")
rows = []
for m in selected_metrics:
    rows.append({
        "Metric": m,
        "Correlation to Actual Payout": safe_corr(merged[m].pct_change(), merged["Actual_Payout"]),
        "Correlation to Shareholder Value Change": safe_corr(merged[m].pct_change(), value_return),
    })
diag = pd.DataFrame(rows).sort_values("Correlation to Shareholder Value Change", ascending=False)
st.dataframe(diag, use_container_width=True)

fig = px.bar(
    diag,
    x="Correlation to Shareholder Value Change",
    y="Metric",
    orientation="h",
    title="Which metrics historically tracked shareholder value?",
)
st.plotly_chart(fig, use_container_width=True, key="value_corr_chart")

st.subheader("6. Current Plan Backtest")
st.write("Enter the current or proposed plan weighting. The tool will estimate what payouts would have been historically.")

threshold, target, maximum = st.columns(3)
with threshold:
    threshold_val = st.number_input("Threshold attainment", value=0.90, step=0.01)
with target:
    target_val = st.number_input("Target attainment", value=1.00, step=0.01)
with maximum:
    max_val = st.number_input("Maximum attainment", value=1.20, step=0.01)

weights = {}
cols = st.columns(min(4, len(selected_metrics)))
for i, metric in enumerate(selected_metrics):
    with cols[i % len(cols)]:
        weights[metric] = st.number_input(f"Weight: {metric}", min_value=0.0, max_value=100.0, value=0.0, step=5.0) / 100.0

if sum(weights.values()) == 0:
    st.warning("Enter at least one plan weight above zero to backtest the current plan.")
else:
    pred = modeled_payout(merged, weights, metric_directions, threshold_val, target_val, max_val)
    backtest = merged[["Year", "Actual_Payout", "Shareholder_Value"]].copy()
    backtest["Modeled_Payout"] = pred
    backtest["Error"] = backtest["Modeled_Payout"] - backtest["Actual_Payout"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Payout Fit R²", "N/A" if pd.isna(r2(backtest["Actual_Payout"], backtest["Modeled_Payout"])) else f"{r2(backtest['Actual_Payout'], backtest['Modeled_Payout']):.2f}")
    c2.metric("Pay/Value Correlation", "N/A" if pd.isna(safe_corr(backtest["Modeled_Payout"], value_return)) else f"{safe_corr(backtest['Modeled_Payout'], value_return):.2f}")
    c3.metric("Average Modeled Payout", f"{backtest['Modeled_Payout'].mean():.0%}")
    c4.metric("Average Actual Payout", f"{backtest['Actual_Payout'].mean():.0%}")

    st.dataframe(backtest, use_container_width=True)
    fig2 = px.line(backtest, x="Year", y=["Actual_Payout", "Modeled_Payout"], markers=True, title="Actual vs. Modeled Payout")
    st.plotly_chart(fig2, use_container_width=True, key="backtest_chart")

st.subheader("7. Optimization")
col_a, col_b = st.columns(2)
with col_a:
    max_metrics = st.slider("Maximum metrics in optimized plan", 1, min(5, len(selected_metrics)), min(3, len(selected_metrics)))
with col_b:
    step = st.selectbox("Weighting increment", [10, 25], index=1)

if st.button("Run Optimization"):
    results = optimize_plans(merged, selected_metrics, metric_directions, threshold_val, target_val, max_val, max_metrics, step)
    st.dataframe(results.head(25), use_container_width=True)
    best = results.iloc[0]
    st.success(f"Top design: {best['Metric Mix']}")
    st.download_button(
        "Download optimization results",
        results.to_csv(index=False).encode("utf-8"),
        file_name="incentive_design_lab_optimization_results.csv",
        mime="text/csv",
    )

st.subheader("8. Draft Consultant Takeaway")
if len(diag) > 0:
    top_value_metric = diag.iloc[0]["Metric"]
    st.write(
        f"Historical analysis indicates that **{top_value_metric}** had the strongest relationship with shareholder value change among the selected metrics. "
        "The backtesting module can be used to compare actual payouts against the current plan design and evaluate whether alternative metric weightings would have improved alignment while maintaining reasonable payout cost and volatility."
    )
