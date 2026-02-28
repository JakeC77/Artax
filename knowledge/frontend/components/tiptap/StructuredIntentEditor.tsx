import { useEffect, useRef, forwardRef, useImperativeHandle } from "react";
import { useEditor, EditorContent, Editor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import { Node, mergeAttributes } from "@tiptap/core";
import { Box, Paper, Chip, useTheme } from "@mui/material";
import type { IntentPackage } from "../../services/graphql";
import {
  intentPackageToEditor,
  editorToIntentPackage,
  diffPackages,
  type IntentField,
  type TiptapDocNode,
} from "../../utils/intentEditorUtils";
import type { UserEditableField } from "../../contexts/IntentContext";
import TiptapToolbar from "./TiptapToolbar";

// ============================================================================
// Custom Tiptap Nodes for Structured Intent
// ============================================================================

/**
 * SectionHeader - Non-editable section label
 * Renders as a visual header that cannot be selected, deleted, or edited
 */
const SectionHeader = Node.create({
  name: "sectionHeader",
  group: "block",
  content: "text*",
  marks: "", // No marks allowed
  selectable: false,
  draggable: false,
  atom: false, // Changed from true - atom:true was blocking keyboard events

  addAttributes() {
    return {
      level: { default: "h2" }, // h1 for "Mission", h2 for section labels
      field: { default: null }, // 'objective' | 'why' | 'success_looks_like' | 'summary'
    };
  },

  parseHTML() {
    return [{ tag: "div[data-section-header]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-section-header": "",
        "data-level": HTMLAttributes.level || "h2",
        contenteditable: "false",
        class: "section-header",
      }),
      0,
    ];
  },
});

/**
 * SectionContent - Editable content area within a section
 * Contains the user-editable content for each field
 */
const SectionContent = Node.create({
  name: "sectionContent",
  group: "block",
  content: "block+", // Paragraphs, lists, etc.
  isolating: true, // Keep cursor contained within this section
  defining: true, // Helps with proper cursor and selection handling

  addAttributes() {
    return {
      field: { default: null }, // Maps to IntentPackage field
    };
  },

  parseHTML() {
    return [{ tag: "div[data-section-content]" }];
  },

  renderHTML({ HTMLAttributes }) {
    return [
      "div",
      mergeAttributes(HTMLAttributes, {
        "data-section-content": "",
        "data-field": HTMLAttributes.field || "",
        class: "section-content",
      }),
      0,
    ];
  },
});

// ============================================================================
// Component Types
// ============================================================================

export interface StructuredIntentEditorProps {
  intentPackage: IntentPackage;
  onChange?: (pkg: IntentPackage) => void;
  onEditorReady?: (editor: Editor) => void;
  recentlyUpdatedFields?: IntentField[];
  editable?: boolean;
  height?: number | string;
  // Callback when user edits specific fields (for tracking user_edited_fields)
  onFieldsEdited?: (fields: UserEditableField[]) => void;
}

export interface StructuredIntentEditorRef {
  getEditor: () => Editor | null;
  getIntentPackage: () => IntentPackage | null;
}

// ============================================================================
// Component
// ============================================================================

// Map IntentField to UserEditableField format
const intentFieldToUserEditableField = (field: IntentField): UserEditableField => {
  switch (field) {
    case 'objective':
      return 'mission.objective';
    case 'why':
      return 'mission.why';
    case 'success_looks_like':
      return 'mission.success_looks_like';
    case 'summary':
      return 'summary';
    case 'title':
      return 'title';
    default:
      return field as UserEditableField;
  }
};

const StructuredIntentEditor = forwardRef<
  StructuredIntentEditorRef,
  StructuredIntentEditorProps
>(function StructuredIntentEditor(
  {
    intentPackage,
    onChange,
    onEditorReady,
    recentlyUpdatedFields = [],
    editable = true,
    height = "100%",
    onFieldsEdited,
  },
  ref,
) {
  const theme = useTheme();
  // packageRef tracks the current state (updated by user typing AND external updates)
  const packageRef = useRef(intentPackage);
  const isUpdatingRef = useRef(false);
  // Track when user is actively typing to ignore prop changes that echo back
  const isUserEditingRef = useRef(false);
  const userEditTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Track the last external package we received (from props) to detect true external changes
  // This is ONLY updated when we actually apply an external update to the editor
  const lastExternalPackageRef = useRef<IntentPackage | null>(null);

  // NOTE: We intentionally do NOT sync packageRef with intentPackage prop here
  // packageRef is updated in two places:
  // 1. onUpdate callback (user typing)
  // 2. The external update useEffect (when AI sends new content)
  // Syncing it here would overwrite user edits when the parent re-renders

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        // Enable headings for user content
        heading: {
          levels: [1, 2, 3],
        },
        // Disable horizontal rule
        horizontalRule: false,
      }),
      Underline,
      SectionHeader,
      SectionContent,
    ],
    content: intentPackageToEditor(intentPackage),
    editable,
    editorProps: {
      // Ensure keyboard events aren't blocked
      handleKeyDown: () => {
        // Return false to let Tiptap handle the key event normally
        return false;
      },
    },
    onUpdate: ({ editor }) => {
      if (isUpdatingRef.current) return;

      // Mark that user is actively editing - this prevents the prop change
      // from echoing back and resetting the editor
      isUserEditingRef.current = true;

      // Clear any pending timeout to prevent premature reset when typing fast
      if (userEditTimeoutRef.current) {
        clearTimeout(userEditTimeoutRef.current);
      }

      const editorJSON = editor.getJSON() as TiptapDocNode;
      const previousPackage = packageRef.current;
      const updatedPackage = editorToIntentPackage(
        editorJSON,
        previousPackage,
      );

      // Detect which fields were edited by comparing old and new packages
      if (onFieldsEdited) {
        const changedFields = diffPackages(previousPackage, updatedPackage);
        if (changedFields.length > 0) {
          // Convert IntentField to UserEditableField format
          const userEditableFields = changedFields.map(intentFieldToUserEditableField);
          onFieldsEdited(userEditableFields);
        }
      }

      packageRef.current = updatedPackage;

      if (onChange) {
        onChange(updatedPackage);
      }

      // Clear the editing flag after a short delay (allows prop to settle)
      userEditTimeoutRef.current = setTimeout(() => {
        isUserEditingRef.current = false;
        userEditTimeoutRef.current = null;
      }, 150);
    },
  });

  // Expose editor to parent via ref
  useImperativeHandle(
    ref,
    () => ({
      getEditor: () => editor,
      getIntentPackage: () => {
        if (!editor) return packageRef.current;
        const editorJSON = editor.getJSON() as TiptapDocNode;
        return editorToIntentPackage(editorJSON, packageRef.current);
      },
    }),
    [editor],
  );

  // Notify parent when editor is ready
  useEffect(() => {
    if (editor && onEditorReady) {
      onEditorReady(editor);
    }
  }, [editor, onEditorReady]);

  // Update editor content when intentPackage changes from EXTERNAL source only
  // Compare against LAST EXTERNAL package (not packageRef which includes user edits)
  useEffect(() => {
    if (!editor) return;
    if (!intentPackage) return;

    // If user is actively typing, ignore this prop change - it's just an echo
    // from the parent component's state update
    if (isUserEditingRef.current) {
      return;
    }

    // Compare with the last EXTERNAL package we received (ignoring user edits in between)
    // This ensures we detect when AI sends us different content
    const lastExternal = lastExternalPackageRef.current;
    if (lastExternal) {
      const isSameAsLastExternal =
        lastExternal.mission?.objective === intentPackage.mission?.objective &&
        lastExternal.mission?.why === intentPackage.mission?.why &&
        lastExternal.mission?.success_looks_like ===
          intentPackage.mission?.success_looks_like &&
        lastExternal.summary === intentPackage.summary;

      if (isSameAsLastExternal) {
        return;
      }
    }

    // This is a true external change (from AI or initial load)
    // Prevent update loops
    isUpdatingRef.current = true;

    const newContent = intentPackageToEditor(intentPackage);
    editor.commands.setContent(newContent);

    // Update BOTH refs
    packageRef.current = intentPackage;
    lastExternalPackageRef.current = intentPackage;

    // Re-enable updates after a tick
    setTimeout(() => {
      isUpdatingRef.current = false;
    }, 0);
  }, [intentPackage, editor]);

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (userEditTimeoutRef.current) {
        clearTimeout(userEditTimeoutRef.current);
      }
    };
  }, []);

  if (!editor) {
    return null;
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 2,
        overflow: "hidden",
        border: "1px solid",
        borderColor: "divider",
        bgcolor:
          theme.palette.mode === "light"
            ? "background.paper"
            : "background.paper",
        maxHeight: height, // Use maxHeight so content determines size, but won't exceed container
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* WYSIWYG Toolbar - shared component */}
      {editable && <TiptapToolbar editor={editor} showUnderline={true} />}

      {/* Editor Content - styled like a markdown editor */}
      <Box
        sx={{
          flex: 1,
          minHeight: 0, // Critical: allows flex child to shrink and enable scrolling
          overflow: "auto",
          "& .ProseMirror": {
            p: 3,
            outline: "none",
            fontFamily: theme.typography.fontFamily,
            fontSize: "1rem",
            lineHeight: 1.75,
            color: "text.primary",
            bgcolor: theme.palette.mode === "light" ? "#FFFFFF" : "transparent",

            // Section Headers - h1 for "Mission", h2 for section labels (OBJECTIVE, etc.)
            "& .section-header": {
              display: "flex",
              alignItems: "center",
              gap: 1.5,
              userSelect: "none",
              cursor: "default",
              pointerEvents: "none",
              lineHeight: 1.3,
              "&:first-of-type": {
                mt: 0,
              },
            },
            // H1 - "Mission" parent header
            '& .section-header[data-level="h1"]': {
              fontSize: "1.5rem",
              fontWeight: 700,
              color: "text.primary",
              mt: 0,
              mb: 2,
            },
            // H2 - Section labels (OBJECTIVE, WHY, etc.) - uppercase, smaller
            '& .section-header[data-level="h2"]': {
              fontSize: "1rem",
              fontWeight: 700,
              color: "text.primary",
              mt: 3,
              mb: 0.5,
              letterSpacing: "0.02em",
            },

            // Section Content (editable areas) - minimal styling
            "& .section-content": {
              position: "relative",
              mb: 3,
              minHeight: "24px",
              // Subtle left border for updated fields
              ...recentlyUpdatedFields.reduce<Record<string, object>>(
                (acc, field) => ({
                  ...acc,
                  [`&[data-field="${field}"]`]: {
                    borderLeft: "3px solid",
                    borderColor:
                      theme.palette.mode === "light"
                        ? "primary.main"
                        : "primary.light",
                    pl: 2,
                    ml: -2,
                  },
                }),
                {},
              ),
            },

            // Standard markdown text styles
            "& p": {
              m: 0,
              mb: 1,
              "&:last-child": {
                mb: 0,
              },
            },
            "& strong": {
              fontWeight: 600,
            },
            "& em": {
              fontStyle: "italic",
            },
            "& ul, & ol": {
              pl: 2.5,
              mb: 1,
              mt: 0,
            },
            "& li": {
              mb: 0.5,
              "& p": {
                mb: 0,
              },
            },
            "& blockquote": {
              borderLeft: "4px solid",
              borderColor:
                theme.palette.mode === "light" ? "grey.300" : "grey.600",
              pl: 2,
              ml: 0,
              my: 1,
              color: "text.secondary",
            },
            "& code": {
              bgcolor: theme.palette.mode === "light" ? "grey.100" : "grey.800",
              px: 0.5,
              py: 0.25,
              borderRadius: 0.5,
              fontSize: "0.875em",
              fontFamily:
                "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
            },
            "& s": {
              textDecoration: "line-through",
              color: "text.secondary",
            },
          },
        }}
      >
        <EditorContent editor={editor} />
      </Box>

      {/* Footer bar - always visible for consistent layout, content shown only when there are updates */}
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 2,
          py: 1,
          borderTop: "1px solid",
          borderColor: "divider",
          bgcolor: theme.palette.mode === "light" ? "grey.50" : "grey.900",
          minHeight: 40, // Consistent height even when empty
        }}
      >
        {recentlyUpdatedFields.length > 0 && (
          <>
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
              Theo updated:
            </Box>
            {recentlyUpdatedFields.map((field) => (
              <Chip
                key={field}
                label={field.replace(/_/g, " ")}
                size="small"
                sx={{
                  textTransform: "capitalize",
                  bgcolor:
                    theme.palette.mode === "light" ? "primary.50" : "primary.900",
                  color:
                    theme.palette.mode === "light"
                      ? "primary.700"
                      : "primary.200",
                  fontWeight: 500,
                  fontSize: "0.75rem",
                  height: 24,
                  "& .MuiChip-label": {
                    px: 1.5,
                  },
                }}
              />
            ))}
          </>
        )}
      </Box>
    </Paper>
  );
});

export default StructuredIntentEditor;
