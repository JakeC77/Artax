/**
 * Utility functions for formatting data scope filters in a human-readable way
 */

export interface DataScopeFilter {
  property: string;
  operator: string;
  value: string | string[] | number | number[] | boolean;
}

/**
 * Format a property name from camelCase or snake_case to Title Case
 * e.g., "writtenDate" -> "Written Date", "sales_date" -> "Sales Date"
 */
function formatPropertyName(property: string): string {
  // Handle camelCase
  const withSpaces = property.replace(/([a-z])([A-Z])/g, '$1 $2');
  // Handle snake_case
  const withoutUnderscores = withSpaces.replace(/_/g, ' ');
  // Capitalize first letter of each word
  return withoutUnderscores
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

/**
 * Format a date string to a more readable format
 * e.g., "2025-10-15" -> "Oct 15, 2025"
 */
function formatDate(dateStr: string): string {
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) {
      return dateStr;
    }
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return dateStr;
  }
}

/**
 * Check if a string looks like a date (YYYY-MM-DD format)
 */
function isDateString(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value);
}

/**
 * Format a single value (handles dates, strings, etc.)
 */
function formatValue(value: string | number | boolean): string {
  if (typeof value === 'string' && isDateString(value)) {
    return formatDate(value);
  }
  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }
  return String(value);
}

/**
 * Format the operator to be more readable
 */
function formatOperator(operator: string): string {
  const operatorMap: Record<string, string> = {
    'between': '→',
    'equals': 'is',
    'eq': 'is',
    'not_equals': 'is not',
    'neq': 'is not',
    'contains': 'contains',
    'not_contains': 'does not contain',
    'starts_with': 'starts with',
    'ends_with': 'ends with',
    'greater_than': '>',
    'gt': '>',
    'less_than': '<',
    'lt': '<',
    'greater_than_or_equal': '≥',
    'gte': '≥',
    'less_than_or_equal': '≤',
    'lte': '≤',
    'in': 'is one of',
    'not_in': 'is not one of',
    'is_null': 'is empty',
    'is_not_null': 'is not empty',
    'is in range': '→',
  };

  return operatorMap[operator.toLowerCase()] || operator;
}

/**
 * Format a filter object into a human-readable string
 *
 * Examples:
 * - { property: "writtenDate", operator: "between", value: ["2025-10-15", "2026-01-13"] }
 *   -> "Written Date: Oct 15, 2025 → Jan 13, 2026"
 *
 * - { property: "region", operator: "equals", value: "West Coast" }
 *   -> "Region: West Coast"
 *
 * - { property: "status", operator: "in", value: ["Active", "Pending"] }
 *   -> "Status: Active, Pending"
 */
export function formatFilter(filter: unknown): string {
  // Handle string filters (already formatted)
  if (typeof filter === 'string') {
    return filter;
  }

  // Handle non-object filters
  if (typeof filter !== 'object' || filter === null) {
    return String(filter);
  }

  const f = filter as DataScopeFilter;

  // Check if it has the expected structure
  if (!f.property) {
    // Fallback to JSON for unknown structure
    return JSON.stringify(filter);
  }

  const propertyName = formatPropertyName(f.property);

  // Handle filters without operator (just property and value)
  if (!f.operator && f.value !== undefined) {
    if (Array.isArray(f.value)) {
      return `${propertyName}: ${f.value.map(v => formatValue(v)).join(', ')}`;
    }
    return `${propertyName}: ${formatValue(f.value)}`;
  }

  // Handle null/empty checks
  if (f.operator === 'is_null' || f.operator === 'is_not_null') {
    return `${propertyName} ${formatOperator(f.operator)}`;
  }

  // Handle between/range operators with array values
  if ((f.operator === 'between' || f.operator === 'is in range') && Array.isArray(f.value) && f.value.length === 2) {
    const [start, end] = f.value;
    return `${propertyName}: ${formatValue(start)} → ${formatValue(end)}`;
  }

  // Handle array values (in, not_in, etc.)
  if (Array.isArray(f.value)) {
    const formattedValues = f.value.map(v => formatValue(v)).join(', ');
    const op = formatOperator(f.operator);
    // For simple "is one of" we can simplify
    if (op === 'is one of' || op === 'is') {
      return `${propertyName}: ${formattedValues}`;
    }
    return `${propertyName} ${op}: ${formattedValues}`;
  }

  // Handle single value
  const formattedValue = formatValue(f.value);
  const op = formatOperator(f.operator);

  // For "is" operator, use colon format for cleaner look
  if (op === 'is') {
    return `${propertyName}: ${formattedValue}`;
  }

  return `${propertyName} ${op} ${formattedValue}`;
}

/**
 * Format multiple filters into an array of human-readable strings
 */
export function formatFilters(filters: unknown[]): string[] {
  return filters.map(formatFilter);
}
