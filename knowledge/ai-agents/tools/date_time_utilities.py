"""Date and time utilities tool for analysis workflows.

Why: Agents need to perform date arithmetic, calculate periods, and work with date ranges
when analyzing time-series data, calculating durations, or determining reporting periods.

Use cases:
- Calculate days/months/years between two dates
- Determine fiscal quarters, year-to-date periods
- Parse and format dates consistently
- Calculate age from birthdate
- Determine business days in a period
"""

from __future__ import annotations

import logging
from datetime import datetime, date, timedelta
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from app.tools import register_tool

logger = logging.getLogger(__name__)


class DateRange(BaseModel):
    """A date range with start and end dates."""
    start_date: str = Field(description="Start date (ISO format: YYYY-MM-DD)")
    end_date: str = Field(description="End date (ISO format: YYYY-MM-DD)")
    days: int = Field(description="Number of days in the range")
    months: float = Field(description="Approximate number of months (days/30.44)")
    years: float = Field(description="Approximate number of years (days/365.25)")
    business_days: Optional[int] = Field(default=None, description="Number of business days (Mon-Fri)")


class DateTimeResult(BaseModel):
    """Result from a date/time operation."""
    operation: str = Field(description="The operation performed")
    result: Any = Field(description="The result of the operation")
    formatted: str = Field(description="Human-readable formatted result")
    details: Optional[dict[str, Any]] = Field(default=None, description="Additional details")


def _parse_date(date_str: str) -> date:
    """Parse a date string in various formats."""
    formats = [
        "%Y-%m-%d",      # ISO format
        "%m/%d/%Y",      # US format
        "%d/%m/%Y",      # European format
        "%Y/%m/%d",      # Alternative ISO
        "%B %d, %Y",     # Full month name
        "%b %d, %Y",     # Abbreviated month
        "%Y-%m-%dT%H:%M:%S",  # ISO with time
        "%Y-%m-%dT%H:%M:%SZ", # ISO with UTC
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).date()
        except ValueError:
            continue

    raise ValueError(f"Could not parse date: {date_str}. Supported formats: YYYY-MM-DD, MM/DD/YYYY, etc.")


def _count_business_days(start: date, end: date) -> int:
    """Count business days (Monday-Friday) between two dates."""
    if start > end:
        start, end = end, start

    business_days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            business_days += 1
        current += timedelta(days=1)

    return business_days


def _get_quarter(d: date) -> int:
    """Get the quarter (1-4) for a date."""
    return (d.month - 1) // 3 + 1


def _get_fiscal_quarter(d: date, fiscal_year_start_month: int = 1) -> tuple[int, int]:
    """Get fiscal quarter and fiscal year for a date.

    Args:
        d: The date
        fiscal_year_start_month: Month when fiscal year starts (1=Jan, 7=Jul, 10=Oct)

    Returns:
        Tuple of (fiscal_quarter, fiscal_year)
    """
    # Adjust month relative to fiscal year start
    adjusted_month = (d.month - fiscal_year_start_month) % 12
    fiscal_quarter = adjusted_month // 3 + 1

    # Fiscal year is the calendar year the fiscal year ends in
    if d.month >= fiscal_year_start_month:
        fiscal_year = d.year + (1 if fiscal_year_start_month > 1 else 0)
    else:
        fiscal_year = d.year

    return fiscal_quarter, fiscal_year


@register_tool("date_time_utilities")
async def date_time_utilities(
    _ctx: RunContext[dict],
    operation: Literal[
        "date_diff",
        "add_days",
        "add_months",
        "get_quarter",
        "get_fiscal_quarter",
        "get_period_info",
        "calculate_age",
        "format_date",
        "get_date_range",
        "business_days"
    ],
    date1: Optional[str] = None,
    date2: Optional[str] = None,
    days: Optional[int] = None,
    months: Optional[int] = None,
    fiscal_year_start_month: int = 1,
    output_format: str = "%Y-%m-%d",
) -> dict[str, Any]:
    """Perform date and time calculations for analysis.

    This tool handles common date operations needed in analysis:
    - Calculate differences between dates (days, months, years)
    - Add/subtract days or months from dates
    - Determine quarters (calendar or fiscal)
    - Calculate ages from birthdates
    - Count business days in a range
    - Get period information (year-to-date, quarter-to-date, etc.)

    Args:
        ctx: Pydantic AI context (passed automatically)
        operation: The operation to perform:
            - "date_diff": Calculate difference between date1 and date2
            - "add_days": Add days to date1
            - "add_months": Add months to date1
            - "get_quarter": Get calendar quarter for date1
            - "get_fiscal_quarter": Get fiscal quarter for date1
            - "get_period_info": Get comprehensive period info for date1
            - "calculate_age": Calculate age from date1 (birthdate) to date2 (or today)
            - "format_date": Format date1 using output_format
            - "get_date_range": Get range info between date1 and date2
            - "business_days": Count business days between date1 and date2
        date1: Primary date (ISO format: YYYY-MM-DD)
        date2: Secondary date for comparisons (ISO format: YYYY-MM-DD)
        days: Number of days for add_days operation
        months: Number of months for add_months operation
        fiscal_year_start_month: Month fiscal year starts (1=Jan, 7=Jul, 10=Oct)
        output_format: strftime format for date output (default: %Y-%m-%d)

    Returns:
        Dictionary with operation result, formatted string, and details

    Examples:
        >>> # Calculate days between two dates
        >>> result = await date_time_utilities(ctx, "date_diff", date1="2024-01-01", date2="2024-12-31")
        >>> # Returns: {"operation": "date_diff", "result": 365, "formatted": "365 days (12.0 months)"}

        >>> # Calculate age
        >>> result = await date_time_utilities(ctx, "calculate_age", date1="1985-06-15", date2="2024-01-01")
        >>> # Returns: {"operation": "calculate_age", "result": 38, "formatted": "38 years old"}

        >>> # Get fiscal quarter (October fiscal year start)
        >>> result = await date_time_utilities(ctx, "get_fiscal_quarter", date1="2024-01-15", fiscal_year_start_month=10)
        >>> # Returns: {"operation": "get_fiscal_quarter", "result": {"quarter": 2, "fiscal_year": 2024}}
    """
    try:
        # Parse dates
        d1 = _parse_date(date1) if date1 else None
        d2 = _parse_date(date2) if date2 else date.today()

        if operation == "date_diff":
            if not d1:
                raise ValueError("date1 is required for date_diff")
            diff = (d2 - d1).days
            months_approx = diff / 30.44
            years_approx = diff / 365.25

            return {
                "operation": "date_diff",
                "result": diff,
                "formatted": f"{diff} days ({months_approx:.1f} months, {years_approx:.2f} years)",
                "details": {
                    "days": diff,
                    "months": round(months_approx, 2),
                    "years": round(years_approx, 2),
                    "from_date": d1.isoformat(),
                    "to_date": d2.isoformat()
                }
            }

        elif operation == "add_days":
            if not d1:
                raise ValueError("date1 is required for add_days")
            if days is None:
                raise ValueError("days parameter is required for add_days")
            result_date = d1 + timedelta(days=days)

            return {
                "operation": "add_days",
                "result": result_date.isoformat(),
                "formatted": f"{d1.isoformat()} + {days} days = {result_date.isoformat()}",
                "details": {
                    "original_date": d1.isoformat(),
                    "days_added": days,
                    "result_date": result_date.isoformat()
                }
            }

        elif operation == "add_months":
            if not d1:
                raise ValueError("date1 is required for add_months")
            if months is None:
                raise ValueError("months parameter is required for add_months")

            # Calculate new month and year
            new_month = d1.month + months
            new_year = d1.year + (new_month - 1) // 12
            new_month = ((new_month - 1) % 12) + 1

            # Handle day overflow (e.g., Jan 31 + 1 month)
            import calendar
            max_day = calendar.monthrange(new_year, new_month)[1]
            new_day = min(d1.day, max_day)

            result_date = date(new_year, new_month, new_day)

            return {
                "operation": "add_months",
                "result": result_date.isoformat(),
                "formatted": f"{d1.isoformat()} + {months} months = {result_date.isoformat()}",
                "details": {
                    "original_date": d1.isoformat(),
                    "months_added": months,
                    "result_date": result_date.isoformat()
                }
            }

        elif operation == "get_quarter":
            if not d1:
                raise ValueError("date1 is required for get_quarter")
            quarter = _get_quarter(d1)

            return {
                "operation": "get_quarter",
                "result": quarter,
                "formatted": f"Q{quarter} {d1.year}",
                "details": {
                    "date": d1.isoformat(),
                    "quarter": quarter,
                    "year": d1.year
                }
            }

        elif operation == "get_fiscal_quarter":
            if not d1:
                raise ValueError("date1 is required for get_fiscal_quarter")
            fq, fy = _get_fiscal_quarter(d1, fiscal_year_start_month)

            return {
                "operation": "get_fiscal_quarter",
                "result": {"quarter": fq, "fiscal_year": fy},
                "formatted": f"FQ{fq} FY{fy}",
                "details": {
                    "date": d1.isoformat(),
                    "fiscal_quarter": fq,
                    "fiscal_year": fy,
                    "fiscal_year_start_month": fiscal_year_start_month
                }
            }

        elif operation == "get_period_info":
            if not d1:
                d1 = date.today()

            # Year-to-date
            ytd_start = date(d1.year, 1, 1)
            ytd_days = (d1 - ytd_start).days + 1

            # Quarter-to-date
            quarter = _get_quarter(d1)
            qtd_start = date(d1.year, (quarter - 1) * 3 + 1, 1)
            qtd_days = (d1 - qtd_start).days + 1

            # Month-to-date
            mtd_start = date(d1.year, d1.month, 1)
            mtd_days = (d1 - mtd_start).days + 1

            return {
                "operation": "get_period_info",
                "result": {
                    "year": d1.year,
                    "quarter": quarter,
                    "month": d1.month,
                    "day_of_year": ytd_days,
                    "ytd_days": ytd_days,
                    "qtd_days": qtd_days,
                    "mtd_days": mtd_days
                },
                "formatted": f"{d1.isoformat()}: Q{quarter} {d1.year}, Day {ytd_days} of year, MTD: {mtd_days} days",
                "details": {
                    "date": d1.isoformat(),
                    "year": d1.year,
                    "quarter": quarter,
                    "month": d1.month,
                    "week_of_year": d1.isocalendar()[1],
                    "day_of_week": d1.strftime("%A"),
                    "ytd_start": ytd_start.isoformat(),
                    "qtd_start": qtd_start.isoformat(),
                    "mtd_start": mtd_start.isoformat()
                }
            }

        elif operation == "calculate_age":
            if not d1:
                raise ValueError("date1 (birthdate) is required for calculate_age")

            age_years = d2.year - d1.year
            # Adjust if birthday hasn't occurred yet this year
            if (d2.month, d2.day) < (d1.month, d1.day):
                age_years -= 1

            return {
                "operation": "calculate_age",
                "result": age_years,
                "formatted": f"{age_years} years old",
                "details": {
                    "birthdate": d1.isoformat(),
                    "as_of_date": d2.isoformat(),
                    "age_years": age_years
                }
            }

        elif operation == "format_date":
            if not d1:
                raise ValueError("date1 is required for format_date")

            formatted = d1.strftime(output_format)

            return {
                "operation": "format_date",
                "result": formatted,
                "formatted": formatted,
                "details": {
                    "original_date": d1.isoformat(),
                    "format_string": output_format,
                    "formatted_date": formatted
                }
            }

        elif operation == "get_date_range":
            if not d1:
                raise ValueError("date1 is required for get_date_range")

            diff = abs((d2 - d1).days)
            biz_days = _count_business_days(d1, d2)

            start, end = (d1, d2) if d1 <= d2 else (d2, d1)

            return {
                "operation": "get_date_range",
                "result": {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "days": diff,
                    "business_days": biz_days
                },
                "formatted": f"{start.isoformat()} to {end.isoformat()}: {diff} days ({biz_days} business days)",
                "details": {
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "total_days": diff,
                    "business_days": biz_days,
                    "weekend_days": diff - biz_days,
                    "months": round(diff / 30.44, 2),
                    "years": round(diff / 365.25, 2)
                }
            }

        elif operation == "business_days":
            if not d1:
                raise ValueError("date1 is required for business_days")

            biz_days = _count_business_days(d1, d2)

            return {
                "operation": "business_days",
                "result": biz_days,
                "formatted": f"{biz_days} business days",
                "details": {
                    "from_date": d1.isoformat(),
                    "to_date": d2.isoformat(),
                    "business_days": biz_days
                }
            }

        else:
            raise ValueError(f"Unknown operation: {operation}")

    except Exception as e:
        logger.error(f"Date/time operation failed: {e}", exc_info=True)
        return {
            "operation": operation,
            "result": None,
            "formatted": f"Error: {str(e)}",
            "error": str(e)
        }


__all__ = ["date_time_utilities", "DateTimeResult", "DateRange"]
