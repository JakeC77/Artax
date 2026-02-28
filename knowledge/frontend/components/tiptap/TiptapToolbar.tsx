import { Box, IconButton, Divider, Tooltip, useTheme } from "@mui/material";
import { Editor } from "@tiptap/react";
import {
  FormatBold,
  FormatItalic,
  FormatUnderlined,
  FormatListBulleted,
  FormatListNumbered,
  FormatQuote,
  Code,
  Undo,
  Redo,
} from "@mui/icons-material";

// ============================================================================
// Toolbar Button Components
// ============================================================================

interface ToolbarButtonProps {
  onClick: () => void;
  isActive?: boolean;
  disabled?: boolean;
  tooltip: string;
  children: React.ReactNode;
}

function ToolbarButton({
  onClick,
  isActive,
  disabled,
  tooltip,
  children,
}: ToolbarButtonProps) {
  const theme = useTheme();
  return (
    <Tooltip title={tooltip} arrow placement="top">
      <IconButton
        size="small"
        onClick={onClick}
        disabled={disabled}
        sx={{
          borderRadius: 1,
          p: 0.75,
          bgcolor: isActive
            ? theme.palette.mode === "light"
              ? "primary.light"
              : "primary.dark"
            : "transparent",
          color: isActive ? "primary.contrastText" : "text.secondary",
          "&:hover": {
            bgcolor: isActive
              ? theme.palette.mode === "light"
                ? "primary.main"
                : "primary.dark"
              : "action.hover",
          },
        }}
      >
        {children}
      </IconButton>
    </Tooltip>
  );
}

interface HeadingButtonProps {
  editor: Editor;
  level: 1 | 2 | 3;
}

function HeadingButton({ editor, level }: HeadingButtonProps) {
  const theme = useTheme();
  const isActive = editor.isActive("heading", { level });

  return (
    <Tooltip title={`Heading ${level}`} arrow placement="top">
      <Box
        component="button"
        onClick={() => editor.chain().focus().toggleHeading({ level }).run()}
        sx={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minWidth: 28,
          height: 28,
          borderRadius: 1,
          border: "none",
          cursor: "pointer",
          fontWeight: 600,
          fontSize: "0.875rem",
          bgcolor: isActive
            ? theme.palette.mode === "light"
              ? "primary.light"
              : "primary.dark"
            : "transparent",
          color: isActive ? "primary.contrastText" : "text.secondary",
          "&:hover": {
            bgcolor: isActive
              ? theme.palette.mode === "light"
                ? "primary.main"
                : "primary.dark"
              : "action.hover",
          },
        }}
      >
        H{level}
      </Box>
    </Tooltip>
  );
}

// ============================================================================
// Main Toolbar Component
// ============================================================================

export interface TiptapToolbarProps {
  editor: Editor | null;
  /** Show underline button (requires Underline extension) */
  showUnderline?: boolean;
}

export default function TiptapToolbar({
  editor,
  showUnderline = true,
}: TiptapToolbarProps) {
  if (!editor) return null;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 0.5,
        px: 1.5,
        py: 1,
        borderBottom: "1px solid",
        borderColor: "divider",
        bgcolor: "action.hover",
        flexWrap: "wrap",
      }}
    >
      {/* Text formatting */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBold().run()}
        isActive={editor.isActive("bold")}
        tooltip="Bold (Ctrl+B)"
      >
        <FormatBold sx={{ fontSize: 18 }} />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleItalic().run()}
        isActive={editor.isActive("italic")}
        tooltip="Italic (Ctrl+I)"
      >
        <FormatItalic sx={{ fontSize: 18 }} />
      </ToolbarButton>
      {showUnderline && (
        <ToolbarButton
          onClick={() => editor.chain().focus().toggleUnderline().run()}
          isActive={editor.isActive("underline")}
          tooltip="Underline (Ctrl+U)"
        >
          <FormatUnderlined sx={{ fontSize: 18 }} />
        </ToolbarButton>
      )}

      <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

      {/* Headings */}
      <HeadingButton editor={editor} level={1} />
      <HeadingButton editor={editor} level={2} />
      <HeadingButton editor={editor} level={3} />

      <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

      {/* Lists */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBulletList().run()}
        isActive={editor.isActive("bulletList")}
        tooltip="Bullet List"
      >
        <FormatListBulleted sx={{ fontSize: 18 }} />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleOrderedList().run()}
        isActive={editor.isActive("orderedList")}
        tooltip="Numbered List"
      >
        <FormatListNumbered sx={{ fontSize: 18 }} />
      </ToolbarButton>

      <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

      {/* Block formatting */}
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleBlockquote().run()}
        isActive={editor.isActive("blockquote")}
        tooltip="Quote"
      >
        <FormatQuote sx={{ fontSize: 18 }} />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().toggleCodeBlock().run()}
        isActive={editor.isActive("codeBlock")}
        tooltip="Code Block"
      >
        <Code sx={{ fontSize: 18 }} />
      </ToolbarButton>

      <Divider orientation="vertical" flexItem sx={{ mx: 0.5 }} />

      {/* Undo/Redo */}
      <ToolbarButton
        onClick={() => editor.chain().focus().undo().run()}
        disabled={!editor.can().undo()}
        tooltip="Undo (Ctrl+Z)"
      >
        <Undo sx={{ fontSize: 18 }} />
      </ToolbarButton>
      <ToolbarButton
        onClick={() => editor.chain().focus().redo().run()}
        disabled={!editor.can().redo()}
        tooltip="Redo (Ctrl+Y)"
      >
        <Redo sx={{ fontSize: 18 }} />
      </ToolbarButton>
    </Box>
  );
}
