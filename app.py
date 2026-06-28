
import io
import re
import itertools
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Executive Incentive Design Lab", layout="wide")

# -----------------------------
# Helpers
# -----------------------------

KNOWN_METRICS = {
    "adjusted ebitda": ("Adjusted EBITDA", "Profitability"),
    "ebitda": ("EBITDA", "Profitability"),
    "ebitda margin": ("EBITDA Margin", "Profitability"),
    "adjusted eps": ("Adjusted EPS", "Profitability"),
    "eps": ("EPS", "Profitability"),
    "net sales": ("Net Sales", "Growth"),
    "sales": ("Sales", "Growth"),
    "revenue": ("Revenue", "Growth"),
    "organic sales": ("Organic Sales", "Growth"),
    "organic growth": ("Organic Growth", "Growth"),
    "free cash flow": ("Free Cash Flow", "Cash Flow"),
    "cash flow before debt reduction": ("Cash Flow Before Debt Reduction", "Cash Flow"),
    "operating cash flow": ("Operating Cash Flow", "Cash Flow"),
    "cash conversion": ("Cash Conversion", "Cash Flow"),
    "roic": ("ROIC", "Capital Efficiency"),
    "return on invested capital": ("ROIC", "Capital Efficiency"),
    "return on capital": ("Return on Capital", "Capital Efficiency"),
    "gross margin": ("Gross Margin", "Profitability"),
    "operating margin": ("Operating Margin", "Profitability"),
    "net leverage": ("Net Leverage", "Balance Sheet"),
    "leverage ratio": ("Leverage Ratio", "Balance Sheet"),
    "debt reduction": ("Debt Reduction", "Balance Sheet"),
    "productivity": ("Productivity Savings", "Operations"),
    "cost savings": ("Cost Savings", "Operations"),
    "pricing": ("Pricing", "Commercial"),
    "price realization": ("Pricing Realization", "Commercial"),
    "innovation": ("Innovation", "Strategy"),
    "sustainability": ("Sustainability", "ESG"),
    "safety": ("Safety", "Human Capital"),
}

def clean_num(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    if s in ["", "-", "—", "nm", "n/a", "NA", "N/A"]:
        return np.nan
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg = True
        s = s[1:-1]
    s = s.replace("$", "").replace(",", "").replace("%", "").replace("x", "").strip()
    try:
        v = float(s)
        return -v if neg else v
    except Exception:
        return np.nan

def parse_pasted_table(txt):
    if not txt or not txt.strip():
        return pd.DataFrame()
    txt = txt.strip()
    try:
        df = pd.read_csv(io.StringIO(txt), sep="\t")
        if df.shape[1] <= 1:
            df = pd.read_csv(io.StringIO(txt))
        return df.dropna(how="all")
    except Exception:
        try:
            return pd.read_csv(io.StringIO(txt))
        except Exception:
            return pd.DataFrame()

def standardize_year(series):
    out = []
    for x in series:
        if pd.isna(x):
            out.append(np.nan)
            continue
        s = str(x).strip()
        m = re.search(r"(19|20)\d{2}", s)
        if m:
            out.append(int(m.group(0)))
        else:
            try:
                v = int(float(s))
                out.append(v if 1900 <= v <= 2100 else np.nan)
            except Exception:
                out.append(np.nan)
    return pd.Series(out)

def infer_year_col(df):
    for c in df.columns:
        s = standardize_year(df[c])
        if s.notna().sum() >= max(2, len(df) * 0.5):
            return c
    return df.columns[0] if len(df.columns) else None

def extract_text_from_pdf(file):
    text = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(file)
        for page in reader.pages:
            text += "\n" + (page.extract_text() or "")
    except Exception as e:
        st.warning(f"Could not read PDF text with pypdf: {e}")
    return text

def extract_text_from_docx(file):
    text = ""
    try:
        from docx import Document
        doc = Document(file)
        text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.warning(f"Could not read DOCX: {e}")
    return text

def read_upload_table(file):
    if file is None:
        return pd.DataFrame()
    name = file.name.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(file)
        if name.endswith(".xlsx") or name.endswith(".xls"):
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Could not read file: {e}")
    return pd.DataFrame()

def discover_metric_mentions(text):
    lower = text.lower()
    rows = []
    for key, (display, category) in KNOWN_METRICS.items():
        pattern = r"\b" + re.escape(key) + r"\b"
        mentions = re.findall(pattern, lower)
        if mentions:
            # approximate years mentioned near the term
            years = set()
            for m in re.finditer(pattern, lower):
                window = lower[max(0, m.start()-250): min(len(lower), m.end()+250)]
                years.update(re.findall(r"(?:19|20)\d{2}", window))
            rows.append({
                "Metric": display,
                "Category": category,
                "Mention Count": len(mentions),
                "Years Mentioned": len(years),
                "Management Emphasis": min(5, max(1, round(len(mentions) / 10 + len(years) / 4, 1))),
                "Source": "Document extraction"
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (df.groupby(["Metric", "Category"], as_index=False)
              .agg({"Mention Count": "sum", "Years Mentioned": "max", "Management Emphasis": "max", "Source": "first"})
              .sort_values(["Management Emphasis", "Mention Count"], ascending=False))

def extract_candidate_financial_values(text, selected_metrics):
    # Conservative extractor: looks for rows containing a selected metric and nearby years/values.
    rows = []
    for metric in selected_metrics:
        pattern = re.compile(re.escape(metric), re.IGNORECASE)
        for m in pattern.finditer(text):
            window = text[max(0, m.start()-500): min(len(text), m.end()+1000)]
            years = re.findall(r"(?:19|20)\d{2}", window)
            nums = re.findall(r"(?<![A-Za-z])\(?\$?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\)?", window)
            # only add if multiple years and numbers nearby; user must review.
            if len(years) >= 2 and len(nums) >= len(years):
                for y, n in zip(years[:10], nums[:10]):
                    val = clean_num(n)
                    if pd.notna(val) and 1900 <= int(y) <= 2100:
                        rows.append({
                            "Metric": metric,
                            "Year": int(y),
                            "Extracted Value": val,
                            "Confidence": "Review",
                            "Context": window[:250].replace("\n", " ")
                        })
                break
    return pd.DataFrame(rows).drop_duplicates(subset=["Metric", "Year"], keep="first") if rows else pd.DataFrame()

def metric_category(name):
    n = str(name).lower()
    for key, (display, cat) in KNOWN_METRICS.items():
        if key in n or n in key:
            return cat
    return "Other"

def score_metrics(model_df, metric_cols, value_col, payout_col=None, mgmt_df=None):
    rows = []
    for m in metric_cols:
        x = pd.to_numeric(model_df[m].map(clean_num), errors="coerce")
        y = pd.to_numeric(model_df[value_col].map(clean_num), errors="coerce")
        valid = pd.concat([x, y], axis=1).dropna()
        corr_val = valid.iloc[:,0].corr(valid.iloc[:,1]) if len(valid) >= 3 else np.nan
        payout_corr = np.nan
        if payout_col:
            p = pd.to_numeric(model_df[payout_col].map(clean_num), errors="coerce")
            validp = pd.concat([x, p], axis=1).dropna()
            payout_corr = validp.iloc[:,0].corr(validp.iloc[:,1]) if len(validp) >= 3 else np.nan
        vol = x.pct_change().replace([np.inf, -np.inf], np.nan).std()
        stability = max(0, 100 - min(100, (0 if pd.isna(vol) else vol * 100)))
        mgmt = 0
        if mgmt_df is not None and not mgmt_df.empty and "Metric" in mgmt_df.columns:
            match = mgmt_df[mgmt_df["Metric"].astype(str).str.lower() == str(m).lower()]
            if not match.empty and "Management Emphasis" in match.columns:
                mgmt = float(pd.to_numeric(match["Management Emphasis"], errors="coerce").fillna(0).max()) * 20
        value_score = 0 if pd.isna(corr_val) else abs(corr_val) * 100
        payout_score = 0 if pd.isna(payout_corr) else abs(payout_corr) * 100
        overall = 0.50 * value_score + 0.20 * payout_score + 0.15 * stability + 0.15 * mgmt
        rows.append({
            "Metric": m,
            "Category": metric_category(m),
            "Shareholder Value Corr.": corr_val,
            "Payout Corr.": payout_corr,
            "Stability Score": stability,
            "Management Emphasis Score": mgmt,
            "Evidence Score": overall
        })
    return pd.DataFrame(rows).sort_values("Evidence Score", ascending=False)

def merge_data(perf, payout, value, perf_year, payout_year, value_year):
    a = perf.copy()
    b = payout.copy()
    c = value.copy()
    a["Year"] = standardize_year(a[perf_year])
    b["Year"] = standardize_year(b[payout_year])
    c["Year"] = standardize_year(c[value_year])
    a = a.dropna(subset=["Year"])
    b = b.dropna(subset=["Year"])
    c = c.dropna(subset=["Year"])
    a["Year"] = a["Year"].astype(int)
    b["Year"] = b["Year"].astype(int)
    c["Year"] = c["Year"].astype(int)
    b = b[[col for col in b.columns if col == "Year" or col != payout_year]]
    c = c[[col for col in c.columns if col == "Year" or col != value_year]]
    out = a.merge(b, on="Year", how="inner", suffixes=("", "_payout"))
    out = out.merge(c, on="Year", how="inner", suffixes=("", "_value"))
    return out.sort_values("Year")

def download_df_button(df, label, filename):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, file_name=filename, mime="text/csv")

# -----------------------------
# UI
# -----------------------------

st.title("Executive Incentive Design Lab")
st.caption("Company DNA | Incentive DNA | Management Priority Metrics | Historical Diagnostics")

st.info("Paste from Excel, upload files, or extract management priority metrics from investor communications.")

with st.expander("Download / copy template formats"):
    st.markdown("""
**Performance Data**
```text
Year    Adjusted EBITDA    Cash Flow Before Debt Reduction    ROIC    Organic Sales Growth
2024    1693               672                                6.35    2.8
```

**Payout History**
```text
Year    Actual Payout
2024    26%
```

**Shareholder Value**
```text
Year    TSR    Stock Price    Market Cap
2024    10.5%  26.01          8152
```

**Management Priority Metrics**
```text
Metric    Category    Management Emphasis
Adjusted EBITDA    Profitability    5
Free Cash Flow     Cash Flow        5
ROIC               Capital Efficiency 4
```
""")

st.header("1. Import Data")

c1, c2, c3 = st.columns(3)

with c1:
    st.subheader("Performance Data")
    method = st.radio("Input method for performance data", ["Paste from Excel", "Upload file", "Use sample"], horizontal=True, key="perf_method")
    if method == "Paste from Excel":
        perf_txt = st.text_area("Paste performance data here", height=160, key="perf_txt")
        perf_df = parse_pasted_table(perf_txt)
    elif method == "Upload file":
        perf_file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="perf_file")
        perf_df = read_upload_table(perf_file)
    else:
        perf_df = pd.DataFrame({
            "Year": list(range(2016, 2026)),
            "Adjusted EBITDA": [714, 716.8, 931.2, 1030.8, 1070, 1041, 1600, 1876, 1693, 1372],
            "Cash Flow Before Debt Reduction": [320, 375.6, 471.66, 544.995, 520, 580, 743, 808, 672, 467],
            "ROIC": [5.29, 6.10, 2.48, 1.75, 1.15, 1.64, 5.51, 7.47, 6.35, -3.29],
            "Net Sales": [4298, 4406, 6029, 6160, 6560, 7156, 9440, 9428, 8807, 2156],
        })
    if not perf_df.empty:
        st.success(f"Detected {len(perf_df)} rows and {len(perf_df.columns)} columns.")
        st.dataframe(perf_df.head(10), use_container_width=True)

with c2:
    st.subheader("Payout History")
    method = st.radio("Input method for payout history", ["Paste from Excel", "Upload file", "Use sample"], horizontal=True, key="payout_method")
    if method == "Paste from Excel":
        pay_txt = st.text_area("Paste payout history here", height=160, key="pay_txt")
        payout_df = parse_pasted_table(pay_txt)
    elif method == "Upload file":
        payout_file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="payout_file")
        payout_df = read_upload_table(payout_file)
    else:
        payout_df = pd.DataFrame({"Year": list(range(2016, 2026)), "Actual Payout": ["55%","50%","100%","150%","100%","64%","200%","153%","26%","0%"]})
    if not payout_df.empty:
        st.success(f"Detected {len(payout_df)} rows and {len(payout_df.columns)} columns.")
        st.dataframe(payout_df.head(10), use_container_width=True)

with c3:
    st.subheader("Shareholder Value")
    method = st.radio("Input method for shareholder value", ["Paste from Excel", "Upload file", "Use sample"], horizontal=True, key="value_method")
    if method == "Paste from Excel":
        val_txt = st.text_area("Paste shareholder value here", height=160, key="val_txt")
        value_df = parse_pasted_table(val_txt)
    elif method == "Upload file":
        value_file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="value_file")
        value_df = read_upload_table(value_file)
    else:
        value_df = pd.DataFrame({
            "Year": list(range(2016, 2026)),
            "Stock Price": [10.30,13.04,9.18,14.67,15.25,17.83,20.66,23.28,26.01,14.74],
            "Market Cap": [3963,4785,3302,4833,4587,5988,6833,7544,8152,4445],
        })
        value_df["TSR"] = value_df["Stock Price"].pct_change()
    if not value_df.empty:
        st.success(f"Detected {len(value_df)} rows and {len(value_df.columns)} columns.")
        st.dataframe(value_df.head(10), use_container_width=True)

st.header("2. Management Priority Metrics")

m1, m2 = st.columns([1, 1])

with m1:
    st.subheader("Option A: Paste or upload a metric library")
    lib_method = st.radio("Metric library input", ["Paste table", "Upload file", "Use sample"], horizontal=True, key="lib_method")
    if lib_method == "Paste table":
        lib_txt = st.text_area("Paste management priority metrics", height=180, key="lib_txt")
        mgmt_df_manual = parse_pasted_table(lib_txt)
    elif lib_method == "Upload file":
        lib_file = st.file_uploader("Upload metric library CSV/XLSX", type=["csv","xlsx","xls"], key="lib_file")
        mgmt_df_manual = read_upload_table(lib_file)
    else:
        mgmt_df_manual = pd.DataFrame({
            "Metric": ["Adjusted EBITDA", "Cash Flow Before Debt Reduction", "ROIC", "Net Sales"],
            "Category": ["Profitability", "Cash Flow", "Capital Efficiency", "Growth"],
            "Management Emphasis": [5, 5, 4, 4],
        })
    if not mgmt_df_manual.empty:
        st.dataframe(mgmt_df_manual, use_container_width=True)

with m2:
    st.subheader("Option B: Extract from investor communications")
    docs = st.file_uploader(
        "Upload PDFs/DOCX/TXT containing 10-Ks, investor decks, proxy/CD&A, or transcripts",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        key="docs",
    )
    extracted_text = ""
    if docs:
        for f in docs:
            if f.name.lower().endswith(".pdf"):
                extracted_text += "\n" + extract_text_from_pdf(f)
            elif f.name.lower().endswith(".docx"):
                extracted_text += "\n" + extract_text_from_docx(f)
            else:
                extracted_text += "\n" + f.read().decode("utf-8", errors="ignore")
        extracted_lib = discover_metric_mentions(extracted_text)
        if extracted_lib.empty:
            st.warning("No recurring known metrics found. Add metrics manually or extend the dictionary.")
        else:
            st.success(f"Found {len(extracted_lib)} candidate management metrics.")
            st.dataframe(extracted_lib, use_container_width=True)
            download_df_button(extracted_lib, "Download extracted metric library", "management_metric_library.csv")

            st.caption("Experimental: extract nearby historical values. Review before using.")
            selected_extract = st.multiselect("Metrics to attempt value extraction", extracted_lib["Metric"].tolist(), default=extracted_lib["Metric"].head(5).tolist())
            if st.button("Extract historical values from documents"):
                values = extract_candidate_financial_values(extracted_text, selected_extract)
                if values.empty:
                    st.warning("No reliable historical values found. Use the metric names and paste/upload values manually.")
                else:
                    st.dataframe(values, use_container_width=True)
                    download_df_button(values, "Download extracted values for review", "extracted_metric_values_review.csv")
    else:
        extracted_lib = pd.DataFrame()

# Combine library
mgmt_sources = []
if 'mgmt_df_manual' in locals() and not mgmt_df_manual.empty:
    mgmt_sources.append(mgmt_df_manual)
if 'extracted_lib' in locals() and not extracted_lib.empty:
    mgmt_sources.append(extracted_lib)
mgmt_df = pd.concat(mgmt_sources, ignore_index=True) if mgmt_sources else pd.DataFrame()
if not mgmt_df.empty:
    if "Metric" not in mgmt_df.columns:
        st.warning("Management metric library needs a Metric column.")
    else:
        if "Category" not in mgmt_df.columns:
            mgmt_df["Category"] = mgmt_df["Metric"].map(metric_category)
        if "Management Emphasis" not in mgmt_df.columns:
            mgmt_df["Management Emphasis"] = 3
        mgmt_df = mgmt_df.drop_duplicates(subset=["Metric"], keep="first")
        st.subheader("Combined Management Priority Metrics")
        st.dataframe(mgmt_df, use_container_width=True)

st.header("3. Map Data")

if perf_df.empty or payout_df.empty or value_df.empty:
    st.warning("Import performance data, payout history, and shareholder value data to continue.")
    st.stop()

map_cols = st.columns(3)
with map_cols[0]:
    perf_year = st.selectbox("Performance year column", perf_df.columns, index=list(perf_df.columns).index(infer_year_col(perf_df)) if infer_year_col(perf_df) in perf_df.columns else 0)
with map_cols[1]:
    payout_year = st.selectbox("Payout year column", payout_df.columns, index=list(payout_df.columns).index(infer_year_col(payout_df)) if infer_year_col(payout_df) in payout_df.columns else 0)
with map_cols[2]:
    value_year = st.selectbox("Shareholder value year column", value_df.columns, index=list(value_df.columns).index(infer_year_col(value_df)) if infer_year_col(value_df) in value_df.columns else 0)

numeric_perf = [c for c in perf_df.columns if c != perf_year]
payout_candidates = [c for c in payout_df.columns if c != payout_year]
value_candidates = [c for c in value_df.columns if c != value_year]

selected_metrics = st.multiselect("Candidate metrics to analyze (maximum 20)", numeric_perf, default=numeric_perf[:min(10, len(numeric_perf))], max_selections=20)
payout_col = st.selectbox("Actual payout column", payout_candidates)
value_col = st.selectbox("Shareholder value measure", value_candidates)

st.header("4. Modeling Dataset")
try:
    model_df = merge_data(perf_df, payout_df, value_df, perf_year, payout_year, value_year)
    if model_df.empty:
        st.error("Merged dataset is empty. Check year columns and overlapping fiscal years.")
        st.stop()
    st.dataframe(model_df, use_container_width=True)
    download_df_button(model_df, "Download modeling dataset", "modeling_dataset.csv")
except Exception as e:
    st.error(f"Could not merge data: {e}")
    st.stop()

st.header("5. Historical Diagnostics")

if not selected_metrics:
    st.warning("Select at least one candidate metric.")
    st.stop()

score_df = score_metrics(model_df, selected_metrics, value_col, payout_col, mgmt_df)
st.subheader("Metric Evidence Scorecard")
st.dataframe(score_df, use_container_width=True)
download_df_button(score_df, "Download metric evidence scorecard", "metric_evidence_scorecard.csv")

d1, d2 = st.columns(2)
with d1:
    fig = px.bar(score_df.sort_values("Shareholder Value Corr."), x="Shareholder Value Corr.", y="Metric", orientation="h",
                 title="Which metrics are most associated with shareholder value?")
    st.plotly_chart(fig, use_container_width=True, key="value_corr_chart")
with d2:
    fig2 = px.bar(score_df.sort_values("Payout Corr."), x="Payout Corr.", y="Metric", orientation="h",
                  title="Which metrics are most associated with historical payout?")
    st.plotly_chart(fig2, use_container_width=True, key="payout_corr_chart")

st.subheader("Alignment Gap")
gap_df = score_df.copy()
gap_df["Alignment Gap"] = gap_df["Payout Corr."].abs().fillna(0) - gap_df["Shareholder Value Corr."].abs().fillna(0)
st.dataframe(gap_df[["Metric", "Category", "Shareholder Value Corr.", "Payout Corr.", "Alignment Gap", "Evidence Score"]], use_container_width=True)

fig3 = px.bar(gap_df, x="Metric", y=["Shareholder Value Corr.", "Payout Corr."], barmode="group",
              title="What investors rewarded vs. what the plan rewarded")
st.plotly_chart(fig3, use_container_width=True, key="gap_chart")

top_metric = score_df.iloc[0]["Metric"]
st.success(f"Initial read: **{top_metric}** has the strongest overall evidence score based on the selected data and management-priority inputs.")

st.header("6. Metric Cards")
metric_choice = st.selectbox("Select a metric", score_df["Metric"])
card = score_df[score_df["Metric"] == metric_choice].iloc[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Shareholder Value Corr.", f"{card['Shareholder Value Corr.']:.2f}" if pd.notna(card['Shareholder Value Corr.']) else "n/a")
c2.metric("Payout Corr.", f"{card['Payout Corr.']:.2f}" if pd.notna(card['Payout Corr.']) else "n/a")
c3.metric("Management Emphasis", f"{card['Management Emphasis Score']:.0f}/100")
c4.metric("Evidence Score", f"{card['Evidence Score']:.1f}/100")

st.caption("Correlations are directional, especially with small annual samples. Use these diagnostics as evidence to support consultant judgment, not as a mechanical recommendation.")

st.header("7. Design Lab")
st.write("Use the top-ranked metrics to build alternative designs. This section is intentionally simple in this version.")

plan_metrics = st.multiselect("Metrics in proposed design", selected_metrics, default=score_df["Metric"].head(min(3, len(score_df))).tolist(), max_selections=5)
if plan_metrics:
    weights = {}
    cols = st.columns(len(plan_metrics))
    for i, m in enumerate(plan_metrics):
        weights[m] = cols[i].slider(f"Weight: {m}", 0, 100, int(100/len(plan_metrics)), 5)
    total_w = sum(weights.values())
    if total_w != 100:
        st.warning(f"Weights sum to {total_w}%. Adjust to 100%.")
    else:
        design_score = sum(weights[m] / 100 * float(score_df.loc[score_df["Metric"] == m, "Evidence Score"].iloc[0]) for m in plan_metrics)
        st.metric("Proposed Design Evidence Score", f"{design_score:.1f}/100")
        st.write("Proposed weights")
        st.dataframe(pd.DataFrame({"Metric": list(weights.keys()), "Weight": list(weights.values())}), use_container_width=True)

st.header("8. Draft Consultant Takeaway")
if not score_df.empty:
    top3 = score_df.head(3)["Metric"].tolist()
    low_gap = gap_df.sort_values("Alignment Gap", ascending=False).head(1)["Metric"].iloc[0]
    st.info(
        f"The historical diagnostics suggest that {', '.join(top3)} are among the strongest candidate metrics based on the available data. "
        f"{low_gap} shows a relatively high payout-versus-value gap and may warrant additional review. "
        "These results should be validated against business strategy, investor messaging, and compensation committee judgment."
    )
