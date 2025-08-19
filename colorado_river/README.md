## Colorado & Gunnison River Flow — Streamlit App

A small, teaching-oriented Streamlit app that fetches and visualizes USGS river data (Colorado & Gunnison Rivers near Grand Junction). It shows instantaneous values (IV), daily values (DV), basic feature engineering, sampling gap diagnostics, and simple anomaly scores.

### Data sources
- **USGS Water Services API**: `nwis/iv` (instantaneous values) and `nwis/dv` (daily values)
  - 00060 = discharge (cubic feet per second)
  - 00065 = gage height (feet)

### Repository layout
- `app.py`: Streamlit UI and charts
- `usgs.py`: USGS API client, caching to `./data/` as Parquet
- `eda.py`: Helpers for timezone handling, resampling, feature engineering, and anomalies
- `requirements.txt`: Python deps
- `setup.sh`: Creates/updates a local conda/mamba env at `./.venv` and installs deps
- `run.sh`: Runs Streamlit inside the env (uses `python -m streamlit`)
- `data/`: Cached Parquet files per site and window

### Quick start
Prerequisites:
- macOS/Linux with either `mamba` or `conda` on PATH

Steps:
1) Make scripts executable once:
   - `chmod +x setup.sh run.sh`
2) Launch the app:
   - `./run.sh`
3) Open the URL printed by Streamlit (default `http://localhost:8501`).

Notes:
- The scripts use a prefix-based env at `./.venv` so you do not need to `conda init` or manually activate anything.
- If you prefer, you can still `conda activate /abs/path/to/.venv` and run `python -m streamlit run app.py` by hand.

### How it works (short version)
- IV data are fetched in UTC, converted to America/Denver for display, then made timezone-naive for Arrow/Streamlit compatibility.
- DV data are date-indexed (no timezone).
- Data are cached to `./data/` as Parquet for speed. If you change windows (e.g., IV days, DV years), new cache files are written.

### JSON debug views
For easier troubleshooting of timestamp and schema, the app includes expanders showing small slices of the raw JSON from USGS:
- “Raw IV JSON (sample)” under the IV section
- “Raw DV JSON (sample)” under the DV section

### Troubleshooting
- **“bad interpreter” or temp-dir shebang errors when starting Streamlit**
  - We invoke Streamlit via `python -m streamlit` inside the env. Always use `./run.sh`. If you still see issues, remove `./.venv` and run `./setup.sh` again.

- **ArrowInvalid / tz-aware timestamp errors in Streamlit tables**
  - This app normalizes datetimes before display. If you still see Arrow errors:
    - Ensure deps match `requirements.txt` (notably `pandas>=2.2` and `pyarrow`).
    - Delete stale cache files in `./data/` and refresh.

- **Port already in use**
  - Stop the other process, or run on a different port: `python -m streamlit run app.py --server.port 8502`

- **Watchdog warning**
  - Optional, but recommended for faster file-change detection: `pip install watchdog`

### USGS site catalog
Defined in `usgs.py` (`SITE_CATALOG`). You can add more site codes as needed, e.g.:
```
"Colorado River near Cameo (09095500)": "09095500",
"Gunnison River near Grand Junction (09152500)": "09152500",
"Colorado River at CO–UT State Line (09163500)": "09163500",
```

### Development
- Python formatting and style: keep code readable and explicit
- Cached data: safe to delete `./data/*.parquet` when schemas change

### License
No license specified. Add one if you intend to distribute.


