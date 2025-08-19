"""
Streamlit app (beginner-friendly walkthrough)

What this app does:
- Lets you pick a USGS river gauge near Grand Junction, CO.
- Downloads two kinds of data:
  - IV (Instantaneous Values): near-real-time measurements (e.g., every 15 minutes).
  - DV (Daily Values): daily aggregates, like the daily mean discharge.
- Shows recent samples in a table and line charts.
- Computes simple daily features from IV data and rolling anomaly scores.

Key Python/pandas ideas used here:
- A pandas DataFrame is like a spreadsheet table in code (rows and columns).
- Time-indexed DataFrames use a DatetimeIndex so time operations (resample, diff) are easy.
- Timezones: we fetch in UTC, convert to the local "America/Denver" timezone for display,
  and then drop timezone info when sending to Streamlit to avoid serialization errors.

How the page is organized:
- Left column: IV tables and charts.
- Right column: DV table, daily features derived from IV, and anomaly chart.
"""

import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, timedelta, timezone
import os
import json

from usgs import SITE_CATALOG, load_or_fetch_iv, load_or_fetch_dv
from usgs import fetch_iv_json, fetch_dv_json
from eda import to_local, daily_features, rolling_anoms, summarize_gaps


def arrow_safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy that is safe for Streamlit/Arrow to serialize.

    Steps:
    - Reset the index so time indexes become normal columns.
    - Attempt to coerce any date/time-like columns to pandas datetime64[ns].
    - Drop timezone info from tz-aware columns (make them timezone-naive).
    """
    if df.empty:
        return df
    frame = df.reset_index()
    for col in list(frame.columns):
        s = frame[col]
        # Only attempt datetime coercion for object-like columns
        if pd.api.types.is_object_dtype(s) or pd.api.types.is_string_dtype(s):
            try:
                coerced = pd.to_datetime(s, errors="coerce")
                # Keep coercion only if it's largely successful
                if coerced.notna().sum() >= max(1, int(0.8 * len(coerced))):
                    frame[col] = coerced
            except Exception:
                pass
            # If still object, but contains any Timestamp/datetime-like, force coerce
            try:
                sample = pd.Series([v for v in s if v is not None]).head(20)
                if any(isinstance(v, (pd.Timestamp,)) for v in sample):
                    frame[col] = pd.to_datetime(s, errors="coerce")
            except Exception:
                pass
        # If datetime-like, ensure timezone-naive for Arrow
        if pd.api.types.is_datetime64_any_dtype(frame[col]):
            try:
                if getattr(frame[col].dt, "tz", None) is not None:
                    frame[col] = frame[col].dt.tz_localize(None)
            except Exception:
                # If dropping tz fails, fall back to string format
                frame[col] = frame[col].astype(str)
    return frame


def _dump_json(tag: str, site: str, payload: dict) -> None:
    try:
        os.makedirs("debug", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        path = os.path.join("debug", f"{tag}_{site}_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _dump_df(tag: str, site: str, df: pd.DataFrame) -> None:
    try:
        os.makedirs("debug", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        head_path = os.path.join("debug", f"{tag}_{site}_{ts}_head.csv")
        dtypes_path = os.path.join("debug", f"{tag}_{site}_{ts}_dtypes.txt")
        df.head(50).to_csv(head_path)
        with open(dtypes_path, "w", encoding="utf-8") as f:
            f.write(str(df.dtypes))
    except Exception:
        pass


def show_dataframe(df: pd.DataFrame, *, site: str, tag: str, enable_debug: bool) -> None:
    """Render a DataFrame safely in Streamlit.

    - First try Arrow-safe conversion.
    - If it still fails, stringify datetime-like columns as a fallback.
    - Optionally dump debug artifacts.
    """
    try:
        safe = arrow_safe_df(df)
        if enable_debug:
            _dump_df(f"{tag}_arrow_safe", site, safe)
        st.dataframe(safe)
    except Exception as exc:
        # Fallback: stringify any datetime-like columns
        try:
            fallback = df.reset_index().copy()
            for col in list(fallback.columns):
                s = fallback[col]
                if pd.api.types.is_datetime64_any_dtype(s) or "datetime" in str(s.dtype).lower() or "date" in col.lower():
                    fallback[col] = s.astype(str)
            if enable_debug:
                _dump_df(f"{tag}_fallback", site, fallback)
            st.warning(f"Display fallback used for {tag} due to serialization error: {exc}")
            st.dataframe(fallback)
        except Exception as exc2:
            st.error(f"Failed to render {tag}: {exc2}")

st.set_page_config(page_title="Colorado River Flow — GJ", layout="wide")
st.title("Colorado & Gunnison River Flow — near Grand Junction")

# ========== Sidebar controls ==========
site_label = st.sidebar.selectbox("Site", list(SITE_CATALOG.keys()), index=0)
site = SITE_CATALOG[site_label]

iv_days = st.sidebar.slider("Instantaneous window (days)", 1, 30, 7)
dv_years = st.sidebar.slider("Daily window (years)", 1, 20, 5)
debug_dump = st.sidebar.checkbox("Save debug snapshots", value=False)

# ========== Instantaneous (IV) ==========
left, right = st.columns(2)

with left:
    st.subheader("Instantaneous values (IV): discharge & stage")
    df_iv = load_or_fetch_iv(site, days=iv_days)
    if df_iv.empty:
        st.info("No IV data returned for this range.")
    else:
        # Convert to local time for readability; to_local now drops tz
        df_iv_local = to_local(df_iv)

        # Diagnostic summary about sampling cadence/gaps
        with st.expander("Sampling/Gaps Summary", expanded=False):
            gaps = summarize_gaps(df_iv_local)
            # Serialize to JSON-friendly strings to avoid Arrow mixed-type issues
            gaps_json = {}
            for k, v in gaps.items():
                if isinstance(v, pd.Timestamp):
                    gaps_json[k] = v.strftime("%Y-%m-%d %H:%M:%S")
                elif pd.isna(v):
                    gaps_json[k] = None
                elif isinstance(v, float):
                    gaps_json[k] = f"{v:.3f}"
                else:
                    gaps_json[k] = str(v)
            st.json(gaps_json)

        st.markdown("**Recent samples**")
        if debug_dump:
            _dump_df("iv_raw", site, df_iv)
            _dump_df("iv_local", site, df_iv_local)
        show_dataframe(df_iv_local.tail(20), site=site, tag="iv_display", enable_debug=debug_dump)

        with st.expander("Raw IV JSON (sample)", expanded=False):
            try:
                # Use the same window as df_iv for comparability
                end_utc = datetime.now(timezone.utc)
                start_utc = end_utc - timedelta(days=iv_days)
                js = fetch_iv_json(site, start_utc, end_utc)
                # Show a compact, human-friendly slice
                st.json({
                    "queryURL": js.get("value", {}).get("queryInfo", {}).get("queryURL", ""),
                    "first_series_name": (js.get("value", {}).get("timeSeries", [{}])[0] or {}).get("name"),
                    "first_point": ((js.get("value", {}).get("timeSeries", [{}])[0] or {}).get("values", [{}])[0] or {}).get("value", [{}])[0] if js.get("value", {}).get("timeSeries") else None,
                })
                if debug_dump:
                    _dump_json("iv_json", site, js)
            except Exception as e:
                st.write(f"IV JSON fetch error: {e}")

        # Prepare a tidy frame for Altair (friendly with Streamlit)
        base = arrow_safe_df(df_iv_local).rename(columns={"time": "t"})
        for field, label in [("discharge_cfs", "Discharge (cfs)"), ("stage_ft", "Stage (ft)")]:
            if field in base.columns:
                chart = (
                    alt.Chart(base)
                    .mark_line()
                    .encode(x="t:T", y=alt.Y(f"{field}:Q", title=label))
                    .properties(height=220)
                )
                st.altair_chart(chart, use_container_width=True)

# ========== Daily aggregates & anomalies ==========
with right:
    st.subheader("Daily means & basic features")
    df_dv = load_or_fetch_dv(site, years=dv_years)
    if df_dv.empty:
        st.info("No DV data returned for this range.")
    else:
        st.markdown("**USGS Daily Means (discharge)**")
        if debug_dump:
            _dump_df("dv", site, df_dv)
        show_dataframe(df_dv.tail(10), site=site, tag="dv_display", enable_debug=debug_dump)

        with st.expander("Raw DV JSON (sample)", expanded=False):
            try:
                end_utc = datetime.now(timezone.utc)
                start_utc = end_utc - timedelta(days=365 * dv_years)
                js = fetch_dv_json(site, start_utc, end_utc)
                st.json({
                    "queryURL": js.get("value", {}).get("queryInfo", {}).get("queryURL", ""),
                    "first_series_name": (js.get("value", {}).get("timeSeries", [{}])[0] or {}).get("name"),
                    "first_point": ((js.get("value", {}).get("timeSeries", [{}])[0] or {}).get("values", [{}])[0] or {}).get("value", [{}])[0] if js.get("value", {}).get("timeSeries") else None,
                })
                if debug_dump:
                    _dump_json("dv_json", site, js)
            except Exception as e:
                st.write(f"DV JSON fetch error: {e}")

        # Derive daily features from IV (independent of DV for teaching)
        feats = daily_features(df_iv)
        if feats.empty:
            st.info("Daily IV features not available yet (no IV data).")
        else:
            st.markdown("**Daily features (from IV resample)**")
            if debug_dump:
                _dump_df("feats", site, feats)
            show_dataframe(feats.tail(10), site=site, tag="feats_display", enable_debug=debug_dump)

            # Simple anomaly visualization: first z-score column if present
            anoms = rolling_anoms(feats)
            zcols = [c for c in anoms.columns if c.endswith("_z")]
            if zcols:
                # Ensure a 'date' column exists for Altair
                zdf = anoms.reset_index().rename(columns={"date": "date"})
                if debug_dump:
                    _dump_df("anoms", site, anoms)
                zdf = arrow_safe_df(zdf)
                if debug_dump:
                    _dump_df("anoms_display", site, zdf)
                chart = (
                    alt.Chart(zdf)
                    .mark_line()
                    .encode(x="date:T", y=alt.Y(zcols[0] + ":Q", title=zcols[0]))
                    .properties(height=220)
                )
                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No numeric columns to compute z-scores on.")

st.caption(
    "Data: USGS Water Services (nwis/iv, nwis/dv). 00060=discharge (cfs), 00065=gage height (ft)."
)
