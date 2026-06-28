
import io
import re
from collections import defaultdict

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Executive Incentive Design Lab", layout="wide")

# ============================================================
# Executive Incentive Design Lab
# Version: Workflow + Company DNA + Evidence Engine
# ============================================================

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

CATEGORY_MAP = {
    "Growth": ["sales", "revenue", "organic", "volume", "bookings"],
    "Profitability": ["ebitda", "ebit", "eps", "margin", "income", "profit"],
    "Cash Flow": ["cash", "fcf", "free cash", "working capital"],
    "Capital Efficiency": ["roic", "roe", "roa", "return", "capital"],
    "Balance Sheet": ["leverage", "debt", "liquidity"],
    "Operations": ["productivity", "cost", "efficiency", "savings"],
    "Commercial": ["pricing", "price", "mix"],
    "ESG / Human Capital": ["safety", "sustainability", "emissions", "diversity"],
}


# Capital IQ mapping dictionary.
# This is intentionally practical, not exhaustive. Expand over time as engagements reveal new metrics.
CAPIQ_FIELD_DICTIONARY = [
    {
        "Canonical Metric": "Revenue",
        "Aliases": ["revenue", "sales", "net sales", "total revenue", "net revenue"],
        "Category": "Growth",
        "Capital IQ Field": "IQ_TOTAL_REV",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Best standard field for revenue/net sales. Use company data if organic sales is required."
    },
    {
        "Canonical Metric": "Organic Sales",
        "Aliases": ["organic sales", "organic revenue", "organic growth", "organic sales growth"],
        "Category": "Growth",
        "Capital IQ Field": "",
        "Source Type": "Company / Investor Materials",
        "Status": "Needs company values",
        "Notes": "Usually company-defined and not standard in Capital IQ."
    },
    {
        "Canonical Metric": "EBITDA",
        "Aliases": ["ebitda"],
        "Category": "Profitability",
        "Capital IQ Field": "IQ_EBITDA",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Standard EBITDA. May differ from company adjusted EBITDA."
    },
    {
        "Canonical Metric": "Adjusted EBITDA",
        "Aliases": ["adjusted ebitda", "adj ebitda", "ebitda excluding", "ebitda ex"],
        "Category": "Profitability",
        "Capital IQ Field": "",
        "Source Type": "Company / Investor Materials",
        "Status": "Needs company values",
        "Notes": "Management-defined non-GAAP metric. Use proxy, earnings releases, investor deck, or FP&A."
    },
    {
        "Canonical Metric": "EBITDA Margin",
        "Aliases": ["ebitda margin", "adjusted ebitda margin"],
        "Category": "Profitability",
        "Capital IQ Field": "IQ_EBITDA / IQ_TOTAL_REV",
        "Source Type": "Derived from Capital IQ",
        "Status": "Derived",
        "Notes": "Use company adjusted EBITDA margin if management-defined."
    },
    {
        "Canonical Metric": "EBIT",
        "Aliases": ["ebit", "operating income"],
        "Category": "Profitability",
        "Capital IQ Field": "IQ_EBIT",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Standard EBIT / operating income field."
    },
    {
        "Canonical Metric": "Gross Margin",
        "Aliases": ["gross margin", "gross profit margin"],
        "Category": "Profitability",
        "Capital IQ Field": "IQ_GROSS_MARGIN",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Margin field. Confirm scale as percent."
    },
    {
        "Canonical Metric": "EPS",
        "Aliases": ["eps", "earnings per share", "adjusted eps", "normalized eps"],
        "Category": "Profitability",
        "Capital IQ Field": "IQ_EPS_NORM",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Normalized EPS. Company adjusted EPS may need manual values."
    },
    {
        "Canonical Metric": "Free Cash Flow",
        "Aliases": ["free cash flow", "fcf", "cash flow"],
        "Category": "Cash Flow",
        "Capital IQ Field": "IQ_LEVERED_FCF",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Levered FCF is usually closest standard field. Confirm against company definition."
    },
    {
        "Canonical Metric": "Operating Cash Flow",
        "Aliases": ["operating cash flow", "cash from operations", "cash flow from operations"],
        "Category": "Cash Flow",
        "Capital IQ Field": "IQ_CASH_FROM_OPER",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Cash from operating activities."
    },
    {
        "Canonical Metric": "Cash Flow Before Debt Reduction",
        "Aliases": ["cash flow before debt reduction", "cash flow available for debt reduction"],
        "Category": "Cash Flow",
        "Capital IQ Field": "",
        "Source Type": "Company / Investor Materials",
        "Status": "Needs company values",
        "Notes": "Company-defined metric. Use proxy/plan calculation or FP&A."
    },
    {
        "Canonical Metric": "ROIC",
        "Aliases": ["roic", "return on invested capital", "return on capital"],
        "Category": "Capital Efficiency",
        "Capital IQ Field": "IQ_RETURN_INVESTED_CAPITAL",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Closest standard Capital IQ return metric. Confirm definition."
    },
    {
        "Canonical Metric": "ROE",
        "Aliases": ["roe", "return on equity"],
        "Category": "Capital Efficiency",
        "Capital IQ Field": "IQ_RETURN_EQUITY",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Return on equity."
    },
    {
        "Canonical Metric": "ROA",
        "Aliases": ["roa", "return on assets"],
        "Category": "Capital Efficiency",
        "Capital IQ Field": "IQ_RETURN_ASSETS",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Return on assets."
    },
    {
        "Canonical Metric": "Net Debt",
        "Aliases": ["net debt"],
        "Category": "Balance Sheet",
        "Capital IQ Field": "IQ_NET_DEBT",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Use for leverage/debt reduction calculations."
    },
    {
        "Canonical Metric": "Leverage Ratio",
        "Aliases": ["leverage ratio", "net leverage", "debt leverage"],
        "Category": "Balance Sheet",
        "Capital IQ Field": "IQ_NET_DEBT / IQ_EBITDA",
        "Source Type": "Derived from Capital IQ",
        "Status": "Derived",
        "Notes": "Use company adjusted leverage if disclosed."
    },
    {
        "Canonical Metric": "Debt Reduction",
        "Aliases": ["debt reduction", "deleveraging"],
        "Category": "Balance Sheet",
        "Capital IQ Field": "YoY change in IQ_NET_DEBT",
        "Source Type": "Derived from Capital IQ",
        "Status": "Derived",
        "Notes": "Derived from year-over-year net debt movement."
    },
    {
        "Canonical Metric": "Market Cap",
        "Aliases": ["market cap", "market capitalization"],
        "Category": "Shareholder Value",
        "Capital IQ Field": "IQ_MARKETCAP",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Shareholder value measure."
    },
    {
        "Canonical Metric": "Stock Price",
        "Aliases": ["stock price", "share price", "closing price"],
        "Category": "Shareholder Value",
        "Capital IQ Field": "IQ_CLOSEPRICE_ADJ",
        "Source Type": "Capital IQ",
        "Status": "Ready",
        "Notes": "Adjusted close price."
    },
    {
        "Canonical Metric": "Pricing",
        "Aliases": ["pricing", "price realization", "pricing realization", "price mix"],
        "Category": "Commercial",
        "Capital IQ Field": "",
        "Source Type": "Company / Investor Materials",
        "Status": "Needs company values",
        "Notes": "Typically company-specific commercial KPI."
    },
    {
        "Canonical Metric": "Cost Savings",
        "Aliases": ["cost savings", "cost reduction"],
        "Category": "Operations",
        "Capital IQ Field": "",
        "Source Type": "Company / Investor Materials",
        "Status": "Needs company values",
        "Notes": "Typically company-specific productivity or transformation KPI."
    },
    {
        "Canonical Metric": "Productivity Savings",
        "Aliases": ["productivity", "productivity savings"],
        "Category": "Operations",
        "Capital IQ Field": "",
        "Source Type": "Company / Investor Materials",
        "Status": "Needs company values",
        "Notes": "Typically company-specific operational KPI."
    },
    {
        "Canonical Metric": "Safety",
        "Aliases": ["safety", "trir", "recordable incident rate"],
        "Category": "Human Capital",
        "Capital IQ Field": "",
        "Source Type": "Company / ESG / Internal",
        "Status": "Needs company values",
        "Notes": "Usually internal or sustainability report metric."
    },
]

def normalize_text_for_match(x):
    return re.sub(r"[^a-z0-9]+", " ", str(x).lower()).strip()

def capiq_dictionary_df():
    return pd.DataFrame(CAPIQ_FIELD_DICTIONARY)

def map_metric_to_capiq(metric):
    """Map a management/candidate metric to the most likely Capital IQ field."""
    m = normalize_text_for_match(metric)
    best = None
    best_score = 0

    for row in CAPIQ_FIELD_DICTIONARY:
        candidates = [row["Canonical Metric"]] + row.get("Aliases", [])
        for alias in candidates:
            a = normalize_text_for_match(alias)
            score = 0
            if m == a:
                score = 100
            elif m in a or a in m:
                score = 85
            else:
                # token overlap
                mt = set(m.split())
                at = set(a.split())
                if mt and at:
                    score = 100 * len(mt & at) / max(len(mt), len(at))
            if score > best_score:
                best_score = score
                best = row

    if best is None or best_score < 35:
        return {
            "Input Metric": metric,
            "Mapped Metric": metric,
            "Category": metric_category(metric),
            "Capital IQ Field": "",
            "Source Type": "Company / Manual",
            "Status": "Needs mapping",
            "Match Confidence": round(best_score, 1),
            "Notes": "No strong Capital IQ dictionary match. Review manually."
        }

    return {
        "Input Metric": metric,
        "Mapped Metric": best["Canonical Metric"],
        "Category": best["Category"],
        "Capital IQ Field": best["Capital IQ Field"],
        "Source Type": best["Source Type"],
        "Status": best["Status"],
        "Match Confidence": round(best_score, 1),
        "Notes": best["Notes"]
    }

def build_capiq_mapping_table(metrics):
    rows = [map_metric_to_capiq(m) for m in metrics if str(m).strip()]
    if not rows:
        return pd.DataFrame()
    out = pd.DataFrame(rows)
    # Remove duplicate input rows
    return out.drop_duplicates(subset=["Input Metric"], keep="first")

def capiq_export_fields(mapping_df):
    """Create a unique field list for Capital IQ export, expanding derived fields into components."""
    if mapping_df is None or mapping_df.empty:
        return pd.DataFrame()
    fields = []
    for f in mapping_df["Capital IQ Field"].dropna().astype(str):
        if not f.strip():
            continue
        # Derived field expressions may include multiple IQ_ fields.
        found = re.findall(r"IQ_[A-Z0-9_]+", f)
        if found:
            fields.extend(found)
        elif f.startswith("IQ_"):
            fields.append(f)
    # Always include shareholder value basics
    fields.extend(["IQ_MARKETCAP", "IQ_CLOSEPRICE_ADJ"])
    unique = sorted(set(fields))
    return pd.DataFrame({"Capital IQ Field": unique})


# -----------------------------
# Utility functions
# -----------------------------

def clean_num(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip()
    if s in ["", "-", "—", "nm", "n/a", "NA", "N/A", "None"]:
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
    if df is None or df.empty:
        return None
    for c in df.columns:
        s = standardize_year(df[c])
        if s.notna().sum() >= max(2, len(df) * 0.5):
            return c
    return df.columns[0] if len(df.columns) else None

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

def extract_text_from_pdf(file):
    text = ""
    try:
        import pypdf
        reader = pypdf.PdfReader(file)
        for i, page in enumerate(reader.pages):
            text += f"\n\n--- PAGE {i+1} ---\n"
            text += page.extract_text() or ""
    except Exception as e:
        st.warning(f"Could not read PDF text: {e}")
    return text


def extract_pdf_tables(file):
    """Extract tables from a PDF using pdfplumber. Returns a list of DataFrames."""
    tables = []
    try:
        import pdfplumber
        with pdfplumber.open(file) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                page_tables = page.extract_tables() or []
                for t_idx, table in enumerate(page_tables, start=1):
                    if not table or len(table) < 2:
                        continue
                    # Normalize rows
                    cleaned = []
                    max_len = max(len(r) for r in table if r)
                    for r in table:
                        if not r:
                            continue
                        rr = [(c or "").strip() for c in r]
                        rr += [""] * (max_len - len(rr))
                        cleaned.append(rr)
                    if len(cleaned) < 2:
                        continue
                    df = pd.DataFrame(cleaned)
                    df.attrs["page"] = page_num
                    df.attrs["table"] = t_idx
                    tables.append(df)
    except Exception as e:
        st.warning(f"Could not extract PDF tables with pdfplumber: {e}")
    return tables

def find_years_in_cells(cells):
    years = []
    for i, cell in enumerate(cells):
        s = str(cell)
        found = re.findall(r"(?:19|20)\d{2}", s)
        if found:
            # if multiple years in one cell, take each, but preserve cell index
            for y in found:
                years.append((i, int(y)))
    return years

def normalize_metric_label(label):
    s = str(label).strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace(":", "")
    return s

def row_looks_like_metric(row, selected_terms):
    label = " ".join([str(x) for x in row[:3]]).lower()
    for term in selected_terms:
        if str(term).lower() in label or label in str(term).lower():
            return term
    return None

def extract_metric_values_from_tables(tables, selected_metrics):
    """Attempt to convert PDF tables into long-form metric/year/value records."""
    records = []
    selected_terms = [str(m) for m in selected_metrics if str(m).strip()]
    if not selected_terms:
        return pd.DataFrame()

    for df in tables:
        page = df.attrs.get("page", "")
        table_no = df.attrs.get("table", "")

        # Find a row that contains year headers.
        header_idx = None
        header_years = []
        for idx in range(min(len(df), 8)):
            yrs = find_years_in_cells(df.iloc[idx].tolist())
            if len(yrs) >= 2:
                header_idx = idx
                header_years = yrs
                break

        if header_idx is None:
            # Also check all rows, because some annual report tables have years lower down.
            for idx in range(len(df)):
                yrs = find_years_in_cells(df.iloc[idx].tolist())
                if len(yrs) >= 2:
                    header_idx = idx
                    header_years = yrs
                    break

        if header_idx is None or len(header_years) < 2:
            continue

        # Analyze rows below the header for selected metric labels.
        for ridx in range(header_idx + 1, len(df)):
            row = df.iloc[ridx].tolist()
            metric_match = row_looks_like_metric(row, selected_terms)
            if not metric_match:
                continue

            label = normalize_metric_label(" ".join([str(x) for x in row[:3] if str(x).strip()]))
            for col_idx, year in header_years:
                if col_idx >= len(row):
                    continue
                val = clean_num(row[col_idx])
                if pd.notna(val):
                    records.append({
                        "Metric": metric_match,
                        "Year": int(year),
                        "Extracted Value": val,
                        "Source Label": label,
                        "Source Page": page,
                        "Source Table": table_no,
                        "Confidence": "Table match - review"
                    })

    if not records:
        return pd.DataFrame()
    out = pd.DataFrame(records)
    out = out.drop_duplicates(subset=["Metric", "Year"], keep="first")
    return out.sort_values(["Metric", "Year"])

def extract_metric_values_from_text_blocks(text, selected_metrics):
    """Fallback extraction from raw text. Useful when tables are not detected."""
    records = []
    selected_terms = [str(m) for m in selected_metrics if str(m).strip()]
    if not text or not selected_terms:
        return pd.DataFrame()

    for metric in selected_terms:
        pattern = re.compile(re.escape(metric), re.IGNORECASE)
        for m in pattern.finditer(text):
            window = text[max(0, m.start()-600): min(len(text), m.end()+1600)]
            years = re.findall(r"(?:19|20)\d{2}", window)
            if len(years) < 2:
                continue

            # Look for common table-like number runs after metric mention.
            nums = re.findall(r"\(?\$?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\)?", window)
            cleaned_nums = []
            for n in nums:
                v = clean_num(n)
                if pd.notna(v):
                    cleaned_nums.append(v)

            # Filter years out of values where possible
            cleaned_nums = [v for v in cleaned_nums if not (1900 <= v <= 2100)]
            if len(cleaned_nums) < len(set(years[:10])):
                continue

            unique_years = []
            for y in years:
                yy = int(y)
                if yy not in unique_years:
                    unique_years.append(yy)

            # Use first N values as a review-only estimate.
            for y, v in zip(unique_years[:10], cleaned_nums[:10]):
                records.append({
                    "Metric": metric,
                    "Year": int(y),
                    "Extracted Value": v,
                    "Source Label": "Text block near metric mention",
                    "Source Page": "",
                    "Source Table": "",
                    "Confidence": "Text match - low confidence review"
                })
            break

    if not records:
        return pd.DataFrame()
    out = pd.DataFrame(records).drop_duplicates(subset=["Metric", "Year"], keep="first")
    return out.sort_values(["Metric", "Year"])

def pivot_extracted_values(extracted_values_df):
    """Convert reviewed long-form extracted values into a wide Year-by-metric table."""
    if extracted_values_df is None or extracted_values_df.empty:
        return pd.DataFrame()
    df = extracted_values_df.copy()
    if not {"Metric", "Year", "Extracted Value"}.issubset(df.columns):
        return pd.DataFrame()
    df["Year"] = standardize_year(df["Year"])
    df["Extracted Value"] = pd.to_numeric(df["Extracted Value"].map(clean_num), errors="coerce")
    df = df.dropna(subset=["Year", "Extracted Value"])
    df["Year"] = df["Year"].astype(int)
    wide = df.pivot_table(index="Year", columns="Metric", values="Extracted Value", aggfunc="first").reset_index()
    wide.columns = [str(c) for c in wide.columns]
    return wide

def merge_performance_with_extracted_values(perf_df, perf_year, extracted_wide):
    """Add extracted metric value series to the performance data by Year."""
    if extracted_wide is None or extracted_wide.empty:
        return perf_df.copy()
    base = perf_df.copy()
    base["Year"] = standardize_year(base[perf_year])
    base = base.dropna(subset=["Year"])
    base["Year"] = base["Year"].astype(int)
    extra = extracted_wide.copy()
    extra["Year"] = standardize_year(extra["Year"])
    extra = extra.dropna(subset=["Year"])
    extra["Year"] = extra["Year"].astype(int)
    merged = base.merge(extra, on="Year", how="left", suffixes=("", "_extracted"))
    return merged


def consultant_potential_metric_analysis(candidate_df, score_df=None, existing_plan_metrics=None):
    """
    Evaluate potential metrics before full annual values are available.
    This is not TSR correlation. It is a disclosure-based and design-fit screen.
    """
    if candidate_df is None or candidate_df.empty:
        return pd.DataFrame()

    existing_plan_metrics = existing_plan_metrics or []
    existing_lower = [str(x).lower() for x in existing_plan_metrics]

    # Category-level compensation design fit.
    design_fit = {
        "Profitability": (95, "Core annual incentive financial metric"),
        "Cash Flow": (95, "Strong cash generation and funding discipline metric"),
        "Capital Efficiency": (90, "Useful for balancing growth and investment discipline"),
        "Growth": (85, "Useful when growth strategy is central and measurable"),
        "Operations": (75, "Useful if tied to controllable execution priorities"),
        "Commercial": (70, "Useful when pricing/mix execution is central"),
        "Balance Sheet": (65, "Often useful as a modifier or gating metric"),
        "Strategy": (60, "Potentially useful, but definition and measurement must be clear"),
        "ESG": (50, "May be useful as a strategic modifier, less direct TSR linkage expected"),
        "Human Capital": (50, "May be useful as a modifier or qualitative component"),
        "Other": (45, "Needs consultant review before inclusion"),
    }

    rows = []
    for _, r in candidate_df.iterrows():
        metric = str(r.get("Potential New Metric", r.get("Metric", ""))).strip()
        if not metric:
            continue
        category = str(r.get("Category", metric_category(metric))).strip()
        has_values = bool(r.get("Has Historical Values", False))

        emphasis = float(pd.to_numeric(pd.Series([r.get("Management Emphasis", 0)]), errors="coerce").fillna(0).iloc[0])
        mentions = float(pd.to_numeric(pd.Series([r.get("Mention Count", 0)]), errors="coerce").fillna(0).iloc[0])
        years = float(pd.to_numeric(pd.Series([r.get("Years Mentioned", 0)]), errors="coerce").fillna(0).iloc[0])
        confidence = float(pd.to_numeric(pd.Series([r.get("Extraction Confidence", 0)]), errors="coerce").fillna(0).iloc[0])

        fit_score, fit_reason = design_fit.get(category, design_fit["Other"])

        # Distinctiveness vs current analyzed/current plan metrics.
        metric_lower = metric.lower()
        duplicate_like = any(metric_lower in e or e in metric_lower for e in existing_lower)
        distinctiveness = 45 if duplicate_like else 85

        # Disclosure score represents how strongly management appears to emphasize the metric.
        disclosure_score = (
            0.45 * min(100, emphasis * 20) +
            0.25 * min(100, mentions * 2.5) +
            0.20 * min(100, years * 10) +
            0.10 * confidence
        )

        # Candidate score is intentionally not correlation-based.
        candidate_score = (
            0.45 * disclosure_score +
            0.25 * fit_score +
            0.20 * distinctiveness +
            0.10 * (100 if has_values else 40)
        )

        if has_values:
            status = "Ready for correlation testing"
            next_step = "Include in Evidence Engine"
        else:
            status = "Needs annual values"
            next_step = "Paste annual values in 2B, then test TSR/payout correlation"

        if candidate_score >= 80:
            priority = "High"
        elif candidate_score >= 65:
            priority = "Medium"
        else:
            priority = "Lower"

        if category == "Profitability":
            why = f"{metric} appears to be a recurring profitability measure that may capture earnings quality and margin performance."
            data_needed = f"Annual {metric} values, preferably adjusted/management-defined."
        elif category == "Cash Flow":
            why = f"{metric} appears to be a recurring cash-generation measure and may be useful for payout affordability and shareholder alignment."
            data_needed = f"Annual {metric} values using the company-defined calculation."
        elif category == "Capital Efficiency":
            why = f"{metric} may test whether the company is creating value from invested capital, not just growing earnings."
            data_needed = f"Annual {metric} values and definition consistency by year."
        elif category == "Growth":
            why = f"{metric} may test whether growth outcomes have translated into shareholder value."
            data_needed = f"Annual {metric} values, with organic/acquisition impacts separated if possible."
        elif category == "Operations":
            why = f"{metric} may capture controllable execution priorities discussed by management."
            data_needed = f"Annual KPI values and consistent definition."
        elif category == "Commercial":
            why = f"{metric} may capture commercial execution, pricing discipline, or mix improvement."
            data_needed = f"Annual pricing/mix metric values, if disclosed or available from management."
        else:
            why = f"{metric} was identified in management disclosures and may be relevant depending on strategy and measurability."
            data_needed = f"Annual values and a consistent definition."

        rows.append({
            "Potential Metric": metric,
            "Category": category,
            "Priority": priority,
            "Candidate Score": round(candidate_score, 1),
            "Disclosure Score": round(disclosure_score, 1),
            "Design Fit Score": fit_score,
            "Distinct From Current Metrics": "No / possible duplicate" if duplicate_like else "Yes",
            "Status": status,
            "Why It May Matter": why,
            "Data Needed": data_needed,
            "Recommended Next Step": next_step,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["Priority", "Candidate Score"], ascending=[True, False]).replace({"Priority": {"High": "High", "Medium": "Medium", "Lower": "Lower"}}).sort_values("Candidate Score", ascending=False)


def create_candidate_metric_narrative(analysis_df):
    if analysis_df is None or analysis_df.empty:
        return "No potential new metrics were identified for assessment."
    high = analysis_df[analysis_df["Priority"] == "High"]["Potential Metric"].head(5).tolist()
    medium = analysis_df[analysis_df["Priority"] == "Medium"]["Potential Metric"].head(5).tolist()

    parts = []
    if high:
        parts.append("High-priority new metrics to investigate: " + ", ".join(high) + ".")
    if medium:
        parts.append("Additional metrics for consultant review: " + ", ".join(medium) + ".")
    if not parts:
        parts.append("The extracted metrics appear to be lower-priority or require further review before testing.")
    parts.append("These are preliminary recommendations based on management disclosure emphasis and incentive design fit. They are not TSR-correlation conclusions until annual values are added.")
    return " ".join(parts)



def extract_text_from_docx(file):
    text = ""
    try:
        from docx import Document
        doc = Document(file)
        text = "\n".join([p.text for p in doc.paragraphs])
    except Exception as e:
        st.warning(f"Could not read DOCX: {e}")
    return text

def discover_metric_mentions(text):
    lower = text.lower()
    rows = []
    for key, (display, category) in KNOWN_METRICS.items():
        pattern = r"\b" + re.escape(key) + r"\b"
        hits = list(re.finditer(pattern, lower))
        if hits:
            years = set()
            pages = set()
            for m in hits:
                window = lower[max(0, m.start()-350): min(len(lower), m.end()+350)]
                years.update(re.findall(r"(?:19|20)\d{2}", window))
                page_match = re.findall(r"--- page (\d+) ---", lower[max(0, m.start()-1200):m.start()])
                if page_match:
                    pages.add(page_match[-1])
            consistency = min(10, len(years))
            freq_score = min(5, len(hits) / 12)
            year_score = min(5, consistency / 2)
            emphasis = min(5, max(1, round((freq_score + year_score) / 2, 1)))
            confidence = min(99, 45 + len(hits) * 2 + consistency * 4)
            rows.append({
                "Metric": display,
                "Category": category,
                "Mention Count": len(hits),
                "Years Mentioned": consistency,
                "Management Emphasis": emphasis,
                "Extraction Confidence": confidence,
                "Pages Found": ", ".join(sorted(pages, key=lambda x: int(x))[:10]) if pages else "",
                "Source": "Document extraction"
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return (
        df.groupby(["Metric", "Category"], as_index=False)
        .agg({
            "Mention Count": "sum",
            "Years Mentioned": "max",
            "Management Emphasis": "max",
            "Extraction Confidence": "max",
            "Pages Found": "first",
            "Source": "first"
        })
        .sort_values(["Management Emphasis", "Mention Count"], ascending=False)
    )

def extract_candidate_financial_values(text, selected_metrics):
    rows = []
    for metric in selected_metrics:
        pattern = re.compile(re.escape(metric), re.IGNORECASE)
        for m in pattern.finditer(text):
            window = text[max(0, m.start()-800): min(len(text), m.end()+1400)]
            years = re.findall(r"(?:19|20)\d{2}", window)
            nums = re.findall(r"\(?\$?-?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?\)?", window)
            if len(years) >= 2 and len(nums) >= len(years):
                for y, n in zip(years[:12], nums[:12]):
                    val = clean_num(n)
                    if pd.notna(val):
                        rows.append({
                            "Metric": metric,
                            "Year": int(y),
                            "Extracted Value": val,
                            "Confidence": "Review",
                            "Context": window[:300].replace("\n", " ")
                        })
                break
    return pd.DataFrame(rows).drop_duplicates(subset=["Metric", "Year"], keep="first") if rows else pd.DataFrame()

def metric_category(name):
    n = str(name).lower()
    for key, (display, cat) in KNOWN_METRICS.items():
        if key in n or n in key:
            return cat
    for cat, words in CATEGORY_MAP.items():
        if any(w in n for w in words):
            return cat
    return "Other"

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
    out = a.merge(b, on="Year", how="inner", suffixes=("", "_payout"))
    out = out.merge(c, on="Year", how="inner", suffixes=("", "_value"))
    return out.sort_values("Year")


def merge_candidate_values_into_performance(perf_df, perf_year, candidate_df):
    """Merge a CAPIQ/company candidate metric annual values table into the performance dataset."""
    if candidate_df is None or candidate_df.empty:
        return perf_df.copy()
    base = perf_df.copy()
    extra = candidate_df.copy()

    # Identify year column in candidate table
    extra_year = infer_year_col(extra)
    if extra_year is None:
        return base

    base["Year"] = standardize_year(base[perf_year])
    extra["Year"] = standardize_year(extra[extra_year])
    base = base.dropna(subset=["Year"])
    extra = extra.dropna(subset=["Year"])
    base["Year"] = base["Year"].astype(int)
    extra["Year"] = extra["Year"].astype(int)

    # Drop duplicate original candidate year column if it is not literally Year
    if extra_year != "Year" and extra_year in extra.columns:
        extra = extra.drop(columns=[extra_year])

    merged = base.merge(extra, on="Year", how="left", suffixes=("", "_candidate"))
    return merged


def safe_corr(x, y):
    valid = pd.concat([x, y], axis=1).replace([np.inf, -np.inf], np.nan).dropna()
    if len(valid) < 3:
        return np.nan
    if valid.iloc[:,0].nunique() < 2 or valid.iloc[:,1].nunique() < 2:
        return np.nan
    return valid.iloc[:,0].corr(valid.iloc[:,1])

def lag_corr(metric_series, value_series, lag=1):
    # Metric in year t compared with shareholder value in year t+lag
    x = metric_series.shift(lag)
    y = value_series
    return safe_corr(x, y)

def calc_trend_stability(x):
    vals = pd.to_numeric(x.map(clean_num), errors="coerce").replace([np.inf, -np.inf], np.nan)
    growth = vals.pct_change().replace([np.inf, -np.inf], np.nan)
    vol = growth.std()
    completeness = vals.notna().mean() * 100
    if pd.isna(vol):
        stability = 50
    else:
        stability = max(0, 100 - min(100, abs(vol) * 100))
    return 0.65 * stability + 0.35 * completeness

def score_metrics(model_df, metric_cols, value_col, payout_col=None, mgmt_df=None):
    rows = []
    y_value = pd.to_numeric(model_df[value_col].map(clean_num), errors="coerce")
    y_payout = pd.to_numeric(model_df[payout_col].map(clean_num), errors="coerce") if payout_col else None

    for m in metric_cols:
        x = pd.to_numeric(model_df[m].map(clean_num), errors="coerce")
        corr_value = safe_corr(x, y_value)
        corr_value_lag = lag_corr(x, y_value, lag=1)
        corr_payout = safe_corr(x, y_payout) if y_payout is not None else np.nan
        stability = calc_trend_stability(model_df[m])

        mgmt_score = 0
        mgmt_mentions = 0
        confidence = 0
        if mgmt_df is not None and not mgmt_df.empty and "Metric" in mgmt_df.columns:
            exact = mgmt_df[mgmt_df["Metric"].astype(str).str.lower() == str(m).lower()]
            fuzzy = mgmt_df[mgmt_df["Metric"].astype(str).str.lower().apply(lambda z: z in str(m).lower() or str(m).lower() in z)]
            match = exact if not exact.empty else fuzzy
            if not match.empty:
                if "Management Emphasis" in match.columns:
                    mgmt_score = float(pd.to_numeric(match["Management Emphasis"], errors="coerce").fillna(0).max()) * 20
                if "Mention Count" in match.columns:
                    mgmt_mentions = float(pd.to_numeric(match["Mention Count"], errors="coerce").fillna(0).max())
                if "Extraction Confidence" in match.columns:
                    confidence = float(pd.to_numeric(match["Extraction Confidence"], errors="coerce").fillna(0).max())

        value_score = 0 if pd.isna(corr_value) else abs(corr_value) * 100
        lag_score = 0 if pd.isna(corr_value_lag) else abs(corr_value_lag) * 100
        payout_score = 0 if pd.isna(corr_payout) else abs(corr_payout) * 100

        evidence = (
            0.35 * value_score +
            0.15 * lag_score +
            0.15 * payout_score +
            0.15 * stability +
            0.15 * mgmt_score +
            0.05 * confidence
        )

        rows.append({
            "Metric": m,
            "Category": metric_category(m),
            "Shareholder Value Corr.": corr_value,
            "Lagged Value Corr.": corr_value_lag,
            "Payout Corr.": corr_payout,
            "Stability Score": stability,
            "Management Emphasis Score": mgmt_score,
            "Mention Count": mgmt_mentions,
            "Extraction Confidence": confidence,
            "Evidence Score": evidence
        })

    return pd.DataFrame(rows).sort_values("Evidence Score", ascending=False)

def download_df_button(df, label, filename):
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(label, csv, file_name=filename, mime="text/csv")


def build_potential_new_metrics(candidate_df, mgmt_df, perf_cols):
    """Identify management-priority metrics that were found in documents but are not yet in the performance dataset."""
    if candidate_df is None or candidate_df.empty:
        return pd.DataFrame()

    rows = []
    perf_lower = {str(c).lower(): c for c in perf_cols}

    for _, r in candidate_df.iterrows():
        metric = str(r.get("Metric", "")).strip()
        if not metric:
            continue
        has_values = bool(r.get("Has Historical Values", False))
        if has_values:
            continue

        mgmt_row = pd.DataFrame()
        if mgmt_df is not None and not mgmt_df.empty and "Metric" in mgmt_df.columns:
            exact = mgmt_df[mgmt_df["Metric"].astype(str).str.lower() == metric.lower()]
            fuzzy = mgmt_df[mgmt_df["Metric"].astype(str).str.lower().apply(lambda x: x in metric.lower() or metric.lower() in x)]
            mgmt_row = exact if not exact.empty else fuzzy

        mention_count = 0
        years_mentioned = 0
        emphasis = 0
        confidence = 0
        if not mgmt_row.empty:
            if "Mention Count" in mgmt_row.columns:
                mention_count = float(pd.to_numeric(mgmt_row["Mention Count"], errors="coerce").fillna(0).max())
            if "Years Mentioned" in mgmt_row.columns:
                years_mentioned = float(pd.to_numeric(mgmt_row["Years Mentioned"], errors="coerce").fillna(0).max())
            if "Management Emphasis" in mgmt_row.columns:
                emphasis = float(pd.to_numeric(mgmt_row["Management Emphasis"], errors="coerce").fillna(0).max())
            if "Extraction Confidence" in mgmt_row.columns:
                confidence = float(pd.to_numeric(mgmt_row["Extraction Confidence"], errors="coerce").fillna(0).max())

        # Practical recommendation score. This is not TSR correlation yet. It is a sourcing/priority score.
        priority_score = min(100, emphasis * 16 + min(20, mention_count / 2) + min(15, years_mentioned * 2) + min(15, confidence / 7))

        if priority_score >= 75:
            action = "Collect annual values and test"
        elif priority_score >= 50:
            action = "Review with consultant"
        else:
            action = "Lower priority"

        rows.append({
            "Potential New Metric": metric,
            "Category": r.get("Category", metric_category(metric)),
            "Management Emphasis": emphasis,
            "Mention Count": mention_count,
            "Years Mentioned": years_mentioned,
            "Extraction Confidence": confidence,
            "Priority Score": priority_score,
            "Recommended Action": action,
        })

    out = pd.DataFrame(rows)
    if out.empty:
        return out
    return out.sort_values(["Priority Score", "Mention Count"], ascending=False)

def build_missing_values_template(potential_df, model_df):
    if potential_df is None or potential_df.empty or model_df is None or model_df.empty:
        return pd.DataFrame()
    years = sorted(model_df["Year"].dropna().astype(int).unique().tolist()) if "Year" in model_df.columns else []
    template = pd.DataFrame({"Year": years})
    for m in potential_df["Potential New Metric"].tolist():
        template[m] = ""
    return template


def assess_new_metric_candidates(potential_df, existing_metrics):
    """Create a consultant-style assessment of potential metrics before annual data is available."""
    if potential_df is None or potential_df.empty:
        return pd.DataFrame()

    existing_lower = [str(m).lower() for m in existing_metrics]
    rows = []

    category_fit = {
        "Profitability": 95,
        "Cash Flow": 95,
        "Capital Efficiency": 90,
        "Growth": 85,
        "Operations": 75,
        "Commercial": 70,
        "Balance Sheet": 70,
        "Strategy": 65,
        "ESG": 55,
        "Human Capital": 55,
        "Other": 45,
    }

    for _, r in potential_df.iterrows():
        metric = str(r.get("Potential New Metric", "")).strip()
        category = str(r.get("Category", metric_category(metric))).strip()
        emphasis = float(pd.to_numeric(pd.Series([r.get("Management Emphasis", 0)]), errors="coerce").fillna(0).iloc[0])
        mentions = float(pd.to_numeric(pd.Series([r.get("Mention Count", 0)]), errors="coerce").fillna(0).iloc[0])
        years = float(pd.to_numeric(pd.Series([r.get("Years Mentioned", 0)]), errors="coerce").fillna(0).iloc[0])
        confidence = float(pd.to_numeric(pd.Series([r.get("Extraction Confidence", 0)]), errors="coerce").fillna(0).iloc[0])

        # Distinctiveness: downweight if it appears to be a duplicate of an existing analyzed metric.
        metric_lower = metric.lower()
        duplicate_like = any(metric_lower in e or e in metric_lower for e in existing_lower)
        distinctiveness = 45 if duplicate_like else 85

        # Practicality: assume financial/capital/cash/growth metrics are easier to quantify.
        practicality = category_fit.get(category, 55)

        # Not correlation. This is a screening priority score.
        assessment_score = (
            0.30 * min(100, emphasis * 20) +
            0.20 * min(100, mentions * 2) +
            0.15 * min(100, years * 10) +
            0.15 * practicality +
            0.10 * distinctiveness +
            0.10 * confidence
        )

        if assessment_score >= 80:
            priority = "High"
            recommendation = "Paste annual values in 2B and test against TSR"
        elif assessment_score >= 65:
            priority = "Medium"
            recommendation = "Review with consultant; collect values if strategically relevant"
        else:
            priority = "Lower"
            recommendation = "Keep in library, but do not prioritize for current analysis"

        if category in ["Profitability", "Cash Flow", "Capital Efficiency", "Growth"]:
            data_needed = f"10-year annual history for {metric}"
        elif category in ["Operations", "Commercial", "Strategy"]:
            data_needed = f"Consistent annual KPI definition for {metric}"
        else:
            data_needed = f"Confirm definition and annual availability for {metric}"

        if category == "Capital Efficiency":
            why = "Tests whether capital discipline has been rewarded by investors."
        elif category == "Cash Flow":
            why = "Tests whether cash generation is a value driver and potential incentive anchor."
        elif category == "Profitability":
            why = "Tests whether earnings quality and margin expansion are value drivers."
        elif category == "Growth":
            why = "Tests whether top-line or organic growth has translated into shareholder value."
        elif category == "Operations":
            why = "Tests whether operational execution is linked to value creation."
        elif category == "Commercial":
            why = "Tests whether pricing or commercial execution has affected value."
        else:
            why = "Potential management priority identified in disclosures."

        rows.append({
            "Potential Metric": metric,
            "Category": category,
            "Preliminary Assessment Score": round(assessment_score, 1),
            "Priority": priority,
            "Why It May Matter": why,
            "Data Needed": data_needed,
            "Distinct From Current Metrics": "No / possible duplicate" if duplicate_like else "Yes",
            "Recommendation": recommendation,
        })

    return pd.DataFrame(rows).sort_values("Preliminary Assessment Score", ascending=False)



def sample_perf():
    return pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "Adjusted EBITDA": [714, 716.8, 931.2, 1030.8, 1070, 1041, 1600, 1876, 1693, 1372],
        "Cash Flow Before Debt Reduction": [320, 375.6, 471.66, 544.995, 520, 580, 743, 808, 672, 467],
        "ROIC": [5.29, 6.10, 2.48, 1.75, 1.15, 1.64, 5.51, 7.47, 6.35, -3.29],
        "Net Sales": [4298, 4406, 6029, 6160, 6560, 7156, 9440, 9428, 8807, 2156],
    })

def sample_payout():
    return pd.DataFrame({"Year": list(range(2016, 2026)), "Actual Payout": ["55%","50%","100%","150%","100%","64%","200%","153%","26%","0%"]})

def sample_value():
    df = pd.DataFrame({
        "Year": list(range(2016, 2026)),
        "Stock Price": [10.30,13.04,9.18,14.67,15.25,17.83,20.66,23.28,26.01,14.74],
        "Market Cap": [3963,4785,3302,4833,4587,5988,6833,7544,8152,4445],
    })
    df["TSR"] = df["Stock Price"].pct_change()
    return df

# -----------------------------
# Session state
# -----------------------------

for key in ["perf_df", "payout_df", "value_df", "mgmt_df", "model_df", "score_df", "extracted_values_df", "extracted_values_wide_df", "selected_metrics"]:
    if key not in st.session_state:
        st.session_state[key] = pd.DataFrame() if key.endswith("_df") else []

# -----------------------------
# Sidebar workflow
# -----------------------------

st.sidebar.title("Design Lab")
company_name = st.sidebar.text_input("Company", value="Graphic Packaging")
workflow = st.sidebar.radio(
    "Workflow",
    [
        "1. Import Data",
        "2. Management Metrics",
        "2A. Capital IQ Mapping",
        "2B. Candidate Metric Values",
        "3. Company DNA",
        "4. Evidence Engine",
        "5. Design Lab",
        "6. Committee Summary",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Version 2.0 prototype")
st.sidebar.caption("Directional analytics only. Consultant judgment required.")

st.title("Executive Incentive Design Lab")
st.caption("Company DNA | Management Priority Metrics | Evidence-Based Incentive Design")

# -----------------------------
# 1. Import Data
# -----------------------------

if workflow == "1. Import Data":
    st.header("1. Import Data")
    st.info("Start with three datasets: performance history, historical payouts, and shareholder value.")

    with st.expander("Copy template formats"):
        st.markdown("""
**Performance Data**
```text
Year    Adjusted EBITDA    Cash Flow Before Debt Reduction    ROIC
2024    1693               672                                6.35
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
""")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.subheader("Performance Data")
        method = st.radio("Input method", ["Paste from Excel", "Upload file", "Use sample"], horizontal=True, key="perf_method")
        if method == "Paste from Excel":
            txt = st.text_area("Paste performance data", height=180, key="perf_txt")
            df = parse_pasted_table(txt)
        elif method == "Upload file":
            file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="perf_file")
            df = read_upload_table(file)
        else:
            df = sample_perf()
        if not df.empty:
            st.session_state.perf_df = df
            st.success(f"Detected {len(df)} rows and {len(df.columns)} columns.")
            st.dataframe(df.head(10), use_container_width=True)

    with c2:
        st.subheader("Payout History")
        method = st.radio("Input method", ["Paste from Excel", "Upload file", "Use sample"], horizontal=True, key="payout_method")
        if method == "Paste from Excel":
            txt = st.text_area("Paste payout data", height=180, key="pay_txt")
            df = parse_pasted_table(txt)
        elif method == "Upload file":
            file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="payout_file")
            df = read_upload_table(file)
        else:
            df = sample_payout()
        if not df.empty:
            st.session_state.payout_df = df
            st.success(f"Detected {len(df)} rows and {len(df.columns)} columns.")
            st.dataframe(df.head(10), use_container_width=True)

    with c3:
        st.subheader("Shareholder Value")
        method = st.radio("Input method", ["Paste from Excel", "Upload file", "Use sample"], horizontal=True, key="value_method")
        if method == "Paste from Excel":
            txt = st.text_area("Paste shareholder value data", height=180, key="value_txt")
            df = parse_pasted_table(txt)
        elif method == "Upload file":
            file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="value_file")
            df = read_upload_table(file)
        else:
            df = sample_value()
        if not df.empty:
            st.session_state.value_df = df
            st.success(f"Detected {len(df)} rows and {len(df.columns)} columns.")
            st.dataframe(df.head(10), use_container_width=True)

# -----------------------------
# 2. Management Metrics
# -----------------------------

elif workflow == "2. Management Metrics":
    st.header("2. Management Priority Metrics")
    st.info("Use investor communications to identify the metrics management consistently emphasizes.")

    c1, c2 = st.columns([1, 1.2])

    with c1:
        st.subheader("Manual Metric Library")
        method = st.radio("Input method", ["Paste table", "Upload file", "Use sample"], horizontal=True, key="mgmt_method")
        if method == "Paste table":
            txt = st.text_area("Paste metric library", height=200, key="mgmt_txt")
            manual_df = parse_pasted_table(txt)
        elif method == "Upload file":
            file = st.file_uploader("Upload CSV/XLSX", type=["csv","xlsx","xls"], key="mgmt_file")
            manual_df = read_upload_table(file)
        else:
            manual_df = pd.DataFrame({
                "Metric": ["Adjusted EBITDA", "Cash Flow Before Debt Reduction", "ROIC", "Net Sales"],
                "Category": ["Profitability", "Cash Flow", "Capital Efficiency", "Growth"],
                "Management Emphasis": [5, 5, 4, 4],
            })
        if not manual_df.empty:
            st.dataframe(manual_df, use_container_width=True)

    with c2:
        st.subheader("Extract from Investor Communications")
        docs = st.file_uploader(
            "Upload PDFs, DOCX, or TXT files",
            type=["pdf", "docx", "txt"],
            accept_multiple_files=True,
            key="docs",
        )
        extracted_df = pd.DataFrame()
        extracted_text = ""
        if docs:
            with st.spinner("Extracting management metrics..."):
                for f in docs:
                    if f.name.lower().endswith(".pdf"):
                        extracted_text += "\n" + extract_text_from_pdf(f)
                    elif f.name.lower().endswith(".docx"):
                        extracted_text += "\n" + extract_text_from_docx(f)
                    else:
                        extracted_text += "\n" + f.read().decode("utf-8", errors="ignore")
                extracted_df = discover_metric_mentions(extracted_text)

            if extracted_df.empty:
                st.warning("No known recurring metrics found. Add metrics manually or extend the dictionary.")
            else:
                st.success(f"Found {len(extracted_df)} candidate management metrics.")
                edited_extracted = st.data_editor(
                    extracted_df,
                    use_container_width=True,
                    num_rows="dynamic",
                    key="extracted_editor",
                )
                download_df_button(edited_extracted, "Download extracted metric library", "management_metric_library.csv")

                with st.expander("Extract Annual Metric Values from 10-K Tables", expanded=True):
                    st.caption(
                        "This step attempts to pull year-by-year financial values from 10-K tables. "
                        "Review carefully before using. Annual values are required before new metrics can be tested against TSR."
                    )
                    selected_extract = st.multiselect(
                        "Metrics to attempt value extraction",
                        edited_extracted["Metric"].tolist(),
                        default=edited_extracted["Metric"].head(min(8, len(edited_extracted))).tolist()
                    )
                    if st.button("Extract annual values from uploaded documents"):
                        all_tables = []
                        # Re-read uploaded files for table extraction. Text extraction above consumes TXT files, but not PDF/DOCX table files.
                        for f in docs:
                            try:
                                f.seek(0)
                            except Exception:
                                pass
                            if f.name.lower().endswith(".pdf"):
                                all_tables.extend(extract_pdf_tables(f))

                        table_values = extract_metric_values_from_tables(all_tables, selected_extract)
                        text_values = extract_metric_values_from_text_blocks(extracted_text, selected_extract)

                        values = pd.concat([table_values, text_values], ignore_index=True) if not table_values.empty or not text_values.empty else pd.DataFrame()
                        if values.empty:
                            st.warning("No annual values were found. Try adding a pasted annual values table below or use the downloadable template from Company DNA.")
                        else:
                            st.success(f"Found {len(values)} metric-year values. Review and edit before using.")
                            reviewed = st.data_editor(values, use_container_width=True, num_rows="dynamic", key="review_extracted_values")
                            st.session_state.extracted_values_df = reviewed
                            wide = pivot_extracted_values(reviewed)
                            st.session_state.extracted_values_wide_df = wide
                            st.markdown("**Wide table that will be added to the performance dataset:**")
                            st.dataframe(wide, use_container_width=True)
                            download_df_button(reviewed, "Download extracted values for review", "extracted_metric_values_review.csv")
                            download_df_button(wide, "Download extracted values wide table", "extracted_metric_values_wide.csv")

                    st.markdown("**Optional manual annual values paste**")
                    manual_values_txt = st.text_area(
                        "Paste annual values for new metrics here. Format: Year plus one column per metric.",
                        height=120,
                        key="manual_extracted_values_txt"
                    )
                    manual_values = parse_pasted_table(manual_values_txt)
                    if not manual_values.empty:
                        st.session_state.extracted_values_wide_df = manual_values
                        st.success("Manual annual values table loaded and will be merged into the performance dataset.")
                        st.dataframe(manual_values, use_container_width=True)
        else:
            edited_extracted = pd.DataFrame()

    combined = []
    if "manual_df" in locals() and not manual_df.empty:
        combined.append(manual_df)
    if "edited_extracted" in locals() and not edited_extracted.empty:
        combined.append(edited_extracted)

    if combined:
        mgmt_df = pd.concat(combined, ignore_index=True)
        if "Metric" in mgmt_df.columns:
            if "Category" not in mgmt_df.columns:
                mgmt_df["Category"] = mgmt_df["Metric"].map(metric_category)
            if "Management Emphasis" not in mgmt_df.columns:
                mgmt_df["Management Emphasis"] = 3
            if "Extraction Confidence" not in mgmt_df.columns:
                mgmt_df["Extraction Confidence"] = 0
            mgmt_df = mgmt_df.drop_duplicates(subset=["Metric"], keep="first")
            st.session_state.mgmt_df = mgmt_df

            st.subheader("Curated Management Priority Metrics")
            curated = st.data_editor(mgmt_df, use_container_width=True, num_rows="dynamic", key="curated_mgmt")
            st.session_state.mgmt_df = curated
            download_df_button(curated, "Download curated metric library", "curated_management_metric_library.csv")

# -----------------------------
# 2A. Capital IQ Mapping
# -----------------------------

elif workflow == "2A. Capital IQ Mapping":
    st.header("2A. Capital IQ Mapping")
    st.info(
        "Use 10-Ks and investor materials to identify candidate metrics, then map those metrics to Capital IQ fields where possible. "
        "Capital IQ provides reliable annual values for standard financial metrics; company-specific adjusted metrics still need manual/company data."
    )

    mgmt_df = st.session_state.mgmt_df if "mgmt_df" in st.session_state else pd.DataFrame()

    if mgmt_df.empty or "Metric" not in mgmt_df.columns:
        st.warning("Run Management Metrics first, or paste candidate metrics below.")
        pasted = st.text_area("Optional: paste candidate metrics, one per line", height=160, key="manual_capiq_metric_list")
        metrics = [x.strip() for x in pasted.splitlines() if x.strip()]
    else:
        st.subheader("Candidate metrics from Management Priority Metrics")
        metrics = mgmt_df["Metric"].dropna().astype(str).unique().tolist()
        st.write(", ".join(metrics))

    extra = st.text_area("Add additional metrics to map, one per line", height=120, key="extra_capiq_metrics")
    if extra.strip():
        metrics += [x.strip() for x in extra.splitlines() if x.strip()]

    metrics = list(dict.fromkeys(metrics))

    if not metrics:
        st.stop()

    mapping_df = build_capiq_mapping_table(metrics)
    st.subheader("Capital IQ Metric Mapping")
    st.caption("Review the suggested mapping. Standard fields can be pulled from Capital IQ. Company-specific metrics need manual/company values.")
    edited_mapping = st.data_editor(mapping_df, use_container_width=True, num_rows="dynamic", key="capiq_mapping_editor")
    st.session_state.capiq_mapping_df = edited_mapping
    download_df_button(edited_mapping, "Download Capital IQ mapping", "capital_iq_metric_mapping.csv")

    c1, c2, c3 = st.columns(3)
    c1.metric("Mapped to Capital IQ", int((edited_mapping["Source Type"].astype(str).str.contains("Capital IQ", case=False, na=False)).sum()))
    c2.metric("Needs company values", int((edited_mapping["Status"].astype(str).str.contains("Needs", case=False, na=False)).sum()))
    c3.metric("Derived metrics", int((edited_mapping["Status"].astype(str) == "Derived").sum()))

    export_df = capiq_export_fields(edited_mapping)
    st.subheader("Capital IQ Download Field List")
    st.caption("Use these fields for a 10-year annual Capital IQ export. Include fiscal year/date in the export.")
    if export_df.empty:
        st.warning("No Capital IQ fields identified.")
    else:
        st.dataframe(export_df, use_container_width=True)
        download_df_button(export_df, "Download Capital IQ field list", "capital_iq_field_list.csv")

    needs_company = edited_mapping[edited_mapping["Capital IQ Field"].fillna("").astype(str).str.strip() == ""]
    if not needs_company.empty:
        st.subheader("Company-Specific Metrics Requiring Manual Values")
        st.caption("These are not standard Capital IQ fields. Use proxy, investor materials, earnings releases, or FP&A.")
        st.dataframe(needs_company[["Input Metric", "Mapped Metric", "Category", "Status", "Notes"]], use_container_width=True)

    with st.expander("View / edit built-in Capital IQ dictionary"):
        dictionary = capiq_dictionary_df()
        st.dataframe(dictionary, use_container_width=True)
        download_df_button(dictionary, "Download built-in dictionary", "capital_iq_dictionary.csv")


# -----------------------------
# 2B. Candidate Metric Values
# -----------------------------

elif workflow == "2B. Candidate Metric Values":
    st.header("2B. Candidate Metric Annual Values")
    st.info(
        "Paste or upload the annual values from your Capital IQ export and any company-specific metrics. "
        "This is the step that makes candidate metrics testable against TSR and payouts."
    )

    st.markdown("""
**Recommended format**

```text
Year    Revenue    Net Sales    Pricing    Cost Savings    Productivity Savings    Leverage Ratio
2025    ...
2024    ...
2023    ...
```

Use one row per year and one column per candidate metric. These values will be merged into the performance dataset by Year.
""")

    method = st.radio("Input method", ["Paste from Excel / Capital IQ", "Upload CSV/XLSX", "Use blank template"], horizontal=True, key="candidate_values_method")

    candidate_df = pd.DataFrame()
    if method == "Paste from Excel / Capital IQ":
        txt = st.text_area("Paste annual values for candidate metrics here", height=240, key="candidate_values_txt")
        candidate_df = parse_pasted_table(txt)
    elif method == "Upload CSV/XLSX":
        file = st.file_uploader("Upload candidate metric values", type=["csv", "xlsx", "xls"], key="candidate_values_file")
        candidate_df = read_upload_table(file)
    else:
        # Build a blank template from management metrics and imported years if available.
        years = []
        if not st.session_state.perf_df.empty:
            ycol = infer_year_col(st.session_state.perf_df)
            if ycol:
                years = sorted(standardize_year(st.session_state.perf_df[ycol]).dropna().astype(int).unique().tolist())
        if not years:
            years = list(range(2016, 2026))
        metrics = []
        if not st.session_state.mgmt_df.empty and "Metric" in st.session_state.mgmt_df.columns:
            metrics = st.session_state.mgmt_df["Metric"].dropna().astype(str).head(12).tolist()
        if not metrics:
            metrics = ["Revenue", "Net Sales", "Pricing", "Cost Savings", "Productivity Savings", "Leverage Ratio"]
        candidate_df = pd.DataFrame({"Year": years})
        for m in metrics:
            candidate_df[m] = ""

    if not candidate_df.empty:
        st.success(f"Loaded {len(candidate_df)} rows and {len(candidate_df.columns)} columns.")
        edited_candidate_df = st.data_editor(candidate_df, use_container_width=True, num_rows="dynamic", key="candidate_values_editor")
        st.session_state.candidate_values_df = edited_candidate_df
        download_df_button(edited_candidate_df, "Download candidate metric values", "candidate_metric_values.csv")

        st.subheader("Candidate metrics now available for testing")
        ycol = infer_year_col(edited_candidate_df)
        metrics_available = [c for c in edited_candidate_df.columns if c != ycol]
        st.write(", ".join(metrics_available) if metrics_available else "No metric columns found.")

        st.success(
            "Next: go to Company DNA. These candidate metrics will be merged into the performance dataset and will appear in the correlation selection list."
        )
    else:
        st.warning("Paste or upload a candidate metric annual values table to continue.")


# -----------------------------
# 3. Company DNA
# -----------------------------

elif workflow == "3. Company DNA":
    st.header("3. Company DNA")
    st.info("Build a one-page profile of what has historically created value, what the incentive plan rewarded, and where gaps may exist.")

    if st.session_state.perf_df.empty or st.session_state.payout_df.empty or st.session_state.value_df.empty:
        st.warning("Complete Import Data first.")
        st.stop()

    perf_df = st.session_state.perf_df
    payout_df = st.session_state.payout_df
    value_df = st.session_state.value_df
    mgmt_df = st.session_state.mgmt_df

    st.subheader("Map data")
    c1, c2, c3 = st.columns(3)
    with c1:
        perf_year = st.selectbox("Performance year column", perf_df.columns, index=list(perf_df.columns).index(infer_year_col(perf_df)) if infer_year_col(perf_df) in perf_df.columns else 0)
    with c2:
        payout_year = st.selectbox("Payout year column", payout_df.columns, index=list(payout_df.columns).index(infer_year_col(payout_df)) if infer_year_col(payout_df) in payout_df.columns else 0)
    with c3:
        value_year = st.selectbox("Shareholder value year column", value_df.columns, index=list(value_df.columns).index(infer_year_col(value_df)) if infer_year_col(value_df) in value_df.columns else 0)

    # If annual values were extracted from 10-K tables or manually pasted, merge them into performance data.
    if "extracted_values_wide_df" in st.session_state and not st.session_state.extracted_values_wide_df.empty:
        perf_df = merge_performance_with_extracted_values(perf_df, perf_year, st.session_state.extracted_values_wide_df)
        st.success("Extracted/manual annual metric values have been added to the performance dataset for testing.")
        with st.expander("Performance dataset after adding extracted metric values"):
            st.dataframe(perf_df, use_container_width=True)

    if "candidate_values_df" in st.session_state and not st.session_state.candidate_values_df.empty:
        perf_df = merge_candidate_values_into_performance(perf_df, perf_year, st.session_state.candidate_values_df)
        st.success("Candidate metric annual values have been merged into the performance dataset.")
        with st.expander("Performance dataset after adding candidate metric annual values"):
            st.dataframe(perf_df, use_container_width=True)

    perf_cols = [c for c in perf_df.columns if c != perf_year and c != "Year"]
    payout_cols = [c for c in payout_df.columns if c != payout_year]
    value_cols = [c for c in value_df.columns if c != value_year]

    # Metric Discovery Crosswalk:
    # 10-K / investor communication metrics may not be present in the performance history yet.
    # We show both sets, then only run correlations on metrics with actual annual values.
    mgmt_metrics = []
    if mgmt_df is not None and not mgmt_df.empty and "Metric" in mgmt_df.columns:
        mgmt_metrics = mgmt_df["Metric"].dropna().astype(str).unique().tolist()

    all_candidates = []
    for m in perf_cols:
        all_candidates.append({
            "Metric": m,
            "Source": "Performance dataset",
            "Has Historical Values": True,
            "Category": metric_category(m),
            "Action": "Analyze"
        })
    for m in mgmt_metrics:
        has_values = any(str(m).lower() == str(c).lower() for c in perf_cols)
        if not any(str(m).lower() == str(x["Metric"]).lower() for x in all_candidates):
            all_candidates.append({
                "Metric": m,
                "Source": "10-K / investor communications",
                "Has Historical Values": has_values,
                "Category": metric_category(m),
                "Action": "Needs values" if not has_values else "Analyze"
            })

    candidate_df = pd.DataFrame(all_candidates)
    if not candidate_df.empty:
        st.subheader("Metric Discovery Crosswalk")
        st.caption("This shows metrics found in 10-Ks/investor communications and whether annual values are available. Once values are extracted or pasted, those metrics become analyzable.")
        st.dataframe(candidate_df, use_container_width=True)
        missing_values = candidate_df[(candidate_df["Source"] == "10-K / investor communications") & (~candidate_df["Has Historical Values"])]
        if not missing_values.empty:
            st.warning(
                f"{len(missing_values)} management-priority metrics were found in the documents but do not yet have annual values in the performance dataset. "
                "They can be included in the management-priority library, but TSR/payout correlations require a Year-by-Year value series."
            )

            st.subheader("Potential New Metrics from 10-K / Investor Communications")
            potential_df = build_potential_new_metrics(candidate_df, mgmt_df, perf_cols)
            if potential_df.empty:
                st.caption("No additional potential metrics were identified beyond the performance dataset.")
            else:
                st.caption(
                    "These are management-priority metrics surfaced from the document review. "
                    "They are not yet in the performance dataset, so the app cannot calculate TSR or payout correlations until annual values are added."
                )
                st.dataframe(potential_df, use_container_width=True)
                download_df_button(potential_df, "Download potential new metrics", "potential_new_metrics_from_10k.csv")

                st.subheader("Potential Metric Analysis")
                potential_analysis = consultant_potential_metric_analysis(potential_df, existing_plan_metrics=perf_cols)
                if not potential_analysis.empty:
                    st.caption(
                        "This is a consultant-style screen of potential new incentive metrics from the 10-K review. "
                        "It does not require TSR correlation yet. It ranks which metrics are worth collecting and testing."
                    )

                    # Summary cards
                    p1, p2, p3 = st.columns(3)
                    p1.metric("High-priority candidates", int((potential_analysis["Priority"] == "High").sum()))
                    p2.metric("Medium-priority candidates", int((potential_analysis["Priority"] == "Medium").sum()))
                    p3.metric("Ready for testing", int((potential_analysis["Status"] == "Ready for correlation testing").sum()))

                    st.dataframe(potential_analysis, use_container_width=True)
                    download_df_button(potential_analysis, "Download potential metric analysis", "potential_metric_analysis.csv")

                    narrative = create_candidate_metric_narrative(potential_analysis)
                    st.success(narrative)

                    high_priority = potential_analysis[potential_analysis["Priority"] == "High"]
                    if not high_priority.empty:
                        st.markdown("**Recommended metrics to collect annual values for first:**")
                        st.dataframe(
                            high_priority[["Potential Metric", "Category", "Candidate Score", "Why It May Matter", "Data Needed", "Recommended Next Step"]],
                            use_container_width=True
                        )

                st.markdown("**Next step:** collect annual values for the metrics you want to test.")
                missing_template = build_missing_values_template(potential_df, model_df if "model_df" in locals() else pd.DataFrame())
                if not missing_template.empty:
                    st.dataframe(missing_template.head(10), use_container_width=True)
                    download_df_button(missing_template, "Download annual values template", "annual_values_needed_for_new_metrics.csv")

    analyzable_metrics = candidate_df[candidate_df["Has Historical Values"]]["Metric"].tolist() if not candidate_df.empty else perf_cols
    default_metrics = analyzable_metrics[:min(10, len(analyzable_metrics))]

    selected_metrics = st.multiselect(
        "Candidate metrics to analyze correlations (maximum 20; must have annual values)",
        analyzable_metrics,
        default=default_metrics,
        max_selections=20
    )
    payout_col = st.selectbox("Actual payout column", payout_cols)
    value_col = st.selectbox("Shareholder value measure", value_cols)

    try:
        model_df = merge_data(perf_df, payout_df, value_df, perf_year, payout_year, value_year)
        st.session_state.model_df = model_df
        st.session_state.selected_metrics = selected_metrics
    except Exception as e:
        st.error(f"Could not merge data: {e}")
        st.stop()

    if model_df.empty:
        st.error("Merged dataset is empty. Check year fields and overlapping fiscal years.")
        st.stop()

    # Match selected 10-K metrics to performance columns when names are case-equivalent.
    metric_lookup = {str(c).lower(): c for c in model_df.columns}
    selected_for_model = [metric_lookup.get(str(m).lower(), m) for m in selected_metrics if str(m).lower() in metric_lookup]

    score_df = score_metrics(model_df, selected_for_model, value_col, payout_col, mgmt_df)
    st.session_state.score_df = score_df

    st.subheader(f"{company_name} Company DNA")

    top_value = score_df.sort_values("Shareholder Value Corr.", key=lambda s: s.abs(), ascending=False).head(3)
    top_payout = score_df.sort_values("Payout Corr.", key=lambda s: s.abs(), ascending=False).head(3)
    top_evidence = score_df.head(3)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Historical periods", len(model_df))
    k2.metric("Metrics tested", len(selected_metrics))
    k3.metric("Top value driver", top_value.iloc[0]["Metric"] if not top_value.empty else "n/a")
    k4.metric("Top evidence score", f"{score_df.iloc[0]['Evidence Score']:.0f}/100" if not score_df.empty else "n/a")

    st.markdown("### Primary Value Drivers")
    st.dataframe(top_value[["Metric", "Category", "Shareholder Value Corr.", "Lagged Value Corr.", "Evidence Score"]], use_container_width=True)

    st.markdown("### Primary Incentive Drivers")
    st.dataframe(top_payout[["Metric", "Category", "Payout Corr.", "Evidence Score"]], use_container_width=True)

    fig = px.bar(score_df.head(10), x="Evidence Score", y="Metric", orientation="h", title="Company DNA: strongest overall evidence scores")
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, use_container_width=True, key="dna_evidence_chart")

    alignment_gap = score_df.copy()
    alignment_gap["Alignment Gap"] = alignment_gap["Payout Corr."].abs().fillna(0) - alignment_gap["Shareholder Value Corr."].abs().fillna(0)
    gap_metric = alignment_gap.sort_values("Alignment Gap", ascending=False).iloc[0]["Metric"]
    st.success(
        f"Initial read: {top_evidence.iloc[0]['Metric']} appears to be the strongest overall candidate metric. "
        f"{gap_metric} shows the largest payout-versus-value gap and may warrant additional review."
    )

    with st.expander("Modeling dataset"):
        st.dataframe(model_df, use_container_width=True)
        download_df_button(model_df, "Download modeling dataset", "modeling_dataset.csv")

# -----------------------------
# 4. Evidence Engine
# -----------------------------

elif workflow == "4. Evidence Engine":
    st.header("4. Evidence Engine")
    st.info("Review the underlying evidence. Metrics extracted from 10-Ks are compared only when they also have annual values in the performance dataset or extracted value table.")

    if st.session_state.score_df.empty:
        st.warning("Run Company DNA first.")
        st.stop()

    score_df = st.session_state.score_df.copy()

    st.subheader("Metric Evidence Scorecard")
    st.dataframe(score_df, use_container_width=True)
    download_df_button(score_df, "Download metric evidence scorecard", "metric_evidence_scorecard.csv")

    c1, c2 = st.columns(2)
    with c1:
        fig = px.bar(
            score_df.sort_values("Shareholder Value Corr.", key=lambda s: s.abs()),
            x="Shareholder Value Corr.",
            y="Metric",
            orientation="h",
            title="Shareholder value relationship"
        )
        st.plotly_chart(fig, use_container_width=True, key="ev_value")
    with c2:
        fig = px.bar(
            score_df.sort_values("Payout Corr.", key=lambda s: s.abs()),
            x="Payout Corr.",
            y="Metric",
            orientation="h",
            title="Historical payout relationship"
        )
        st.plotly_chart(fig, use_container_width=True, key="ev_payout")

    st.subheader("Alignment Gap")
    gap_df = score_df.copy()
    gap_df["Alignment Gap"] = gap_df["Payout Corr."].abs().fillna(0) - gap_df["Shareholder Value Corr."].abs().fillna(0)
    st.dataframe(gap_df[["Metric", "Category", "Shareholder Value Corr.", "Payout Corr.", "Alignment Gap", "Evidence Score"]], use_container_width=True)

    fig = px.bar(gap_df, x="Metric", y=["Shareholder Value Corr.", "Payout Corr."], barmode="group",
                 title="What investors rewarded vs. what the plan rewarded")
    st.plotly_chart(fig, use_container_width=True, key="gap_grouped")

    # Show potential metrics that have not yet been tested, if available from Company DNA session context.
    st.subheader("Potential New Metrics Not Yet Tested")
    st.caption("These metrics were identified from management disclosures but need annual values before they can be correlated with TSR or payouts.")
    if "mgmt_df" in st.session_state and not st.session_state.mgmt_df.empty and "model_df" in st.session_state and not st.session_state.model_df.empty:
        existing = st.session_state.selected_metrics if "selected_metrics" in st.session_state else []
        # Rebuild a simple potential list from management library versus current analyzed metrics.
        analyzed_lower = [str(x).lower() for x in existing]
        rows = []
        for _, r in st.session_state.mgmt_df.iterrows():
            metric = str(r.get("Metric", "")).strip()
            if metric and metric.lower() not in analyzed_lower:
                rows.append({
                    "Potential New Metric": metric,
                    "Category": r.get("Category", metric_category(metric)),
                    "Management Emphasis": r.get("Management Emphasis", 0),
                    "Mention Count": r.get("Mention Count", 0),
                    "Years Mentioned": r.get("Years Mentioned", 0),
                    "Extraction Confidence": r.get("Extraction Confidence", 0),
                })
        potential_evidence_df = pd.DataFrame(rows)
        if not potential_evidence_df.empty:
            assessed = consultant_potential_metric_analysis(potential_evidence_df, existing_plan_metrics=existing)
            st.dataframe(assessed, use_container_width=True)
            st.success(create_candidate_metric_narrative(assessed))
        else:
            st.write("No untested management-priority metrics found.")
    else:
        st.write("Run Management Metrics and Company DNA first.")


    st.subheader("Metric Cards")
    metric = st.selectbox("Metric", score_df["Metric"].tolist())
    row = score_df[score_df["Metric"] == metric].iloc[0]

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Value Corr.", f"{row['Shareholder Value Corr.']:.2f}" if pd.notna(row["Shareholder Value Corr."]) else "n/a")
    k2.metric("Lagged Corr.", f"{row['Lagged Value Corr.']:.2f}" if pd.notna(row["Lagged Value Corr."]) else "n/a")
    k3.metric("Payout Corr.", f"{row['Payout Corr.']:.2f}" if pd.notna(row["Payout Corr."]) else "n/a")
    k4.metric("Stability", f"{row['Stability Score']:.0f}/100")
    k5.metric("Evidence", f"{row['Evidence Score']:.0f}/100")

# -----------------------------
# 5. Design Lab
# -----------------------------

elif workflow == "5. Design Lab":
    st.header("5. Design Lab")
    st.info("Use analyzed metrics to build a practical alternative design. Potential new metrics from 10-Ks must first be added as annual values before they can be tested here.")

    if st.session_state.score_df.empty:
        st.warning("Run Company DNA first.")
        st.stop()

    score_df = st.session_state.score_df.copy()
    available = score_df["Metric"].tolist()

    plan_metrics = st.multiselect("Metrics in proposed design", available, default=available[:min(3, len(available))], max_selections=5)
    if not plan_metrics:
        st.stop()

    weights = {}
    cols = st.columns(len(plan_metrics))
    for i, m in enumerate(plan_metrics):
        weights[m] = cols[i].slider(f"Weight: {m}", 0, 100, int(100 / len(plan_metrics)), 5)

    total = sum(weights.values())
    if total != 100:
        st.warning(f"Weights sum to {total}%. Adjust to 100%.")
        st.stop()

    design_rows = []
    design_score = 0
    for m, w in weights.items():
        evidence = float(score_df.loc[score_df["Metric"] == m, "Evidence Score"].iloc[0])
        design_score += (w / 100) * evidence
        design_rows.append({"Metric": m, "Weight": w, "Evidence Score": evidence, "Weighted Evidence": (w / 100) * evidence})

    design_df = pd.DataFrame(design_rows)
    st.metric("Proposed Design Evidence Score", f"{design_score:.1f}/100")
    st.dataframe(design_df, use_container_width=True)

    fig = px.bar(design_df, x="Metric", y="Weight", title="Proposed design weights")
    st.plotly_chart(fig, use_container_width=True, key="design_weights")

    st.subheader("Find better metric combinations")
    max_metrics = st.slider("Maximum metrics in plan", 1, min(5, len(available)), min(3, len(available)))
    require_metric = st.selectbox("Required metric", ["None"] + available)
    if st.button("Run simple design search"):
        combos = []
        candidates = available[:min(10, len(available))]
        for r in range(1, max_metrics + 1):
            for combo in __import__("itertools").combinations(candidates, r):
                if require_metric != "None" and require_metric not in combo:
                    continue
                score = np.mean([float(score_df.loc[score_df["Metric"] == m, "Evidence Score"].iloc[0]) for m in combo])
                combos.append({"Metrics": " / ".join(combo), "Avg Evidence Score": score, "Metric Count": r})
        combo_df = pd.DataFrame(combos).sort_values("Avg Evidence Score", ascending=False).head(10)
        st.dataframe(combo_df, use_container_width=True)

# -----------------------------
# 6. Committee Summary
# -----------------------------

elif workflow == "6. Committee Summary":
    st.header("6. Committee Summary")
    st.info("Board-ready draft language for consultant review and refinement.")

    if st.session_state.score_df.empty:
        st.warning("Run Company DNA first.")
        st.stop()

    score_df = st.session_state.score_df.copy()
    top = score_df.iloc[0]
    top3 = score_df.head(3)["Metric"].tolist()

    gap_df = score_df.copy()
    gap_df["Alignment Gap"] = gap_df["Payout Corr."].abs().fillna(0) - gap_df["Shareholder Value Corr."].abs().fillna(0)
    gap = gap_df.sort_values("Alignment Gap", ascending=False).iloc[0]

    summary = f"""
Executive Incentive Design Assessment

Company: {company_name}

Preliminary Findings

The historical diagnostics indicate that {top['Metric']} has the strongest overall evidence score among the candidate metrics reviewed. The top-ranked candidate metrics were {", ".join(top3)}.

The analysis compares three perspectives:

1. Management priorities, based on recurring metrics identified in investor communications.
2. Historical shareholder value relationships, based on correlation and lagged correlation to the selected shareholder value measure.
3. Incentive alignment, based on the relationship between each metric and historical incentive payouts.

The largest payout-versus-value gap was observed for {gap['Metric']}. This does not mean the metric is inappropriate, but it suggests the committee may want to review whether the current plan places the right level of emphasis on that outcome.

Recommended Next Step

Use the Design Lab to compare alternative metric combinations that increase emphasis on the strongest historical value drivers while maintaining a practical, explainable incentive design.

Important Caveat

The analysis is directional and should be interpreted with consultant judgment. Annual samples are small, company strategy changes over time, and correlation does not establish causation.
""".strip()

    st.text_area("Draft consultant takeaway", summary, height=350)
    st.download_button("Download summary", summary.encode("utf-8"), file_name="committee_summary.txt", mime="text/plain")
