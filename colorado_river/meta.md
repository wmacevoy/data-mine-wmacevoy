## Meta utilities: discovering and configuring USGS sites

This doc explains how to use the meta tooling to discover USGS stream gage sites and how to configure your own site list in `config.json` for the app and CLI.

### What is meta?
- `meta.py` is a small utility that can:
  - Discover USGS sites directly from the USGS Site Service (recommended for exploration)
  - Show only the currently configured sources in `config.json`
- `meta.sh` is a wrapper that runs `meta.py` inside your local environment.

### Quick start
- Run discovery for Colorado sites and print a table:
```bash
./meta.sh --format table
```
- JSON output (e.g., to pipe into `jq`):
```bash
./meta.sh --format json | jq '.usgs_sources | to_entries | .[0:5]'
```

### Options
`./meta.sh [--mode usgs|config] [--format table|json] [--state XX ...] [--parameter codes] [--site-status active|all]`

- **--mode**: `usgs` (default) queries the USGS Site Service. `config` shows only the sites defined in `config.json`.
- **--format**: `table` (default) or `json`.
- **--state**: repeatable state filters (default: `CO`). Example: `--state CO --state UT`.
- **--parameter**: comma-separated parameter codes (default: `00060,00065` for discharge and stage).
- **--site-status**: `active` (default) or `all`.

Examples:
```bash
# All active Colorado stream gages that report discharge (00060) and stage (00065)
./meta.sh --format table

# Colorado + Utah, active sites, show as JSON
./meta.sh --format json --state CO --state UT | jq '.usgs_sources | length'

# Only discharge (flow) in Colorado
./meta.sh --format table --parameter 00060

# Include inactive sites as well (discovery mode)
./meta.sh --format table --site-status all

# Show the currently configured sources from config.json
./meta.sh --mode config --format table
```

### Updating configured sources in config.json
The app reads the `usgs_sources` mapping in `config.json`. Keys are human-readable labels, values are USGS site codes.

Current structure (excerpt):
```json
{
  "usgs_sources": {
    "Colorado River near Cameo (09095500)": "09095500",
    "Gunnison River near Grand Junction (09152500)": "09152500",
    "Colorado River at CO–UT State Line (09163500)": "09163500"
  },
  "debug": true,
  "streamlit": {
    "browser_gather_usage_stats": false,
    "server_headless": true
  }
}
```

Add a site by editing `config.json` or using `jq`:
```bash
# Add Animas River at Durango (09361500)
jq '.usgs_sources += {"Animas River at Durango (09361500)": "09361500"}' config.json > config.tmp && mv config.tmp config.json

# Add two more in one shot
jq '.usgs_sources += {"Eagle River at Avon (09067000)":"09067000", "Roaring Fork River at Glenwood Springs (09085000)":"09085000"}' \
  config.json > config.tmp && mv config.tmp config.json
```

Tip: Use discovery to find labels and site codes you want to add, then paste them into `config.json`.

### Notes
- Discovery uses the USGS Site Service (`/nwis/site/`) in RDB format and filters by state, parameter codes, and site status.
- The app itself will still let you type any site code in the sidebar if you want to do ad-hoc exploration; `config.json` just controls the curated list shown by default.


