"""
core/pdf_converter.py

Converts bank-statement PDFs (and Excel/CSV) into pandas DataFrames.

Key behaviours:
  - Handles multi-page PDFs where the header row repeats on every page
  - Normalises column names: strips whitespace and embedded newlines
  - Drops entirely-empty rows/columns that pdfplumber inserts as separators
  - Falls back to camelot for complex/scanned PDFs (if installed)
  - Raises a clear error for image-only (scanned) PDFs with no extractable text
"""

import os
import re
import pandas as pd
import pdfplumber
from typing import Optional

try:
    import camelot
    CAMELOT_AVAILABLE = True
except Exception:
    CAMELOT_AVAILABLE = False


# ─── Public API ────────────────────────────────────────────────────────────────

def pdf_to_dataframe(file_path: str) -> pd.DataFrame:
    """
    Convert a PDF file to a pandas DataFrame.
    Tries pdfplumber first (text-based PDFs), falls back to camelot.
    """
    df = _try_pdfplumber(file_path)
    if df is not None and len(df) > 0:
        return df

    df = _try_camelot(file_path)
    if df is not None and len(df) > 0:
        return df

    raise ValueError(
        "Could not extract table data from this PDF. "
        "The file may be a scanned image or contains no structured table. "
        "Please export the bank statement as Excel (.xlsx) or CSV instead."
    )


def detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return "pdf"
    elif ext in [".xlsx", ".xls"]:
        return "excel"
    elif ext == ".csv":
        return "csv"
    else:
        return "unknown"


def _find_csv_header_row(file_path: str, encoding: str = "utf-8", max_scan: int = 35) -> int:
    """
    Scan the first `max_scan` rows of a CSV to find the actual header row.

    Heuristic: the header row is the first row that:
      - has multiple non-empty columns (at least 3)
      - does NOT look like a key-value metadata line (no ':- ' or ':--')
      - is followed by rows with similar structure

    Returns the 0-based row index to pass as `skiprows` to pd.read_csv.
    Returns 0 if no metadata prefix is detected (normal CSV).
    """
    try:
        with open(file_path, encoding=encoding, errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_scan:
                    break
                # Skip blank lines
                stripped = line.strip()
                if not stripped:
                    continue
                # Skip obvious metadata lines (contain ':- ' or ':--' patterns)
                if re.search(r':-', stripped):
                    continue
                # Count comma-separated segments
                parts = stripped.split(',')
                non_empty = [p.strip() for p in parts if p.strip()]
                # A real header has ≥3 populated columns and at least 2 look
                # like column names (not plain integers or currency values)
                if len(non_empty) >= 3:
                    text_like = [p for p in non_empty if not re.match(r'^[\d,.\s]+$', p)]
                    if len(text_like) >= 2:
                        return i
    except Exception:
        pass
    return 0


def _find_excel_header_row(file_path: str, max_scan: int = 10) -> int:
    """
    Scan first rows of an Excel file to locate the actual column-header row.
    Some partner reports (e.g. Indonepal) embed 1–2 metadata lines before the
    real header.  Heuristic: first row with ≥ 3 distinct text-like values.
    Returns the 0-based row index; 0 means row 0 is already the header.
    """
    try:
        df_raw = pd.read_excel(file_path, header=None, nrows=max_scan, dtype=str)
        for i, row in df_raw.iterrows():
            vals = [str(v).strip() for v in row
                    if str(v).strip() not in ('', 'nan', 'None', 'NaN')]
            # Exclude rows that are just numbers / filter strings / separators
            text_like = [v for v in vals
                         if not re.match(r'^[\d,.\s|=\-:]+$', v)
                         and len(v) > 1]
            if len(text_like) >= 3:
                return int(i)
    except Exception:
        pass
    return 0


def load_file_to_dataframe(file_path: str, filename: str) -> pd.DataFrame:
    file_type = detect_file_type(filename)
    if file_type == "pdf":
        return pdf_to_dataframe(file_path)
    elif file_type == "excel":
        skip = _find_excel_header_row(file_path)
        df = pd.read_excel(file_path, dtype=str, skiprows=skip)
        # Drop rows where ALL cells are blank (e.g. stray footer / Total rows
        # where every column is NaN after the real data).
        df = df.dropna(how='all').reset_index(drop=True)
        return df
    elif file_type == "csv":
        for enc in ("utf-8", "latin1", "cp1252"):
            try:
                skip = _find_csv_header_row(file_path, encoding=enc)
                df = pd.read_csv(file_path, dtype=str, skiprows=skip, encoding=enc)
                if len(df.columns) >= 2:
                    return df
            except Exception:
                continue
        raise ValueError(f"Could not read CSV file: {filename}")
    else:
        raise ValueError(f"Unsupported file type: {filename}")


# ─── Internal helpers ──────────────────────────────────────────────────────────

def _normalise_col(name: str) -> str:
    """
    Normalise a PDF-extracted column name:
      - Strip leading/trailing whitespace
      - Collapse embedded newlines and multiple spaces to a single space
    """
    if not name:
        return name
    return re.sub(r'\s+', ' ', str(name)).strip()


def _is_repeated_header(row: list, headers: list, threshold: float = 0.6) -> bool:
    """
    Return True if `row` looks like a repeated header from a subsequent page.
    We compare normalised lowercase values; at least `threshold` fraction
    of non-empty header positions must match.
    """
    if not row or not headers:
        return False
    n = min(len(row), len(headers))
    # Only consider positions where the reference header is non-empty
    ref_positions = [(i, h.strip().lower()) for i, h in enumerate(headers[:n]) if h.strip()]
    if not ref_positions:
        return False
    matches = sum(
        1 for i, h in ref_positions
        if str(row[i]).strip().lower() == h
    )
    return matches >= max(2, len(ref_positions) * threshold)


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Post-process a raw PDF-extracted DataFrame:
      1. Drop columns that are entirely NaN/empty
      2. Drop rows where every cell matches its column name (stray header rows)
      3. Drop rows that are entirely NaN/empty
    """
    # Drop fully-empty columns
    df = df.dropna(axis=1, how="all")
    df = df.loc[:, ~(df == "").all()]

    # Drop rows that are an exact repeat of the header
    col_names_lower = [c.strip().lower() for c in df.columns]
    def is_header_row(row):
        return all(
            str(v).strip().lower() == col_names_lower[i]
            for i, v in enumerate(row)
        )
    df = df[~df.apply(is_header_row, axis=1)]

    # Drop fully-empty rows
    df = df.replace("", pd.NA).dropna(how="all")

    return df.reset_index(drop=True)


def _try_pdfplumber(file_path: str) -> Optional[pd.DataFrame]:
    """
    Extract tables from a text-based PDF using pdfplumber.

    Multi-page strategy:
      - First table on the first page defines the headers.
      - Subsequent tables on later pages check whether their first row is a
        repeated header; if so, it is skipped.
      - Columns whose names contain newlines (common in wrapped PDF headers)
        are normalised to single-space strings.
    """
    try:
        all_rows: list = []
        headers: Optional[list] = None

        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if not table or len(table) < 2:
                        continue

                    first_row = [_normalise_col(str(c)) if c else "" for c in table[0]]

                    if headers is None:
                        # First table: use row 0 as headers, row 1+ as data
                        headers = [h if h else f"col_{i}" for i, h in enumerate(first_row)]
                        data_rows = table[1:]
                    else:
                        # Subsequent tables: check for repeated header row
                        if _is_repeated_header(first_row, headers):
                            data_rows = table[1:]   # skip repeated header
                        else:
                            data_rows = table       # no header repeat; include all rows

                    for row in data_rows:
                        # Skip entirely-blank rows (pdfplumber uses None for empty cells)
                        if not any(cell for cell in row):
                            continue
                        # Pad/trim row to match header length
                        padded = (list(row) + [""] * len(headers))[:len(headers)]
                        all_rows.append([str(c).strip() if c else "" for c in padded])

        if headers and all_rows:
            df = pd.DataFrame(all_rows, columns=headers)
            df = _clean_dataframe(df)
            if len(df) > 0:
                return df

    except Exception as e:
        print(f"[pdf_converter] pdfplumber failed: {e}")

    return None


def _try_camelot(file_path: str) -> Optional[pd.DataFrame]:
    """
    Fallback extractor using camelot (handles complex/borderless tables).
    Skips repeated header rows across pages using the same heuristic.
    """
    if not CAMELOT_AVAILABLE:
        return None
    try:
        tables = camelot.read_pdf(file_path, pages="all", flavor="stream")
        if not tables or len(tables) == 0:
            return None

        dfs = []
        headers: Optional[list] = None

        for t in tables:
            raw = t.df
            if raw.empty:
                continue
            first_row = [_normalise_col(str(v)) for v in raw.iloc[0]]

            if headers is None:
                headers = [h if h.strip() else f"col_{i}" for i, h in enumerate(first_row)]
                raw.columns = headers
                dfs.append(raw.iloc[1:])
            else:
                if _is_repeated_header(first_row, headers):
                    raw.columns = headers
                    dfs.append(raw.iloc[1:])
                else:
                    raw.columns = headers
                    dfs.append(raw)

        if dfs:
            combined = pd.concat(dfs, ignore_index=True)
            combined = _clean_dataframe(combined)
            return combined if len(combined) > 0 else None

    except Exception as e:
        print(f"[pdf_converter] camelot failed: {e}")

    return None
