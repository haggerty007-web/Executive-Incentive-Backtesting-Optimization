
import pandas as pd
import streamlit as st
import plotly.express as px

from analytics.utils import parse_table, read_file, infer_year_col, download_df
from analytics.metric_engine import map_metrics, capiq_fields, add_bridge_columns, merge_candidate_values, build_metric_objects
from analytics.driver_engine import normalize_manual_driver_table, summarize_value_drivers, driver_to_metric_linkages
from analytics.evidence_engine import master_dataset, score_metrics, compare_current
from reporting.committee_report import committee_summary
from data.metric_catalog import METRIC_CATALOG

st.set_page_config(page_title="Executive Incentive Design Lab V4", layout="wide")

def sample_perf():
    return pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "Adjusted EBITDA Actual": [714, 716.8, 931.2, 1030.8, 1070, 1041, 1600, 1876, 1693, 1372],
        "Cash Flow Actual": [320, 375.6, 471.66, 544.995, 520, 580, 743, 808, 672, 467],
    })

def sample_payout():
    return pd.DataFrame({"Year": list(range(2016, 2026)), "Actual Payout": ["55%","50%","100%","150%","100%","64%","200%","153%","26%","0%"]})

def sample_value():
    return pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "IQ_MARKETCAP": [3963,4785,3302,4833,4587,5988,6833,7544,8152,4445],
        "IQ_CLOSEPRICE_ADJ": [10.30,13.04,9.18,14.67,15.25,17.83,20.66,23.28,26.01,14.74],
    })

for key in ["perf_df", "payout_df", "value_df", "mgmt_df", "driver_df", "driver_summary_df", "driver_linkage_df", "mapping_df", "candidate_df", "metric_objects", "master_df", "score_df"]:
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame()
if "current_metrics" not in st.session_state:
    st.session_state.current_metrics = []

st.sidebar.title("Design Lab V4")
company = st.sidebar.text_input("Company", value="Graphic Packaging")
page = st.sidebar.radio("Workflow", [
    "1. Import Data",
    "2. Management Metrics",
    "3. Management Value Drivers",
    "4. Metric Catalog & Capital IQ",
    "5. Annual Values",
    "6. Build Metric Objects",
    "7. Evidence Engine",
    "8. Design Lab",
    "9. Committee Summary",
])

if not st.session_state.driver_df.empty:
    st.sidebar.success(f"Driver data saved: {len(st.session_state.driver_df)} rows")
if not st.session_state.score_df.empty:
    st.sidebar.success(f"Evidence results: {len(st.session_state.score_df)} metrics")

st.title("Executive Incentive Design Lab V4")
st.caption("Evidence Engine | Metric Objects | Management Value Drivers | Current vs Alternative Metrics")

if page == "1. Import Data":
    st.header("1. Import Data")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.subheader("Current Plan / Performance")
        method = st.radio("Method", ["Paste", "Upload", "Sample"], horizontal=True, key="perf_method")
        df = parse_table(st.text_area("Paste performance data", height=180, key="perf_txt")) if method == "Paste" else read_file(st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="perf_file")) if method == "Upload" else sample_perf()
        if not df.empty:
            st.session_state.perf_df = df
            st.dataframe(df, use_container_width=True)
    with c2:
        st.subheader("Payout History")
        method = st.radio("Method", ["Paste", "Upload", "Sample"], horizontal=True, key="pay_method")
        df = parse_table(st.text_area("Paste payout data", height=180, key="pay_txt")) if method == "Paste" else read_file(st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="pay_file")) if method == "Upload" else sample_payout()
        if not df.empty:
            st.session_state.payout_df = df
            st.dataframe(df, use_container_width=True)
    with c3:
        st.subheader("Shareholder Value")
        method = st.radio("Method", ["Paste", "Upload", "Sample"], horizontal=True, key="val_method")
        df = parse_table(st.text_area("Paste shareholder value", height=180, key="val_txt")) if method == "Paste" else read_file(st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="val_file")) if method == "Upload" else sample_value()
        if not df.empty:
            st.session_state.value_df = df
            st.dataframe(df, use_container_width=True)

elif page == "2. Management Metrics":
    st.header("2. Management Metrics")
    method = st.radio("Method", ["Paste", "Upload", "Sample"], horizontal=True)
    if method == "Paste":
        df = parse_table(st.text_area("Paste metric library", height=220))
    elif method == "Upload":
        df = read_file(st.file_uploader("Upload metric library", type=["csv","xlsx","xls"]))
    else:
        df = pd.DataFrame({
            "Metric": ["Adjusted EBITDA", "Cash Flow Before Debt Reduction", "Revenue", "EBITDA", "ROIC", "Free Cash Flow", "Pricing", "Productivity Savings", "Cost Savings", "Safety"],
            "Category": ["Profitability", "Cash Flow", "Growth", "Profitability", "Capital Efficiency", "Cash Flow", "Commercial", "Operations", "Operations", "Human Capital"],
            "Management Emphasis": [5,5,5,5,4,4,4,4,4,3],
        })
    if not df.empty:
        if "Metric" not in df.columns:
            st.error("Need a Metric column.")
        else:
            if "Management Emphasis" not in df.columns:
                df["Management Emphasis"] = 3
            if "Mention Count" not in df.columns:
                df["Mention Count"] = 0
            if "Extraction Confidence" not in df.columns:
                df["Extraction Confidence"] = 0
            st.session_state.mgmt_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            download_df(st, st.session_state.mgmt_df, "Download management metrics", "management_metrics.csv")

elif page == "3. Management Value Drivers":
    st.header("3. Management Value Drivers")
    st.info("Paste either long format (Year / Driver / Impact) or wide bridge format (Year / Price / Volume-Mix / Inflation / FX / Other).")
    manual = st.text_area("Paste management driver history", height=220, placeholder="Year\tPrice\tVolume/Mix\tInflation\tFX\tOther\n2023\t556\t-204\t-175\t-11\t102")
    manual_df = parse_table(manual)
    driver_df = pd.DataFrame()
    if not manual_df.empty:
        driver_df = normalize_manual_driver_table(manual_df)
        if not driver_df.empty:
            st.success(f"Recognized {len(driver_df)} driver-year observations.")
    if driver_df.empty and not st.session_state.driver_df.empty:
        driver_df = st.session_state.driver_df.copy()
        st.info("Using saved driver data from this session.")
    if driver_df.empty:
        st.warning("No driver data loaded yet.")
    else:
        driver_df = st.data_editor(driver_df, use_container_width=True, num_rows="dynamic")
        summary = summarize_value_drivers(driver_df)
        linkages = driver_to_metric_linkages(summary)
        st.session_state.driver_df = driver_df.copy()
        st.session_state.driver_summary_df = summary.copy()
        st.session_state.driver_linkage_df = linkages.copy()
        st.subheader("Driver Summary")
        st.dataframe(summary, use_container_width=True)
        st.subheader("Driver-to-Metric Linkages")
        st.dataframe(linkages, use_container_width=True)
        download_df(st, driver_df, "Download driver history", "management_driver_history.csv")
        download_df(st, summary, "Download driver summary", "management_driver_summary.csv")
        download_df(st, linkages, "Download driver linkages", "driver_metric_linkages.csv")

elif page == "4. Metric Catalog & Capital IQ":
    st.header("4. Metric Catalog & Capital IQ")
    mgmt = st.session_state.mgmt_df
    metrics = mgmt["Metric"].dropna().astype(str).tolist() if not mgmt.empty and "Metric" in mgmt.columns else []
    if not st.session_state.driver_linkage_df.empty:
        metrics += st.session_state.driver_linkage_df["Linked Financial / Incentive Metric"].dropna().astype(str).tolist()
    add = st.text_area("Add metrics to map, one per line", height=100)
    metrics += [x.strip() for x in add.splitlines() if x.strip()]
    metrics = list(dict.fromkeys(metrics))
    if not metrics:
        st.warning("Add management metrics first.")
        st.stop()
    mapping = st.data_editor(map_metrics(metrics), use_container_width=True, num_rows="dynamic")
    st.session_state.mapping_df = mapping
    st.subheader("Capital IQ Field List")
    fields = capiq_fields(mapping)
    st.dataframe(fields, use_container_width=True)
    download_df(st, mapping, "Download metric mapping", "metric_mapping.csv")
    download_df(st, fields, "Download Capital IQ field list", "capital_iq_fields.csv")
    with st.expander("Built-in Metric Catalog"):
        catalog = pd.DataFrame(METRIC_CATALOG)
        st.dataframe(catalog, use_container_width=True)

elif page == "5. Annual Values":
    st.header("5. Annual Values")
    method = st.radio("Method", ["Paste", "Upload", "Blank template"], horizontal=True)
    if method == "Paste":
        df = parse_table(st.text_area("Paste annual values", height=240))
    elif method == "Upload":
        df = read_file(st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"]))
    else:
        years = list(range(2016, 2026))
        if not st.session_state.perf_df.empty:
            y = infer_year_col(st.session_state.perf_df)
            years = sorted(st.session_state.perf_df[y].dropna().astype(str).str.extract(r'((?:19|20)\d{2})')[0].dropna().astype(int).unique().tolist())
        df = pd.DataFrame({"Year": years})
        if not st.session_state.mapping_df.empty:
            for f in capiq_fields(st.session_state.mapping_df)["Capital IQ Field"]:
                df[f] = ""
    if not df.empty:
        st.session_state.candidate_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
        download_df(st, st.session_state.candidate_df, "Download annual values", "annual_values.csv")

def build_context():
    perf, payout, value = st.session_state.perf_df, st.session_state.payout_df, st.session_state.value_df
    if perf.empty or payout.empty or value.empty:
        st.warning("Import data first.")
        st.stop()
    py, payy, vy = infer_year_col(perf), infer_year_col(payout), infer_year_col(value)
    c1, c2, c3 = st.columns(3)
    with c1:
        perf_year = st.selectbox("Performance year column", perf.columns, index=list(perf.columns).index(py) if py in perf.columns else 0)
    with c2:
        payout_year = st.selectbox("Payout year column", payout.columns, index=list(payout.columns).index(payy) if payy in payout.columns else 0)
    with c3:
        value_year = st.selectbox("Shareholder value year column", value.columns, index=list(value.columns).index(vy) if vy in value.columns else 0)
    perf2 = perf.copy()
    if not st.session_state.candidate_df.empty:
        perf2 = merge_candidate_values(perf2, perf_year, st.session_state.candidate_df)
    if not st.session_state.mapping_df.empty:
        perf2 = add_bridge_columns(perf2, st.session_state.mapping_df)
    master = master_dataset(perf2, payout, value, perf_year, payout_year, value_year)
    return perf2, payout, value, master, perf_year, payout_year, value_year

if page == "6. Build Metric Objects":
    st.header("6. Build Metric Objects")
    perf2, payout, value, master, perf_year, payout_year, value_year = build_context()
    with st.expander("Merged performance dataset"):
        st.dataframe(perf2, use_container_width=True)
    objs = st.data_editor(build_metric_objects(perf2, st.session_state.mapping_df), use_container_width=True, num_rows="dynamic")
    st.session_state.metric_objects = objs
    st.session_state.master_df = master
    st.metric("Ready metric objects", int(objs["Ready"].sum()) if "Ready" in objs.columns else 0)
    st.dataframe(objs, use_container_width=True)
    download_df(st, objs, "Download metric objects", "metric_objects.csv")

elif page == "7. Evidence Engine":
    st.header("7. Evidence Engine")
    perf2, payout, value, master, perf_year, payout_year, value_year = build_context()
    objs = st.session_state.metric_objects
    if objs.empty:
        objs = build_metric_objects(perf2, st.session_state.mapping_df)
    payout_cols = [c for c in payout.columns if c != payout_year]
    value_cols = [c for c in value.columns if c != value_year]
    ready = objs[objs["Ready"] == True]["Metric"].tolist() if "Ready" in objs.columns else objs["Metric"].tolist()
    c1, c2 = st.columns(2)
    with c1:
        current_metrics = st.multiselect("Current incentive metrics", ready, default=ready[:min(2, len(ready))])
    with c2:
        selected = st.multiselect("Metrics to test", ready, default=ready[:min(15, len(ready))], max_selections=30)
    payout_col = st.selectbox("Payout column", payout_cols)
    value_col = st.selectbox("Shareholder value outcome", value_cols)
    score = score_metrics(master, objs, selected, value_col, payout_col, st.session_state.mgmt_df, st.session_state.driver_linkage_df)
    st.session_state.score_df = score
    st.session_state.current_metrics = current_metrics
    if score.empty:
        st.error("No correlations available. Check annual values and metric objects.")
        st.stop()
    current, alt = compare_current(score, current_metrics)
    st.subheader("Metric Evidence Scorecard")
    st.dataframe(score, use_container_width=True)
    download_df(st, score, "Download scorecard", "metric_evidence_scorecard.csv")
    st.subheader("Current vs Alternative Metrics")
    a, b = st.columns(2)
    with a:
        st.markdown("**Current metrics**")
        st.dataframe(current, use_container_width=True)
    with b:
        st.markdown("**Alternative candidates**")
        st.dataframe(alt, use_container_width=True)
    st.plotly_chart(px.bar(score.sort_values("Evidence Score").tail(12), x="Evidence Score", y="Metric", orientation="h", title="Evidence score"), use_container_width=True)
    st.plotly_chart(px.bar(score.sort_values("Directional Corr.").tail(12), x="Directional Corr.", y="Metric", orientation="h", title="Directional relationship to shareholder value"), use_container_width=True)

elif page == "8. Design Lab":
    st.header("8. Design Lab")
    score = st.session_state.score_df
    if score.empty:
        st.warning("Run Evidence Engine first.")
        st.stop()
    metrics = score["Metric"].tolist()
    selected = st.multiselect("Metrics in proposed design", metrics, default=metrics[:min(3, len(metrics))], max_selections=5)
    if not selected:
        st.stop()
    weights, rows, design_score = {}, [], 0
    cols = st.columns(len(selected))
    for i, m in enumerate(selected):
        weights[m] = cols[i].slider(f"Weight: {m}", 0, 100, int(100 / len(selected)), 5)
    total = sum(weights.values())
    if total != 100:
        st.warning(f"Weights sum to {total}%. Adjust to 100%.")
        st.stop()
    for m, w in weights.items():
        ev = float(score.loc[score["Metric"] == m, "Evidence Score"].iloc[0])
        design_score += ev * w / 100
        rows.append({"Metric": m, "Weight": w, "Evidence Score": ev, "Weighted Evidence": ev * w / 100})
    df = pd.DataFrame(rows)
    st.metric("Design evidence score", f"{design_score:.1f}/100")
    st.dataframe(df, use_container_width=True)
    st.plotly_chart(px.bar(df, x="Metric", y="Weight", title="Proposed weights"), use_container_width=True)

elif page == "9. Committee Summary":
    st.header("9. Committee Summary")
    score = st.session_state.score_df
    if score.empty:
        st.warning("Run Evidence Engine first.")
        st.stop()
    current, alt = compare_current(score, st.session_state.current_metrics)
    text = committee_summary(company, score, st.session_state.current_metrics, alt, st.session_state.driver_summary_df)
    st.text_area("Draft summary", text, height=320)
    st.download_button("Download summary", text.encode("utf-8"), "committee_summary.txt", "text/plain")
