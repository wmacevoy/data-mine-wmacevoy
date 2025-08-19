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

from usgs import SITE_CATALOG, load_or_fetch_iv, load_or_fetch_dv
from usgs import fetch_iv_json, fetch_dv_json
from eda import to_local, daily_features, rolling_anoms, summarize_gaps


def arrow_safe_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy suitable for Streamlit/Arrow serialization.

    - If index is datetime-like, reset index to a column.
    - Remove timezone info from any datetime64 columns.
    """
    if df.empty:
        return df
    frame = df.reset_index()
    for col in frame.columns:
        s = frame[col]
        if getattr(s, "dt", None) is not None:
            try:
                frame[col] = s.dt.tz_localize(None)
            except Exception:
                # Non-tz or object dt access, ignore
                pass
    return frame

st.set_page_config(page_title="Colorado River Flow — GJ", layout="wide")
st.title("Colorado & Gunnison River Flow — near Grand Junction")

# ========== Sidebar controls ==========
site_label = st.sidebar.selectbox("Site", list(SITE_CATALOG.keys()), index=0)
site = SITE_CATALOG[site_label]

iv_days = st.sidebar.slider("Instantaneous window (days)", 1, 30, 7)
dv_years = st.sidebar.slider("Daily window (years)", 1, 20, 5)

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
            # Ensure tz-aware timestamps render cleanly
            for key in ("start", "end"):
                if key in gaps.index:
                    val = gaps.loc[key]
                    if hasattr(val, "tz_localize"):
                        try:
                            gaps.loc[key] = val.tz_localize(None)
                        except Exception:
                            gaps.loc[key] = str(val)
            st.write(gaps)

        st.markdown("**Recent samples**")
        st.dataframe(arrow_safe_df(df_iv_local.tail(20)))

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
        st.dataframe(arrow_safe_df(df_dv.tail(10)))

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
            except Exception as e:
                st.write(f"DV JSON fetch error: {e}")

        # Derive daily features from IV (independent of DV for teaching)
        feats = daily_features(df_iv)
        if feats.empty:
            st.info("Daily IV features not available yet (no IV data).")
        else:
            st.markdown("**Daily features (from IV resample)**")
            st.dataframe(feats.tail(10))

            # Simple anomaly visualization: first z-score column if present
            anoms = rolling_anoms(feats)
            zcols = [c for c in anoms.columns if c.endswith("_z")]
            if zcols:
                # Ensure a 'date' column exists for Altair
                zdf = anoms.reset_index().rename(columns={"date": "date"})
                zdf = arrow_safe_df(zdf)
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
