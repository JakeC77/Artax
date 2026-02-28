/**
 * EntityCard Component
 *
 * Card-based display of a scope entity with view/edit modes.
 * Edit mode batches all changes into a single chat message for turn-based AI interaction.
 *
 * Action Panel Pattern:
 * - Card is a fixed, persistent surface
 * - Action panels slide in from the right edge and rest ON TOP of the card
 * - The card itself never changes, moves, or re-renders when panel opens
 * - Panel casts a left-edge shadow to communicate depth
 */

import { useState, useCallback, useMemo } from "react";
import {
  Box,
  Typography,
  Chip,
  Collapse,
  Tooltip,
  IconButton,
  Button,
  TextField,
} from "@mui/material";
import { alpha, useTheme, type Theme } from "@mui/material/styles";
import CloseIcon from "@mui/icons-material/Close";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import EditIcon from "@mui/icons-material/Edit";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import AddIcon from "@mui/icons-material/Add";
import LinkIcon from "@mui/icons-material/Link";

import SlideOutFilterPanel from "./SlideOutFilterPanel";
import SlideOutFieldsPanel from "./SlideOutFieldsPanel";
import RemoveEntityPanel from "./RemoveEntityPanel";
import { useReducedMotion } from "../../../../hooks/useReducedMotion";
import { useEntityFieldMetadata } from "../../../../hooks/useEntityFieldMetadata";
import type {
  ScopeState,
  ScopeEntity,
  Filter,
  RelevanceLevel,
} from "../../../../types/scopeState";
import { formatFilter } from "../../../../utils/filterFormatters";

// ============================================================================
// Types
// ============================================================================

/** Info about the last update to this entity from Theo */
export interface EntityUpdate {
  summary: string; // e.g., "Added Zoloft to medication filter"
  changedFields: string[]; // e.g., ["filters", "fields_of_interest"] - for footer display
  timestamp: number;
  isNew?: boolean; // Whether this entity was just added
  // Specific items that changed (for highlighting)
  changedFilterIds?: string[]; // Filter IDs that were modified
  addedFilterIds?: string[]; // New filter IDs that were added
  changedFieldNames?: string[]; // Field names that were modified
  addedFieldNames?: string[]; // New field names that were added
}

export interface EntityCardProps {
  entity: ScopeEntity;
  /** Full scope state (for inline operations) */
  scopeState?: ScopeState | null;
  /** Connection context (e.g., "Connected via Prescription") */
  connectionInfo?: string;
  /** Called when user saves all changes (single batched message) */
  onSubmitChanges?: (chatMessage: string) => void;
  /** Called when user wants to preview data */
  onPreview?: () => void;
  /** Actual count from execution (if available) */
  actualCount?: number;
  /** Whether this card is disabled/excluded from scope */
  disabled?: boolean;
  /** Last update from Theo for this entity */
  lastUpdate?: EntityUpdate | null;
}

// Pending changes tracked during edit mode
interface PendingChanges {
  filtersToRemove: Set<string>; // filter IDs
  filtersToAdd: string[]; // filter description strings (new filters only)
  filterEdits: Map<string, string>; // filter ID -> edit description (for existing filters)
  fieldsToAdd: string[];
  fieldsToRemove: string[];
  removeEntity: boolean;
  removeReason: string;
  reasoningEdit: string | null; // edited reasoning (null = unchanged)
}

const EMPTY_CHANGES: PendingChanges = {
  filtersToRemove: new Set(),
  filtersToAdd: [],
  filterEdits: new Map(),
  fieldsToAdd: [],
  fieldsToRemove: [],
  removeEntity: false,
  removeReason: "",
  reasoningEdit: null,
};

// ============================================================================
// Helpers
// ============================================================================

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

function formatCount(count: number): string {
  if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
  if (count >= 1000) return `${(count / 1000).toFixed(1)}K`;
  return count?.toLocaleString();
}

// ============================================================================
// Main Component
// ============================================================================

export default function EntityCard({
  entity,
  scopeState,
  connectionInfo,
  onSubmitChanges,
  onPreview,
  actualCount,
  disabled = false,
  lastUpdate,
}: EntityCardProps) {
  const theme = useTheme();
  const prefersReducedMotion = useReducedMotion();
  const isDarkMode = theme.palette.mode === "dark";
  const whyDataCalloutSx = {
    bgcolor: isDarkMode
      ? "background.default"
      : alpha(theme.palette.secondary.main, 0.16),
    borderLeft: "3px solid",
    borderColor: isDarkMode
      ? "divider"
      : alpha(theme.palette.secondary.dark, 0.7),
    borderRadius: 0.5,
    p: 1.5,
  };

  // Mode state
  const [isEditMode, setIsEditMode] = useState(false);

  // Pending changes (only used in edit mode)
  const [pendingChanges, setPendingChanges] = useState<PendingChanges>({
    ...EMPTY_CHANGES,
    filtersToRemove: new Set(),
    filterEdits: new Map(),
  });

  // Action panel state - only one can be open at a time
  const [editingFilter, setEditingFilter] = useState<Filter | null>(null);
  const [isAddingFilter, setIsAddingFilter] = useState(false);
  const [isEditingFields, setIsEditingFields] = useState(false);
  const [isRemovingEntity, setIsRemovingEntity] = useState(false);

  // Collapsible section states
  const [filtersExpanded, setFiltersExpanded] = useState(true);
  const [fieldsExpanded, setFieldsExpanded] = useState(true);

  // Fetch available fields
  const { fields: availableFields, loading: fieldsLoading } =
    useEntityFieldMetadata(entity.entity_type);

  const relevanceColors = getRelevanceColors(entity.relevance_level, theme);
  const isPrimary = entity.relevance_level === "primary";
  const rawCount = actualCount ?? entity.estimated_count;
  // Normalize to number (handle string values from backend)
  const numericCount = typeof rawCount === 'string' ? parseInt(rawCount, 10) : rawCount;
  const displayCount = numericCount ?? 0;
  // Only show warning (orange) if count is null, undefined, or exactly 0
  const isZeroWarning = numericCount == null || numericCount === 0;

  const isActionPanelOpen =
    editingFilter !== null ||
    isAddingFilter ||
    isEditingFields ||
    isRemovingEntity;

  // Check if a filter was recently changed/added
  const isFilterHighlighted = useCallback(
    (filterId: string) => {
      if (!lastUpdate) return false;
      return (
        lastUpdate.changedFilterIds?.includes(filterId) ||
        lastUpdate.addedFilterIds?.includes(filterId)
      );
    },
    [lastUpdate],
  );

  // Check if a field was recently changed/added
  const isFieldHighlighted = useCallback(
    (fieldName: string) => {
      if (!lastUpdate) return false;
      return (
        lastUpdate.changedFieldNames?.includes(fieldName) ||
        lastUpdate.addedFieldNames?.includes(fieldName)
      );
    },
    [lastUpdate],
  );

  // Current field names (original + pending adds - pending removes)
  const currentFieldNames = useMemo(() => {
    const original = entity.fields_of_interest?.map((f) => f.field) || [];
    if (!isEditMode) return original;
    const withAdds = [...original, ...pendingChanges.fieldsToAdd];
    return withAdds.filter((f) => !pendingChanges.fieldsToRemove.includes(f));
  }, [
    entity.fields_of_interest,
    isEditMode,
    pendingChanges.fieldsToAdd,
    pendingChanges.fieldsToRemove,
  ]);

  // Check if there are any pending changes
  const hasChanges = useMemo(() => {
    return (
      pendingChanges.filtersToRemove.size > 0 ||
      pendingChanges.filtersToAdd.length > 0 ||
      pendingChanges.filterEdits.size > 0 ||
      pendingChanges.fieldsToAdd.length > 0 ||
      pendingChanges.fieldsToRemove.length > 0 ||
      (pendingChanges.reasoningEdit !== null &&
        pendingChanges.reasoningEdit !== entity.reasoning)
    );
  }, [pendingChanges, entity.reasoning]);

  // Enter edit mode
  const handleEnterEditMode = useCallback(() => {
    if (disabled) return;
    setIsEditMode(true);
    setPendingChanges({
      ...EMPTY_CHANGES,
      filtersToRemove: new Set(),
      filterEdits: new Map(),
    });
  }, [disabled]);

  // Cancel edit mode
  const handleCancelEdit = useCallback(() => {
    setIsEditMode(false);
    setPendingChanges({
      ...EMPTY_CHANGES,
      filtersToRemove: new Set(),
      filterEdits: new Map(),
    });
    setEditingFilter(null);
    setIsAddingFilter(false);
    setIsEditingFields(false);
    setIsRemovingEntity(false);
  }, []);

  // Save all changes
  const handleSaveChanges = useCallback(() => {
    if (!hasChanges || !onSubmitChanges) {
      handleCancelEdit();
      return;
    }

    const parts: string[] = [];

    if (pendingChanges.filtersToRemove.size > 0) {
      const filterNames = entity.filters
        .filter((f) => pendingChanges.filtersToRemove.has(f.id))
        .map((f) => `"${f.display_text || f.property}"`);
      if (filterNames.length > 0) {
        parts.push(
          `remove filter${filterNames.length > 1 ? "s" : ""} ${filterNames.join(", ")}`,
        );
      }
    }

    if (pendingChanges.filtersToAdd.length > 0) {
      parts.push(
        `add filter${pendingChanges.filtersToAdd.length > 1 ? "s" : ""}: ${pendingChanges.filtersToAdd.join("; ")}`,
      );
    }

    if (pendingChanges.filterEdits.size > 0) {
      // Filter edits already contain the full edit description
      pendingChanges.filterEdits.forEach((editDescription) => {
        parts.push(editDescription);
      });
    }

    if (pendingChanges.fieldsToAdd.length > 0) {
      const fieldNames = pendingChanges.fieldsToAdd
        .map((f) => `"${f}"`)
        .join(", ");
      parts.push(
        `add field${pendingChanges.fieldsToAdd.length > 1 ? "s" : ""} ${fieldNames}`,
      );
    }

    if (pendingChanges.fieldsToRemove.length > 0) {
      const fieldNames = pendingChanges.fieldsToRemove
        .map((f) => `"${f}"`)
        .join(", ");
      parts.push(
        `remove field${pendingChanges.fieldsToRemove.length > 1 ? "s" : ""} ${fieldNames}`,
      );
    }

    if (
      pendingChanges.reasoningEdit !== null &&
      pendingChanges.reasoningEdit !== entity.reasoning
    ) {
      parts.push(
        `update reasoning to: "${pendingChanges.reasoningEdit.trim()}"`,
      );
    }

    if (parts.length > 0) {
      const message = `Update ${entity.entity_type}: ${parts.join(", ")}`;
      onSubmitChanges(message);
    }

    handleCancelEdit();
  }, [hasChanges, onSubmitChanges, pendingChanges, entity, handleCancelEdit]);

  // Toggle filter removal
  const handleToggleFilterRemoval = useCallback((filterId: string) => {
    setPendingChanges((prev) => {
      const newSet = new Set(prev.filtersToRemove);
      if (newSet.has(filterId)) {
        newSet.delete(filterId);
      } else {
        newSet.add(filterId);
      }
      return { ...prev, filtersToRemove: newSet };
    });
  }, []);

  // Add or edit filter (from action panel)
  const handleFilterSubmit = useCallback(
    (filterDescription: string) => {
      setPendingChanges((prev) => {
        if (editingFilter) {
          // Editing existing filter - track as an edit (not add + remove)
          const newFilterEdits = new Map(prev.filterEdits);
          newFilterEdits.set(editingFilter.id, filterDescription);
          return {
            ...prev,
            filterEdits: newFilterEdits,
          };
        } else {
          // Adding new filter
          return {
            ...prev,
            filtersToAdd: [...prev.filtersToAdd, filterDescription],
          };
        }
      });
      setIsAddingFilter(false);
      setEditingFilter(null);
    },
    [editingFilter],
  );

  // Remove pending filter
  const handleRemovePendingFilter = useCallback((index: number) => {
    setPendingChanges((prev) => ({
      ...prev,
      filtersToAdd: prev.filtersToAdd.filter((_, i) => i !== index),
    }));
  }, []);

  // Handle field changes from action panel
  const handleFieldsUpdate = useCallback((chatMessage: string) => {
    const allFields =
      chatMessage.match(/"([^"]+)"/g)?.map((f) => f.replace(/"/g, "")) || [];
    const hasAdd = chatMessage.includes(": add ");
    const hasRemove = chatMessage.includes(" remove ");

    if (hasAdd && hasRemove) {
      const [addPart, removePart] = chatMessage.split(" and remove ");
      const addedFields =
        addPart.match(/"([^"]+)"/g)?.map((f) => f.replace(/"/g, "")) || [];
      const removedFields =
        removePart.match(/"([^"]+)"/g)?.map((f) => f.replace(/"/g, "")) || [];

      setPendingChanges((prev) => ({
        ...prev,
        fieldsToAdd: [
          ...prev.fieldsToAdd.filter((f) => !removedFields.includes(f)),
          ...addedFields.filter((f) => !prev.fieldsToAdd.includes(f)),
        ],
        fieldsToRemove: [
          ...prev.fieldsToRemove.filter((f) => !addedFields.includes(f)),
          ...removedFields.filter((f) => !prev.fieldsToRemove.includes(f)),
        ],
      }));
    } else if (hasAdd) {
      setPendingChanges((prev) => ({
        ...prev,
        fieldsToAdd: [
          ...prev.fieldsToAdd,
          ...allFields.filter((f) => !prev.fieldsToAdd.includes(f)),
        ],
        fieldsToRemove: prev.fieldsToRemove.filter(
          (f) => !allFields.includes(f),
        ),
      }));
    } else if (hasRemove) {
      setPendingChanges((prev) => ({
        ...prev,
        fieldsToRemove: [
          ...prev.fieldsToRemove,
          ...allFields.filter((f) => !prev.fieldsToRemove.includes(f)),
        ],
        fieldsToAdd: prev.fieldsToAdd.filter((f) => !allFields.includes(f)),
      }));
    }
    setIsEditingFields(false);
  }, []);

  // Handle entity removal - submits immediately
  const handleRemoveEntitySubmit = useCallback(
    (chatMessage: string) => {
      onSubmitChanges?.(chatMessage);
      setIsEditMode(false);
      setPendingChanges({
        ...EMPTY_CHANGES,
        filtersToRemove: new Set(),
        filterEdits: new Map(),
      });
      setIsRemovingEntity(false);
    },
    [onSubmitChanges],
  );

  const toggleFilters = useCallback(
    () => setFiltersExpanded((prev) => !prev),
    [],
  );
  const toggleFields = useCallback(
    () => setFieldsExpanded((prev) => !prev),
    [],
  );

  // Close action panel
  const handleCloseActionPanel = useCallback(() => {
    setEditingFilter(null);
    setIsAddingFilter(false);
    setIsEditingFields(false);
    setIsRemovingEntity(false);
  }, []);

  return (
    <Box
      sx={{
        border: "1px solid",
        borderColor: isEditMode
          ? "primary.main"
          : isPrimary
            ? "primary.main"
            : "divider",
        borderRadius: 0.5,
        bgcolor: disabled
          ? alpha(theme.palette.grey[500], 0.05)
          : isDarkMode
            ? "background.paper"
            : "background.default",
        opacity: disabled ? 0.6 : 1,
        overflow: "hidden",
        position: "relative",
        // Green left border for newly added entities
        ...(lastUpdate?.isNew && {
          borderLeft: "3px solid",
          borderLeftColor: "#0F5C4C",
        }),
      }}
    >
      {/* Main layout - flex split when action panel is open */}
      <Box
        sx={{ display: "flex", minHeight: isActionPanelOpen ? 280 : "auto" }}
      >
        {/* Left side: Full content when closed, minimal header when panel open */}
        <Box
          sx={{
            flex: isActionPanelOpen ? "0 0 50%" : "1 1 auto",
            p: 2,
            display: "flex",
            flexDirection: "column",
            transition: prefersReducedMotion ? "none" : "flex 0.2s ease",
          }}
        >
          {/* Top right: Delete button (edit mode only, non-primary, triggers remove panel) */}
          {isEditMode && !isPrimary && !isActionPanelOpen && (
            <Box sx={{ position: "absolute", top: 8, right: 8, zIndex: 5 }}>
              <IconButton
                size="small"
                onClick={() => setIsRemovingEntity(true)}
                aria-label="Remove entity from scope"
                sx={{
                  color: "#0F5C4C",
                  "&:hover": {
                    bgcolor: alpha("#0F5C4C", 0.08),
                  },
                }}
              >
                <DeleteOutlineIcon fontSize="small" />
              </IconButton>
            </Box>
          )}

          {/* Header: Entity name + count + badges - always visible */}
          <Box
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              mb: isActionPanelOpen ? 0 : 1,
              pr: isActionPanelOpen ? 0 : 6,
            }}
          >
            <Typography
              variant="h6"
              sx={{
                fontWeight: 600,
                fontSize: "1.25rem",
                textDecoration: pendingChanges.removeEntity
                  ? "line-through"
                  : "none",
                opacity: pendingChanges.removeEntity ? 0.5 : 1,
              }}
            >
              {entity.entity_type}
            </Typography>
            {displayCount != null && (
              <Typography
                variant="body2"
                sx={{
                  color: isZeroWarning ? "warning.main" : "text.secondary",
                  fontWeight: isZeroWarning ? 600 : 500,
                  fontSize: "0.85rem",
                }}
              >
                ({displayCount === 0 ? "0 records" : formatCount(displayCount)})
              </Typography>
            )}
            <Chip
              label={formatRelevanceLevel(entity.relevance_level)}
              size="small"
              sx={{
                bgcolor: relevanceColors.bg,
                color: relevanceColors.text,
                fontWeight: 600,
                fontSize: "0.7rem",
                height: 22,
              }}
            />
            {isEditMode && (
              <Chip
                label="Editing"
                size="small"
                sx={{
                  bgcolor: alpha(theme.palette.warning.main, 0.15),
                  color: theme.palette.warning.dark,
                  fontWeight: 600,
                  fontSize: "0.65rem",
                  height: 20,
                }}
              />
            )}
          </Box>

          {/* Contextual content when action panel is open */}
          {isActionPanelOpen && (
            <Box sx={{ flex: 1, mt: 1 }}>
              {/* Removing entity: show reasoning */}
              {isRemovingEntity && entity.reasoning && (
                <Box sx={whyDataCalloutSx}>
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      display: "block",
                      mb: 0.5,
                    }}
                  >
                    Why this data?
                  </Typography>
                  <Typography
                    variant="body2"
                    sx={{ color: "text.primary", lineHeight: 1.5 }}
                  >
                    {entity.reasoning}
                  </Typography>
                </Box>
              )}

              {/* Editing filters: show current filters */}
              {(isAddingFilter || editingFilter) && (
                <Box>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 500, mb: 1, color: "text.secondary" }}
                  >
                    Applied Filters
                  </Typography>
                  {entity.filters.length === 0 ? (
                    <Typography
                      variant="body2"
                      sx={{ color: "text.disabled", fontStyle: "italic" }}
                    >
                      No filters applied
                    </Typography>
                  ) : (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                      {entity.filters.map((filter: Filter) => {
                        const isMarkedForRemoval =
                          pendingChanges.filtersToRemove.has(filter.id);
                        const pendingEdit = pendingChanges.filterEdits.get(
                          filter.id,
                        );
                        const isBeingEdited = !!pendingEdit;
                        const displayLabel = isBeingEdited
                          ? pendingEdit.length > 30
                            ? `${pendingEdit.slice(0, 30)}...`
                            : pendingEdit
                          : filter.display_text || formatFilter(filter);

                        return (
                          <Tooltip
                            key={filter.id}
                            title={filter.reasoning || ""}
                            arrow
                            placement="top"
                          >
                            <Chip
                              label={displayLabel}
                              size="small"
                              onClick={() => setEditingFilter(filter)}
                              onDelete={
                                !isMarkedForRemoval
                                  ? () => {
                                      if (isBeingEdited) {
                                        setPendingChanges((prev) => {
                                          const newEdits = new Map(
                                            prev.filterEdits,
                                          );
                                          newEdits.delete(filter.id);
                                          return {
                                            ...prev,
                                            filterEdits: newEdits,
                                          };
                                        });
                                      } else {
                                        handleToggleFilterRemoval(filter.id);
                                      }
                                    }
                                  : undefined
                              }
                              deleteIcon={
                                !isMarkedForRemoval ? (
                                  <CloseIcon
                                    sx={{ fontSize: "14px !important" }}
                                  />
                                ) : undefined
                              }
                              sx={{
                                bgcolor: isBeingEdited
                                  ? alpha(theme.palette.warning.main, 0.15)
                                  : isMarkedForRemoval
                                    ? alpha(theme.palette.error.main, 0.1)
                                    : alpha(theme.palette.primary.main, 0.08),
                                color: isBeingEdited
                                  ? theme.palette.warning.dark
                                  : isMarkedForRemoval
                                    ? theme.palette.error.main
                                    : theme.palette.primary.dark,
                                border: "1px solid",
                                borderColor: isBeingEdited
                                  ? theme.palette.warning.main
                                  : isMarkedForRemoval
                                    ? theme.palette.error.main
                                    : alpha(theme.palette.primary.main, 0.2),
                                fontWeight: 500,
                                fontSize: "0.8rem",
                                textDecoration: isMarkedForRemoval
                                  ? "line-through"
                                  : "none",
                                opacity: isMarkedForRemoval ? 0.7 : 1,
                                cursor: "pointer",
                                "&:hover": {
                                  bgcolor: isBeingEdited
                                    ? alpha(theme.palette.warning.main, 0.25)
                                    : isMarkedForRemoval
                                      ? alpha(theme.palette.error.main, 0.15)
                                      : alpha(theme.palette.primary.main, 0.15),
                                },
                              }}
                            />
                          </Tooltip>
                        );
                      })}
                    </Box>
                  )}
                </Box>
              )}

              {/* Editing fields: show current fields */}
              {isEditingFields && (
                <Box>
                  <Typography
                    variant="body2"
                    sx={{ fontWeight: 500, mb: 1, color: "text.secondary" }}
                  >
                    Selected Fields
                  </Typography>
                  {currentFieldNames.length === 0 ? (
                    <Typography
                      variant="body2"
                      sx={{ color: "text.disabled", fontStyle: "italic" }}
                    >
                      No fields selected
                    </Typography>
                  ) : (
                    <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                      {currentFieldNames.map((fieldName) => (
                        <Chip
                          key={fieldName}
                          label={fieldName}
                          size="small"
                          sx={{
                            bgcolor: alpha(theme.palette.grey[500], 0.1),
                            color: "text.primary",
                            fontSize: "0.75rem",
                          }}
                        />
                      ))}
                    </Box>
                  )}
                </Box>
              )}
            </Box>
          )}

          {/* Full content - only when action panel is closed */}
          {!isActionPanelOpen && (
            <>
              {/* Connected via - shown for non-primary entities */}
              {connectionInfo && !isPrimary && (
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 0.5,
                    mb: 1.5,
                  }}
                >
                  <LinkIcon sx={{ fontSize: 14, color: "text.secondary" }} />
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      fontSize: "0.75rem",
                    }}
                  >
                    {connectionInfo}
                  </Typography>
                </Box>
              )}

              {/* Rationale section with beige background */}
              {(entity.reasoning || isEditMode) && (
                <Box
                  sx={{
                    ...whyDataCalloutSx,
                    mb: 2,
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      color: "text.secondary",
                      fontWeight: 600,
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      display: "block",
                      mb: 0.5,
                    }}
                  >
                    Why this data?
                  </Typography>
                  {isEditMode ? (
                    <TextField
                      fullWidth
                      size="small"
                      multiline
                      minRows={2}
                      maxRows={4}
                      placeholder="Why is this data needed for your analysis?"
                      value={
                        pendingChanges.reasoningEdit ?? entity.reasoning ?? ""
                      }
                      onChange={(e) =>
                        setPendingChanges((prev) => ({
                          ...prev,
                          reasoningEdit: e.target.value,
                        }))
                      }
                      sx={{
                        "& .MuiOutlinedInput-root": {
                          bgcolor: "background.paper",
                          fontSize: "0.875rem",
                        },
                      }}
                    />
                  ) : (
                    entity.reasoning && (
                      <Typography
                        variant="body2"
                        sx={{ color: "text.primary", lineHeight: 1.5 }}
                      >
                        {entity.reasoning}
                      </Typography>
                    )
                  )}
                </Box>
              )}

              {/* Filters section - collapsible */}
              <Box sx={{ mb: 2 }}>
                <Box
                  component="button"
                  type="button"
                  onClick={toggleFilters}
                  aria-expanded={filtersExpanded}
                  aria-controls={`filters-${entity.entity_type}`}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    cursor: "pointer",
                    userSelect: "none",
                    background: "none",
                    border: "none",
                    padding: 0,
                    font: "inherit",
                    color: "inherit",
                    "&:hover": { color: "primary.main" },
                  }}
                >
                  {filtersExpanded ? (
                    <ExpandLessIcon
                      sx={{ fontSize: 18, mr: 0.5 }}
                      aria-hidden="true"
                    />
                  ) : (
                    <ExpandMoreIcon
                      sx={{ fontSize: 18, mr: 0.5 }}
                      aria-hidden="true"
                    />
                  )}
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Filters (
                    {entity.filters.length + pendingChanges.filtersToAdd.length}{" "}
                    applied)
                  </Typography>
                </Box>

                <Collapse in={filtersExpanded}>
                  <Box
                    id={`filters-${entity.entity_type}`}
                    sx={{
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "center",
                      gap: 0.75,
                      mt: 1,
                      pl: 3,
                    }}
                  >
                    {/* Existing filters */}
                    {entity.filters.map((filter) => {
                      const isMarkedForRemoval =
                        pendingChanges.filtersToRemove.has(filter.id);
                      const isHighlighted = isFilterHighlighted(filter.id);
                      const pendingEdit = pendingChanges.filterEdits.get(
                        filter.id,
                      );
                      const isBeingEdited = !!pendingEdit;

                      // If filter has a pending edit, show the edit description
                      const displayLabel = isBeingEdited
                        ? pendingEdit.length > 40
                          ? `${pendingEdit.slice(0, 40)}...`
                          : pendingEdit
                        : filter.display_text || formatFilter(filter);

                      return (
                        <Tooltip
                          key={filter.id}
                          title={filter.reasoning || ""}
                          arrow
                          placement="top"
                        >
                          <Chip
                            label={displayLabel}
                            size="small"
                            onDelete={
                              isEditMode && !isMarkedForRemoval
                                ? () => {
                                    if (isBeingEdited) {
                                      // Clear the pending edit
                                      setPendingChanges((prev) => {
                                        const newEdits = new Map(
                                          prev.filterEdits,
                                        );
                                        newEdits.delete(filter.id);
                                        return {
                                          ...prev,
                                          filterEdits: newEdits,
                                        };
                                      });
                                    } else {
                                      handleToggleFilterRemoval(filter.id);
                                    }
                                  }
                                : undefined
                            }
                            deleteIcon={
                              isEditMode && !isMarkedForRemoval ? (
                                <CloseIcon
                                  sx={{ fontSize: "14px !important" }}
                                />
                              ) : undefined
                            }
                            onClick={
                              isEditMode
                                ? isMarkedForRemoval
                                  ? () => handleToggleFilterRemoval(filter.id)
                                  : () => setEditingFilter(filter)
                                : undefined
                            }
                            sx={{
                              bgcolor: isBeingEdited
                                ? alpha(theme.palette.warning.main, 0.15)
                                : isMarkedForRemoval
                                  ? alpha(theme.palette.error.main, 0.1)
                                  : alpha(theme.palette.primary.main, 0.08),
                              color: isBeingEdited
                                ? theme.palette.warning.dark
                                : isMarkedForRemoval
                                  ? theme.palette.error.main
                                  : theme.palette.primary.dark,
                              border: "1px solid",
                              borderColor: isBeingEdited
                                ? theme.palette.warning.main
                                : isMarkedForRemoval
                                  ? theme.palette.error.main
                                  : alpha(theme.palette.primary.main, 0.2),
                              fontWeight: 500,
                              fontSize: "0.8rem",
                              textDecoration: isMarkedForRemoval
                                ? "line-through"
                                : "none",
                              opacity: isMarkedForRemoval ? 0.7 : 1,
                              cursor: isEditMode ? "pointer" : "default",
                              // Highlight border for recently changed filters
                              ...(isHighlighted &&
                                !isMarkedForRemoval &&
                                !isBeingEdited && {
                                  borderLeft: "3px solid",
                                  borderLeftColor: "#0F5C4C",
                                }),
                              "&:hover":
                                isEditMode && !isMarkedForRemoval
                                  ? {
                                      bgcolor: isBeingEdited
                                        ? alpha(
                                            theme.palette.warning.main,
                                            0.25,
                                          )
                                        : alpha(
                                            theme.palette.primary.main,
                                            0.15,
                                          ),
                                      borderColor: isBeingEdited
                                        ? theme.palette.warning.dark
                                        : theme.palette.primary.main,
                                    }
                                  : {},
                            }}
                          />
                        </Tooltip>
                      );
                    })}

                    {/* Pending filters to add */}
                    {pendingChanges.filtersToAdd.map((filterDesc, idx) => (
                      <Chip
                        key={`pending-${idx}`}
                        label={
                          filterDesc.length > 30
                            ? `${filterDesc.slice(0, 30)}...`
                            : filterDesc
                        }
                        size="small"
                        onDelete={() => handleRemovePendingFilter(idx)}
                        deleteIcon={
                          <CloseIcon sx={{ fontSize: "14px !important" }} />
                        }
                        sx={{
                          bgcolor: alpha(theme.palette.success.main, 0.1),
                          color: theme.palette.success.dark,
                          border: "1px dashed",
                          borderColor: theme.palette.success.main,
                          fontWeight: 500,
                          fontSize: "0.8rem",
                        }}
                      />
                    ))}

                    {/* Add filter button (edit mode only) */}
                    {isEditMode && (
                      <Chip
                        icon={<AddIcon sx={{ fontSize: "14px !important" }} />}
                        label="Filter"
                        size="small"
                        onClick={() => setIsAddingFilter(true)}
                        sx={{
                          bgcolor: "transparent",
                          border: "1px dashed",
                          borderColor: "divider",
                          color: "text.secondary",
                          fontWeight: 500,
                          fontSize: "0.8rem",
                          cursor: "pointer",
                          "&:hover": {
                            bgcolor: alpha(theme.palette.primary.main, 0.04),
                            borderColor: "primary.main",
                            color: "primary.main",
                          },
                        }}
                      />
                    )}
                  </Box>
                </Collapse>
              </Box>

              {/* Fields of Interest section - collapsible */}
              <Box>
                <Box
                  component="button"
                  type="button"
                  onClick={toggleFields}
                  aria-expanded={fieldsExpanded}
                  aria-controls={`fields-${entity.entity_type}`}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    cursor: "pointer",
                    userSelect: "none",
                    background: "none",
                    border: "none",
                    padding: 0,
                    font: "inherit",
                    color: "inherit",
                    "&:hover": { color: "primary.main" },
                  }}
                >
                  {fieldsExpanded ? (
                    <ExpandLessIcon
                      sx={{ fontSize: 18, mr: 0.5 }}
                      aria-hidden="true"
                    />
                  ) : (
                    <ExpandMoreIcon
                      sx={{ fontSize: 18, mr: 0.5 }}
                      aria-hidden="true"
                    />
                  )}
                  <Typography variant="body2" sx={{ fontWeight: 500 }}>
                    Fields of Interest ({currentFieldNames.length} fields)
                  </Typography>
                </Box>

                <Collapse in={fieldsExpanded}>
                  <Box
                    id={`fields-${entity.entity_type}`}
                    sx={{
                      display: "flex",
                      flexWrap: "wrap",
                      alignItems: "center",
                      gap: 0.5,
                      mt: 1,
                      pl: 3,
                    }}
                  >
                    {/* Original fields (with removal state) */}
                    {entity.fields_of_interest?.map((field, idx) => {
                      const isMarkedForRemoval =
                        pendingChanges.fieldsToRemove.includes(field.field);
                      const isHighlighted = isFieldHighlighted(field.field);
                      return (
                        <Tooltip
                          key={idx}
                          title={field.justification || ""}
                          arrow
                          placement="top"
                        >
                          <Chip
                            label={field.field}
                            size="small"
                            onDelete={
                              isEditMode && !isMarkedForRemoval
                                ? () => {
                                    setPendingChanges((prev) => ({
                                      ...prev,
                                      fieldsToRemove: [
                                        ...prev.fieldsToRemove,
                                        field.field,
                                      ],
                                    }));
                                  }
                                : undefined
                            }
                            deleteIcon={
                              isEditMode && !isMarkedForRemoval ? (
                                <CloseIcon
                                  sx={{ fontSize: "12px !important" }}
                                />
                              ) : undefined
                            }
                            onClick={
                              isEditMode && isMarkedForRemoval
                                ? () => {
                                    setPendingChanges((prev) => ({
                                      ...prev,
                                      fieldsToRemove:
                                        prev.fieldsToRemove.filter(
                                          (f) => f !== field.field,
                                        ),
                                    }));
                                  }
                                : undefined
                            }
                            sx={{
                              bgcolor: isMarkedForRemoval
                                ? alpha(theme.palette.error.main, 0.1)
                                : alpha(theme.palette.grey[500], 0.1),
                              color: isMarkedForRemoval
                                ? theme.palette.error.main
                                : "text.primary",
                              fontSize: "0.75rem",
                              textDecoration: isMarkedForRemoval
                                ? "line-through"
                                : "none",
                              opacity: isMarkedForRemoval ? 0.7 : 1,
                              cursor:
                                isEditMode && isMarkedForRemoval
                                  ? "pointer"
                                  : "default",
                              // Highlight border for recently changed fields
                              ...(isHighlighted &&
                                !isMarkedForRemoval && {
                                  borderLeft: "3px solid",
                                  borderLeftColor: "#0F5C4C",
                                }),
                            }}
                          />
                        </Tooltip>
                      );
                    })}

                    {/* Pending fields to add */}
                    {pendingChanges.fieldsToAdd.map((fieldName, idx) => (
                      <Chip
                        key={`add-${idx}`}
                        label={fieldName}
                        size="small"
                        onDelete={() => {
                          setPendingChanges((prev) => ({
                            ...prev,
                            fieldsToAdd: prev.fieldsToAdd.filter(
                              (f) => f !== fieldName,
                            ),
                          }));
                        }}
                        deleteIcon={
                          <CloseIcon sx={{ fontSize: "12px !important" }} />
                        }
                        sx={{
                          bgcolor: alpha(theme.palette.success.main, 0.1),
                          color: theme.palette.success.dark,
                          fontSize: "0.75rem",
                          border: "1px dashed",
                          borderColor: theme.palette.success.main,
                        }}
                      />
                    ))}

                    {/* Add field button (edit mode only) */}
                    {isEditMode && (
                      <Chip
                        icon={<AddIcon sx={{ fontSize: "14px !important" }} />}
                        label="Field"
                        size="small"
                        onClick={() => setIsEditingFields(true)}
                        sx={{
                          bgcolor: "transparent",
                          border: "1px dashed",
                          borderColor: "divider",
                          color: "text.secondary",
                          fontWeight: 500,
                          fontSize: "0.75rem",
                          cursor: "pointer",
                          "&:hover": {
                            bgcolor: alpha(theme.palette.primary.main, 0.04),
                            borderColor: "primary.main",
                            color: "primary.main",
                          },
                        }}
                      />
                    )}
                  </Box>
                </Collapse>
              </Box>

              {/* Footer: Theo update notification + action buttons (view mode) */}
              {!isEditMode && (
                <Box
                  sx={{
                    mt: 2,
                    pt: 1.5,
                    borderTop: "1px solid",
                    borderColor: "divider",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                  }}
                >
                  {/* Left side: Theo update notification or empty */}
                  <Box sx={{ flex: 1, minWidth: 0 }}>
                    {lastUpdate && (
                      <Box
                        sx={{ display: "flex", alignItems: "center", gap: 1.5 }}
                      >
                        {/* Green dot indicator + label */}
                        <Box
                          component="span"
                          sx={{
                            fontSize: "0.8125rem",
                            color: "text.secondary",
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                          }}
                        >
                          <Box
                            component="span"
                            sx={{
                              width: 8,
                              height: 8,
                              borderRadius: "50%",
                              bgcolor: "primary.main",
                              flexShrink: 0,
                            }}
                          />
                          {lastUpdate.isNew ? "Theo added:" : "Theo updated:"}
                        </Box>
                        {/* Field chips */}
                        <Box
                          sx={{ display: "flex", gap: 0.5, flexWrap: "wrap" }}
                        >
                          {lastUpdate.changedFields.map((field) => (
                            <Chip
                              key={field}
                              label={field.replace(/_/g, " ")}
                              size="small"
                              sx={{
                                textTransform: "capitalize",
                                bgcolor:
                                  theme.palette.mode === "light"
                                    ? "primary.50"
                                    : "primary.900",
                                color:
                                  theme.palette.mode === "light"
                                    ? "primary.700"
                                    : "primary.200",
                                fontWeight: 500,
                                fontSize: "0.75rem",
                                height: 24,
                                "& .MuiChip-label": { px: 1.5 },
                              }}
                            />
                          ))}
                        </Box>
                      </Box>
                    )}
                  </Box>
                  {/* Right side: action buttons */}
                  <Box
                    sx={{
                      display: "flex",
                      alignItems: "center",
                      flexShrink: 0,
                    }}
                  >
                    {onSubmitChanges && (
                      <Button
                        size="small"
                        variant="text"
                        startIcon={
                          <EditIcon sx={{ fontSize: "16px !important" }} />
                        }
                        onClick={handleEnterEditMode}
                        disabled={disabled}
                        sx={{
                          color: "#0F5C4C",
                          textTransform: "none",
                          fontWeight: 500,
                          fontSize: "13px",
                          py: 0.25,
                          px: 1,
                          minWidth: "auto",
                          "&:hover": { bgcolor: alpha("#0F5C4C", 0.08) },
                        }}
                      >
                        Edit
                      </Button>
                    )}
                    {onSubmitChanges && onPreview && (
                      <Box
                        sx={{
                          width: "1px",
                          height: 16,
                          bgcolor: "divider",
                          mx: 0.5,
                        }}
                      />
                    )}
                    {onPreview && (
                      <Button
                        size="small"
                        variant="text"
                        startIcon={
                          <VisibilityOutlinedIcon
                            sx={{ fontSize: "16px !important" }}
                          />
                        }
                        onClick={onPreview}
                        disabled={disabled}
                        sx={{
                          color: "#0F5C4C",
                          textTransform: "none",
                          fontWeight: 500,
                          fontSize: "13px",
                          py: 0.25,
                          px: 1,
                          minWidth: "auto",
                          "&:hover": { bgcolor: alpha("#0F5C4C", 0.08) },
                        }}
                      >
                        Preview
                      </Button>
                    )}
                  </Box>
                </Box>
              )}

              {/* Edit mode footer: Cancel/Save buttons */}
              {isEditMode && (
                <Box
                  sx={{
                    mt: 2,
                    pt: 1.5,
                    borderTop: "1px solid",
                    borderColor: "divider",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "flex-end",
                    gap: 1,
                  }}
                >
                  <Button
                    size="small"
                    onClick={handleCancelEdit}
                    sx={{ color: "text.secondary", textTransform: "none" }}
                  >
                    Cancel
                  </Button>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={handleSaveChanges}
                    disabled={!hasChanges}
                    sx={{ textTransform: "none" }}
                  >
                    Save Changes
                  </Button>
                </Box>
              )}
            </>
          )}
        </Box>

        {/* Right side: Action Panel - integrated into the card */}
        {isActionPanelOpen && (
          <Box
            sx={{
              flex: "0 0 50%",
              borderLeft: "1px solid",
              borderColor: "divider",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {isRemovingEntity ? (
              <RemoveEntityPanel
                entity={entity}
                scopeState={scopeState || null}
                onSubmit={handleRemoveEntitySubmit}
                onCancel={handleCloseActionPanel}
              />
            ) : isEditingFields ? (
              <SlideOutFieldsPanel
                entityType={entity.entity_type}
                selectedFields={currentFieldNames}
                availableFields={availableFields}
                loading={fieldsLoading}
                onSubmit={handleFieldsUpdate}
                onCancel={handleCloseActionPanel}
              />
            ) : isAddingFilter || editingFilter ? (
              <SlideOutFilterPanel
                entityType={entity.entity_type}
                filter={editingFilter}
                availableFields={availableFields}
                onSubmit={handleFilterSubmit}
                onCancel={handleCloseActionPanel}
              />
            ) : null}
          </Box>
        )}
      </Box>
    </Box>
  );
}
