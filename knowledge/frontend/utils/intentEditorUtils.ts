/**
 * Intent Editor Utilities
 *
 * Serialization functions for converting between IntentPackage and Tiptap editor JSON.
 * These are extracted to a separate file to comply with React Fast Refresh requirements.
 */

import type { IntentPackage } from '../services/graphql'

// Tiptap JSON Node Types
export interface TiptapTextNode {
  type: 'text'
  text: string
}

export interface TiptapParagraphNode {
  type: 'paragraph'
  content?: TiptapTextNode[]
}

export interface TiptapListItemNode {
  type: 'listItem'
  content?: TiptapParagraphNode[]
}

export interface TiptapBulletListNode {
  type: 'bulletList'
  content?: TiptapListItemNode[]
}

export interface TiptapOrderedListNode {
  type: 'orderedList'
  content?: TiptapListItemNode[]
}

export interface TiptapSectionHeaderNode {
  type: 'sectionHeader'
  attrs: {
    level: 'h1' | 'h2' | 'h3'
    field: string | null
  }
  content: TiptapTextNode[]
}

export interface TiptapSectionContentNode {
  type: 'sectionContent'
  attrs: {
    field: string
  }
  content: (TiptapParagraphNode | TiptapBulletListNode | TiptapOrderedListNode)[]
}

export type TiptapNode =
  | TiptapTextNode
  | TiptapParagraphNode
  | TiptapListItemNode
  | TiptapBulletListNode
  | TiptapOrderedListNode
  | TiptapSectionHeaderNode
  | TiptapSectionContentNode

export interface TiptapDocNode {
  type: 'doc'
  content: TiptapNode[]
}

/**
 * Convert IntentPackage to Tiptap editor JSON
 */
export function intentPackageToEditor(pkg: IntentPackage): TiptapDocNode {
  const createSection = (
    level: 'h1' | 'h2' | 'h3',
    field: string | null,
    label: string,
    content: string
  ): TiptapNode[] => {
    const nodes: TiptapNode[] = [
      {
        type: 'sectionHeader',
        attrs: { level, field },
        content: [{ type: 'text', text: label }],
      },
    ]

    if (field) {
      // Parse content - support bullet lists if content contains bullet points
      const contentNodes: (TiptapParagraphNode | TiptapBulletListNode)[] = []
      const lines = content.split('\n').filter((line) => line.trim())

      // Check if content looks like a list
      const isList = lines.every((line) =>
        line.trim().startsWith('•') || line.trim().startsWith('-') || line.trim().startsWith('*')
      )

      if (isList && lines.length > 0) {
        contentNodes.push({
          type: 'bulletList',
          content: lines.map((line) => ({
            type: 'listItem',
            content: [
              {
                type: 'paragraph',
                content: [
                  {
                    type: 'text',
                    text: line.replace(/^[•\-*]\s*/, '').trim(),
                  },
                ],
              },
            ],
          })),
        })
      } else if (lines.length > 0) {
        // Regular paragraphs
        lines.forEach((line) => {
          contentNodes.push({
            type: 'paragraph',
            content: [{ type: 'text', text: line.trim() }],
          })
        })
      } else {
        // Empty content - add placeholder paragraph
        contentNodes.push({
          type: 'paragraph',
          content: [],
        })
      }

      nodes.push({
        type: 'sectionContent',
        attrs: { field },
        content: contentNodes,
      })
    }

    return nodes
  }

  return {
    type: 'doc',
    content: [
      // Mission - parent header (non-editable, no field)
      ...createSection('h1', null, 'Mission', ''),

      // OBJECTIVE - uppercase label, styled as H2
      ...createSection('h2', 'objective', 'OBJECTIVE', pkg.mission.objective || ''),

      // WHY - uppercase label, styled as H2
      ...createSection('h2', 'why', 'WHY', pkg.mission.why || ''),

      // SUCCESS LOOKS LIKE - uppercase label, styled as H2
      ...createSection(
        'h2',
        'success_looks_like',
        'SUCCESS LOOKS LIKE',
        pkg.mission.success_looks_like || ''
      ),

      // SUMMARY - uppercase label, styled as H2
      ...createSection('h2', 'summary', 'SUMMARY', pkg.summary || ''),
    ],
  }
}

/**
 * Extract text content from Tiptap nodes recursively
 */
function extractTextFromNodes(content: TiptapNode[] | undefined): string {
  if (!content || !Array.isArray(content)) return ''

  return content
    .map((node) => {
      if (node.type === 'text') {
        return (node as TiptapTextNode).text || ''
      }
      if (node.type === 'paragraph') {
        const paragraphNode = node as TiptapParagraphNode
        return extractTextFromNodes(paragraphNode.content as TiptapNode[] | undefined)
      }
      if (node.type === 'bulletList') {
        const listNode = node as TiptapBulletListNode
        return (listNode.content || [])
          .map((item) => {
            if (item.type === 'listItem' && item.content) {
              return '• ' + extractTextFromNodes(item.content as TiptapNode[] | undefined)
            }
            return ''
          })
          .join('\n')
      }
      if (node.type === 'orderedList') {
        const listNode = node as TiptapOrderedListNode
        return (listNode.content || [])
          .map((item, index) => {
            if (item.type === 'listItem' && item.content) {
              return `${index + 1}. ` + extractTextFromNodes(item.content as TiptapNode[] | undefined)
            }
            return ''
          })
          .join('\n')
      }
      // For other nodes with content
      if ('content' in node && node.content) {
        return extractTextFromNodes(node.content as TiptapNode[] | undefined)
      }
      return ''
    })
    .join('\n')
    .trim()
}

/**
 * Convert Tiptap editor JSON to IntentPackage
 * Merges editor content with existing package metadata
 */
export function editorToIntentPackage(
  editorJSON: TiptapDocNode | null,
  existingPackage: IntentPackage
): IntentPackage {
  if (!editorJSON || !editorJSON.content) {
    return existingPackage
  }

  const sections: Record<string, string> = {}

  // Walk through content, find sectionContent nodes
  for (const node of editorJSON.content) {
    if (node.type === 'sectionContent') {
      const sectionNode = node as TiptapSectionContentNode
      const field = sectionNode.attrs?.field
      if (field) {
        const text = extractTextFromNodes(sectionNode.content as TiptapNode[] | undefined)
        sections[field] = text
      }
    }
  }

  return {
    ...existingPackage, // Preserve AI metadata (team_guidance, etc.)
    schema_version: existingPackage.schema_version ?? 1,

    // Update user-editable fields from editor
    mission: {
      objective: sections.objective ?? existingPackage.mission.objective,
      why: sections.why ?? existingPackage.mission.why,
      success_looks_like: sections.success_looks_like ?? existingPackage.mission.success_looks_like,
    },
    summary: sections.summary ?? existingPackage.summary,
  }
}

/**
 * Compare two IntentPackages and return which fields changed
 */
export type IntentField = 'objective' | 'why' | 'success_looks_like' | 'summary' | 'title'

export function diffPackages(
  previous: IntentPackage,
  current: IntentPackage
): IntentField[] {
  const changed: IntentField[] = []

  if (previous.title !== current.title) {
    changed.push('title')
  }
  if (previous.summary !== current.summary) {
    changed.push('summary')
  }
  if (previous.mission.objective !== current.mission.objective) {
    changed.push('objective')
  }
  if (previous.mission.why !== current.mission.why) {
    changed.push('why')
  }
  if (previous.mission.success_looks_like !== current.mission.success_looks_like) {
    changed.push('success_looks_like')
  }

  return changed
}
