#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

cd -- "$(dirname -- "${BASH_SOURCE[0]:-$0}")"
here="$(pwd)"

DATA_DIR="$here/data"
ARCHIVE_DIR="$here/archive"

mkdir -p "$ARCHIVE_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' RETURN

# Normalize line endings: CRLF/CR -> LF, write to stdout
normalize_to_lf() {
  # awk version avoids nonstandard deps (dos2unix/perl)
  awk '{ sub(/\r$/, ""); print }' "$1"
}

# Is csv with same number of columns in each row and header line
is_csv() {
  local path="$1"
  [[ -f "$path" ]] || return 1
  # sample first 20 non-empty lines
  awk -F',' '
    NF>0 {
      commas = gsub(/,/, ",")
      if (max_fields == 0) max_fields = NF
      if (NF != max_fields) bad=1
      if ($0 ~ /\t|;/) bad=1
      if (NR>20) exit
    }
    END { exit bad }
  ' "$path"
}

archive_one() {
  local dataset="$1"
  local src="$DATA_DIR/$dataset.csv"

  if [[ ! -f "$src" ]]; then
    echo "skip: $dataset (missing $src)" >&2
    return 0
  fi
  if ! is_csv "$src"; then
    echo "skip: $dataset (not detected as CSV)" >&2
    return 0
  fi

  # Normalize into temp dir with a clean filename
  normalize_to_lf "$src" > "$tmpdir/$dataset.csv"

  # Create a zip with just dataset.csv inside; -X strips extra attrs; -j drops paths
  ( cd "$TMP_DIR" && zip -q -X -j "$dataset.csv.zip" "$dataset.csv" )

  mv -f "$TMP_DIR/$dataset.csv.zip" "$ARCHIVE_DIR/$dataset.csv.zip"
  echo "archived: $dataset -> archive/$dataset.csv.zip"
}

main() {
  local datasets=()

  if (( $# == 0 )); then
    # No args: archive all *.csv in data/
    if [[ -d "$DATA_DIR" ]]; then
      while IFS= read -r f; do
        [[ -e "$f" ]] || continue
        datasets+=( "$(basename "${f%.csv}")" )
      done < <(cd "$DATA_DIR" && printf '%s\n' *.csv 2>/dev/null || true)
    fi
  else
    # Use provided dataset basenames (without .csv)
    for d in "$@"; do
      datasets+=( "$d" )
    done
  fi

  if (( ${#datasets[@]} == 0 )); then
    echo "Nothing to do. Provide dataset names or add CSVs to $DATA_DIR." >&2
    echo "Usage: $(basename "$0") [dataset [dataset ...]]" >&2
    exit 0
  fi

  for d in "${datasets[@]}"; do
    archive_one "$d"
  done
}

main "$@"