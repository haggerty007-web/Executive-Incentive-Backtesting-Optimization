
import io
import re
import itertools
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Executive Incentive Design Lab V3", layout="wide")

# ============================================================
# Executive Incentive Design Lab V3
# Metric Object Engine
# ============================================================

METRIC_CATALOG = [
    {"Canonical Metric":"Revenue","Aliases":["revenue","sales","net sales","total revenue","net revenue"],"Category":"Growth","Capital IQ Field":"IQ_TOTAL_REV","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Use as standard revenue/net sales. Organic sales usually needs company data."},
    {"Canonical Metric":"Organic Sales","Aliases":["organic sales","organic revenue","organic growth","organic sales growth"],"Category":"Growth","Capital IQ Field":"","Source Type":"Company / Investor Materials","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Company-defined. Usually not available in Capital IQ."},
    {"Canonical Metric":"EBITDA","Aliases":["ebitda"],"Category":"Profitability","Capital IQ Field":"IQ_EBITDA","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Standard EBITDA. May differ from plan-defined Adjusted EBITDA."},
    {"Canonical Metric":"Adjusted EBITDA","Aliases":["adjusted ebitda","adj ebitda","adjusted ebitda actual","ebitda excluding"],"Category":"Profitability","Capital IQ Field":"","Source Type":"Company / Investor Materials","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Management-defined non-GAAP metric."},
    {"Canonical Metric":"EBITDA Margin","Aliases":["ebitda margin","adjusted ebitda margin"],"Category":"Profitability","Capital IQ Field":"IQ_EBITDA / IQ_TOTAL_REV","Source Type":"Derived from Capital IQ","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Margin should generally be tested as level, not growth."},
    {"Canonical Metric":"EBIT","Aliases":["ebit","operating income"],"Category":"Profitability","Capital IQ Field":"IQ_EBIT","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Standard EBIT/operating income."},
    {"Canonical Metric":"Operating Margin","Aliases":["operating margin","ebit margin"],"Category":"Profitability","Capital IQ Field":"IQ_EBIT / IQ_TOTAL_REV","Source Type":"Derived from Capital IQ","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Margin level vs shareholder value change."},
    {"Canonical Metric":"Gross Margin","Aliases":["gross margin","gross profit margin"],"Category":"Profitability","Capital IQ Field":"IQ_GROSS_MARGIN","Source Type":"Capital IQ","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Margin level. Confirm Capital IQ scale."},
    {"Canonical Metric":"EPS","Aliases":["eps","earnings per share","normalized eps","diluted eps"],"Category":"Profitability","Capital IQ Field":"IQ_EPS_NORM","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive / LTI","Notes":"Normalized EPS. Company adjusted EPS may need manual values."},
    {"Canonical Metric":"Free Cash Flow","Aliases":["free cash flow","fcf","levered fcf"],"Category":"Cash Flow","Capital IQ Field":"IQ_LEVERED_FCF","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Levered FCF is a standard proxy. Confirm against plan definition."},
    {"Canonical Metric":"Operating Cash Flow","Aliases":["operating cash flow","cash from operations"],"Category":"Cash Flow","Capital IQ Field":"IQ_CASH_FROM_OPER","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Cash from operating activities."},
    {"Canonical Metric":"Cash Flow Before Debt Reduction","Aliases":["cash flow before debt reduction","cash flow actual"],"Category":"Cash Flow","Capital IQ Field":"","Source Type":"Company / Investor Materials","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Company-defined plan metric."},
    {"Canonical Metric":"ROIC","Aliases":["roic","return on invested capital","return on capital"],"Category":"Capital Efficiency","Capital IQ Field":"IQ_RETURN_INVESTED_CAPITAL","Source Type":"Capital IQ","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive / LTI","Notes":"Return metric. Use level or change, not growth."},
    {"Canonical Metric":"ROE","Aliases":["roe","return on equity"],"Category":"Capital Efficiency","Capital IQ Field":"IQ_RETURN_EQUITY","Source Type":"Capital IQ","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"LTI / annual incentive","Notes":"Return on equity."},
    {"Canonical Metric":"Net Debt","Aliases":["net debt"],"Category":"Balance Sheet","Capital IQ Field":"IQ_NET_DEBT","Source Type":"Capital IQ","Default Transformation":"Absolute Change","Direction":"Lower is better","Outcome Basis":"YoY % Change","Incentive Use":"Modifier / balance sheet objective","Notes":"Change in net debt may be more useful than level."},
    {"Canonical Metric":"Leverage Ratio","Aliases":["leverage ratio","net leverage","debt leverage"],"Category":"Balance Sheet","Capital IQ Field":"IQ_NET_DEBT / IQ_EBITDA","Source Type":"Derived from Capital IQ","Default Transformation":"Level","Direction":"Lower is better","Outcome Basis":"YoY % Change","Incentive Use":"Modifier / balance sheet objective","Notes":"Use company adjusted leverage if available."},
    {"Canonical Metric":"Pricing","Aliases":["pricing","price realization","pricing realization","price mix"],"Category":"Commercial","Capital IQ Field":"","Source Type":"Company / Investor Materials","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Strategic / operating metric","Notes":"Company-specific commercial KPI."},
    {"Canonical Metric":"Cost Savings","Aliases":["cost savings","cost reduction"],"Category":"Operations","Capital IQ Field":"","Source Type":"Company / Investor Materials","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Strategic / operating metric","Notes":"Company-specific operating KPI."},
    {"Canonical Metric":"Productivity Savings","Aliases":["productivity","productivity savings"],"Category":"Operations","Capital IQ Field":"","Source Type":"Company / Investor Materials","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Strategic / operating metric","Notes":"Company-specific operating KPI."},
    {"Canonical Metric":"Safety","Aliases":["safety","trir","recordable incident rate"],"Category":"Human Capital","Capital IQ Field":"","Source Type":"Company / ESG / Internal","Default Transformation":"Level","Direction":"Lower is better","Outcome Basis":"YoY % Change","Incentive Use":"Modifier / ESG metric","Notes":"Usually internal or sustainability report data."},
    {"Canonical Metric":"Operating Income","Aliases":["operating income","income from operations","income from operation","operating profit"],"Category":"Profitability","Capital IQ Field":"IQ_EBIT","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Annual incentive","Notes":"Closest Capital IQ proxy is EBIT / operating income. Useful when 10-K bridge tables explain Income from Operations."},
    {"Canonical Metric":"Volume/Mix","Aliases":["volume/mix","volume mix","volume","mix","sales volume"],"Category":"Commercial","Capital IQ Field":"","Source Type":"10-K Bridge / Investor Materials","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Operating driver","Notes":"Management bridge driver. Can be analyzed when annual bridge impacts are pasted."},
    {"Canonical Metric":"Inflation","Aliases":["inflation","commodity inflation","input costs","raw materials","material costs","freight","energy","labor inflation"],"Category":"Operations","Capital IQ Field":"","Source Type":"10-K Bridge / Investor Materials","Default Transformation":"Level","Direction":"Lower is better","Outcome Basis":"YoY % Change","Incentive Use":"Operating driver / context","Notes":"Management bridge driver. Usually a headwind rather than a direct incentive metric."},
    {"Canonical Metric":"Foreign Exchange","Aliases":["foreign exchange","fx","currency"],"Category":"Commercial","Capital IQ Field":"","Source Type":"10-K Bridge / Investor Materials","Default Transformation":"Level","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Operating driver / context","Notes":"Management bridge driver. Usually context rather than a core incentive metric."},
    {"Canonical Metric":"Market Cap","Aliases":["market cap","market capitalization"],"Category":"Shareholder Value","Capital IQ Field":"IQ_MARKETCAP","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Outcome","Notes":"Shareholder value outcome."},
    {"Canonical Metric":"Stock Price","Aliases":["stock price","share price","closing price"],"Category":"Shareholder Value","Capital IQ Field":"IQ_CLOSEPRICE_ADJ","Source Type":"Capital IQ","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Outcome","Notes":"Adjusted close price. Proxy for TSR if dividends unavailable."},
]

def clean_num(x):
    if pd.isna(x): return np.nan
    s = str(x).strip()
    if s in ["","-","—","nm","n/a","NA","N/A","None"]: return np.nan
    neg = s.startswith("(") and s.endswith(")")
    if neg: s = s[1:-1]
    s = s.replace("$","").replace(",","").replace("%","").replace("x","").strip()
    try:
        v = float(s); return -v if neg else v
    except Exception:
        return np.nan

def numeric(s):
    return pd.to_numeric(s.map(clean_num), errors="coerce").replace([np.inf, -np.inf], np.nan)

def parse_table(txt):
    if not txt or not txt.strip(): return pd.DataFrame()
    txt = txt.strip()
    for sep in ["\t", ","]:
        try:
            df = pd.read_csv(io.StringIO(txt), sep=sep)
            if df.shape[1] > 1: return df.dropna(how="all")
        except Exception:
            pass
    try:
        return pd.read_csv(io.StringIO(txt), delim_whitespace=True).dropna(how="all")
    except Exception:
        return pd.DataFrame()

def read_file(file):
    if file is None: return pd.DataFrame()
    try:
        return pd.read_csv(file) if file.name.lower().endswith(".csv") else pd.read_excel(file)
    except Exception as e:
        st.error(f"Could not read file: {e}"); return pd.DataFrame()

def standardize_year(series):
    vals = []
    for x in series:
        if pd.isna(x): vals.append(np.nan); continue
        m = re.search(r"(19|20)\d{2}", str(x))
        if m: vals.append(int(m.group(0)))
        else:
            try:
                v = int(float(str(x))); vals.append(v if 1900 <= v <= 2100 else np.nan)
            except Exception: vals.append(np.nan)
    return pd.Series(vals)

def infer_year_col(df):
    if df is None or df.empty: return None
    for c in df.columns:
        y = standardize_year(df[c])
        if y.notna().sum() >= max(2, len(df)*0.5): return c
    return df.columns[0]

def norm_text(x): return re.sub(r"[^a-z0-9]+", " ", str(x).lower()).strip()

def find_col(df, col):
    target = str(col).lower()
    for c in df.columns:
        if str(c).lower() == target: return c
    for c in df.columns:
        if re.sub(r"\.\d+$","",str(c).lower()) == target: return c
    return None

def catalog_match(metric):
    n = norm_text(metric); best = None; best_score = 0
    for row in METRIC_CATALOG:
        for a in [row["Canonical Metric"]] + row["Aliases"]:
            aa = norm_text(a)
            if n == aa: score = 100
            elif n in aa or aa in n: score = 86
            else:
                ns, aas = set(n.split()), set(aa.split())
                score = 100 * len(ns & aas) / max(len(ns), len(aas)) if ns and aas else 0
            if score > best_score: best_score = score; best = row
    if best and best_score >= 35:
        out = best.copy(); out["Match Confidence"] = round(best_score, 1); return out
    return {"Canonical Metric":metric,"Aliases":[],"Category":"Other","Capital IQ Field":"","Source Type":"Company / Manual","Default Transformation":"YoY % Change","Direction":"Higher is better","Outcome Basis":"YoY % Change","Incentive Use":"Review","Notes":"No strong catalog match.","Match Confidence":round(best_score,1)}

def apply_transformation(series, rule):
    s = numeric(series)
    if rule == "YoY % Change": return s.pct_change()
    if rule == "Absolute Change": return s.diff()
    if rule == "3-Year Average": return s.rolling(3).mean()
    if rule == "3-Year CAGR": return (s / s.shift(3)) ** (1/3) - 1
    return s

def safe_corr(x, y):
    z = pd.concat([x, y], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(z) < 4 or z.iloc[:,0].nunique() < 2 or z.iloc[:,1].nunique() < 2: return np.nan
    return z.iloc[:,0].corr(z.iloc[:,1])

def stability(series):
    s = numeric(series); completeness = s.notna().mean()*100
    vol = s.pct_change().replace([np.inf, -np.inf], np.nan).std()
    vol_score = 50 if pd.isna(vol) else max(0, 100 - min(100, abs(vol)*100))
    return 0.65*vol_score + 0.35*completeness

def download_df(df, label, filename):
    st.download_button(label, df.to_csv(index=False).encode("utf-8"), file_name=filename, mime="text/csv")


# -----------------------------
# Management Value Driver Engine
# -----------------------------

DRIVER_TAXONOMY = {
    "Pricing": ["price", "pricing", "price realization", "price/mix"],
    "Volume/Mix": ["volume", "mix", "volume/mix", "sales volume"],
    "Inflation": ["inflation", "commodity inflation", "input cost", "raw material", "materials", "freight", "energy", "labor"],
    "Foreign Exchange": ["foreign exchange", "fx", "currency"],
    "Productivity": ["productivity", "productivity savings", "cost reduction", "cost savings", "continuous improvement", "efficiency"],
    "Acquisition / Divestiture": ["acquisition", "divestiture", "m&a", "acquired", "sold business"],
    "Synergies": ["synergies", "synergy"],
    "Other": ["other"],
}

BRIDGE_KEYWORDS = [
    "components of the change",
    "income from operations",
    "variance",
    "bridge",
    "walk",
    "drivers",
    "price",
    "volume/mix",
    "inflation",
    "foreign exchange",
]

def canonical_driver(label):
    n = norm_text(label)
    for canon, aliases in DRIVER_TAXONOMY.items():
        for a in aliases:
            aa = norm_text(a)
            if aa and (aa == n or aa in n or n in aa):
                return canon
    return str(label).strip().title() if str(label).strip() else "Other"

def extract_pdf_tables_for_drivers(file):
    """Extract raw tables from a PDF. Returns list of (page, table_df)."""
    tables = []
    try:
        import pdfplumber
        file.seek(0)
        with pdfplumber.open(file) as pdf:
            for page_no, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables() or []
                for raw in page_tables:
                    if not raw or len(raw) < 2:
                        continue
                    max_len = max(len(r) for r in raw if r)
                    rows = []
                    for r in raw:
                        if not r:
                            continue
                        rr = [(c or "").strip() for c in r] + [""] * (max_len - len(r))
                        rows.append(rr)
                    if len(rows) >= 2:
                        tables.append((page_no, pd.DataFrame(rows)))
    except Exception:
        pass
    return tables

def table_contains_bridge_language(df):
    txt = " ".join(df.astype(str).values.flatten()).lower()
    return any(k in txt for k in BRIDGE_KEYWORDS) and any(k in txt for k in ["price", "volume", "inflation", "foreign"])

def extract_year_from_table(df):
    txt = " ".join(df.astype(str).values.flatten())
    years = re.findall(r"(?:19|20)\d{2}", txt)
    if not years:
        return np.nan
    # In bridge tables, the final year is usually the target year being explained.
    return int(sorted([int(y) for y in years])[-1])

def extract_driver_records_from_bridge_table(df, source_page=""):
    """
    Extract rows like:
    2021 | Price | Volume/Mix | Inflation | FX | 2022 | Increase | Percent Change
    Consolidated | 407 | 1,131 | 173 | (710) | (37) | ... | 906 | 499 | 123%
    """
    records = []
    if df is None or df.empty:
        return records

    year = extract_year_from_table(df)
    # Find the header row that contains driver columns.
    header_idx = None
    header = None
    for i in range(min(8, len(df))):
        row = [str(x).strip() for x in df.iloc[i].tolist()]
        row_text = " ".join(row).lower()
        if ("price" in row_text and ("volume" in row_text or "mix" in row_text)) or ("inflation" in row_text and "foreign" in row_text):
            header_idx = i
            header = row
            break
    if header is None:
        # Sometimes header is split across two lines. Combine first several rows by column.
        max_rows = min(8, len(df))
        combined = []
        for j in range(df.shape[1]):
            combined.append(" ".join(str(df.iloc[i, j]) for i in range(max_rows) if str(df.iloc[i, j]).strip()))
        if any("price" in x.lower() for x in combined) and any("volume" in x.lower() or "mix" in x.lower() for x in combined):
            header_idx = 0
            header = combined

    if header is None:
        return records

    driver_cols = []
    for j, h in enumerate(header):
        canon = canonical_driver(h)
        if canon not in ["Other"] and any(term in norm_text(h) for term in ["price", "volume", "mix", "inflation", "foreign", "exchange", "fx", "productivity", "cost", "synerg"]):
            driver_cols.append((j, canon, h))
        elif norm_text(h) == "other":
            driver_cols.append((j, "Other", h))

    if not driver_cols:
        return records

    # Find data row. Prefer row labeled consolidated, total, segment, etc.
    start = header_idx + 1 if header_idx is not None else 1
    data_rows = []
    for i in range(start, len(df)):
        row = df.iloc[i].tolist()
        row_text = " ".join(str(x).lower() for x in row)
        numeric_count = sum(pd.notna(clean_num(x)) for x in row)
        if numeric_count >= 3:
            score = numeric_count + (5 if any(k in row_text for k in ["consolidated", "total", "income from operations", "operating income"]) else 0)
            data_rows.append((score, i, row))
    if not data_rows:
        return records
    data_rows = sorted(data_rows, reverse=True)
    row_idx, row = data_rows[0][1], data_rows[0][2]

    for col_idx, canon, original_label in driver_cols:
        if col_idx >= len(row):
            continue
        impact = clean_num(row[col_idx])
        if pd.isna(impact):
            continue
        records.append({
            "Year": year,
            "Driver": canon,
            "Original Label": original_label,
            "Impact": impact,
            "Source Page": source_page,
            "Source Type": "10-K bridge table",
            "Confidence": "Table extraction - review"
        })
    return records

def extract_driver_records_from_text(text):
    """Fallback extractor for bridge-style sentences. Lower confidence than table extraction."""
    records = []
    if not text:
        return pd.DataFrame()
    # page markers may be absent; scan windows around bridge terms.
    lower = text.lower()
    for m in re.finditer(r"(components of the change|income from operations|increased|decreased)", lower):
        window = text[max(0, m.start()-700): min(len(text), m.end()+1800)]
        years = re.findall(r"(?:19|20)\d{2}", window)
        year = int(sorted([int(y) for y in years])[-1]) if years else np.nan
        for canon, aliases in DRIVER_TAXONOMY.items():
            for a in aliases:
                # Look for alias followed/preceded by dollar amount.
                pat1 = re.compile(r"(" + re.escape(a) + r").{0,80}?\(?\$?(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*million", re.I)
                for hit in pat1.finditer(window):
                    val = clean_num(hit.group(2))
                    if pd.notna(val):
                        records.append({
                            "Year": year,
                            "Driver": canon,
                            "Original Label": hit.group(1),
                            "Impact": val,
                            "Source Page": "",
                            "Source Type": "10-K text extraction",
                            "Confidence": "Text extraction - low confidence"
                        })
    return pd.DataFrame(records).drop_duplicates() if records else pd.DataFrame()

def extract_management_value_drivers(files):
    all_records = []
    full_text = ""
    for f in files or []:
        name = f.name.lower()
        if name.endswith(".pdf"):
            for page_no, table in extract_pdf_tables_for_drivers(f):
                if table_contains_bridge_language(table):
                    all_records.extend(extract_driver_records_from_bridge_table(table, source_page=page_no))
        full_text += "\n" + extract_text(f)
    text_records = extract_driver_records_from_text(full_text)
    table_records = pd.DataFrame(all_records)
    if table_records.empty and text_records.empty:
        return pd.DataFrame()
    out = pd.concat([table_records, text_records], ignore_index=True)
    out = out.drop_duplicates(subset=["Year", "Driver", "Impact"], keep="first")
    return out.sort_values(["Year", "Driver"])


def normalize_manual_driver_table(manual_df):
    """
    Accept either:
    1. Long format: Year, Driver, Impact
    2. Wide bridge format: Year, Price, Volume/Mix, Inflation, FX, Other, etc.
    Returns long format.
    """
    if manual_df is None or manual_df.empty:
        return pd.DataFrame()

    df = manual_df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    cols_lower = {c.lower(): c for c in df.columns}
    if {"year", "driver", "impact"}.issubset(set(cols_lower.keys())):
        out = df[[cols_lower["year"], cols_lower["driver"], cols_lower["impact"]]].copy()
        out.columns = ["Year", "Driver", "Impact"]
        out["Driver"] = out["Driver"].map(canonical_driver)
        out["Impact"] = out["Impact"].map(clean_num)
        out["Original Label"] = out["Driver"]
        out["Source Page"] = ""
        out["Source Type"] = "Manual paste"
        out["Confidence"] = "Manual review"
        return out.dropna(subset=["Year", "Driver", "Impact"])

    year_col = infer_year_col(df)
    if year_col is None:
        return pd.DataFrame()

    non_driver_terms = [
        "starting", "ending", "beginning", "income from operations",
        "net change", "increase", "decrease", "percent", "change",
        "year", "total", "consolidated"
    ]

    driver_candidates = []
    for c in df.columns:
        if c == year_col:
            continue
        c_norm = norm_text(c)
        if any(t in c_norm for t in non_driver_terms):
            continue
        canon = canonical_driver(c)
        numeric_count = df[c].map(clean_num).notna().sum()
        if numeric_count >= 1 and (canon != "Other" or c_norm == "other"):
            driver_candidates.append((c, canon))

    if not driver_candidates:
        return pd.DataFrame()

    rows = []
    for _, r in df.iterrows():
        year = standardize_year(pd.Series([r[year_col]])).iloc[0]
        if pd.isna(year):
            continue
        for col, canon in driver_candidates:
            impact = clean_num(r[col])
            if pd.isna(impact):
                continue
            rows.append({
                "Year": int(year),
                "Driver": canon,
                "Original Label": col,
                "Impact": impact,
                "Source Page": "",
                "Source Type": "Manual wide bridge paste",
                "Confidence": "Manual review"
            })

    return pd.DataFrame(rows)

def summarize_value_drivers(driver_df):
    if driver_df is None or driver_df.empty:
        return pd.DataFrame()
    df = driver_df.copy()
    df["Impact"] = pd.to_numeric(df["Impact"].map(clean_num), errors="coerce")
    summary = df.groupby("Driver", as_index=False).agg(
        Years_Mentioned=("Year", lambda x: len(set(pd.Series(x).dropna().astype(int)))),
        Observations=("Impact", "count"),
        Total_Impact=("Impact", "sum"),
        Avg_Impact=("Impact", "mean"),
        Positive_Years=("Impact", lambda x: int((x > 0).sum())),
        Negative_Years=("Impact", lambda x: int((x < 0).sum())),
    )
    summary["Consistency"] = np.where(
        summary["Observations"] > 0,
        summary[["Positive_Years", "Negative_Years"]].max(axis=1) / summary["Observations"],
        np.nan
    )
    summary["Driver Evidence Score"] = (
        np.minimum(summary["Years_Mentioned"], 10) * 6 +
        np.minimum(summary["Observations"], 10) * 3 +
        np.minimum(abs(summary["Avg_Impact"]), 1000) / 1000 * 25 +
        summary["Consistency"].fillna(0) * 15
    ).round(1)
    return summary.sort_values("Driver Evidence Score", ascending=False)

def driver_to_metric_linkages(driver_summary):
    """Connect management drivers to incentive/financial metrics."""
    if driver_summary is None or driver_summary.empty:
        return pd.DataFrame()
    mapping = {
        "Pricing": ["Revenue", "Operating Income", "EBITDA", "EBITDA Margin", "Pricing"],
        "Volume/Mix": ["Revenue", "Operating Income", "EBITDA", "Volume/Mix"],
        "Inflation": ["Operating Income", "EBITDA Margin", "Free Cash Flow", "Cost Savings", "Inflation"],
        "Foreign Exchange": ["Revenue", "Operating Income", "EBITDA", "Foreign Exchange"],
        "Productivity": ["Operating Income", "EBITDA", "Free Cash Flow", "Cost Savings", "Productivity Savings"],
        "Synergies": ["EBITDA", "Free Cash Flow"],
        "Acquisition / Divestiture": ["Revenue", "EBITDA", "ROIC"],
        "Other": ["Adjusted EBITDA"],
    }
    rows = []
    for _, r in driver_summary.iterrows():
        driver = r["Driver"]
        for metric in mapping.get(driver, []):
            rows.append({
                "Management Driver": driver,
                "Linked Financial / Incentive Metric": metric,
                "Rationale": f"{driver} is a recurring management-explained driver that may affect {metric}.",
                "Driver Evidence Score": r["Driver Evidence Score"],
            })
    return pd.DataFrame(rows)

def extract_text(file):
    try: file.seek(0)
    except Exception: pass
    name = file.name.lower()
    if name.endswith(".pdf"):
        try:
            import pypdf
            return "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(file).pages)
        except Exception: return ""
    if name.endswith(".docx"):
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(file).paragraphs)
        except Exception: return ""
    try: return file.read().decode("utf-8", errors="ignore")
    except Exception: return ""

def discover_metrics(text):
    lower = text.lower(); rows = []
    for row in METRIC_CATALOG:
        hits=[]; years=set()
        for alias in row["Aliases"]+[row["Canonical Metric"]]:
            for m in re.finditer(r"\b"+re.escape(alias.lower())+r"\b", lower):
                hits.append(m)
                years.update(re.findall(r"(?:19|20)\d{2}", lower[max(0,m.start()-300):min(len(lower),m.end()+300)]))
        if hits:
            mentions=len(hits); yrs=min(10,len(years))
            rows.append({"Metric":row["Canonical Metric"],"Category":row["Category"],"Management Emphasis":min(5,max(1,round((min(5,mentions/12)+min(5,yrs/2))/2,1))),"Mention Count":mentions,"Years Mentioned":yrs,"Extraction Confidence":min(99,45+mentions*2+yrs*4),"Source":"10-K / investor communications"})
    return pd.DataFrame(rows).drop_duplicates("Metric").sort_values(["Management Emphasis","Mention Count"], ascending=False) if rows else pd.DataFrame()

def map_metrics(metrics):
    rows=[]
    for m in metrics:
        cat=catalog_match(m)
        rows.append({"Input Metric":m,"Display Metric":cat["Canonical Metric"],"Category":cat["Category"],"Capital IQ Field / Formula":cat["Capital IQ Field"],"Source Type":cat["Source Type"],"Default Transformation":cat["Default Transformation"],"Direction":cat["Direction"],"Outcome Basis":cat["Outcome Basis"],"Incentive Use":cat["Incentive Use"],"Match Confidence":cat["Match Confidence"],"Notes":cat["Notes"]})
    return pd.DataFrame(rows).drop_duplicates("Input Metric") if rows else pd.DataFrame()

def capiq_fields(mapping_df):
    fields=[]
    if mapping_df is not None and not mapping_df.empty:
        for f in mapping_df["Capital IQ Field / Formula"].fillna("").astype(str):
            fields.extend(re.findall(r"IQ_[A-Z0-9_]+", f))
    fields.extend(["IQ_MARKETCAP","IQ_CLOSEPRICE_ADJ"])
    return pd.DataFrame({"Capital IQ Field":sorted(set(fields))})

def add_bridge_columns(perf_df, mapping_df):
    if perf_df is None or perf_df.empty or mapping_df is None or mapping_df.empty: return perf_df.copy()
    out=perf_df.copy()
    for _,r in mapping_df.iterrows():
        display=str(r["Display Metric"]); field=str(r["Capital IQ Field / Formula"]); input_metric=str(r["Input Metric"])
        if find_col(out, display) or find_col(out, input_metric): continue
        fields=re.findall(r"IQ_[A-Z0-9_]+", field)
        if len(fields)==1 and "/" not in field and "YoY" not in field:
            c=find_col(out, fields[0])
            if c: out[display]=out[c]
        elif "/" in field and len(fields)>=2:
            num=find_col(out, fields[0]); den=find_col(out, fields[1])
            if num and den:
                n=numeric(out[num]); d=numeric(out[den])
                out[display]=np.where(d!=0, n/d, np.nan)
    return out


def driver_history_to_wide(driver_df):
    """
    Convert long-form management bridge driver history into annual columns.
    Example output columns: Pricing, Volume/Mix, Inflation, Foreign Exchange.
    These become metric objects and can be tested like other annual metrics.
    """
    if driver_df is None or driver_df.empty:
        return pd.DataFrame()
    required = {"Year", "Driver", "Impact"}
    if not required.issubset(set(driver_df.columns)):
        return pd.DataFrame()
    df = driver_df.copy()
    df["Year"] = standardize_year(df["Year"])
    df["Impact"] = pd.to_numeric(df["Impact"].map(clean_num), errors="coerce")
    df = df.dropna(subset=["Year", "Driver", "Impact"])
    if df.empty:
        return pd.DataFrame()
    df["Year"] = df["Year"].astype(int)
    wide = df.pivot_table(index="Year", columns="Driver", values="Impact", aggfunc="sum").reset_index()
    wide.columns = [str(c) for c in wide.columns]
    return wide

def merge_candidate_values(perf_df, perf_year, candidate_df):
    if candidate_df is None or candidate_df.empty: return perf_df.copy()
    y2=infer_year_col(candidate_df)
    if not y2: return perf_df.copy()
    a=perf_df.copy(); b=candidate_df.copy()
    a["Year"]=standardize_year(a[perf_year]); b["Year"]=standardize_year(b[y2])
    a=a.dropna(subset=["Year"]); b=b.dropna(subset=["Year"])
    a["Year"]=a["Year"].astype(int); b["Year"]=b["Year"].astype(int)
    if y2!="Year" and y2 in b.columns: b=b.drop(columns=[y2])
    return a.merge(b, on="Year", how="left", suffixes=("", "_candidate"))

def build_metric_objects(perf_df, mapping_df):
    rows=[]; existing=set()
    if mapping_df is not None and not mapping_df.empty:
        for _,r in mapping_df.iterrows():
            for name in [r["Display Metric"], r["Input Metric"]]:
                col=find_col(perf_df, name)
                if col and col not in existing:
                    rows.append({"Metric":name,"Column":col,"Category":r["Category"],"Source Type":r["Source Type"],"Transformation":r["Default Transformation"],"Direction":r["Direction"],"Outcome Basis":r["Outcome Basis"],"Incentive Use":r["Incentive Use"],"Ready":numeric(perf_df[col]).notna().sum()>=4})
                    existing.add(col)
    for c in perf_df.columns:
        if c in existing or c=="Year": continue
        cat=catalog_match(c)
        rows.append({"Metric":c,"Column":c,"Category":cat["Category"],"Source Type":"Uploaded / Existing","Transformation":cat["Default Transformation"],"Direction":cat["Direction"],"Outcome Basis":cat["Outcome Basis"],"Incentive Use":cat["Incentive Use"],"Ready":numeric(perf_df[c]).notna().sum()>=4})
    return pd.DataFrame(rows).drop_duplicates("Column") if rows else pd.DataFrame()

def master_dataset(perf_df,payout_df,value_df,perf_year,payout_year,value_year):
    a=perf_df.copy(); b=payout_df.copy(); c=value_df.copy()
    a["Year"]=standardize_year(a[perf_year]); b["Year"]=standardize_year(b[payout_year]); c["Year"]=standardize_year(c[value_year])
    a=a.dropna(subset=["Year"]); b=b.dropna(subset=["Year"]); c=c.dropna(subset=["Year"])
    a["Year"]=a["Year"].astype(int); b["Year"]=b["Year"].astype(int); c["Year"]=c["Year"].astype(int)
    return a.merge(b,on="Year",how="inner",suffixes=("", "_payout")).merge(c,on="Year",how="inner",suffixes=("", "_value")).sort_values("Year")

def score_metrics(master, metric_objects, selected_metrics, value_col, payout_col, mgmt_df):
    rows=[]; y_value=apply_transformation(master[value_col], "YoY % Change"); y_payout=numeric(master[payout_col])
    mgmt_lookup={}
    if mgmt_df is not None and not mgmt_df.empty and "Metric" in mgmt_df.columns:
        for _,r in mgmt_df.iterrows(): mgmt_lookup[norm_text(r["Metric"])]=r
    for _,obj in metric_objects.iterrows():
        metric=obj["Metric"]
        if metric not in selected_metrics: continue
        col=obj["Column"]; x=apply_transformation(master[col], obj["Transformation"])
        corr_now=safe_corr(x,y_value); corr_lag=safe_corr(x.shift(1),y_value); corr_roll=safe_corr(x.rolling(3).mean(),y_value.rolling(3).mean()); corr_payout=safe_corr(x,y_payout)
        directional=(corr_now * (-1 if obj["Direction"]=="Lower is better" else 1)) if pd.notna(corr_now) else np.nan
        value_score=0 if pd.isna(directional) else max(0,directional)*100
        lag_score=0 if pd.isna(corr_lag) else abs(corr_lag)*100
        roll_score=0 if pd.isna(corr_roll) else abs(corr_roll)*100
        payout_score=0 if pd.isna(corr_payout) else abs(corr_payout)*100
        st_score=stability(master[col])
        mgmt_score=mentions=confidence=0
        for key,r in mgmt_lookup.items():
            if key in norm_text(metric) or norm_text(metric) in key:
                mgmt_score=float(pd.to_numeric(pd.Series([r.get("Management Emphasis",0)]),errors="coerce").fillna(0).iloc[0])*20
                mentions=float(pd.to_numeric(pd.Series([r.get("Mention Count",0)]),errors="coerce").fillna(0).iloc[0])
                confidence=float(pd.to_numeric(pd.Series([r.get("Extraction Confidence",0)]),errors="coerce").fillna(0).iloc[0])
                break
        design_fit={"Growth":80,"Profitability":92,"Cash Flow":92,"Capital Efficiency":90,"Balance Sheet":70,"Operations":72,"Commercial":68,"Human Capital":50,"Other":45}.get(obj["Category"],45)
        driver_score=0
        if "driver_linkage_df" in st.session_state and not st.session_state.driver_linkage_df.empty:
            dl=st.session_state.driver_linkage_df
            match=dl[dl["Linked Financial / Incentive Metric"].astype(str).str.lower()==str(metric).lower()]
            if not match.empty:
                driver_score=float(pd.to_numeric(match["Driver Evidence Score"],errors="coerce").fillna(0).max())

        # Direct bridge-driver metrics such as Pricing, Volume/Mix, Inflation, and FX
        # should also receive their own driver evidence score.
        if "driver_summary_df" in st.session_state and not st.session_state.driver_summary_df.empty:
            ds=st.session_state.driver_summary_df
            dmatch=ds[ds["Driver"].astype(str).str.lower()==str(metric).lower()]
            if not dmatch.empty:
                driver_score=max(driver_score, float(pd.to_numeric(dmatch["Driver Evidence Score"],errors="coerce").fillna(0).max()))
        evidence=0.27*value_score+0.12*lag_score+0.10*roll_score+0.09*payout_score+0.09*st_score+0.09*design_fit+0.09*mgmt_score+0.05*confidence+0.10*driver_score
        rows.append({"Metric":metric,"Column":col,"Category":obj["Category"],"Source Type":obj["Source Type"],"Transformation":obj["Transformation"],"Direction":obj["Direction"],"Current Corr.":corr_now,"Directional Corr.":directional,"Lagged Corr.":corr_lag,"Rolling 3Y Corr.":corr_roll,"Payout Corr.":corr_payout,"Stability":st_score,"Management Score":mgmt_score,"Driver Evidence Score":driver_score,"Design Fit":design_fit,"Evidence Score":evidence,"Mention Count":mentions,"Extraction Confidence":confidence})
    return pd.DataFrame(rows).sort_values("Evidence Score",ascending=False) if rows else pd.DataFrame()

def compare_current(score_df, current_metrics):
    current=score_df[score_df["Metric"].isin(current_metrics)].copy()
    alt=score_df[~score_df["Metric"].isin(current_metrics)].copy()
    base=current["Evidence Score"].mean() if not current.empty else np.nan
    alt["Improvement vs Current Avg"]=alt["Evidence Score"]-base if pd.notna(base) else np.nan
    return current, alt.sort_values("Evidence Score",ascending=False)


# -----------------------------
# Recommendation Workspace Engine
# -----------------------------

# -----------------------------
# Recommendation Workspace Engine
# -----------------------------

def build_recommendation_universe(score_df, current_metrics, driver_linkage_df=None):
    if score_df is None or score_df.empty:
        return pd.DataFrame()

    df = score_df.copy()
    current_set = {str(x) for x in current_metrics or []}
    current_avg = df[df["Metric"].astype(str).isin(current_set)]["Evidence Score"].mean()
    if pd.isna(current_avg):
        current_avg = df["Evidence Score"].mean()

    df["Current Plan Metric"] = df["Metric"].astype(str).isin(current_set)
    df["Improvement vs Current Avg"] = df["Evidence Score"] - current_avg

    def confidence(row):
        sample_proxy = 0
        for col in ["Current Corr.", "Lagged Corr.", "Rolling 3Y Corr.", "Payout Corr."]:
            if col in row and pd.notna(row[col]):
                sample_proxy += 2
        extraction = row.get("Extraction Confidence", 0)
        if sample_proxy >= 6 and extraction >= 70:
            return "High"
        if sample_proxy >= 4 or extraction >= 50:
            return "Medium"
        return "Low"

    def recommendation(row):
        if row["Current Plan Metric"]:
            return "Current metric"
        score = row["Evidence Score"]
        improvement = row["Improvement vs Current Avg"]
        driver = row.get("Driver Evidence Score", 0)
        if score >= 80 and improvement >= 5:
            return "Strong candidate"
        if score >= 70 and (improvement >= 0 or driver >= 50):
            return "Consider"
        if driver >= 60 and score < 70:
            return "Strategic driver; needs more data"
        return "Lower priority"

    def why(row):
        reasons = []
        if pd.notna(row.get("Directional Corr.", np.nan)) and abs(row.get("Directional Corr.", 0)) >= 0.60:
            reasons.append("strong shareholder-value relationship")
        if pd.notna(row.get("Lagged Corr.", np.nan)) and abs(row.get("Lagged Corr.", 0)) >= 0.50:
            reasons.append("meaningful lagged relationship")
        if row.get("Management Score", 0) >= 70:
            reasons.append("management emphasis")
        if row.get("Driver Evidence Score", 0) >= 50:
            reasons.append("linked to recurring management value drivers")
        if row.get("Stability", 0) >= 70:
            reasons.append("relatively stable history")
        if row.get("Design Fit", 0) >= 85:
            reasons.append("strong incentive design fit")
        return "; ".join(reasons) if reasons else "included for consultant review"

    df["Confidence"] = df.apply(confidence, axis=1)
    df["Recommendation"] = df.apply(recommendation, axis=1)
    df["Why It Matters"] = df.apply(why, axis=1)
    df["Data Status"] = np.where(
        df[[c for c in ["Current Corr.", "Lagged Corr.", "Rolling 3Y Corr."] if c in df.columns]].notna().any(axis=1),
        "Quantitatively tested",
        "Strategic evidence only"
    )

    cols = [
        "Metric", "Category", "Source Type", "Current Plan Metric", "Recommendation",
        "Evidence Score", "Confidence", "Improvement vs Current Avg",
        "Directional Corr.", "Lagged Corr.", "Rolling 3Y Corr.", "Payout Corr.",
        "Management Score", "Driver Evidence Score", "Design Fit", "Data Status",
        "Why It Matters"
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values(["Current Plan Metric", "Evidence Score"], ascending=[True, False])


def current_plan_summary(reco_df):
    if reco_df is None or reco_df.empty:
        return pd.DataFrame()
    return reco_df[reco_df["Current Plan Metric"] == True].sort_values("Evidence Score", ascending=False)


def candidate_summary(reco_df):
    if reco_df is None or reco_df.empty:
        return pd.DataFrame()
    cand = reco_df[reco_df["Current Plan Metric"] == False].copy()
    priority_order = {"Strong candidate": 0, "Consider": 1, "Strategic driver; needs more data": 2, "Lower priority": 3}
    cand["_priority"] = cand["Recommendation"].map(priority_order).fillna(9)
    return cand.sort_values(["_priority", "Evidence Score"], ascending=[True, False]).drop(columns=["_priority"])


def build_plan_score(reco_df, selected_metrics, weights):
    if reco_df is None or reco_df.empty or not selected_metrics:
        return pd.DataFrame(), np.nan
    rows, total_score, total_weight = [], 0, 0
    for m in selected_metrics:
        w = weights.get(m, 0)
        row = reco_df[reco_df["Metric"] == m]
        if row.empty:
            continue
        ev = float(row["Evidence Score"].iloc[0])
        total_score += ev * w / 100
        total_weight += w
        rows.append({
            "Metric": m,
            "Weight": w,
            "Evidence Score": ev,
            "Weighted Evidence": ev * w / 100,
            "Confidence": row["Confidence"].iloc[0] if "Confidence" in row.columns else "",
            "Recommendation": row["Recommendation"].iloc[0] if "Recommendation" in row.columns else "",
        })
    return pd.DataFrame(rows), total_score if total_weight == 100 else np.nan


def build_why_not_table(reco_df):
    if reco_df is None or reco_df.empty:
        return pd.DataFrame()
    rows = []
    for _, r in reco_df.iterrows():
        if r.get("Current Plan Metric", False):
            continue
        rec = r.get("Recommendation", "")
        conf = r.get("Confidence", "")
        data_status = r.get("Data Status", "")
        if rec in ["Strong candidate", "Consider"]:
            reason = "Candidate appears supportable based on the current evidence profile."
            action = "Evaluate in alternative design."
        elif rec == "Strategic driver; needs more data":
            reason = "Strategically important but annual quantitative history is incomplete or weaker."
            action = "Collect annual values before using as a formal incentive metric."
        elif conf == "Low":
            reason = "Evidence confidence is low."
            action = "Validate data quality and sample size."
        elif data_status != "Quantitatively tested":
            reason = "Metric has strategic evidence but has not been fully tested quantitatively."
            action = "Add annual history in Annual Values."
        else:
            reason = "Lower evidence score relative to the current candidate universe."
            action = "Keep as background evidence unless strategy requires it."
        rows.append({
            "Metric": r["Metric"],
            "Recommendation": rec,
            "Why Not / Risk": reason,
            "Next Action": action,
        })
    return pd.DataFrame(rows)


def build_recommendation_universe(score_df, current_metrics, driver_linkage_df=None):
    if score_df is None or score_df.empty:
        return pd.DataFrame()

    df = score_df.copy()
    current_set = {str(x) for x in current_metrics or []}
    current_avg = df[df["Metric"].astype(str).isin(current_set)]["Evidence Score"].mean()
    if pd.isna(current_avg):
        current_avg = df["Evidence Score"].mean()

    df["Current Plan Metric"] = df["Metric"].astype(str).isin(current_set)
    df["Improvement vs Current Avg"] = df["Evidence Score"] - current_avg

    def confidence(row):
        sample_proxy = 0
        for col in ["Current Corr.", "Lagged Corr.", "Rolling 3Y Corr.", "Payout Corr."]:
            if col in row and pd.notna(row[col]):
                sample_proxy += 2
        extraction = row.get("Extraction Confidence", 0)
        if sample_proxy >= 6 and extraction >= 70:
            return "High"
        if sample_proxy >= 4 or extraction >= 50:
            return "Medium"
        return "Low"

    def recommendation(row):
        if row["Current Plan Metric"]:
            return "Current metric"
        score = row["Evidence Score"]
        improvement = row["Improvement vs Current Avg"]
        driver = row.get("Driver Evidence Score", 0)
        if score >= 80 and improvement >= 5:
            return "Strong candidate"
        if score >= 70 and (improvement >= 0 or driver >= 50):
            return "Consider"
        if driver >= 60 and score < 70:
            return "Strategic driver; needs more data"
        return "Lower priority"

    def why(row):
        reasons = []
        if pd.notna(row.get("Directional Corr.", np.nan)) and abs(row.get("Directional Corr.", 0)) >= 0.60:
            reasons.append("strong shareholder-value relationship")
        if pd.notna(row.get("Lagged Corr.", np.nan)) and abs(row.get("Lagged Corr.", 0)) >= 0.50:
            reasons.append("meaningful lagged relationship")
        if row.get("Management Score", 0) >= 70:
            reasons.append("management emphasis")
        if row.get("Driver Evidence Score", 0) >= 50:
            reasons.append("linked to recurring management value drivers")
        if row.get("Stability", 0) >= 70:
            reasons.append("relatively stable history")
        if row.get("Design Fit", 0) >= 85:
            reasons.append("strong incentive design fit")
        return "; ".join(reasons) if reasons else "included for consultant review"

    df["Confidence"] = df.apply(confidence, axis=1)
    df["Recommendation"] = df.apply(recommendation, axis=1)
    df["Why It Matters"] = df.apply(why, axis=1)
    df["Data Status"] = np.where(
        df[[c for c in ["Current Corr.", "Lagged Corr.", "Rolling 3Y Corr."] if c in df.columns]].notna().any(axis=1),
        "Quantitatively tested",
        "Strategic evidence only"
    )

    cols = [
        "Metric", "Category", "Source Type", "Current Plan Metric", "Recommendation",
        "Evidence Score", "Confidence", "Improvement vs Current Avg",
        "Directional Corr.", "Lagged Corr.", "Rolling 3Y Corr.", "Payout Corr.",
        "Management Score", "Driver Evidence Score", "Design Fit", "Data Status",
        "Why It Matters"
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values(["Current Plan Metric", "Evidence Score"], ascending=[True, False])


def current_plan_summary(reco_df):
    if reco_df is None or reco_df.empty:
        return pd.DataFrame()
    return reco_df[reco_df["Current Plan Metric"] == True].sort_values("Evidence Score", ascending=False)


def candidate_summary(reco_df):
    if reco_df is None or reco_df.empty:
        return pd.DataFrame()
    cand = reco_df[reco_df["Current Plan Metric"] == False].copy()
    priority_order = {"Strong candidate": 0, "Consider": 1, "Strategic driver; needs more data": 2, "Lower priority": 3}
    cand["_priority"] = cand["Recommendation"].map(priority_order).fillna(9)
    return cand.sort_values(["_priority", "Evidence Score"], ascending=[True, False]).drop(columns=["_priority"])


def build_plan_score(reco_df, selected_metrics, weights):
    if reco_df is None or reco_df.empty or not selected_metrics:
        return pd.DataFrame(), np.nan
    rows, total_score, total_weight = [], 0, 0
    for m in selected_metrics:
        w = weights.get(m, 0)
        row = reco_df[reco_df["Metric"] == m]
        if row.empty:
            continue
        ev = float(row["Evidence Score"].iloc[0])
        total_score += ev * w / 100
        total_weight += w
        rows.append({
            "Metric": m,
            "Weight": w,
            "Evidence Score": ev,
            "Weighted Evidence": ev * w / 100,
            "Confidence": row["Confidence"].iloc[0] if "Confidence" in row.columns else "",
            "Recommendation": row["Recommendation"].iloc[0] if "Recommendation" in row.columns else "",
        })
    return pd.DataFrame(rows), total_score if total_weight == 100 else np.nan


def build_why_not_table(reco_df):
    if reco_df is None or reco_df.empty:
        return pd.DataFrame()
    rows = []
    for _, r in reco_df.iterrows():
        if r.get("Current Plan Metric", False):
            continue
        rec = r.get("Recommendation", "")
        conf = r.get("Confidence", "")
        data_status = r.get("Data Status", "")
        if rec in ["Strong candidate", "Consider"]:
            reason = "Candidate appears supportable based on the current evidence profile."
            action = "Evaluate in alternative design."
        elif rec == "Strategic driver; needs more data":
            reason = "Strategically important but annual quantitative history is incomplete or weaker."
            action = "Collect annual values before using as a formal incentive metric."
        elif conf == "Low":
            reason = "Evidence confidence is low."
            action = "Validate data quality and sample size."
        elif data_status != "Quantitatively tested":
            reason = "Metric has strategic evidence but has not been fully tested quantitatively."
            action = "Add annual history in Annual Values."
        else:
            reason = "Lower evidence score relative to the current candidate universe."
            action = "Keep as background evidence unless strategy requires it."
        rows.append({
            "Metric": r["Metric"],
            "Recommendation": rec,
            "Why Not / Risk": reason,
            "Next Action": action,
        })
    return pd.DataFrame(rows)



def classify_metric_readiness(row):
    has_quant = False
    for col in ["Current Corr.", "Lagged Corr.", "Rolling 3Y Corr.", "Payout Corr."]:
        if col in row and pd.notna(row[col]):
            has_quant = True
    if has_quant:
        return "Ready"
    if row.get("Driver Evidence Score", 0) >= 50 or row.get("Management Score", 0) >= 70:
        return "Needs annual values"
    return "Review"


def build_candidate_metric_objects(score_df, current_metrics):
    if score_df is None or score_df.empty:
        return pd.DataFrame()
    df = build_recommendation_universe(score_df, current_metrics, st.session_state.driver_linkage_df).copy()
    df["Readiness"] = df.apply(classify_metric_readiness, axis=1)

    def action(row):
        if row.get("Current Plan Metric", False):
            return "Retain / review"
        rec = row.get("Recommendation", "")
        readiness = row.get("Readiness", "")
        if rec == "Strong candidate" and readiness == "Ready":
            return "Add / test in plan"
        if rec in ["Strong candidate", "Consider"] and readiness == "Ready":
            return "Consider in alternative"
        if readiness == "Needs annual values":
            return "Collect annual values"
        return "Keep as background evidence"

    def evidence_bucket(row):
        parts = []
        if pd.notna(row.get("Directional Corr.", np.nan)):
            parts.append("Financial")
        if row.get("Management Score", 0) > 0:
            parts.append("Management")
        if row.get("Driver Evidence Score", 0) > 0:
            parts.append("Driver")
        if row.get("Design Fit", 0) > 0:
            parts.append("Design")
        return " + ".join(parts) if parts else "Limited"

    def role(row):
        cat = str(row.get("Category", ""))
        metric = str(row.get("Metric", "")).lower()
        if "capital" in cat.lower() or "roic" in metric:
            return "Capital discipline"
        if "cash" in cat.lower() or "cash" in metric or "fcf" in metric:
            return "Cash generation"
        if "profit" in cat.lower() or "ebitda" in metric or "margin" in metric:
            return "Profitability"
        if "growth" in cat.lower() or "revenue" in metric or "sales" in metric:
            return "Growth"
        if "commercial" in cat.lower() or "pricing" in metric:
            return "Commercial execution"
        if "operations" in cat.lower() or "productivity" in metric or "cost" in metric:
            return "Operational execution"
        return "Other"

    df["Recommended Action"] = df.apply(action, axis=1)
    df["Evidence Sources"] = df.apply(evidence_bucket, axis=1)
    df["Portfolio Role"] = df.apply(role, axis=1)

    cols = [
        "Metric", "Category", "Portfolio Role", "Current Plan Metric",
        "Recommendation", "Recommended Action", "Readiness", "Confidence",
        "Evidence Score", "Improvement vs Current Avg", "Evidence Sources",
        "Why It Matters", "Directional Corr.", "Lagged Corr.", "Rolling 3Y Corr.",
        "Payout Corr.", "Management Score", "Driver Evidence Score", "Design Fit",
        "Data Status"
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values(["Current Plan Metric", "Evidence Score"], ascending=[True, False])


def build_recommended_plan(candidate_objects, current_metrics, max_metrics=4):
    if candidate_objects is None or candidate_objects.empty:
        return pd.DataFrame()
    rows = []
    used_roles = set()
    current = candidate_objects[candidate_objects["Current Plan Metric"] == True].copy()
    candidates = candidate_objects[candidate_objects["Current Plan Metric"] == False].copy()

    if not current.empty:
        keep = current.sort_values("Evidence Score", ascending=False).head(1)
        for _, r in keep.iterrows():
            rows.append({
                "Metric": r["Metric"],
                "Role": r.get("Portfolio Role", ""),
                "Reason": "Retains continuity with the current plan while preserving a metric with the strongest current-plan evidence.",
                "Evidence Score": r["Evidence Score"],
                "Confidence": r.get("Confidence", ""),
                "Recommendation": "Retain"
            })
            used_roles.add(r.get("Portfolio Role", ""))

    pool = candidates[candidates["Recommended Action"].isin(["Add / test in plan", "Consider in alternative"])].copy()
    pool = pool.sort_values("Evidence Score", ascending=False)
    for _, r in pool.iterrows():
        if len(rows) >= max_metrics:
            break
        role = r.get("Portfolio Role", "")
        if role in used_roles and len(rows) < max_metrics - 1:
            continue
        rows.append({
            "Metric": r["Metric"],
            "Role": role,
            "Reason": r.get("Why It Matters", "Strong evidence profile."),
            "Evidence Score": r["Evidence Score"],
            "Confidence": r.get("Confidence", ""),
            "Recommendation": r.get("Recommendation", "")
        })
        used_roles.add(role)

    if len(rows) < min(max_metrics, len(candidate_objects)):
        existing = {r["Metric"] for r in rows}
        for _, r in pool.iterrows():
            if len(rows) >= max_metrics:
                break
            if r["Metric"] in existing:
                continue
            rows.append({
                "Metric": r["Metric"],
                "Role": r.get("Portfolio Role", ""),
                "Reason": r.get("Why It Matters", "Strong evidence profile."),
                "Evidence Score": r["Evidence Score"],
                "Confidence": r.get("Confidence", ""),
                "Recommendation": r.get("Recommendation", "")
            })
            existing.add(r["Metric"])

    plan = pd.DataFrame(rows)
    if plan.empty:
        return plan
    n = len(plan)
    if n == 1:
        weights = [100]
    elif n == 2:
        weights = [50, 50]
    elif n == 3:
        weights = [40, 30, 30]
    else:
        weights = [35, 25, 20, 20][:n]
        if sum(weights) != 100:
            weights[0] += 100 - sum(weights)
    plan["Suggested Weight"] = weights[:len(plan)]
    plan["Weighted Evidence"] = plan["Evidence Score"] * plan["Suggested Weight"] / 100
    return plan


def build_executive_assessment(candidate_objects, recommended_plan):
    if candidate_objects is None or candidate_objects.empty:
        return {"current_score": np.nan, "best_candidate": "n/a", "strong_count": 0, "needs_data": 0, "recommended_plan_score": np.nan}
    current = candidate_objects[candidate_objects["Current Plan Metric"] == True]
    current_score = current["Evidence Score"].mean() if not current.empty else np.nan
    best = candidate_objects[candidate_objects["Current Plan Metric"] == False].sort_values("Evidence Score", ascending=False)
    best_candidate = best.iloc[0]["Metric"] if not best.empty else "n/a"
    strong_count = int(candidate_objects["Recommendation"].isin(["Strong candidate", "Consider"]).sum())
    needs_data = int((candidate_objects["Readiness"] == "Needs annual values").sum())
    rec_score = recommended_plan["Weighted Evidence"].sum() if recommended_plan is not None and not recommended_plan.empty else np.nan
    return {"current_score": current_score, "best_candidate": best_candidate, "strong_count": strong_count, "needs_data": needs_data, "recommended_plan_score": rec_score}


def build_recommendation_narrative(company, candidate_objects, recommended_plan):
    if candidate_objects is None or candidate_objects.empty:
        return "No recommendation narrative is available yet."
    assessment = build_executive_assessment(candidate_objects, recommended_plan)
    current_score = assessment["current_score"]
    rec_score = assessment["recommended_plan_score"]
    best_candidate = assessment["best_candidate"]
    top_drivers = ""
    if "driver_summary_df" in st.session_state and not st.session_state.driver_summary_df.empty:
        top_drivers = ", ".join(st.session_state.driver_summary_df.head(4)["Driver"].astype(str).tolist())
    plan_metrics = ", ".join(recommended_plan["Metric"].astype(str).tolist()) if recommended_plan is not None and not recommended_plan.empty else "not yet available"
    lines = [f"{company} Recommendation Workspace", ""]
    if pd.notna(current_score):
        lines.append(f"The current plan has an average evidence score of {current_score:.1f}/100.")
    if pd.notna(rec_score):
        delta = rec_score - current_score if pd.notna(current_score) else np.nan
        if pd.notna(delta):
            lines.append(f"The initial recommended design has an evidence score of {rec_score:.1f}/100, representing a {delta:+.1f} point change versus the current plan average.")
        else:
            lines.append(f"The initial recommended design has an evidence score of {rec_score:.1f}/100.")
    lines.append(f"The strongest alternative candidate currently surfaced by the evidence model is {best_candidate}.")
    if top_drivers:
        lines.append(f"Management value-driver evidence highlights {top_drivers}, which should inform metric selection and the committee narrative.")
    lines.append(f"The initial recommended plan includes: {plan_metrics}.")
    lines.append("")
    lines.append("Recommendations are directional and should be reviewed with consultant judgment, particularly where annual data is incomplete or where metrics may overlap.")
    return "\\n".join(lines)




# --------------------------------------------------------------------
# Recommendation Workspace Override
# Fixes contradictory recommendations:
# - Top alternative must be a plan-eligible tested alternative, not just the highest non-current row.
# - Initial recommended plan must include a real alternative when one improves on current plan.
# - Do not generate a one-metric 100% plan unless only one metric is available.
# --------------------------------------------------------------------

def _numeric_value(row, col, default=np.nan):
    try:
        val = row.get(col, default)
        return float(val) if pd.notna(val) else default
    except Exception:
        return default

def _is_quantitatively_tested(row):
    for col in ["Directional Corr.", "Lagged Corr.", "Rolling 3Y Corr.", "Payout Corr."]:
        if col in row and pd.notna(row[col]):
            return True
    return False

def classify_metric_readiness(row):
    if _is_quantitatively_tested(row):
        return "Ready"
    if row.get("Driver Evidence Score", 0) >= 50 or row.get("Management Score", 0) >= 70:
        return "Needs annual values"
    return "Review"

def build_candidate_metric_objects(score_df, current_metrics):
    """
    Candidate Metric Object model:
    every current metric, Capital IQ metric, and management driver is placed into
    one evidence framework. This version separates:
    - evidence score
    - plan eligibility
    - recommendation action
    so the workspace does not contradict itself.
    """
    if score_df is None or score_df.empty:
        return pd.DataFrame()

    df = build_recommendation_universe(score_df, current_metrics, st.session_state.driver_linkage_df).copy()
    current_set = {str(x) for x in current_metrics or []}
    current_avg = df[df["Metric"].astype(str).isin(current_set)]["Evidence Score"].mean()
    if pd.isna(current_avg):
        current_avg = df["Evidence Score"].mean()

    df["Current Plan Metric"] = df["Metric"].astype(str).isin(current_set)
    df["Improvement vs Current Avg"] = df["Evidence Score"] - current_avg
    df["Readiness"] = df.apply(classify_metric_readiness, axis=1)

    def role(row):
        cat = str(row.get("Category", ""))
        metric = str(row.get("Metric", "")).lower()
        if "capital" in cat.lower() or "roic" in metric:
            return "Capital discipline"
        if "cash" in cat.lower() or "cash" in metric or "fcf" in metric:
            return "Cash generation"
        if "profit" in cat.lower() or "ebitda" in metric or "margin" in metric or "operating income" in metric:
            return "Profitability"
        if "growth" in cat.lower() or "revenue" in metric or "sales" in metric:
            return "Growth"
        if "commercial" in cat.lower() or "pricing" in metric or "volume" in metric or "foreign exchange" in metric:
            return "Commercial execution"
        if "operations" in cat.lower() or "productivity" in metric or "cost" in metric or "inflation" in metric:
            return "Operational execution"
        return "Other"

    def evidence_bucket(row):
        parts = []
        if _is_quantitatively_tested(row):
            parts.append("Financial")
        if row.get("Management Score", 0) > 0:
            parts.append("Management")
        if row.get("Driver Evidence Score", 0) > 0:
            parts.append("Driver")
        if row.get("Design Fit", 0) > 0:
            parts.append("Design")
        return " + ".join(parts) if parts else "Limited"

    def plan_eligible(row):
        if row.get("Current Plan Metric", False):
            return True
        if row.get("Readiness") != "Ready":
            return False
        # A metric can be tested in an alternative if it improves on current or is close enough
        # to merit consultant review. This prevents arbitrary high thresholds from suppressing
        # useful alternatives such as Revenue in small samples.
        return row.get("Improvement vs Current Avg", -999) >= 0

    def action(row):
        if row.get("Current Plan Metric", False):
            return "Current plan metric"
        if row.get("Readiness") == "Needs annual values":
            return "Collect annual values"
        if row.get("Readiness") != "Ready":
            return "Background evidence"
        improvement = row.get("Improvement vs Current Avg", 0)
        score = row.get("Evidence Score", 0)
        if improvement >= 5:
            return "Add / test in plan"
        if improvement >= 0:
            return "Consider in alternative"
        if score >= current_avg - 2:
            return "Monitor"
        return "Lower priority"

    def recommendation(row):
        if row.get("Current Plan Metric", False):
            return "Current metric"
        if row.get("Readiness") == "Needs annual values":
            return "Strategic driver; needs more data"
        if row.get("Readiness") != "Ready":
            return "Lower priority"
        improvement = row.get("Improvement vs Current Avg", 0)
        if improvement >= 5:
            return "Strong candidate"
        if improvement >= 0:
            return "Consider"
        return "Lower priority"

    def why(row):
        reasons = []
        improvement = row.get("Improvement vs Current Avg", np.nan)
        if row.get("Current Plan Metric", False):
            reasons.append("current plan continuity")
        if pd.notna(improvement) and not row.get("Current Plan Metric", False):
            if improvement > 0:
                reasons.append(f"{improvement:+.1f} evidence-score improvement versus current-plan average")
            else:
                reasons.append(f"{improvement:+.1f} evidence-score difference versus current-plan average")
        if pd.notna(row.get("Directional Corr.", np.nan)) and abs(row.get("Directional Corr.", 0)) >= 0.50:
            reasons.append("shareholder-value relationship")
        if pd.notna(row.get("Lagged Corr.", np.nan)) and abs(row.get("Lagged Corr.", 0)) >= 0.50:
            reasons.append("lagged relationship")
        if row.get("Management Score", 0) >= 70:
            reasons.append("management emphasis")
        if row.get("Driver Evidence Score", 0) >= 50:
            reasons.append("linked to recurring management value drivers")
        return "; ".join(reasons) if reasons else "included for consultant review"

    df["Portfolio Role"] = df.apply(role, axis=1)
    df["Evidence Sources"] = df.apply(evidence_bucket, axis=1)
    df["Plan Eligible"] = df.apply(plan_eligible, axis=1)
    df["Recommended Action"] = df.apply(action, axis=1)
    df["Recommendation"] = df.apply(recommendation, axis=1)
    df["Why It Matters"] = df.apply(why, axis=1)
    df["Data Status"] = np.where(df["Readiness"].eq("Ready"), "Quantitatively tested", "Strategic evidence only")

    cols = [
        "Metric", "Category", "Portfolio Role", "Current Plan Metric", "Plan Eligible",
        "Recommendation", "Recommended Action", "Readiness", "Confidence",
        "Evidence Score", "Improvement vs Current Avg", "Evidence Sources",
        "Why It Matters", "Directional Corr.", "Lagged Corr.", "Rolling 3Y Corr.",
        "Payout Corr.", "Management Score", "Driver Evidence Score", "Design Fit",
        "Data Status"
    ]
    cols = [c for c in cols if c in df.columns]
    return df[cols].sort_values(["Current Plan Metric", "Plan Eligible", "Evidence Score"], ascending=[True, False, False])

def build_recommended_plan(candidate_objects, current_metrics, max_metrics=4):
    """
    Creates a non-contradictory starting recommendation.
    Rule:
    - Keep current-plan continuity metrics when available.
    - Include at least one positive-improvement tested alternative when one exists.
    - Do not show a one-metric 100% design unless there is literally only one eligible metric.
    """
    if candidate_objects is None or candidate_objects.empty:
        return pd.DataFrame()

    current = candidate_objects[candidate_objects["Current Plan Metric"] == True].copy()
    alternatives = candidate_objects[
        (candidate_objects["Current Plan Metric"] == False) &
        (candidate_objects["Readiness"] == "Ready") &
        (candidate_objects["Improvement vs Current Avg"] >= 0)
    ].copy().sort_values(["Improvement vs Current Avg", "Evidence Score"], ascending=[False, False])

    rows = []
    existing = set()

    # Include up to two current plan metrics for continuity, not just one.
    if not current.empty:
        for _, r in current.sort_values("Evidence Score", ascending=False).head(2).iterrows():
            rows.append({
                "Metric": r["Metric"],
                "Role": r.get("Portfolio Role", ""),
                "Reason": "Current plan continuity; retained for comparison and potential transition design.",
                "Evidence Score": r["Evidence Score"],
                "Confidence": r.get("Confidence", ""),
                "Recommendation": "Retain / review",
                "Improvement vs Current Avg": r.get("Improvement vs Current Avg", 0),
                "Current Plan Metric": True
            })
            existing.add(r["Metric"])

    # Add positive-improvement alternatives.
    for _, r in alternatives.iterrows():
        if len(rows) >= max_metrics:
            break
        if r["Metric"] in existing:
            continue
        rows.append({
            "Metric": r["Metric"],
            "Role": r.get("Portfolio Role", ""),
            "Reason": r.get("Why It Matters", "Positive tested alternative."),
            "Evidence Score": r["Evidence Score"],
            "Confidence": r.get("Confidence", ""),
            "Recommendation": r.get("Recommended Action", ""),
            "Improvement vs Current Avg": r.get("Improvement vs Current Avg", np.nan),
            "Current Plan Metric": False
        })
        existing.add(r["Metric"])

    # If there are no positive alternatives, show a current-plan review instead of pretending
    # an alternative plan exists.
    if not rows:
        return pd.DataFrame()

    plan = pd.DataFrame(rows)

    # If plan has only one current metric but eligible alternatives exist, force the top one in.
    if len(plan) == 1 and not alternatives.empty and bool(plan.iloc[0]["Current Plan Metric"]):
        r = alternatives.iloc[0]
        if r["Metric"] not in existing:
            plan = pd.concat([plan, pd.DataFrame([{
                "Metric": r["Metric"],
                "Role": r.get("Portfolio Role", ""),
                "Reason": r.get("Why It Matters", "Positive tested alternative."),
                "Evidence Score": r["Evidence Score"],
                "Confidence": r.get("Confidence", ""),
                "Recommendation": r.get("Recommended Action", ""),
                "Improvement vs Current Avg": r.get("Improvement vs Current Avg", np.nan),
                "Current Plan Metric": False
            }])], ignore_index=True)

    n = len(plan)
    if n == 1:
        weights = [100]
    elif n == 2:
        weights = [50, 50]
    elif n == 3:
        weights = [40, 30, 30]
    elif n == 4:
        weights = [30, 25, 25, 20]
    else:
        base = int(100 / n)
        weights = [base] * n
        weights[0] += 100 - sum(weights)

    plan["Suggested Weight"] = weights[:len(plan)]
    plan["Weighted Evidence"] = plan["Evidence Score"] * plan["Suggested Weight"] / 100
    return plan

def build_executive_assessment(candidate_objects, recommended_plan):
    if candidate_objects is None or candidate_objects.empty:
        return {
            "current_score": np.nan,
            "best_candidate": "n/a",
            "strong_count": 0,
            "needs_data": 0,
            "recommended_plan_score": np.nan,
        }

    current = candidate_objects[candidate_objects["Current Plan Metric"] == True]
    current_score = current["Evidence Score"].mean() if not current.empty else np.nan

    eligible = candidate_objects[
        (candidate_objects["Current Plan Metric"] == False) &
        (candidate_objects["Readiness"] == "Ready")
    ].copy()
    if not eligible.empty:
        eligible = eligible.sort_values(["Improvement vs Current Avg", "Evidence Score"], ascending=[False, False])
        best_candidate = eligible.iloc[0]["Metric"]
    else:
        best_candidate = "n/a"

    strong_count = int(candidate_objects["Recommended Action"].isin(["Add / test in plan", "Consider in alternative"]).sum())
    needs_data = int((candidate_objects["Readiness"] == "Needs annual values").sum())
    rec_score = recommended_plan["Weighted Evidence"].sum() if recommended_plan is not None and not recommended_plan.empty else np.nan
    return {
        "current_score": current_score,
        "best_candidate": best_candidate,
        "strong_count": strong_count,
        "needs_data": needs_data,
        "recommended_plan_score": rec_score,
    }

def build_recommendation_narrative(company, candidate_objects, recommended_plan):
    if candidate_objects is None or candidate_objects.empty:
        return "No recommendation narrative is available yet."

    assessment = build_executive_assessment(candidate_objects, recommended_plan)
    current_score = assessment["current_score"]
    rec_score = assessment["recommended_plan_score"]
    best_candidate = assessment["best_candidate"]

    plan_metrics = ", ".join(recommended_plan["Metric"].astype(str).tolist()) if recommended_plan is not None and not recommended_plan.empty else "not yet available"

    alt_count = 0
    if recommended_plan is not None and not recommended_plan.empty and "Current Plan Metric" in recommended_plan.columns:
        alt_count = int((recommended_plan["Current Plan Metric"] == False).sum())

    lines = [f"{company} Recommendation Workspace", ""]
    if pd.notna(current_score):
        lines.append(f"The current plan has an average evidence score of {current_score:.1f}/100.")
    if best_candidate != "n/a":
        lines.append(f"The strongest tested alternative currently surfaced by the evidence model is {best_candidate}.")
    if pd.notna(rec_score):
        if alt_count > 0:
            delta = rec_score - current_score if pd.notna(current_score) else np.nan
            if pd.notna(delta):
                lines.append(f"The initial alternative design has an evidence score of {rec_score:.1f}/100, representing a {delta:+.1f} point change versus the current plan average.")
            else:
                lines.append(f"The initial alternative design has an evidence score of {rec_score:.1f}/100.")
        else:
            lines.append(f"The system did not identify a tested alternative that clearly improves the current-plan evidence score. The displayed plan should be treated as current-plan review, not a new recommendation.")
    lines.append(f"The initial design includes: {plan_metrics}.")

    if "driver_summary_df" in st.session_state and not st.session_state.driver_summary_df.empty:
        top_drivers = ", ".join(st.session_state.driver_summary_df.head(4)["Driver"].astype(str).tolist())
        lines.append(f"Management value-driver evidence highlights {top_drivers}, which should inform metric selection and the committee narrative.")

    lines.append("")
    lines.append("Recommendations are directional and should be reviewed with consultant judgment, particularly where annual data is incomplete or where metrics overlap.")
    return "\n".join(lines)


def infer_current_plan_defaults(perf_df, perf_year, ready_metrics):
    """
    Current incentive metrics should come from the original uploaded performance/current-plan file,
    not from Capital IQ or bridge-driver columns that are added later.
    """
    if perf_df is None or perf_df.empty:
        return ready_metrics[:min(2, len(ready_metrics))]

    original_cols = [c for c in perf_df.columns if c != perf_year and c in ready_metrics]

    def is_current_plan_like(c):
        name = str(c).lower()
        if name.startswith("iq_"):
            return False
        if name in ["pricing", "volume/mix", "inflation", "foreign exchange", "fx", "other"]:
            return False
        return (
            "actual" in name
            or "payout" not in name and any(term in name for term in ["ebitda", "cash flow", "eps", "revenue", "sales", "roic"])
        )

    preferred = [c for c in original_cols if is_current_plan_like(c)]
    fallback = [c for c in original_cols if not str(c).lower().startswith("iq_")]
    defaults = preferred or fallback or ready_metrics[:min(2, len(ready_metrics))]
    return defaults[:min(2, len(defaults))]

def sample_perf():
    return pd.DataFrame({"Year":list(range(2016,2026)),"Adjusted EBITDA Actual":[714,716.8,931.2,1030.8,1070,1041,1600,1876,1693,1372],"Cash Flow Actual":[320,375.6,471.66,544.995,520,580,743,808,672,467]})
def sample_payout():
    return pd.DataFrame({"Year":list(range(2016,2026)),"Actual Payout":["55%","50%","100%","150%","100%","64%","200%","153%","26%","0%"]})
def sample_value():
    return pd.DataFrame({"Year":list(range(2016,2026)),"IQ_MARKETCAP":[3963,4785,3302,4833,4587,5988,6833,7544,8152,4445],"IQ_CLOSEPRICE_ADJ":[10.30,13.04,9.18,14.67,15.25,17.83,20.66,23.28,26.01,14.74]})

for key in ["perf_df","payout_df","value_df","mgmt_df","driver_df","driver_summary_df","driver_linkage_df","mapping_df","candidate_df","metric_objects","master_df","score_df"]:
    if key not in st.session_state: st.session_state[key]=pd.DataFrame()
if "current_metrics" not in st.session_state: st.session_state.current_metrics=[]

st.sidebar.title("Design Lab V3")
company=st.sidebar.text_input("Company",value="Graphic Packaging")
page=st.sidebar.radio("Workflow",["1. Import Data","2. Management Metrics","2A. Management Value Drivers","3. Metric Catalog & Capital IQ","4. Annual Values","5. Build Metric Objects","6. Evidence Engine","7. Design Lab","8. Committee Summary"])

if "driver_df" in st.session_state and not st.session_state.driver_df.empty:
    st.sidebar.success(f"Driver data saved: {len(st.session_state.driver_df)} rows")

st.title("Executive Incentive Design Lab V3")
st.caption("Metric Object Engine | Transformation Rules | Current vs Alternative Incentive Metrics | HOTFIX: Recommendation functions loaded")

if page=="1. Import Data":
    st.header("1. Import Data")
    c1,c2,c3=st.columns(3)
    with c1:
        st.subheader("Current Plan / Performance")
        m=st.radio("Method",["Paste","Upload","Sample"],horizontal=True,key="perf_method")
        df=parse_table(st.text_area("Paste performance data",height=200,key="perf_txt")) if m=="Paste" else read_file(st.file_uploader("Upload CSV/XLSX",type=["csv","xlsx","xls"],key="perf_file")) if m=="Upload" else sample_perf()
        if not df.empty: st.session_state.perf_df=df; st.dataframe(df,use_container_width=True)
    with c2:
        st.subheader("Payout History")
        m=st.radio("Method",["Paste","Upload","Sample"],horizontal=True,key="pay_method")
        df=parse_table(st.text_area("Paste payout data",height=200,key="pay_txt")) if m=="Paste" else read_file(st.file_uploader("Upload CSV/XLSX",type=["csv","xlsx","xls"],key="pay_file")) if m=="Upload" else sample_payout()
        if not df.empty: st.session_state.payout_df=df; st.dataframe(df,use_container_width=True)
    with c3:
        st.subheader("Shareholder Value")
        m=st.radio("Method",["Paste","Upload","Sample"],horizontal=True,key="val_method")
        df=parse_table(st.text_area("Paste shareholder value",height=200,key="val_txt")) if m=="Paste" else read_file(st.file_uploader("Upload CSV/XLSX",type=["csv","xlsx","xls"],key="val_file")) if m=="Upload" else sample_value()
        if not df.empty: st.session_state.value_df=df; st.dataframe(df,use_container_width=True)

elif page=="2. Management Metrics":
    st.header("2. Management Metrics")
    c1,c2=st.columns(2)
    with c1:
        st.subheader("Manual Metric Library")
        m=st.radio("Method",["Paste","Upload","Sample"],horizontal=True,key="mgmt_method")
        df=parse_table(st.text_area("Paste metric library",height=220,key="mgmt_txt")) if m=="Paste" else read_file(st.file_uploader("Upload metric library",type=["csv","xlsx","xls"],key="mgmt_file")) if m=="Upload" else pd.DataFrame({"Metric":["Adjusted EBITDA","Cash Flow Before Debt Reduction","Revenue","EBITDA","ROIC","Free Cash Flow","Pricing","Productivity Savings","Cost Savings","Safety"],"Category":["Profitability","Cash Flow","Growth","Profitability","Capital Efficiency","Cash Flow","Commercial","Operations","Operations","Human Capital"],"Management Emphasis":[5,5,5,5,4,4,4,4,4,3]})
        if not df.empty: st.dataframe(df,use_container_width=True)
    with c2:
        st.subheader("Extract from Documents")
        files=st.file_uploader("Upload PDFs/DOCX/TXT",type=["pdf","docx","txt"],accept_multiple_files=True)
        ext=pd.DataFrame()
        if files:
            text=""; 
            for f in files: text += "\n"+extract_text(f)
            ext=discover_metrics(text)
            if not ext.empty: st.dataframe(ext,use_container_width=True)
    frames=[]
    if "df" in locals() and not df.empty and "Metric" in df.columns: frames.append(df)
    if not ext.empty: frames.append(ext)
    if frames:
        mgmt=pd.concat(frames,ignore_index=True).drop_duplicates("Metric")
        if "Category" not in mgmt.columns: mgmt["Category"]=mgmt["Metric"].map(lambda x: catalog_match(x)["Category"])
        if "Management Emphasis" not in mgmt.columns: mgmt["Management Emphasis"]=3
        if "Mention Count" not in mgmt.columns: mgmt["Mention Count"]=0
        if "Extraction Confidence" not in mgmt.columns: mgmt["Extraction Confidence"]=0
        st.session_state.mgmt_df=st.data_editor(mgmt,use_container_width=True,num_rows="dynamic")
        download_df(st.session_state.mgmt_df,"Download management metrics","management_metrics.csv")


elif page=="2A. Management Value Drivers":
    st.header("2A. Management Value Drivers")
    st.info("Extract bridge-table drivers such as Price, Volume/Mix, Inflation, FX, Productivity, and Cost Savings from 10-Ks and investor materials.")

    st.markdown("""
This module captures a different evidence layer than Capital IQ. Capital IQ provides standardized financial outcomes. 
10-K bridge tables explain the operating drivers management says caused those outcomes.
""")

    files = st.file_uploader("Upload 10-Ks / annual reports / investor materials", type=["pdf","docx","txt"], accept_multiple_files=True, key="driver_docs")
    manual = st.text_area(
        "Optional: paste management driver history manually",
        height=160,
        placeholder="Wide format example:\nYear\tPrice\tVolume/Mix\tInflation\tFX\tOther\n2023\t556\t-204\t-175\t-11\t102\n\nOr long format:\nYear\tDriver\tImpact\n2023\tPrice\t556"
    )

    driver_df = pd.DataFrame()
    if files:
        with st.spinner("Extracting bridge tables and management drivers..."):
            driver_df = extract_management_value_drivers(files)

    manual_df = parse_table(manual)
    if not manual_df.empty:
        normalized_manual = normalize_manual_driver_table(manual_df)
        if not normalized_manual.empty:
            driver_df = pd.concat([driver_df, normalized_manual], ignore_index=True)
            st.success(f"Recognized {len(normalized_manual)} driver-year observations from the pasted table.")
        else:
            st.warning("Could not recognize the pasted table. Use either long format Year / Driver / Impact, or wide format Year / Price / Volume-Mix / Inflation / FX / Other.")

    if driver_df.empty:
        if not st.session_state.driver_df.empty:
            st.info("Using saved management driver history from this session.")
            driver_df = st.session_state.driver_df.copy()
        else:
            st.warning("No structured driver data found yet. Use the manual paste format or upload reports with bridge/variance tables.")

    if not driver_df.empty:
        driver_df["Driver"] = driver_df["Driver"].map(canonical_driver)
        driver_df = st.data_editor(driver_df, use_container_width=True, num_rows="dynamic", key="driver_editor")

        summary = summarize_value_drivers(driver_df)
        linkages = driver_to_metric_linkages(summary)

        st.session_state.driver_df = driver_df.copy()
        st.session_state.driver_summary_df = summary.copy()
        st.session_state.driver_linkage_df = linkages.copy()

        st.success(
            f"Saved {len(driver_df)} driver-year observations, "
            f"{len(summary)} driver summaries, and {len(linkages)} driver-to-metric linkages for this session."
        )

        download_df(driver_df, "Download management driver history", "management_value_driver_history.csv")

        st.subheader("Driver Summary")
        st.dataframe(summary, use_container_width=True)
        download_df(summary, "Download driver summary", "management_driver_summary.csv")

        st.subheader("Driver-to-Metric Linkages")
        st.dataframe(linkages, use_container_width=True)
        download_df(linkages, "Download driver-to-metric linkages", "driver_metric_linkages.csv")

        if not summary.empty:
            st.success(
                "Most prominent management drivers: "
                + ", ".join(summary.head(5)["Driver"].tolist())
                + ". These should inform the candidate metric universe and committee narrative."
            )


elif page=="3. Metric Catalog & Capital IQ":
    st.header("3. Metric Catalog & Capital IQ")
    if not st.session_state.driver_summary_df.empty:
        st.success("Management value driver evidence is available and will be included in the metric mapping/evidence engine.")
        with st.expander("Saved management value drivers"):
            st.dataframe(st.session_state.driver_summary_df, use_container_width=True)
            if not st.session_state.driver_linkage_df.empty:
                st.dataframe(st.session_state.driver_linkage_df, use_container_width=True)
    mgmt=st.session_state.mgmt_df
    metrics=mgmt["Metric"].dropna().astype(str).tolist() if not mgmt.empty and "Metric" in mgmt.columns else []
    if not st.session_state.driver_linkage_df.empty:
        metrics += st.session_state.driver_linkage_df["Linked Financial / Incentive Metric"].dropna().astype(str).tolist()
    if "driver_summary_df" in st.session_state and not st.session_state.driver_summary_df.empty:
        metrics += st.session_state.driver_summary_df["Driver"].dropna().astype(str).tolist()
        metrics += ["Operating Income"]
    add=st.text_area("Add metrics to map, one per line",height=120)
    metrics += [x.strip() for x in add.splitlines() if x.strip()]
    metrics=list(dict.fromkeys(metrics))
    if not metrics: st.warning("Add management metrics first."); st.stop()
    mapping=st.data_editor(map_metrics(metrics),use_container_width=True,num_rows="dynamic",key="mapping_editor")
    st.session_state.mapping_df=mapping
    st.subheader("Metric Mapping and Default Rules"); st.dataframe(mapping,use_container_width=True)
    download_df(mapping,"Download metric mapping","metric_mapping.csv")
    fields=capiq_fields(mapping)
    st.subheader("Capital IQ Field List"); st.dataframe(fields,use_container_width=True); download_df(fields,"Download Capital IQ field list","capital_iq_fields.csv")
    with st.expander("Built-in Metric Catalog"):
        catalog=pd.DataFrame(METRIC_CATALOG); st.dataframe(catalog,use_container_width=True); download_df(catalog,"Download full metric catalog","metric_catalog.csv")

elif page=="4. Annual Values":
    st.header("4. Annual Values")
    m=st.radio("Method",["Paste","Upload","Blank template"],horizontal=True)
    if m=="Paste": df=parse_table(st.text_area("Paste annual values",height=240))
    elif m=="Upload": df=read_file(st.file_uploader("Upload CSV/XLSX",type=["csv","xlsx","xls"]))
    else:
        years=list(range(2016,2026))
        if not st.session_state.perf_df.empty:
            y=infer_year_col(st.session_state.perf_df); years=sorted(standardize_year(st.session_state.perf_df[y]).dropna().astype(int).unique().tolist())
        fields=capiq_fields(st.session_state.mapping_df)["Capital IQ Field"].tolist() if not st.session_state.mapping_df.empty else []
        df=pd.DataFrame({"Year":years})
        for f in fields: df[f]=""
    if not df.empty:
        st.session_state.candidate_df=st.data_editor(df,use_container_width=True,num_rows="dynamic")
        download_df(st.session_state.candidate_df,"Download annual values","annual_values.csv")

def build_context():
    perf,payout,value=st.session_state.perf_df,st.session_state.payout_df,st.session_state.value_df
    if perf.empty or payout.empty or value.empty: st.warning("Import data first."); st.stop()
    py,payy,vy=infer_year_col(perf),infer_year_col(payout),infer_year_col(value)
    c1,c2,c3=st.columns(3)
    with c1: perf_year=st.selectbox("Performance year column",perf.columns,index=list(perf.columns).index(py) if py in perf.columns else 0)
    with c2: payout_year=st.selectbox("Payout year column",payout.columns,index=list(payout.columns).index(payy) if payy in payout.columns else 0)
    with c3: value_year=st.selectbox("Shareholder value year column",value.columns,index=list(value.columns).index(vy) if vy in value.columns else 0)
    perf2=perf.copy()
    if not st.session_state.candidate_df.empty:
        perf2=merge_candidate_values(perf2,perf_year,st.session_state.candidate_df)

    # Add 10-K bridge drivers as analyzable annual metric columns.
    if "driver_df" in st.session_state and not st.session_state.driver_df.empty:
        driver_wide = driver_history_to_wide(st.session_state.driver_df)
        if not driver_wide.empty:
            perf2 = merge_candidate_values(perf2, perf_year, driver_wide)

    if not st.session_state.mapping_df.empty:
        perf2=add_bridge_columns(perf2,st.session_state.mapping_df)
    master=master_dataset(perf2,payout,value,perf_year,payout_year,value_year)
    return perf2,payout,value,master,perf_year,payout_year,value_year

if page=="5. Build Metric Objects":
    st.header("5. Build Metric Objects")
    if not st.session_state.driver_summary_df.empty:
        st.info("Management value driver evidence is loaded and will be used in Evidence Engine scoring.")
    perf2,payout,value,master,perf_year,payout_year,value_year=build_context()
    with st.expander("Merged performance dataset"):
        st.dataframe(perf2,use_container_width=True)
    bridge_cols=[c for c in ["Pricing","Volume/Mix","Inflation","Foreign Exchange","Productivity","Other","Operating Income"] if c in perf2.columns]
    if bridge_cols:
        st.success("Bridge / operating metrics available for analysis: " + ", ".join(bridge_cols))
    objs=build_metric_objects(perf2,st.session_state.mapping_df)
    ready_preview=objs[objs["Ready"]==True]["Metric"].tolist() if "Ready" in objs.columns and not objs.empty else []
    default_current_preview=infer_current_plan_defaults(st.session_state.perf_df, perf_year, ready_preview)
    if default_current_preview:
        st.info("Default current incentive metrics detected from uploaded performance data: " + ", ".join(default_current_preview))
    objs=st.data_editor(objs,use_container_width=True,num_rows="dynamic",key="metric_objects_editor")
    st.session_state.metric_objects=objs; st.session_state.master_df=master
    st.subheader("Metric Objects"); st.dataframe(objs,use_container_width=True); download_df(objs,"Download metric objects","metric_objects.csv")
    st.metric("Ready metric objects", int(objs["Ready"].sum()) if "Ready" in objs.columns else 0)

elif page=="6. Evidence Engine":
    st.header("6. Evidence Engine")
    perf2,payout,value,master,perf_year,payout_year,value_year=build_context()
    objs=st.session_state.metric_objects
    if objs.empty: objs=build_metric_objects(perf2,st.session_state.mapping_df); st.session_state.metric_objects=objs
    payout_cols=[c for c in payout.columns if c!=payout_year]; value_cols=[c for c in value.columns if c!=value_year]
    ready_metrics=objs[objs["Ready"]==True]["Metric"].tolist() if "Ready" in objs.columns else objs["Metric"].tolist()

    # Stable current-plan selector.
    # The current plan should default to metrics from the original uploaded performance file,
    # not the first two ready metrics after Capital IQ / bridge metrics are added.
    default_current = infer_current_plan_defaults(st.session_state.perf_df, perf_year, ready_metrics)

    # Streamlit keeps widget state across reruns. If this selector was previously empty
    # or contains metrics that are no longer available, reset it to the detected current-plan defaults.
    existing_current = st.session_state.get("current_metrics_selector", [])
    existing_current = [m for m in existing_current if m in ready_metrics]
    if not existing_current:
        st.session_state.current_metrics_selector = default_current
    else:
        st.session_state.current_metrics_selector = existing_current

    if st.button("Reset current metrics to uploaded incentive metrics", key="reset_current_metrics"):
        st.session_state.current_metrics_selector = default_current

    c1,c2=st.columns(2)
    with c1:
        current_metrics=st.multiselect(
            "Current incentive metrics",
            ready_metrics,
            key="current_metrics_selector",
            help="These should be the metrics in the current incentive plan, not automatically suggested alternatives."
        )
        st.caption("Default current-plan metrics: " + (", ".join(default_current) if default_current else "none found"))

    # Metrics to test should be sticky. Do not keep re-adding the top ready metrics
    # after the user has intentionally removed them.
    if "metrics_to_test_initialized" not in st.session_state:
        initial_metrics = list(dict.fromkeys(current_metrics + ready_metrics[:min(15,len(ready_metrics))]))
        st.session_state.metrics_to_test_selector = initial_metrics[:min(30, len(initial_metrics))]
        st.session_state.metrics_to_test_initialized = True
    else:
        existing_test_metrics = st.session_state.get("metrics_to_test_selector", [])
        st.session_state.metrics_to_test_selector = [m for m in existing_test_metrics if m in ready_metrics]

    reset_cols = st.columns([1, 1])
    with reset_cols[0]:
        if st.button("Reset metrics to test to top ready metrics", key="reset_metrics_to_test"):
            initial_metrics = list(dict.fromkeys(current_metrics + ready_metrics[:min(15,len(ready_metrics))]))
            st.session_state.metrics_to_test_selector = initial_metrics[:min(30, len(initial_metrics))]
    with reset_cols[1]:
        if st.button("Clear alternative metrics", key="clear_metrics_to_test"):
            st.session_state.metrics_to_test_selector = list(dict.fromkeys(current_metrics))

    with c2:
        selected_user=st.multiselect(
            "Metrics to test",
            ready_metrics,
            max_selections=30,
            key="metrics_to_test_selector"
        )

    # Hard guarantee for scoring only: current metrics are included in the scorecard,
    # but we do not mutate the user's Metrics to Test selector. This prevents removed
    # alternatives from reappearing when moving between pages.
    selected = list(dict.fromkeys(current_metrics + selected_user))

    payout_col=st.selectbox("Payout column",payout_cols); value_col=st.selectbox("Shareholder value outcome",value_cols)
    st.caption("Metrics to Test is sticky. Removed alternatives will stay removed unless you use a reset button. Current metrics are always scored for comparison.")
    score=score_metrics(master,objs,selected,value_col,payout_col,st.session_state.mgmt_df)
    st.session_state.score_df=score; st.session_state.current_metrics=current_metrics
    if score.empty: st.error("No correlations available. Check annual values and metric object columns."); st.stop()
    current,alt=compare_current(score,current_metrics)
    if current.empty and current_metrics:
        st.warning(
            "Current metrics are selected but did not appear in the scored results. "
            "Check that those current metric columns contain numeric annual values and are marked Ready on Tab 5."
        )
    st.subheader("Metric Evidence Scorecard"); st.dataframe(score,use_container_width=True); download_df(score,"Download scorecard","metric_evidence_scorecard.csv")
    if not st.session_state.driver_summary_df.empty:
        st.subheader("Management Value Driver Evidence")
        st.caption("These are operating drivers management attributed to financial performance. They supplement, but do not replace, correlation evidence.")
        st.dataframe(st.session_state.driver_summary_df, use_container_width=True)
        if not st.session_state.driver_linkage_df.empty:
            st.dataframe(st.session_state.driver_linkage_df, use_container_width=True)

    st.subheader("Current vs Alternative Metrics")
    cc1,cc2=st.columns(2)
    with cc1: st.markdown("**Current metrics**"); st.dataframe(current,use_container_width=True)
    with cc2: st.markdown("**Alternatives**"); st.dataframe(alt,use_container_width=True)
    if not alt.empty and "Improvement vs Current Avg" in alt.columns:
        stronger=alt[alt["Improvement vs Current Avg"]>5]
        if not stronger.empty: st.success("Potential stronger alternatives: "+", ".join(stronger["Metric"].head(6).tolist()))
    st.plotly_chart(px.bar(score.sort_values("Evidence Score").tail(12),x="Evidence Score",y="Metric",orientation="h",title="Evidence score"),use_container_width=True)
    st.plotly_chart(px.bar(score.sort_values("Directional Corr.").tail(12),x="Directional Corr.",y="Metric",orientation="h",title="Directional relationship to shareholder value"),use_container_width=True)

elif page=="7. Design Lab":
    st.header("7. Recommendation Workspace")
    st.info("This page converts the evidence scorecard into a consultant-ready recommendation: current plan assessment, candidate universe, suggested design, and readiness review.")

    score = st.session_state.score_df
    if score.empty:
        st.warning("Run Evidence Engine first.")
        st.stop()

    candidate_objects = build_candidate_metric_objects(score, st.session_state.current_metrics)
    recommended_plan = build_recommended_plan(candidate_objects, st.session_state.current_metrics, max_metrics=4)
    assessment = build_executive_assessment(candidate_objects, recommended_plan)

    st.subheader("Executive Assessment")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Current Plan Score", "n/a" if pd.isna(assessment["current_score"]) else f"{assessment['current_score']:.1f}/100")
    k2.metric("Recommended Plan Score", "n/a" if pd.isna(assessment["recommended_plan_score"]) else f"{assessment['recommended_plan_score']:.1f}/100")
    k3.metric("Top Tested Alternative", assessment["best_candidate"])
    k4.metric("Metrics Needing Data", assessment["needs_data"])

    narrative = build_recommendation_narrative(company, candidate_objects, recommended_plan)
    st.text_area("Draft recommendation narrative", narrative, height=180)

    st.subheader("Current Plan Assessment")
    current_plan = candidate_objects[candidate_objects["Current Plan Metric"] == True].sort_values("Evidence Score", ascending=False)
    if current_plan.empty:
        st.warning("No current plan metrics were selected in the Evidence Engine.")
    else:
        st.dataframe(current_plan, use_container_width=True)

    st.subheader("Recommended Candidate Universe")
    st.caption("All metrics are evaluated as candidate metric objects. Recommendations are based on correlations, lagged/rolling relationships, payout relationship, management emphasis, value-driver evidence, stability, and design fit.")
    candidates = candidate_objects[candidate_objects["Current Plan Metric"] == False].copy()
    st.dataframe(candidates, use_container_width=True)
    download_df(candidate_objects, "Download candidate metric objects", "candidate_metric_objects.csv")

    st.subheader("Initial Design Recommendation")
    st.caption("The system proposes a starting point. The consultant should edit it based on context, strategy, and committee judgment.")
    if recommended_plan.empty:
        st.warning("No design recommendation could be generated from the current scored metrics.")
    else:
        if "Current Plan Metric" in recommended_plan.columns and int((recommended_plan["Current Plan Metric"] == False).sum()) == 0:
            st.warning("The initial design contains only current-plan metrics because no tested alternative improved on the current-plan average. Treat this as a current-plan review, not an alternative recommendation.")
        st.dataframe(recommended_plan, use_container_width=True)
        st.metric("Initial Design Evidence Score", f"{recommended_plan['Weighted Evidence'].sum():.1f}/100")
        st.plotly_chart(px.bar(recommended_plan, x="Metric", y="Suggested Weight", title="Initial recommended weights"), use_container_width=True)
        download_df(recommended_plan, "Download recommended plan", "recommended_plan.csv")

    st.subheader("Edit Alternative Design")
    available = candidate_objects["Metric"].tolist()
    default_metrics = recommended_plan["Metric"].tolist() if not recommended_plan.empty else available[:min(3, len(available))]
    selected = st.multiselect("Select metrics for proposed design", available, default=default_metrics, max_selections=6)

    if selected:
        weights = {}
        cols = st.columns(len(selected))
        default_weight = int(100 / len(selected))
        for i, m in enumerate(selected):
            suggested = int(recommended_plan.loc[recommended_plan["Metric"] == m, "Suggested Weight"].iloc[0]) if not recommended_plan.empty and m in recommended_plan["Metric"].values else default_weight
            weights[m] = cols[i].slider(f"Weight: {m}", 0, 100, suggested, 5)

        total = sum(weights.values())
        if total != 100:
            st.warning(f"Weights sum to {total}%. Adjust to 100%.")
        else:
            design_df, design_score = build_plan_score(candidate_objects, selected, weights)
            st.metric("Edited Design Evidence Score", f"{design_score:.1f}/100")
            if pd.notna(assessment["current_score"]):
                st.metric("Improvement vs Current Plan", f"{design_score - assessment['current_score']:+.1f}")
            st.dataframe(design_df, use_container_width=True)
            st.plotly_chart(px.bar(design_df, x="Metric", y="Weight", title="Edited design weights"), use_container_width=True)

    st.subheader("Why Not? / Readiness Review")
    why_not = build_why_not_table(candidate_objects)
    if not why_not.empty:
        st.dataframe(why_not, use_container_width=True)
        download_df(why_not, "Download readiness review", "metric_readiness_review.csv")


elif page=="8. Committee Summary":
    st.header("8. Committee Summary")
    score=st.session_state.score_df
    if score.empty: st.warning("Run Evidence Engine first."); st.stop()
    current,alt=compare_current(score,st.session_state.current_metrics); top=score.iloc[0]
    text=f"""Executive Incentive Design Lab preliminary findings

Company: {company}

The strongest overall metric object in the analysis is {top['Metric']}, with an evidence score of {top['Evidence Score']:.0f}/100.

The analysis uses metric-specific transformation rules. Revenue, EBITDA, EPS, and FCF are generally tested on year-over-year change. ROIC and margin metrics are generally tested on level. Shareholder value outcomes are generally tested on year-over-year change.

Current metrics reviewed:
{", ".join(st.session_state.current_metrics) if st.session_state.current_metrics else "No current metrics selected"}

Potential alternatives warranting review:
{", ".join(alt.head(5)["Metric"].tolist()) if not alt.empty else "None identified"}

Management value drivers:
{", ".join(st.session_state.driver_summary_df.head(5)["Driver"].tolist()) if "driver_summary_df" in st.session_state and not st.session_state.driver_summary_df.empty else "No structured management driver data loaded"}

Important caveat:
The results are directional. Annual sample sizes are small, strategy changes over time, and correlation does not establish causation. The output should support consultant judgment, not replace it.
"""
    st.text_area("Draft summary",text,height=320)
    st.download_button("Download summary",text.encode("utf-8"),"committee_summary.txt","text/plain")
