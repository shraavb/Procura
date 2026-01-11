"""
Tools for parsing BOM files in various formats.
"""
import logging
import re
from typing import Optional
from decimal import Decimal

import pandas as pd
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def detect_column_mapping(df: pd.DataFrame) -> dict[str, str]:
    """
    Detect which columns contain BOM data based on column names.

    Returns mapping of: {bom_field: column_name}
    """
    column_map = {}
    columns_lower = {col: str(col).lower().strip() for col in df.columns}

    # Part number patterns - prioritize explicit part number columns
    pn_patterns_priority = ["part number", "part_number", "partnumber", "part no", "part #", "pn", "p/n", "mpn", "mfr part"]
    pn_patterns_fallback = ["part", "item", "sku", "item_number", "itemnumber", "libref", "lib ref"]

    # First try priority patterns (exact part number columns)
    for col, col_lower in columns_lower.items():
        # Skip columns that have "supplier" in them - those are supplier part numbers, not the main part number
        if "supplier" in col_lower:
            continue
        if any(pattern in col_lower for pattern in pn_patterns_priority):
            column_map["part_number"] = col
            break

    # If not found, try fallback patterns
    if "part_number" not in column_map:
        for col, col_lower in columns_lower.items():
            if "supplier" in col_lower:
                continue
            if any(pattern in col_lower for pattern in pn_patterns_fallback):
                column_map["part_number"] = col
                break

    # Description patterns - prioritize "description" over fallbacks like "comment"
    desc_patterns_priority = ["description", "desc"]
    desc_patterns_fallback = ["comment", "name", "item_name", "part_name", "component", "value"]

    # First try priority patterns
    for col, col_lower in columns_lower.items():
        if any(pattern in col_lower for pattern in desc_patterns_priority) and "description" not in column_map:
            column_map["description"] = col
            break

    # If not found, try fallback patterns
    if "description" not in column_map:
        for col, col_lower in columns_lower.items():
            if any(pattern in col_lower for pattern in desc_patterns_fallback):
                column_map["description"] = col
                break

    # Quantity patterns
    qty_patterns = ["qty", "quantity", "qnty", "count", "amount"]
    for col, col_lower in columns_lower.items():
        if any(pattern in col_lower for pattern in qty_patterns) and "quantity" not in column_map:
            column_map["quantity"] = col
            break

    # Unit of measure patterns
    uom_patterns = ["uom", "unit", "u/m", "unit_of_measure", "measure"]
    for col, col_lower in columns_lower.items():
        if any(pattern in col_lower for pattern in uom_patterns) and "uom" not in column_map:
            column_map["uom"] = col
            break

    # Designator/Reference - useful for electronics BOMs
    ref_patterns = ["designator", "ref des", "reference", "ref"]
    for col, col_lower in columns_lower.items():
        if any(pattern in col_lower for pattern in ref_patterns) and "designator" not in column_map:
            column_map["designator"] = col
            break

    return column_map


def clean_quantity(value) -> Optional[Decimal]:
    """Clean and convert quantity value to Decimal."""
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        return Decimal(str(value))

    # Try to extract number from string
    value_str = str(value).strip()
    match = re.search(r"[\d.]+", value_str)
    if match:
        return Decimal(match.group())

    return None


def clean_part_number(value) -> Optional[str]:
    """Clean part number value."""
    if pd.isna(value):
        return None

    pn = str(value).strip()
    # Remove common prefixes/suffixes
    pn = re.sub(r"^[#\-\s]+", "", pn)
    return pn if pn else None


def find_header_row(file_path: str, sheet_name: Optional[str] = None) -> int:
    """
    Find the row containing column headers in a BOM file.

    Scans for rows containing recognizable BOM column headers like
    'Part Number', 'Description', 'Quantity', etc.

    Returns the 0-based row index of the header row.
    """
    # Read without headers to scan all rows
    if sheet_name:
        df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
    else:
        df_raw = pd.read_excel(file_path, sheet_name=0, header=None)

    # Patterns that indicate a header row
    header_patterns = [
        "part number", "part_number", "partnumber", "part no", "part #", "pn", "p/n",
        "description", "desc", "component",
        "quantity", "qty", "qnty",
        "designator", "ref des", "reference",
        "manufacturer", "mfr", "mfg",
        "footprint", "package",
    ]

    # Scan first 30 rows to find header row
    for row_idx in range(min(30, len(df_raw))):
        row_values = df_raw.iloc[row_idx].astype(str).str.lower().str.strip()
        matches = sum(1 for val in row_values if any(pattern in val for pattern in header_patterns))
        # If we find 2+ matching column headers, this is likely the header row
        if matches >= 2:
            return row_idx

    # Default to first row if no header row found
    return 0


@tool
def parse_excel_bom(file_path: str, sheet_name: Optional[str] = None) -> dict:
    """
    Parse a BOM from an Excel file.

    Args:
        file_path: Path to the Excel file
        sheet_name: Optional specific sheet to parse (defaults to first sheet)

    Returns:
        Dictionary with parsed items and metadata
    """
    try:
        # Find the actual header row (skip metadata sections)
        header_row = find_header_row(file_path, sheet_name)
        logger.info(f"Detected header row at index {header_row}")

        # Read Excel file starting from the detected header row
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row)
        else:
            df = pd.read_excel(file_path, sheet_name=0, header=header_row)

        # Detect column mapping
        column_map = detect_column_mapping(df)
        logger.info(f"Detected columns: {list(df.columns)}")
        logger.info(f"Column mapping: {column_map}")

        if not column_map:
            return {
                "success": False,
                "error": "Could not detect BOM columns. Please ensure columns are labeled.",
                "items": [],
            }

        # Parse rows
        items = []
        warnings = []

        for idx, row in df.iterrows():
            # Skip empty rows
            if row.isna().all():
                continue

            # Extract values based on detected columns
            part_number = None
            description = None
            quantity = None
            uom = "EA"

            if "part_number" in column_map:
                part_number = clean_part_number(row.get(column_map["part_number"]))

            if "description" in column_map:
                desc_val = row.get(column_map["description"])
                description = str(desc_val).strip() if not pd.isna(desc_val) else None

            if "quantity" in column_map:
                quantity = clean_quantity(row.get(column_map["quantity"]))

            if "uom" in column_map:
                uom_val = row.get(column_map["uom"])
                if not pd.isna(uom_val):
                    uom = str(uom_val).strip().upper()

            # Skip rows without part number or quantity
            if not part_number and not description:
                continue

            if quantity is None or quantity <= 0:
                warnings.append(f"Row {idx + 2}: Missing or invalid quantity for {part_number or description}")
                quantity = Decimal("1")  # Default to 1

            items.append({
                "line_number": len(items) + 1,
                "part_number_raw": part_number,
                "description_raw": description,
                "quantity": float(quantity),
                "unit_of_measure": uom,
            })

        return {
            "success": True,
            "items": items,
            "total_items": len(items),
            "column_mapping": column_map,
            "warnings": warnings,
        }

    except Exception as e:
        logger.error(f"Failed to parse Excel BOM: {e}")
        return {
            "success": False,
            "error": str(e),
            "items": [],
        }


@tool
def parse_csv_bom(file_path: str, delimiter: str = ",") -> dict:
    """
    Parse a BOM from a CSV file.

    Args:
        file_path: Path to the CSV file
        delimiter: Column delimiter (default: comma)

    Returns:
        Dictionary with parsed items and metadata
    """
    try:
        # Use error handling for malformed CSVs
        df = pd.read_csv(file_path, delimiter=delimiter, on_bad_lines='warn', quoting=1)

        # Reuse Excel parsing logic
        column_map = detect_column_mapping(df)

        if not column_map:
            return {
                "success": False,
                "error": "Could not detect BOM columns. Please ensure columns are labeled.",
                "items": [],
            }

        items = []
        warnings = []

        for idx, row in df.iterrows():
            if row.isna().all():
                continue

            part_number = None
            description = None
            quantity = None
            uom = "EA"

            if "part_number" in column_map:
                part_number = clean_part_number(row.get(column_map["part_number"]))

            if "description" in column_map:
                desc_val = row.get(column_map["description"])
                description = str(desc_val).strip() if not pd.isna(desc_val) else None

            if "quantity" in column_map:
                quantity = clean_quantity(row.get(column_map["quantity"]))

            if "uom" in column_map:
                uom_val = row.get(column_map["uom"])
                if not pd.isna(uom_val):
                    uom = str(uom_val).strip().upper()

            if not part_number and not description:
                continue

            if quantity is None or quantity <= 0:
                warnings.append(f"Row {idx + 2}: Missing or invalid quantity")
                quantity = Decimal("1")

            items.append({
                "line_number": len(items) + 1,
                "part_number_raw": part_number,
                "description_raw": description,
                "quantity": float(quantity),
                "unit_of_measure": uom,
            })

        return {
            "success": True,
            "items": items,
            "total_items": len(items),
            "column_mapping": column_map,
            "warnings": warnings,
        }

    except Exception as e:
        logger.error(f"Failed to parse CSV BOM: {e}")
        return {
            "success": False,
            "error": str(e),
            "items": [],
        }


@tool
def validate_bom_structure(items: list[dict]) -> dict:
    """
    Validate the structure and completeness of parsed BOM items.

    Args:
        items: List of parsed BOM items

    Returns:
        Validation results with issues and suggestions
    """
    issues = []
    warnings = []

    if not items:
        return {
            "valid": False,
            "issues": ["No items found in BOM"],
            "warnings": [],
        }

    seen_part_numbers = set()
    seen_line_numbers = set()

    for item in items:
        line = item.get("line_number", "?")

        # Check for duplicates
        pn = item.get("part_number_raw")
        if pn:
            if pn in seen_part_numbers:
                warnings.append(f"Line {line}: Duplicate part number '{pn}'")
            seen_part_numbers.add(pn)

        # Check line number uniqueness
        if line in seen_line_numbers:
            issues.append(f"Duplicate line number: {line}")
        seen_line_numbers.add(line)

        # Validate required fields
        if not pn and not item.get("description_raw"):
            issues.append(f"Line {line}: Missing both part number and description")

        # Validate quantity
        qty = item.get("quantity")
        if qty is None:
            issues.append(f"Line {line}: Missing quantity")
        elif qty <= 0:
            issues.append(f"Line {line}: Invalid quantity ({qty})")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "total_items": len(items),
        "unique_parts": len(seen_part_numbers),
    }
