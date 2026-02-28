from app.tools import register_tool
from pydantic_ai import RunContext
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import pandas as pd
from io import StringIO
import logging

logger = logging.getLogger(__name__)


class AggregationSpec(BaseModel):
    """Specification for a single aggregation operation.

    Gemini-compatible: Uses explicit fields instead of dict.
    """
    column: str = Field(description="Column to aggregate")
    function: str = Field(description="Aggregation function: 'sum', 'count', 'mean', 'min', 'max', 'first', 'last'")


class DataAggregationParams(BaseModel):
    """Parameters for data aggregation operations.

    Gemini-compatible: Uses explicit fields instead of Dict[str, Any].
    """
    # For group_by
    columns: Optional[List[str]] = Field(
        default=None,
        description="Columns to group by (for group_by operation)"
    )
    aggregations: Optional[List[AggregationSpec]] = Field(
        default=None,
        description="List of aggregation specs (for group_by operation)"
    )

    # For filter
    condition: Optional[str] = Field(
        default=None,
        description="Filter condition as pandas query string (for filter operation)"
    )

    # For value_counts
    column: Optional[str] = Field(
        default=None,
        description="Column to count values for (for value_counts operation)"
    )

    # For pivot
    index: Optional[str] = Field(default=None, description="Index column for pivot")
    pivot_columns: Optional[str] = Field(default=None, description="Columns for pivot")
    values: Optional[str] = Field(default=None, description="Values column for pivot")
    aggfunc: Optional[str] = Field(default="sum", description="Aggregation function for pivot")

    # For compute
    expression: Optional[str] = Field(
        default=None,
        description="Pandas expression to compute (for compute operation)"
    )
    column_name: Optional[str] = Field(
        default="computed",
        description="Name for computed column"
    )


@register_tool("data_aggregation")
async def data_aggregation(
    ctx: RunContext[dict],
    data: str,
    operation: str,
    columns: Optional[List[str]] = None,
    aggregations: Optional[List[AggregationSpec]] = None,
    condition: Optional[str] = None,
    column: Optional[str] = None,
    index: Optional[str] = None,
    pivot_columns: Optional[str] = None,
    values: Optional[str] = None,
    aggfunc: Optional[str] = "sum",
    expression: Optional[str] = None,
    column_name: Optional[str] = "computed"
) -> Dict[str, Any]:
    """
    Perform data aggregation operations for analysis.

    Gemini-compatible: Uses explicit parameters instead of Dict[str, Any].

    Args:
        data: CSV string or JSON array to process
        operation: Operation to perform:
            - "describe": Statistical summary (no additional params needed)
            - "group_by": Group and aggregate (use columns + aggregations)
            - "filter": Filter rows by condition (use condition)
            - "value_counts": Count unique values (use column)
            - "pivot": Pivot table (use index, pivot_columns, values, aggfunc)
            - "compute": Compute derived column (use expression, column_name)
        columns: Columns to group by (for group_by)
        aggregations: List of {column, function} specs (for group_by)
        condition: Filter condition as pandas query string (for filter)
        column: Column name for value_counts
        index: Index column for pivot
        pivot_columns: Columns for pivot
        values: Values column for pivot
        aggfunc: Aggregation function for pivot (default: sum)
        expression: Pandas expression for compute
        column_name: Name for computed column (default: computed)

    Returns:
        {"result": ..., "row_count": int, "operation": str}

    Examples:
        # Get statistics
        data_aggregation(csv_data, "describe")

        # Group by and sum
        data_aggregation(csv_data, "group_by",
            columns=["plan_id"],
            aggregations=[{"column": "paid_amount", "function": "sum"}]
        )

        # Filter rows
        data_aggregation(csv_data, "filter", condition="paid_amount > 1000")

        # Value counts
        data_aggregation(csv_data, "value_counts", column="drug_name")
    """

    try:
        # Parse data
        if data.strip().startswith('['):
            import json
            df = pd.DataFrame(json.loads(data))
        else:
            df = pd.read_csv(StringIO(data))

        # Build a mapping from original column names to lowercase for case-insensitive matching
        # Don't rename columns directly to avoid duplicate column name errors
        col_map = {col: col.lower() for col in df.columns}
        col_map_reverse = {v: k for k, v in col_map.items()}  # lowercase -> original

        # Helper to find column with case-insensitive matching
        def find_column(col_name: str) -> str:
            """Find original column name with case-insensitive matching."""
            col_lower = col_name.lower()
            if col_lower in col_map_reverse:
                return col_map_reverse[col_lower]
            return col_name  # Return original if not found

        # Normalize input parameters to lowercase
        if columns:
            columns = [find_column(c) for c in columns]
        if column:
            column = find_column(column)
        if aggregations:
            for spec in aggregations:
                spec.column = find_column(spec.column)
        if condition:
            # Replace column references in condition with actual column names (case-insensitive)
            import re
            for col in df.columns:
                # Match whole words only and replace with the actual column name
                condition = re.sub(rf'\b{re.escape(col)}\b', col, condition, flags=re.IGNORECASE)
        if expression:
            # Replace column references in expression with actual column names (case-insensitive)
            import re
            for col in df.columns:
                expression = re.sub(rf'\b{re.escape(col)}\b', col, expression, flags=re.IGNORECASE)

        logger.info(f"Data aggregation: {operation} on {len(df)} rows")

        if operation == "describe":
            if df.empty or len(df.columns) == 0:
                result = {"message": "No data to describe", "columns": list(df.columns), "rows": 0}
            else:
                result = df.describe(include='all').to_dict()

        elif operation == "group_by":
            if not columns:
                return {
                    "error": "group_by operation requires 'columns' parameter (list of column names to group by)",
                    "operation": operation,
                    "row_count": len(df),
                    "available_columns": list(df.columns),
                    "hint": "Provide column names in columns parameter, e.g., columns=['plan_id', 'drug_name']"
                }
            # Validate columns exist
            missing_cols = [c for c in columns if c not in df.columns]
            if missing_cols:
                return {
                    "error": f"Columns not found: {missing_cols}",
                    "operation": operation,
                    "row_count": len(df),
                    "available_columns": list(df.columns)
                }
            # Build aggregation dict from aggregations list
            if aggregations:
                agg_dict = {spec.column: spec.function for spec in aggregations}
            else:
                agg_dict = "count"  # Default to count if no aggregations specified
            grouped = df.groupby(columns).agg(agg_dict)
            result = grouped.reset_index().to_dict(orient='records')

        elif operation == "filter":
            if not condition or not condition.strip():
                return {
                    "error": "filter operation requires 'condition' parameter (e.g., 'paid_amount > 1000')",
                    "operation": operation,
                    "row_count": len(df),
                    "hint": "Provide a valid pandas query condition in condition parameter"
                }
            filtered = df.query(condition)
            result = {
                "filtered_data": filtered.to_csv(index=False),
                "rows_before": len(df),
                "rows_after": len(filtered)
            }

        elif operation == "value_counts":
            if not column or not column.strip():
                return {
                    "error": "value_counts operation requires 'column' parameter",
                    "operation": operation,
                    "row_count": len(df),
                    "available_columns": list(df.columns),
                    "hint": "Provide a column name in column parameter"
                }
            if column not in df.columns:
                return {
                    "error": f"Column '{column}' not found in data",
                    "operation": operation,
                    "row_count": len(df),
                    "available_columns": list(df.columns)
                }
            counts = df[column].value_counts()
            result = counts.to_dict()

        elif operation == "pivot":
            pivoted = pd.pivot_table(df, index=index, columns=pivot_columns, values=values, aggfunc=aggfunc)
            result = pivoted.to_dict()

        elif operation == "compute":
            if not expression or not expression.strip():
                return {
                    "error": "compute operation requires 'expression' parameter (e.g., 'column_a + column_b' or 'price * quantity')",
                    "operation": operation,
                    "row_count": len(df),
                    "hint": "Provide a valid pandas expression in expression parameter"
                }
            logger.info(f"Compute expression: {expression[:200]}...")
            try:
                df[column_name] = df.eval(expression)
                result = {"data": df.to_csv(index=False)}
            except Exception as eval_error:
                logger.error(f"Compute eval failed for expression '{expression[:100]}': {eval_error}")
                return {
                    "error": f"Invalid expression: {eval_error}. Expression must reference column names directly (e.g., 'price * quantity'), not 'df.column'.",
                    "operation": operation,
                    "row_count": len(df),
                    "available_columns": list(df.columns),
                    "hint": "Use column names directly like 'column_a + column_b', not 'df[\"column_a\"]'"
                }

        else:
            result = {"error": f"Unknown operation: {operation}"}

        return {
            "result": result,
            "row_count": len(df),
            "operation": operation
        }

    except Exception as e:
        logger.error(f"Data aggregation error: {e}")
        return {
            "error": str(e),
            "operation": operation,
            "row_count": 0
        }
