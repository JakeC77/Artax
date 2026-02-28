/**
 * Utility functions for converting between Tiptap's JSON format and Markdown
 * Used for storage (JSON) and AI team communication (Markdown)
 */

import { generateHTML } from '@tiptap/react'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import { Markdown } from 'tiptap-markdown'
import Typography from '@tiptap/extension-typography'
import Color from '@tiptap/extension-color'
import { TextStyle } from '@tiptap/extension-text-style'
import Highlight from '@tiptap/extension-highlight'
import Link from '@tiptap/extension-link'
import Image from '@tiptap/extension-image'

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
]

/**
 * Convert Markdown string to Tiptap JSON format
 * Used when loading content from backend (AI-generated markdown -> editor)
 * Note: This creates a temporary editor instance to properly parse markdown
 */
export function markdownToJSON(markdown: string): object {
  try {
    // Create a temporary editor to convert markdown to JSON
    // The Markdown extension will handle the parsing
    const tempDiv = document.createElement('div')
    const editor = new Editor({
      element: tempDiv,
      extensions,
      content: markdown, // Markdown extension will parse this
    })
    
    const json = editor.getJSON()
    editor.destroy()
    
    return json
  } catch (error) {
    console.error('Failed to convert markdown to JSON:', error)
    // Return empty document on error
    return {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [],
        },
      ],
    }
  }
}

/**
 * Convert Tiptap JSON format to HTML
 * Useful for rendering or export
 */
export function jsonToHTML(json: object): string {
  try {
    return generateHTML(json, extensions)
  } catch (error) {
    console.error('Failed to convert JSON to HTML:', error)
    return ''
  }
}

/**
 * Check if a string is valid JSON
 */
export function isValidJSON(str: string): boolean {
  try {
    JSON.parse(str)
    return true
  } catch (e) {
    return false
  }
}

/**
 * Convert content to Tiptap JSON format, handling both JSON and Markdown inputs
 * This is useful when you're not sure what format the content is in
 */
export function toTiptapJSON(content: string): object {
  if (!content || content.trim() === '') {
    return {
      type: 'doc',
      content: [
        {
          type: 'paragraph',
          content: [],
        },
      ],
    }
  }

  // Try to parse as JSON first
  if (isValidJSON(content)) {
    try {
      return JSON.parse(content)
    } catch (e) {
      // Fall through to markdown conversion
    }
  }

  // Otherwise, treat as markdown
  return markdownToJSON(content)
}

/**
 * Prepare content for storage in database
 * Returns stringified JSON
 */
export function prepareForStorage(jsonContent: object): string {
  return JSON.stringify(jsonContent)
}

/**
 * Parse stored content
 * Handles both JSON strings and plain objects
 */
export function parseStoredContent(content: string | object): object {
  if (typeof content === 'object') {
    return content
  }

  return toTiptapJSON(content)
}

