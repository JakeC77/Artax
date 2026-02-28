/**
 * Helper functions for GraphQL operations with Tiptap content
 * These functions handle the conversion between storage format (JSON) and AI communication format (Markdown)
 */

import { toTiptapJSON, prepareForStorage } from '../utils/tiptapConverters';
import { Editor } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import Typography from '@tiptap/extension-typography';
import Color from '@tiptap/extension-color';
import { TextStyle } from '@tiptap/extension-text-style';
import Highlight from '@tiptap/extension-highlight';
import Link from '@tiptap/extension-link';
import Image from '@tiptap/extension-image';

// Extensions configuration (same as in editor)
const extensions = [
  StarterKit.configure({
    heading: {
      levels: [1, 2, 3],
    },
  }),
  Typography,
  TextStyle,
  Color,
  Highlight.configure({
    multicolor: true,
  }),
  Link.configure({
    openOnClick: false,
  }),
  Image,
  Markdown.configure({
    html: true,
    tightLists: true,
    transformPastedText: true,
    transformCopiedText: true,
  }),
];

/**
 * Convert intent from storage format (JSON) to Markdown for AI team communication
 * Used when sending intent to AI backend
 */
export function intentToMarkdown(intentJSON: string): string {
  try {
    const jsonContent = JSON.parse(intentJSON);
    
    // Create a temporary editor to convert JSON to Markdown
    const tempDiv = document.createElement('div');
    const editor = new Editor({
      element: tempDiv,
      extensions,
      content: jsonContent,
    });
    
    // Use the Markdown extension's getMarkdown method
    const markdownExt = editor.extensionManager.extensions.find(
      ext => ext.name === 'markdown'
    );
    
    let markdown = '';
    if (markdownExt && markdownExt.storage && typeof markdownExt.storage.getMarkdown === 'function') {
      markdown = markdownExt.storage.getMarkdown();
    } else {
      // Fallback: use plain text if markdown extension isn't available
      markdown = editor.getText();
    }
    
    editor.destroy();
    
    return markdown;
  } catch (error) {
    console.error('Failed to convert intent JSON to Markdown:', error);
    // If it's already markdown or plain text, return as-is
    return intentJSON;
  }
}

/**
 * Convert intent from AI-generated Markdown to storage format (JSON)
 * Used when receiving intent from AI backend
 */
export function markdownToIntentJSON(markdown: string): string {
  try {
    const jsonContent = toTiptapJSON(markdown);
    return prepareForStorage(jsonContent);
  } catch (error) {
    console.error('Failed to convert Markdown to intent JSON:', error);
    // Return empty document on error
    return prepareForStorage({
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [],
        },
      ],
    });
  }
}

/**
 * Prepare intent for AI communication
 * Converts stored JSON to Markdown format
 */
export function prepareIntentForAI(storedIntent: string | null): string {
  if (!storedIntent) return '';
  
  // Try to determine if it's already markdown or needs conversion
  try {
    JSON.parse(storedIntent);
    // It's valid JSON, convert to markdown
    return intentToMarkdown(storedIntent);
  } catch {
    // It's not JSON, assume it's already markdown
    return storedIntent;
  }
}

/**
 * Process intent received from AI
 * Converts markdown to JSON for storage
 */
export function processIntentFromAI(aiIntent: string): string {
  // AI always sends markdown, convert to JSON for storage
  return markdownToIntentJSON(aiIntent);
}

