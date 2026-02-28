/**
 * EntityPreviewView Component
 *
 * Full-screen preview of entity data using MUI DataGrid.
 * Replaces the card view when user clicks Preview on an EntityCard.
 */

import { useMemo, useCallback, useEffect, useState } from "react";
import {
  Box,
  Typography,
  Button,
  Paper,
  Chip,
  Stack,
  Link,
  Tooltip,
  keyframes,
} from "@mui/material";
import { alpha, useTheme, type Theme } from "@mui/material/styles";
import { DataGrid, type GridColDef, type GridColumnHeaderParams, type GridRowSelectionModel } from "@mui/x-data-grid";
import StarRoundedIcon from "@mui/icons-material/StarRounded";
import ArrowBackIcon from "@mui/icons-material/ArrowBack";
import RefreshIcon from "@mui/icons-material/Refresh";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";
import FilterListIcon from "@mui/icons-material/FilterList";
import ChatBubbleOutlineIcon from "@mui/icons-material/ChatBubbleOutline";

import { useEntityPreview } from "../../../../hooks/useEntityPreview";
import type {
  ScopeEntity,
  RelevanceLevel,
  Filter,
} from "../../../../types/scopeState";
import type { GraphNode } from "../../../../services/graphql";
import { formatFilter } from "../../../../utils/filterFormatters";

// ============================================================================
// Animations (matching LoadingView)
// ============================================================================

const pulse = keyframes`
  0% {
    transform: scale(0.95);
    opacity: 0.8;
  }
  50% {
    transform: scale(1);
    opacity: 1;
  }
  100% {
    transform: scale(0.95);
    opacity: 0.8;
  }
`;

const rotate = keyframes`
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
`;

// ============================================================================
// Types
// ============================================================================

export interface StagedRowsContext {
  entityType: string;
  rowCount: number;
  rows: Record<string, unknown>[];
}

export interface EntityPreviewViewProps {
  entity: ScopeEntity;
  onBack: () => void;
  scopeChanged?: boolean;
  /** Called when selected rows change - parent can sync to chat dock */
  onSelectionChange?: (context: StagedRowsContext | null) => void;
}

// ============================================================================
// Helper Functions
// ============================================================================

function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count.toLocaleString();
}

function getRelevanceColors(level: RelevanceLevel, theme: Theme) {
  switch (level) {
    case "primary":
      return {
        bg: theme.palette.primary.main,
        text: "#fff",
        border: theme.palette.primary.main,
      };
    case "related":
      return {
        bg: alpha(theme.palette.info.main, 0.15),
        text: theme.palette.info.dark,
        border: alpha(theme.palette.info.main, 0.3),
      };
    case "contextual":
      return {
        bg: alpha(theme.palette.grey[500], 0.15),
        text: theme.palette.text.secondary,
        border: alpha(theme.palette.grey[500], 0.3),
      };
    default:
      return {
        bg: alpha(theme.palette.grey[500], 0.15),
        text: theme.palette.text.secondary,
        border: alpha(theme.palette.grey[500], 0.3),
      };
  }
}

function formatRelevanceLevel(level: RelevanceLevel): string {
  return level.charAt(0).toUpperCase() + level.slice(1);
}

/**
 * Coerce a string value to its most appropriate JS type.
 * Graph properties are always returned as strings — this restores
 * numbers, booleans, and dates for proper DataGrid sorting/display.
 */
function coerceValue(value: string): unknown {
  if (value === "true") return true;
  if (value === "false") return false;

  // Numeric (integer or float)
  if (/^-?\d+(\.\d+)?$/.test(value)) return Number(value);

  return value;
}

/**
 * Transforms GraphNode[] to flat row objects for DataGrid.
 * Converts {properties: [{key, value}]} to {key: value, ...}
 * Skips the graph-level "id" property to avoid overwriting the row id.
 */
function flattenNodes(nodes: GraphNode[]): Record<string, unknown>[] {
  return nodes.map((node, index) => {
    const flatRow: Record<string, unknown> = {
      id: node.id || `row-${index}`,
    };

    if (node.properties) {
      for (const prop of node.properties) {
        // Skip the graph "id" property — we already use node.id as row key
        if (prop.key === "id") continue;
        flatRow[prop.key] = coerceValue(prop.value);
      }
    }

    return flatRow;
  });
}

/**
 * Renders a column header with a field-of-interest indicator (green star + underline).
 */
function FoiHeader({ params, justification }: { params: GridColumnHeaderParams; justification?: string }) {
  const label = (
    <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
      <StarRoundedIcon sx={{ fontSize: 14, color: "#0F5C4C" }} />
      <span style={{ fontWeight: 600 }}>{params.colDef.headerName}</span>
    </Box>
  );

  if (justification) {
    return <Tooltip title={justification} arrow placement="top">{label}</Tooltip>;
  }
  return label;
}

/**
 * Generate DataGrid columns from entity fields of interest or from data keys.
 *
 * Validates that fields_of_interest actually exist in the data before using them.
 * Falls back to data-derived columns when fields don't match (e.g. mock fields
 * with real API data that uses different property names).
 * Columns that match a field_of_interest get a green star + underline.
 */
function generateColumns(
  entity: ScopeEntity,
  data: Record<string, unknown>[],
): GridColDef[] {
  const formatHeaderName = (field: string) =>
    field
      .replace(/([a-z])([A-Z])/g, "$1 $2") // camelCase → spaced
      .replace(/_/g, " ") // snake_case → spaced
      .replace(/^./, (c) => c.toUpperCase()); // capitalize first letter

  // Build lookup of fields of interest: field name → justification
  const foiMap = new Map<string, string>();
  if (entity.fields_of_interest) {
    for (const f of entity.fields_of_interest) {
      foiMap.set(f.field, f.justification);
    }
  }

  // Collect actual data keys for validation
  const dataKeys = new Set<string>();
  if (data.length > 0) {
    data.forEach((row) => {
      Object.keys(row).forEach((key) => {
        if (key !== "id") {
          dataKeys.add(key);
        }
      });
    });
  }

  // Helper: build a column def, adding FOI indicator if the field is in foiMap
  const makeCol = (field: string, headerName: string, justification?: string): GridColDef => {
    const isFoi = foiMap.has(field);
    const foiJustification = justification ?? foiMap.get(field);

    const col: GridColDef = {
      field,
      headerName,
      minWidth: 130,
      flex: 1,
      sortable: true,
    };

    if (justification) {
      col.description = justification;
    }

    if (isFoi) {
      col.renderHeader = (params: GridColumnHeaderParams) => (
        <FoiHeader params={params} justification={foiJustification} />
      );
    }

    return col;
  };

  // When we have data, show ALL fields with FOI fields marked with green stars
  // FOI columns sort first, then priority keys (name, email, type), then rest.
  if (dataKeys.size > 0) {
    const priorityKeys = ["name", "email", "type", "status"];
    const sortedKeys = Array.from(dataKeys).sort((a, b) => {
      const aFoi = foiMap.has(a);
      const bFoi = foiMap.has(b);
      if (aFoi && !bFoi) return -1;
      if (!aFoi && bFoi) return 1;
      const aIdx = priorityKeys.findIndex((p) => a.toLowerCase().includes(p));
      const bIdx = priorityKeys.findIndex((p) => b.toLowerCase().includes(p));
      if (aIdx !== -1 && bIdx === -1) return -1;
      if (aIdx === -1 && bIdx !== -1) return 1;
      return 0;
    });

    return sortedKeys.map((field) =>
      makeCol(field, formatHeaderName(field)),
    );
  }

  // Use fields_of_interest when there's no data yet (loading state)
  if (foiMap.size > 0) {
    return entity.fields_of_interest!.map((f) =>
      makeCol(f.field, formatHeaderName(f.field), f.justification),
    );
  }

  return [];
}

// ============================================================================
// Initial Loading State (matches LoadingView design)
// ============================================================================

interface InitialLoadingStateProps {
  entityType: string;
  onBack: () => void;
}

function InitialLoadingState({ entityType, onBack }: InitialLoadingStateProps) {
  return (
    <Box
      sx={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: 8,
        px: 4,
      }}
    >
      {/* Left side: Animation */}
      <Box sx={{ position: "relative", width: 264, height: 286 }}>
        {/* Animated rings background */}
        <Box
          sx={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            animation: `${rotate} 10s linear infinite`,
            transformOrigin: "130.5px 142.2px",
          }}
        >
          <svg
            width="264"
            height="286"
            viewBox="0 0 264 285"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            style={{ position: "absolute", top: 0, left: 0 }}
          >
            <circle
              opacity="0.9"
              cx="130.479"
              cy="142.479"
              r="95.229"
              stroke="#C6A664"
              strokeWidth="0.5"
            />
            <circle
              opacity="0.8"
              cx="130.961"
              cy="141.961"
              r="112.711"
              stroke="#C6A664"
              strokeWidth="0.5"
            />
            <circle
              cx="130.256"
              cy="142.256"
              r="68.7559"
              fill="#C6A664"
              fillOpacity="0.2"
              stroke="#F4F0E6"
            />
          </svg>
        </Box>

        {/* Main pulsing content */}
        <Box sx={{ animation: `${pulse} 2s ease-in-out infinite` }}>
          <svg
            width="264"
            height="286"
            viewBox="0 0 264 285"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
          >
            {/* Central document icon */}
            <rect
              x="83.1621"
              y="111.079"
              width="94.8066"
              height="64.1178"
              rx="3"
              fill="#F4F0E6"
              fillOpacity="0.85"
            />
            <circle
              cx="87.2722"
              cy="114.641"
              r="1.37004"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <circle
              cx="91.1082"
              cy="114.641"
              r="1.37004"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <circle
              cx="94.9444"
              cy="114.641"
              r="1.37004"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <rect
              x="86.4501"
              y="119.3"
              width="87.6824"
              height="23.0166"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <rect
              x="130.839"
              y="145.604"
              width="43.2932"
              height="9.31626"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <rect
              x="86.4501"
              y="158.757"
              width="87.6824"
              height="9.31626"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <rect
              x="86.4501"
              y="146.7"
              width="26.8527"
              height="2.74008"
              rx="1.37004"
              fill="#C6A664"
              fillOpacity="0.5"
            />
            <rect
              x="86.4501"
              y="151.084"
              width="38.9091"
              height="2.74008"
              rx="1.37004"
              fill="#C6A664"
              fillOpacity="0.5"
            />

            {/* Connection lines and circles */}
            <path
              d="M133.507 39.0052C134.979 39.0052 136.173 37.8113 136.173 36.3386C136.173 34.8658 134.979 33.6719 133.507 33.6719C132.034 33.6719 130.84 34.8658 130.84 36.3386C130.84 37.8113 132.034 39.0052 133.507 39.0052ZM133.507 110.597L134.007 110.597L134.007 36.3386L133.507 36.3386L133.007 36.3386L133.007 110.597L133.507 110.597Z"
              fill="#0F5C4C"
            />
            <path
              d="M133.507 244.597C132.034 244.597 130.84 245.791 130.84 247.264C130.84 248.737 132.034 249.931 133.507 249.931C134.979 249.931 136.173 248.737 136.173 247.264C136.173 245.791 134.979 244.597 133.507 244.597ZM133.507 175.376L133.007 175.376L133.007 247.264L133.507 247.264L134.007 247.264L134.007 175.376L133.507 175.376Z"
              fill="#0F5C4C"
            />
            <path
              d="M231.167 139.036C231.167 140.509 232.361 141.703 233.834 141.703C235.307 141.703 236.501 140.509 236.501 139.036C236.501 137.563 235.307 136.369 233.834 136.369C232.361 136.369 231.167 137.563 231.167 139.036ZM177.746 139.036V139.536H233.834V139.036V138.536H177.746V139.036Z"
              fill="#0F5C4C"
            />
            <path
              d="M31.8959 139.036C31.8959 137.563 30.702 136.369 29.2292 136.369C27.7565 136.369 26.5626 137.563 26.5626 139.036C26.5626 140.509 27.7565 141.703 29.2292 141.703C30.702 141.703 31.8959 140.509 31.8959 139.036ZM82.9479 139.036L82.9479 138.536L29.2292 138.536L29.2292 139.036L29.2292 139.536L82.9479 139.536L82.9479 139.036Z"
              fill="#0F5C4C"
            />
            <path
              d="M194.954 69.9492C196.065 70.9161 197.75 70.7994 198.716 69.6885C199.683 68.5776 199.567 66.8932 198.456 65.9263C197.345 64.9594 195.66 65.0761 194.694 66.187C193.727 67.2979 193.843 68.9823 194.954 69.9492ZM159.576 110.597L159.953 110.925L197.082 68.266L196.705 67.9378L196.328 67.6095L159.199 110.268L159.576 110.597Z"
              fill="#0F5C4C"
            />
            <path
              d="M57.629 61.4247C58.8312 60.5739 59.116 58.9097 58.2653 57.7075C57.4145 56.5054 55.7503 56.2205 54.5481 57.0713C53.3459 57.922 53.061 59.5863 53.9118 60.7884C54.7626 61.9906 56.4268 62.2755 57.629 61.4247ZM92.4276 110.597L92.8357 110.308L56.4967 58.9591L56.0885 59.248L55.6804 59.5368L92.0195 110.886L92.4276 110.597Z"
              fill="#0F5C4C"
            />
            <path
              d="M61.4895 210.268C60.2538 209.466 58.6025 209.818 57.8011 211.054C56.9998 212.29 57.3519 213.941 58.5876 214.742C59.8232 215.544 61.4745 215.192 62.2759 213.956C63.0772 212.72 62.7251 211.069 61.4895 210.268ZM84.1169 175.376L83.6974 175.104L59.619 212.233L60.0385 212.505L60.458 212.777L84.5364 175.648L84.1169 175.376Z"
              fill="#0F5C4C"
            />
            <path
              d="M199.913 210.323C198.707 211.169 198.416 212.832 199.262 214.037C200.109 215.243 201.772 215.534 202.977 214.687C204.183 213.841 204.474 212.178 203.627 210.973C202.781 209.767 201.118 209.476 199.913 210.323ZM175.376 175.376L174.966 175.663L201.036 212.792L201.445 212.505L201.854 212.218L175.785 175.089L175.376 175.376Z"
              fill="#0F5C4C"
            />

            {/* Outer circles */}
            <circle
              cx="133.255"
              cy="18.4213"
              r="17.4213"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="133.388"
              cy="263.734"
              r="16.2605"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="206.304"
              cy="56.2078"
              r="14.1287"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="55.4177"
              cy="45.1482"
              r="14.1287"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="53.8378"
              cy="225.263"
              r="14.1287"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="211.044"
              cy="223.683"
              r="14.1287"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="248.173"
              cy="137.638"
              r="14.1287"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
            <circle
              cx="15.1287"
              cy="137.638"
              r="14.1287"
              stroke="#0F5C4C"
              strokeWidth="2"
            />
          </svg>
        </Box>
      </Box>

      {/* Right side: Text content */}
      <Box sx={{ maxWidth: 400 }}>
        <Typography variant="h3" sx={{ fontWeight: 700, mb: 1 }}>
          Loading Preview
        </Typography>
        <Typography variant="h6" sx={{ color: "text.secondary", mb: 3 }}>
          Fetching data for review...
        </Typography>

        {/* Progress bar (indeterminate) */}
        <Box sx={{ mb: 3 }}>
          <Box
            sx={{
              position: "relative",
              height: 24,
              bgcolor: "action.hover",
              borderRadius: 0.5,
              overflow: "hidden",
            }}
          >
            <Box
              sx={{
                position: "absolute",
                left: 0,
                top: 0,
                bottom: 0,
                width: "30%",
                bgcolor: "primary.main",
                animation: `${pulse} 1.5s ease-in-out infinite`,
              }}
            />
          </Box>
        </Box>

        {/* Entity name */}
        <Box sx={{ mb: 4 }}>
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {entityType}
          </Typography>
        </Box>

        <Button
          variant="text"
          startIcon={<ArrowBackIcon />}
          onClick={onBack}
          sx={{ textTransform: "none", color: "text.secondary" }}
        >
          Cancel and return to Scope View
        </Button>
      </Box>
    </Box>
  );
}

// ============================================================================
// Error State
// ============================================================================

interface ErrorStateProps {
  error: Error;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  const theme = useTheme();

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        py: 8,
        gap: 2,
      }}
    >
      <WarningAmberIcon
        sx={{ fontSize: 48, color: theme.palette.error.main }}
      />
      <Typography variant="h6" sx={{ color: "text.primary" }}>
        Failed to load preview data
      </Typography>
      <Typography
        variant="body2"
        sx={{ color: "text.secondary", textAlign: "center", maxWidth: 400 }}
      >
        {error.message}
      </Typography>
      <Button variant="outlined" startIcon={<RefreshIcon />} onClick={onRetry}>
        Try Again
      </Button>
    </Box>
  );
}

// ============================================================================
// Empty State
// ============================================================================

function EmptyState() {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        py: 8,
        gap: 2,
      }}
    >
      <Typography variant="h6" sx={{ color: "text.primary" }}>
        No records found
      </Typography>
      <Typography variant="body2" sx={{ color: "text.secondary" }}>
        No records match the current filters for this entity.
      </Typography>
    </Box>
  );
}

// ============================================================================
// No Query State
// ============================================================================

function NoQueryState({ onBack }: { onBack: () => void }) {
  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        py: 8,
        gap: 2,
      }}
    >
      <Typography variant="h6" sx={{ color: "text.primary" }}>
        Query not available
      </Typography>
      <Typography variant="body2" sx={{ color: "text.secondary" }}>
        This entity does not have a query configured for data preview.
      </Typography>
      <Button variant="outlined" startIcon={<ArrowBackIcon />} onClick={onBack}>
        Return to Scope View
      </Button>
    </Box>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export default function EntityPreviewView({
  entity,
  onBack,
  scopeChanged = false,
  onSelectionChange,
}: EntityPreviewViewProps) {
  const theme = useTheme();
  const relevanceColors = getRelevanceColors(entity.relevance_level, theme);
  const { data, loading, error, hasMore, totalLoaded, loadMore, refresh } =
    useEntityPreview(entity);

  // Row selection state
  const [rowSelectionModel, setRowSelectionModel] = useState<GridRowSelectionModel>([]);

  // Handle escape key to go back (or clear selection if rows selected)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (rowSelectionModel.length > 0) {
          setRowSelectionModel([]);
        } else {
          onBack();
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onBack, rowSelectionModel.length]);

  // Transform data for DataGrid
  const flatData = useMemo(() => flattenNodes(data), [data]);
  const columns = useMemo(
    () => generateColumns(entity, flatData),
    [entity, flatData],
  );

  // Get selected rows data and notify parent
  const selectedRows = useMemo(() => {
    const selectedIds = new Set(rowSelectionModel);
    return flatData.filter((row) => selectedIds.has(row.id as string | number));
  }, [flatData, rowSelectionModel]);

  // Notify parent when selection changes
  useEffect(() => {
    if (onSelectionChange) {
      if (selectedRows.length > 0) {
        onSelectionChange({
          entityType: entity.entity_type,
          rowCount: selectedRows.length,
          rows: selectedRows,
        });
      } else {
        onSelectionChange(null);
      }
    }
  }, [selectedRows, entity.entity_type, onSelectionChange]);

  const handleLoadMore = useCallback(() => {
    loadMore();
  }, [loadMore]);

  const handleClearSelection = useCallback(() => {
    setRowSelectionModel([]);
  }, []);

  // No query available
  if (!entity.query) {
    return (
      <Box sx={{ display: "flex", flexDirection: "column", height: "100%" }}>
        <NoQueryState onBack={onBack} />
      </Box>
    );
  }

  // Initial loading state - full screen loading animation
  if (loading && totalLoaded === 0) {
    return (
      <Box
        sx={{ display: "flex", flexDirection: "column", height: "100%" }}
        role="region"
        aria-label={`Loading preview data for ${entity.entity_type}`}
      >
        <InitialLoadingState entityType={entity.entity_type} onBack={onBack} />
      </Box>
    );
  }

  return (
    <Box
      sx={{ display: "flex", flexDirection: "column", height: "100%" }}
      role="region"
      aria-label={`Preview data for ${entity.entity_type}`}
    >
      {/* Header: ← Entity [Badge] on one line */}
      <Box sx={{ px: 3, py:3 }}>
        <Link
          component="button"
          onClick={onBack}
          underline="none"
          sx={{
            display: "inline-flex",
            alignItems: "center",
            gap: 1,
            cursor: "pointer",
            "&:hover": {
              "& .back-arrow": {
                color: "primary.main",
              },
            },
          }}
        >
          <ArrowBackIcon
            className="back-arrow"
            sx={{ fontSize: 24, color: "text.secondary", transition: "color 0.15s" }}
          />
          <Typography variant="h4" component="h1" sx={{ fontWeight: 600, color: "text.primary" }}>
            {entity.entity_type}
          </Typography>
          <Chip
            label={formatRelevanceLevel(entity.relevance_level)}
            size="small"
            sx={{
              bgcolor: relevanceColors.bg,
              color: relevanceColors.text,
              fontWeight: 600,
              fontSize: "0.7rem",
              height: 22,
              borderRadius: 0.5,
            }}
          />
        </Link>
      </Box>

      {/* Slim purpose banner - single line with cream background */}
      <Box
        sx={{
          mx: 3,
          mb: 3,
          px: 1.5,
          py: 2,
          bgcolor:
            theme.palette.mode === "light"
              ? alpha(theme.palette.secondary.main, 0.18)
              : alpha(theme.palette.secondary.main, 0.14),
          borderRadius: 0.5,
          border: "1px solid",
          borderColor:
            theme.palette.mode === "light"
              ? alpha(theme.palette.secondary.dark, 0.35)
              : alpha(theme.palette.secondary.light, 0.4),
          display: "flex",
          alignItems: "center",
          gap: 1,
        }}
      >
        <InfoOutlinedIcon
          sx={{ fontSize: 20, color: "secondary.main", flexShrink: 0 }}
        />
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          This preview helps verify the AI understood your intent. Seeing unexpected data?{" "}
          <Link
            component="button"
            onClick={onBack}
            underline="hover"
            sx={{ color: "primary.main", cursor: "pointer", fontSize: "inherit", verticalAlign: "baseline", fontWeight: 600 }}
          >
            Go back
          </Link>{" "}
          to adjust filters.
        </Typography>
      </Box>

      {/* Scope changed warning */}
      {scopeChanged && (
        <Box
          sx={{
            mx: 3,
            mb: 1.5,
            p: 1.5,
            bgcolor: alpha(theme.palette.warning.main, 0.1),
            borderRadius: 1,
            border: "1px solid",
            borderColor: alpha(theme.palette.warning.main, 0.3),
          }}
        >
          <Stack direction="row" alignItems="center" spacing={1}>
            <WarningAmberIcon
              sx={{ fontSize: 16, color: theme.palette.warning.main }}
            />
            <Typography variant="body2" sx={{ color: theme.palette.warning.dark }}>
              Scope has changed. Data may be stale.
              <Button
                size="small"
                onClick={refresh}
                sx={{ ml: 1, textTransform: "none" }}
              >
                Refresh
              </Button>
            </Typography>
          </Stack>
        </Box>
      )}

      {/* Combined filter chips + record count row */}
      <Box sx={{ px: 3, mb: 1.5 }}>
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            gap: 0.75,
            alignItems: "center",
          }}
        >
          {entity.filters.length > 0 && (
            <>
              <FilterListIcon sx={{ fontSize: 18, color: "text.secondary" }} />
              {entity.filters.map((filter: Filter) => (
                <Chip
                  key={filter.id}
                  label={filter.display_text || formatFilter(filter)}
                  size="small"
                  sx={{
                    bgcolor: "background.paper",
                    color: "text.primary",
                    fontWeight: 400,
                    fontSize: "0.8rem",
                    height: 26,
                    borderRadius: 0.5,
                    border: "1px solid",
                    borderColor: "primary.main",
                    cursor: "default",
                    "&:hover": {
                      bgcolor: "action.hover",
                    },
                    "& .MuiChip-label": {
                      px: 1,
                    },
                  }}
                />
              ))}
              <Typography variant="body2" sx={{ color: "text.disabled", mx: 0.5 }}>
                ·
              </Typography>
            </>
          )}
          <Typography variant="body2" sx={{ color: "text.secondary" }}>
            {loading && totalLoaded === 0
              ? "Loading..."
              : `${formatCount(totalLoaded)}${
                  entity.estimated_count != null && entity.estimated_count > 0
                    ? ` of ~${formatCount(entity.estimated_count)}`
                    : ""
                } records`}
          </Typography>
          {hasMore && (
            <>
              <Typography variant="body2" sx={{ color: "text.disabled" }}>
                ·
              </Typography>
              <Link
                component="button"
                onClick={handleLoadMore}
                disabled={loading}
                underline="hover"
                sx={{
                  color: "primary.main",
                  fontSize: "0.875rem",
                  fontWeight: 500,
                  cursor: loading ? "default" : "pointer",
                  opacity: loading ? 0.6 : 1,
                }}
              >
                {loading ? "Loading..." : "Load more"}
              </Link>
            </>
          )}
        </Box>
      </Box>

      {/* Content - DataGrid */}
      <Box sx={{ flex: 1, minHeight: 0, overflow: "auto", px: 3, pb: 2 }}>
        {error ? (
          <ErrorState error={error} onRetry={refresh} />
        ) : flatData.length === 0 ? (
          <EmptyState />
        ) : (
          <Paper
            variant="outlined"
            sx={{
              borderRadius: 0.5,
              overflow: "hidden",
              bgcolor: "background.default",
              height: "100%",
            }}
          >
            <DataGrid
              rows={flatData}
              columns={columns}
              checkboxSelection
              rowSelectionModel={rowSelectionModel}
              onRowSelectionModelChange={setRowSelectionModel}
              disableColumnMenu={false}
              initialState={{
                pagination: {
                  paginationModel: { pageSize: 25, page: 0 },
                },
              }}
              pageSizeOptions={[25, 50, 100]}
              sx={{
                border: "none",
                "& .MuiDataGrid-cell": {
                  borderColor: "divider",
                  display: "flex",
                  alignItems: "center",
                  py: 1.5,
                },
                "& .MuiDataGrid-columnHeaders": {
                  bgcolor: "background.paper",
                  borderColor: "divider",
                  borderBottom: "1px solid",
                },
                "& .MuiDataGrid-columnHeaderTitle": {
                  fontWeight: 600,
                  color: "text.primary",
                },
                "& .MuiDataGrid-columnHeader--sorted .MuiDataGrid-columnHeaderTitle":
                  {
                    color: "primary.main",
                  },
                "& .MuiDataGrid-sortIcon": {
                  opacity: 1,
                  color: "primary.main",
                },
                "& .MuiDataGrid-row": {
                  "&:hover": {
                    bgcolor: alpha(theme.palette.action.hover, 0.5),
                  },
                  "&.Mui-selected": {
                    bgcolor: alpha(theme.palette.primary.main, 0.08),
                    "&:hover": {
                      bgcolor: alpha(theme.palette.primary.main, 0.12),
                    },
                  },
                },
                "& .MuiDataGrid-footerContainer": {
                  borderTop: "1px solid",
                  borderColor: "divider",
                  minHeight: 56,
                  overflow: "hidden",
                },
              }}
            />
          </Paper>
        )}
      </Box>

      {/* Selection status bar */}
      {rowSelectionModel.length > 0 && (
        <Box
          sx={{
            px: 3,
            py: 1.5,
            bgcolor: alpha(theme.palette.primary.main, 0.08),
            borderTop: "1px solid",
            borderColor: alpha(theme.palette.primary.main, 0.2),
          }}
        >
          <Stack direction="row" alignItems="center" justifyContent="space-between">
            <Stack direction="row" alignItems="center" spacing={1}>
              <ChatBubbleOutlineIcon sx={{ fontSize: 16, color: "primary.main" }} />
              <Typography variant="body2" sx={{ color: "text.primary" }}>
                <strong>{rowSelectionModel.length}</strong> row{rowSelectionModel.length !== 1 ? "s" : ""} selected
                <Typography component="span" sx={{ color: "text.secondary", ml: 0.5 }}>
                  — will be included as context in your next message
                </Typography>
              </Typography>
            </Stack>
            <Button
              size="small"
              onClick={handleClearSelection}
              sx={{ textTransform: "none", color: "text.secondary" }}
            >
              Clear
            </Button>
          </Stack>
        </Box>
      )}
    </Box>
  );
}
