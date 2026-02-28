"""
csv_parser.py - CSV parsing and type detection
"""

import csv
import io
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.workflows.data_loading.models import CSVStructure, CSVColumn

logger = logging.getLogger(__name__)

# Optional chardet import for encoding detection
try:
    import chardet
    _CHARDET_AVAILABLE = True
except ImportError:
    _CHARDET_AVAILABLE = False
    logger.warning("chardet not available. Encoding detection will default to utf-8")


def detect_encoding(content: bytes) -> str:
    """Detect file encoding."""
    if not _CHARDET_AVAILABLE:
        logger.debug("chardet not available, defaulting to utf-8")
        return 'utf-8'
    
    try:
        result = chardet.detect(content)
        encoding = result.get('encoding', 'utf-8')
        confidence = result.get('confidence', 0)
        
        # Fallback to utf-8 if confidence is low
        if confidence < 0.7:
            encoding = 'utf-8'
        
        logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
        return encoding
    except Exception as e:
        logger.warning(f"Failed to detect encoding: {e}. Using utf-8")
        return 'utf-8'


def infer_data_type(values: List[str], sample_size: int = 10) -> str:
    """
    Infer data type from sample values.
    
    Returns: string, integer, float, date, boolean
    """
    if not values:
        return "string"
    
    # Sample values for type detection
    sample = values[:sample_size]
    
    # Check for boolean
    bool_count = 0
    for v in sample:
        v_lower = str(v).strip().lower()
        if v_lower in ('true', 'false', 'yes', 'no', '1', '0', 'y', 'n'):
            bool_count += 1
    if bool_count == len(sample) and len(sample) > 0:
        return "boolean"
    
    # Check for integer
    int_count = 0
    for v in sample:
        v_stripped = str(v).strip()
        if v_stripped and v_stripped.replace('-', '').replace('+', '').isdigit():
            int_count += 1
    if int_count == len(sample) and len(sample) > 0:
        return "integer"
    
    # Check for float
    float_count = 0
    for v in sample:
        v_stripped = str(v).strip()
        try:
            float(v_stripped)
            float_count += 1
        except (ValueError, TypeError):
            pass
    if float_count == len(sample) and len(sample) > 0:
        # If all are integers, prefer integer
        if int_count == len(sample):
            return "integer"
        return "float"
    
    # Check for date (common formats)
    date_formats = [
        '%Y-%m-%d',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y-%m-%d %H:%M:%S',
        '%m/%d/%Y %H:%M:%S',
        '%d-%m-%Y',
        '%Y/%m/%d',
    ]
    date_count = 0
    for v in sample:
        v_stripped = str(v).strip()
        if v_stripped:
            for fmt in date_formats:
                try:
                    datetime.strptime(v_stripped, fmt)
                    date_count += 1
                    break
                except ValueError:
                    continue
    if date_count >= len(sample) * 0.8 and len(sample) > 0:  # 80% match
        return "date"
    
    # Default to string
    return "string"


def parse_csv(
    content: bytes,
    has_headers: Optional[bool] = None,
    encoding: Optional[str] = None,
    max_rows: Optional[int] = None
) -> tuple[List[Dict[str, str]], CSVStructure]:
    """
    Parse CSV content and return rows + structure.
    
    Args:
        content: CSV file content as bytes
        has_headers: Whether CSV has headers (None = auto-detect)
        encoding: File encoding (None = auto-detect)
        max_rows: Maximum rows to parse (None = all)
    
    Returns:
        Tuple of (rows, CSVStructure)
    """
    # Detect encoding
    if encoding is None:
        encoding = detect_encoding(content)
    
    # Decode content
    try:
        text = content.decode(encoding)
    except UnicodeDecodeError:
        # Try utf-8 as fallback
        logger.warning(f"Failed to decode with {encoding}, trying utf-8")
        encoding = 'utf-8'
        text = content.decode(encoding, errors='ignore')
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(text))
    
    # Check if headers exist
    if has_headers is None:
        # If DictReader has fieldnames, headers exist
        has_headers = reader.fieldnames is not None
    
    rows = []
    column_values: Dict[str, List[str]] = {}
    
    # Collect rows and column values
    row_count = 0
    for row in reader:
        if max_rows and row_count >= max_rows:
            break
        
        rows.append(row)
        row_count += 1
        
        # Collect values for each column
        for col_name, value in row.items():
            if col_name not in column_values:
                column_values[col_name] = []
            if value:  # Only collect non-empty values
                column_values[col_name].append(str(value))
    
    # Build CSV structure
    columns = []
    for col_name in reader.fieldnames or []:
        values = column_values.get(col_name, [])
        data_type = infer_data_type(values)
        
        columns.append(CSVColumn(
            name=col_name,
            data_type=data_type,
            sample_values=values[:10],  # Keep first 10 samples
            nullable=len(values) < row_count  # Has nulls if fewer values than rows
        ))
    
    structure = CSVStructure(
        columns=columns,
        row_count=len(rows),
        has_headers=has_headers,
        encoding=encoding
    )
    
    logger.info(f"Parsed CSV: {len(columns)} columns, {len(rows)} rows")
    return rows, structure


def parse_csv_from_blob(
    blob_path: str,
    tenant_id: str,
    blob_service: Optional[Any] = None
) -> tuple[List[Dict[str, str]], CSVStructure]:
    """
    Parse CSV from blob storage.
    
    Args:
        blob_path: Path to CSV blob (e.g., "data-loading/{tenantId}/{runId}/input.csv")
        tenant_id: Tenant ID
        blob_service: Optional blob service client
    
    Returns:
        Tuple of (rows, CSVStructure)
    """
    try:
        from azure.storage.blob import BlobServiceClient
        from azure.identity import DefaultAzureCredential
        from app.config import Config
        
        # Get blob client
        if blob_service is None:
            conn_str = Config.AZURE_STORAGE_CONNECTION_STRING
            if conn_str:
                blob_service = BlobServiceClient.from_connection_string(conn_str)
            else:
                account_name = Config.AZURE_STORAGE_ACCOUNT_NAME
                if account_name:
                    credential = DefaultAzureCredential(
                        exclude_workload_identity_credential=True,
                        exclude_developer_cli_credential=True,
                        exclude_powershell_credential=True,
                        exclude_visual_studio_code_credential=True,
                        exclude_shared_token_cache_credential=True,
                    )
                    account_url = f"https://{account_name}.blob.core.windows.net"
                    blob_service = BlobServiceClient(account_url=account_url, credential=credential)
                else:
                    raise ValueError("Azure Storage not configured")
        
        # Extract container and blob name from path
        # Path format: "data-loading/{tenantId}/{runId}/input.csv"
        parts = blob_path.split('/')
        if len(parts) < 2:
            raise ValueError(f"Invalid blob path: {blob_path}")
        
        container_name = 'data-loading'#Config.DOCUMENT_PROCESSED_CONTAINER  # Reuse same container
        blob_name = blob_path
        
        # Download blob
        container = blob_service.get_container_client(container_name)
        blob = container.get_blob_client(blob_name)
        content = blob.download_blob().readall()
        
        logger.info(f"Downloaded CSV from blob: {blob_path} ({len(content)} bytes)")
        
        return parse_csv(content)
        
    except Exception as e:
        logger.error(f"Failed to parse CSV from blob {blob_path}: {e}")
        raise
