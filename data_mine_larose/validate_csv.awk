#!/usr/bin/env awk -f
# validate_csv.awk — strict CSV validator
# Usage:
#   awk -f validate_csv.awk [-v allow_empty=0|1] [-v allow_multiline=1|0] file.csv
# Exits 0 on success; nonzero on any validation error.

BEGIN {
  allow_empty     = (allow_empty == "") ? 0 : allow_empty + 0
  allow_multiline = (allow_multiline == "") ? 1 : allow_multiline + 0
  errors = 0
  header_fields = -1
}

# --- helpers ---------------------------------------------------------------

function trim(s,    t) {
  t = s
  sub(/^[ \t\r\n]+/, "", t)
  sub(/[ \t\r\n]+$/, "", t)
  return t
}

# parse_csv(line, fields, qflags)
# RFC-4180-ish CSV parser (no external deps)
# - Handles commas inside quotes and escaped quotes ("")
# - Returns number of fields (>=1) on success
# - Returns 0 and sets global errmsg on error
# - Sets global need_more=1 if the line ends with an open quoted field
function parse_csv(line, fields, qflags,    i, ch, nextc, inq, n, cur, was_quoted, at_start, after_quote, L) {
  # Remove a single trailing CR (support CRLF)
  sub(/\r$/, "", line)
  L = length(line)

  delete fields; delete qflags
  errmsg = ""
  need_more = 0
  n = 0; cur = ""
  inq = 0; was_quoted = 0; after_quote = 0
  at_start = 1

  for (i = 1; i <= L; i++) {
    ch = substr(line, i, 1)

    if (inq) {
      if (ch == "\"") {
        nextc = (i < L) ? substr(line, i+1, 1) : ""
        if (nextc == "\"") {       # escaped quote: "" -> "
          cur = cur "\""
          i++
        } else {
          inq = 0
          after_quote = 1
        }
      } else {
        cur = cur ch
      }
    } else { # not in quotes
      if (after_quote) {
        # After a closing quote, RFC-4180 only allows comma or end-of-line.
        # Some tools tolerate spaces; we reject non-space junk by default.
        if (ch == ",") {
          n++; fields[n] = cur; qflags[n] = 1
          cur = ""; was_quoted = 0; at_start = 1; after_quote = 0
          continue
        } else if (ch ~ /[ \t]/) {
          # tolerate spaces/tabs until the comma/EOL (do NOT add to cur)
          continue
        } else {
          errmsg = "trailing characters after closing quote"
          return 0
        }
      }

      if (ch == ",") {             # delimiter
        n++; fields[n] = cur; qflags[n] = was_quoted ? 1 : 0
        cur = ""; was_quoted = 0; at_start = 1
      } else if (ch == "\"") {
        if (!at_start) {
          errmsg = "unexpected quote in unquoted field"
          return 0
        }
        inq = 1; was_quoted = 1; at_start = 0
      } else {
        cur = cur ch
        at_start = 0
      }
    }
  }

  if (inq) {
    need_more = 1   # unfinished quoted field; caller may append next line(s)
  }

  if (after_quote) {
    # ended with a quoted field; finalize it
    n++; fields[n] = cur; qflags[n] = 1
  } else {
    # finalize last field (quoted or not)
    n++; fields[n] = cur; qflags[n] = was_quoted ? 1 : 0
  }

  return n
}

# parse_record(record_or_first_line, fields, qflags)
# - If a quoted field is left open and allow_multiline==1, keep getline()ing and re-parse
# - Returns number of fields on success, or 0 on error (errmsg set)
function parse_record(line, fields, qflags,    joined, n, more) {
  joined = line
  for (;;) {
    n = parse_csv(joined, fields, qflags)
    if (n > 0 && !need_more) return n

    if (n == 0 && errmsg != "unclosed quoted field") return 0
    if (!allow_multiline) { errmsg = "newline in quoted field not allowed"; return 0 }

    more = (getline extra) > 0
    if (!more) { errmsg = "unclosed quoted field at EOF"; return 0 }
    joined = joined "\n" extra
  }
}

# --- main ------------------------------------------------------------------

{
  # Reject empty/whitespace-only lines
  if ($0 ~ /^[[:space:]]*$/) {
    errors++
    printf("Line %d: empty/whitespace-only line is not allowed\n", NR) > "/dev/stderr"
    next
  }

  n = parse_record($0, F, Q)
  if (n == 0) {
    errors++
    printf("Line %d: parse error: %s\n", NR, errmsg) > "/dev/stderr"
    next
  }

  if (NR == 1) {
    # Header: require all fields double-quoted; allow empty only if allow_empty=1
    for (i = 1; i <= n; i++) {
      if (Q[i] != 1) {
        errors++
        printf("Line 1: header field %d is not double-quoted\n", i) > "/dev/stderr"
      } else if (!allow_empty && length(trim(F[i])) == 0) {
        errors++
        printf("Line 1: header field %d is empty (set -v allow_empty=1 to allow)\n", i) > "/dev/stderr"
      }
    }
    header_fields = n
  } else {
    if (n != header_fields) {
      errors++
      printf("Line %d: wrong number of fields (got %d, expected %d)\n", NR, n, header_fields) > "/dev/stderr"
    }
  }
}

END {
  if (header_fields < 0) {
    print "Error: file contained no header line." > "/dev/stderr"
    exit 2
  }
  exit errors ? 1 : 0
}