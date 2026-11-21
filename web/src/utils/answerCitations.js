import { getPolicySourceUrl, getSourceUrl } from './policyPresentation.js'

const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character])
const escapeText = value => escapeHtml(value).replaceAll('\n', '<br>')
const citationPattern = /^(?:资料\s*)?(\d+)$/
const articlePattern = /^[\s，,、：:（(]*((?:第\s*(?:[一二两三四五六七八九十百千万零〇\d]\s*)+条)(?:第\s*(?:[一二两三四五六七八九十百千万零〇\d]\s*)+款)?)/

function renderText(text) {
  let html = ''
  let cursor = 0
  for (const match of text.matchAll(/第\s*(?:[\d０-９零〇一二两三四五六七八九十百千万]\s*)+条/g)) {
    html += escapeText(text.slice(cursor, match.index))
    html += `<span class="answer-article">${escapeHtml(match[0])}</span>`
    cursor = match.index + match[0].length
  }
  return html + escapeText(text.slice(cursor))
}

function renderCitation(label, after, sources, original) {
  const match = citationPattern.exec(label)
  if (!match) return null
  const number = Number(match[1])
  if (!Number.isSafeInteger(number) || number < 1) return { html: escapeHtml(original), locationLength: 0 }
  const sourceIndex = sources.findIndex((source, index) => (source.citation_index ?? index) === number - 1)
  if (sourceIndex < 0) return { html: escapeHtml(original), locationLength: 0 }
  const source = sources[sourceIndex]
  const url = getPolicySourceUrl(source)
  const location = articlePattern.exec(after)
  const article = location?.[1]?.replace(/\s/g, '') || ''
  let locationLength = location?.[0].length || 0
  if (location && /[（(]/.test(location[0]) && /^[）)]/.test(after.slice(locationLength))) locationLength++
  const articleAttribute = article ? ` data-article="${escapeHtml(article)}"` : ''
  const target = url ? ' target="_blank" rel="noopener noreferrer"' : ''
  const title = source.title ? `：${source.title}` : ''
  return {
    html: `<a class="answer-citation" href="${escapeHtml(url || '#policy-evidence')}" data-source-index="${sourceIndex}"${articleAttribute}${target} aria-label="${escapeHtml(`查看资料${number}${title}${article ? `，${article}` : ''}`)}">${escapeHtml(label)}</a>`,
    locationLength
  }
}

function renderInline(text, sources) {
  const pattern = /`([^`\n]+)`|\[([^\]\n]+)\]\(([^)\n]*)\)|\*\*([^*\n]+)\*\*|\*([^*\n]+)\*|\[((?:资料\s*)?\d+)\]/g
  let html = ''
  let cursor = 0
  for (const match of text.matchAll(pattern)) {
    if (match.index < cursor) continue
    let locationLength = 0
    html += renderText(text.slice(cursor, match.index))
    if (match[1] !== undefined) {
      html += `<code>${escapeHtml(match[1])}</code>`
    } else if (match[2] !== undefined) {
      const citation = renderCitation(match[2], text.slice(match.index + match[0].length), sources, match[0])
      const url = getSourceUrl(match[3])
      html += citation?.html ?? (url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noopener noreferrer">${renderText(match[2])}</a>` : escapeHtml(match[0]))
      locationLength = citation?.locationLength || 0
    } else if (match[4] !== undefined) {
      html += `<strong>${renderInline(match[4], sources)}</strong>`
    } else if (match[5] !== undefined) {
      html += `<em>${renderInline(match[5], sources)}</em>`
    } else {
      const citation = renderCitation(match[6], text.slice(match.index + match[0].length), sources, match[0])
      html += citation.html
      locationLength = citation.locationLength
    }
    cursor = match.index + match[0].length + locationLength
  }
  return html + renderText(text.slice(cursor))
}

const tableCells = line => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim())
const tableDivider = line => /^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line)

export function formatAnswer(text, sources = []) {
  if (!text) return ''
  const lines = String(text).replace(/\r\n?/g, '\n').split('\n')
  const html = []
  let index = 0
  while (index < lines.length) {
    const line = lines[index]
    if (!line.trim()) { index++; continue }
    if (/^\s*```/.test(line)) {
      const code = []
      index++
      while (index < lines.length && !/^\s*```/.test(lines[index])) code.push(lines[index++])
      if (index < lines.length) index++
      html.push(`<pre><code>${escapeHtml(code.join('\n'))}</code></pre>`)
      continue
    }
    if (line.includes('|') && index + 1 < lines.length && tableDivider(lines[index + 1])) {
      const headers = tableCells(line)
      index += 2
      const rows = []
      while (index < lines.length && lines[index].includes('|') && lines[index].trim()) {
        const cells = tableCells(lines[index++])
        rows.push(`<tr>${headers.map((_, cell) => `<td>${renderInline(cells[cell] || '', sources)}</td>`).join('')}</tr>`)
      }
      html.push(`<div class="answer-table"><table><thead><tr>${headers.map(cell => `<th>${renderInline(cell, sources)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`)
      continue
    }
    const heading = /^(#{1,6})\s+(.+)$/.exec(line)
    if (heading) {
      const level = Math.min(heading[1].length + 2, 6)
      html.push(`<h${level}>${renderInline(heading[2], sources)}</h${level}>`)
      index++
      continue
    }
    const list = /^\s*(?:([-*])|(\d+)\.)\s+(.+)$/.exec(line)
    if (list) {
      const ordered = Boolean(list[2])
      const start = ordered ? Number(list[2]) : 1
      const items = []
      let item
      while (index < lines.length && (item = /^\s*(?:([-*])|(\d+)\.)\s+(.+)$/.exec(lines[index])) && Boolean(item[2]) === ordered) {
        items.push(`<li>${renderInline(item[3], sources)}</li>`)
        index++
      }
      const tag = ordered ? 'ol' : 'ul'
      const startAttribute = ordered && Number.isSafeInteger(start) && start !== 1 ? ` start="${start}"` : ''
      html.push(`<${tag}${startAttribute}>${items.join('')}</${tag}>`)
      continue
    }
    const paragraph = [line]
    index++
    while (index < lines.length && lines[index].trim() && !/^\s*(?:```|#{1,6}\s|[-*]\s|\d+\.\s)/.test(lines[index]) && !(lines[index].includes('|') && tableDivider(lines[index + 1] || ''))) paragraph.push(lines[index++])
    html.push(`<p>${renderInline(paragraph.join('\n'), sources)}</p>`)
  }
  return html.join('')
}
