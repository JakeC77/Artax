import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";
import Typography from "@tiptap/extension-typography";
import Color from "@tiptap/extension-color";
import { TextStyle } from "@tiptap/extension-text-style";
import Highlight from "@tiptap/extension-highlight";
import Link from "@tiptap/extension-link";
import Image from "@tiptap/extension-image";
import Underline from "@tiptap/extension-underline";
import { Markdown } from "tiptap-markdown";
import { Box, Paper, useTheme } from "@mui/material";
import { useEffect } from "react";
import TiptapToolbar from "./TiptapToolbar";

export type TiptapEditorProps = {
  content?: string;
  contentType?: "markdown" | "json" | "html";
  onChange?: (content: string, contentType: "json" | "markdown") => void;
  placeholder?: string;
  height?: number | string;
  editable?: boolean;
};

export default function TiptapEditor({
  content = "",
  contentType = "markdown",
  onChange,
  placeholder = "Start typing...",
  height = 400,
  editable = true,
}: TiptapEditorProps) {
  const theme = useTheme();

  const editor = useEditor(
    {
      extensions: [
        StarterKit.configure({
          heading: {
            levels: [1, 2, 3],
          },
        }),
        Placeholder.configure({
          placeholder,
        }),
        Typography,
        TextStyle,
        Color,
        Highlight.configure({
          multicolor: true,
        }),
        Link.configure({
          openOnClick: false,
          HTMLAttributes: {
            class: "tiptap-link",
          },
        }),
        Image.configure({
          HTMLAttributes: {
            class: "tiptap-image",
          },
        }),
        Underline,
        Markdown.configure({
          html: true,
          tightLists: true,
          transformPastedText: true,
          transformCopiedText: true,
        }),
      ],
      content:
        contentType === "json" && content
          ? (() => {
              try {
                return JSON.parse(content);
              } catch (e) {
                return content;
              }
            })()
          : content,
      editorProps: {
        attributes: {
          class: "tiptap-editor-content",
        },
      },
      editable,
      onUpdate: ({ editor }) => {
        if (onChange) {
          const jsonContent = JSON.stringify(editor.getJSON());
          onChange(jsonContent, "json");
          // Note: Markdown conversion will be handled by conversion utilities when needed for AI
        }
      },
    },
    [contentType],
  );

  // Update editor content when prop changes
  useEffect(() => {
    if (editor && content !== undefined && content !== "") {
      // Don't update if content hasn't actually changed
      if (contentType === "json") {
        try {
          const parsedContent = JSON.parse(content);
          const parsedCurrentContent = editor.getJSON();
          if (
            JSON.stringify(parsedContent) ===
            JSON.stringify(parsedCurrentContent)
          ) {
            return;
          }
          // Set JSON content - this will render visually
          editor.commands.setContent(parsedContent);
        } catch (e) {
          console.error("Failed to parse JSON content:", e);
        }
      } else if (contentType === "markdown") {
        // For markdown, we need to use the Markdown extension to parse it
        // The tiptap-markdown extension automatically converts markdown to visual format
        editor.commands.setContent(content);
      } else {
        editor.commands.setContent(content);
      }
    }
  }, [content, contentType, editor]);

  if (!editor) {
    return null;
  }

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 1,
        overflow: "hidden",
        border: "1px solid",
        borderColor: "divider",
        bgcolor:
          theme.palette.mode === "light"
            ? "background.default"
            : "background.paper",
      }}
    >
      {/* Shared Toolbar */}
      {editable && <TiptapToolbar editor={editor} showUnderline={true} />}

      {/* Editor Content */}
      <Box
        sx={{
          height,
          overflow: "auto",
          "& .tiptap-editor-content": {
            p: 2,
            minHeight: "100%",
            outline: "none",
            fontFamily: theme.typography.fontFamily,
            fontSize: "0.875rem",
            color: "text.primary",
            bgcolor: theme.palette.mode === "light" ? "#FFFFFF" : "transparent",
            "& p": {
              m: 0,
              mb: 1,
            },
            "& h1, & h2, & h3": {
              fontWeight: 700,
              mt: 2,
              mb: 1,
              "&:first-of-type": {
                mt: 0,
              },
            },
            "& h1": {
              fontSize: "1.5rem",
            },
            "& h2": {
              fontSize: "1.25rem",
            },
            "& h3": {
              fontSize: "1.125rem",
            },
            "& ul, & ol": {
              pl: 3,
              mb: 1,
            },
            "& li": {
              mb: 0.5,
            },
            "& blockquote": {
              borderLeft: "4px solid",
              borderColor: "primary.main",
              pl: 2,
              ml: 0,
              my: 1,
              fontStyle: "italic",
              color: "text.secondary",
            },
            "& code": {
              bgcolor: "action.hover",
              px: 0.5,
              py: 0.25,
              borderRadius: 0.5,
              border: "1px solid",
              borderColor: "divider",
              fontSize: "0.875rem",
              fontFamily: "monospace",
            },
            "& pre": {
              bgcolor: "action.hover",
              p: 1.5,
              borderRadius: 1,
              overflow: "auto",
              border: "1px solid",
              borderColor: "divider",
              mb: 1,
              "& code": {
                bgcolor: "transparent",
                px: 0,
                py: 0,
                border: "none",
              },
            },
            "& .tiptap-link": {
              color: "primary.main",
              textDecoration: "underline",
              cursor: "pointer",
            },
            "& .tiptap-image": {
              maxWidth: "100%",
              height: "auto",
              borderRadius: 1,
            },
            "& p.is-editor-empty:first-of-type::before": {
              content: "attr(data-placeholder)",
              float: "left",
              color: "text.disabled",
              pointerEvents: "none",
              height: 0,
            },
          },
        }}
      >
        <EditorContent editor={editor} />
      </Box>
    </Paper>
  );
}
