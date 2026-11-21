import assert from 'node:assert/strict'
import { test } from 'node:test'
import { formatAnswer } from '../src/utils/answerCitations.js'
import { getPolicySources, getPolicySourceLocation, getPolicySourceUrl, groupPolicySources, resolveCitationSource } from '../src/utils/policyPresentation.js'

const policyUrl = 'https://www.gov.cn/zhengce/policy.htm'
const sources = [1, 6, 4, 3, 2].map((chunk, index) => ({
  id: `chunk-${index}`, document_id: 'policy-844',
  title: `住房公积金管理条例（第${chunk}/6段）`,
  url: policyUrl, path: `policy-${chunk}.md`,
  excerpt: `第十八条 缴存基数以原文为准。片段${chunk}。`,
  chunk_index: chunk
}))

test('normalizing sources retains citation order and actual evidence metadata', () => {
  const normalized = getPolicySources({ sources })
  assert.equal(normalized.length, 5)
  assert.deepEqual(normalized.map(source => source.id), sources.map(source => source.id))
  assert.equal(normalized[0].url, policyUrl)
  assert.equal(normalized[0].document_id, 'policy-844')
  assert.equal(normalized[0].excerpt, sources[0].excerpt)
  assert.equal(normalized[0].chunk_index, 1)
})

test('fragments share one original without renumbering citations', () => {
  const grouped = groupPolicySources(sources)
  assert.equal(grouped.length, 1)
  assert.equal(grouped[0].title, '住房公积金管理条例')
  assert.equal(grouped[0].url, policyUrl)
  assert.deepEqual(grouped[0].originalIndices, [0, 1, 2, 3, 4])
  assert.equal(grouped[0].sources[1].chunk_index, 6)
})

test('same names from distinct originals and unidentified sources never merge', () => {
  const records = [
    { title: '实施细则', url: 'https://a.gov.cn/a' },
    { title: '实施细则', url: 'https://b.gov.cn/b' },
    { title: '实施细则' }, { title: '实施细则' }
  ]
  assert.equal(groupPolicySources(records).length, 4)
  assert.equal(groupPolicySources([
    { title: '细则（第1/2段）', document_id: 'same' },
    { title: '细则（第2/2段）', document_id: 'same' }
  ]).length, 1)
  assert.equal(groupPolicySources([
    { title: '细则', url: policyUrl, source_version: 'old' },
    { title: '细则', url: policyUrl, source_version: 'new' }
  ]).length, 2)
})

test('locations use an actual page or labelled fragment without guessing index bases', () => {
  assert.equal(getPolicySourceLocation(sources[1]), '第 6 段')
  assert.equal(getPolicySourceLocation({ page: 18 }), '第 18 页')
  assert.equal(getPolicySourceLocation({ chunk_index: 0 }), '引用摘录')
})

test('article navigation finds the actual Arabic or Chinese clause inside the same original', () => {
  const records = getPolicySources({ sources: [
    { ...sources[0], excerpt: '第十七条 另一条款。' },
    { ...sources[1], excerpt: '开头文字。第十八条 职工缴存额按规定确定。' },
    { ...sources[2], excerpt: '第十九条 其他内容。' }
  ] })
  const resolved = resolveCitationSource(records, 0, '第18条')
  assert.equal(resolved.sourceIndex, 1)
  assert.equal(resolved.matched, true)
  assert.equal(records[resolved.sourceIndex].excerpt.slice(resolved.start, resolved.end), '第十八条')
  assert.deepEqual(records.map(source => source.citation_index), [0, 1, 2])
  const arabic = resolveCitationSource([{ ...sources[0], excerpt: '第18条 正文。' }], 0, '第十八条')
  assert.equal(arabic.matched, true)
  assert.equal(arabic.article, '第18条')
})

test('article navigation keeps an already matching fragment and matches whole clause numbers', () => {
  const records = [
    { ...sources[0], excerpt: '第一百一十八条 不可当作第十八条的编号。' },
    { ...sources[1], excerpt: '第18条 一处来源。' },
    { ...sources[2], excerpt: '第十八条 另一处来源。' }
  ]
  assert.equal(resolveCitationSource(records, 2, '第18条').sourceIndex, 2)
  assert.equal(resolveCitationSource([{ ...sources[0], excerpt: '第一百一十八条 正文。' }], 0, '第18条').matched, false)
  assert.equal(resolveCitationSource([{ ...sources[0], excerpt: '第一百零八条 正文。' }], 0, '第108条').matched, true)
})

test('article matching never crosses document or version identities and never invents a target', () => {
  const records = [
    { ...sources[0], document_id: 'a', excerpt: '第十七条 正文。' },
    { ...sources[1], document_id: 'b', excerpt: '第十八条 别的文件。' },
    { ...sources[2], document_id: 'a', source_version: 'older', excerpt: '第十八条 旧版本。' }
  ]
  assert.equal(groupPolicySources(records).length, 3)
  const resolved = resolveCitationSource(records, 0, '第18条')
  assert.deepEqual(resolved, { sourceIndex: 0, matched: false, start: -1, end: -1, article: '' })
  assert.equal(resolveCitationSource(records, 0, '').matched, false)
})

test('numeric and Chinese citations use authoritative URLs and adjacent article context', () => {
  const html = formatAnswer('资料来源：[资料1]，第18条；另见[资料 5]和[2]。', sources)
  assert.match(html, /href="https:\/\/www\.gov\.cn\/zhengce\/policy\.htm"/)
  assert.match(html, /data-source-index="0" data-article="第18条"/)
  assert.match(html, /data-source-index="4"/)
  assert.match(html, /data-source-index="1"/)
  assert.doesNotMatch(html, /data-source-index="5"/)
})

test('citation links keep clause navigation metadata without displaying repeated clause labels', () => {
  const html = formatAnswer('按规定办理。[资料1]第十八条 / [资料2]，第18条。', sources)
  const visible = html.replace(/<[^>]*>/g, '')
  assert.equal(visible, '按规定办理。资料1 / 资料2。')
  assert.match(html, /data-source-index="0" data-article="第十八条"/)
  assert.match(html, /data-source-index="1" data-article="第18条"/)
})

test('citation-only clause labels across soft line breaks are hidden while substantive clauses and code remain', () => {
  const html = formatAnswer('第十八条规定了缴存比例。\n[资料1]\n第 十 八 条\n\n`[资料1]第18条`\n\n[资料9]第18条', sources)
  assert.match(html, /answer-article">第十八条<\/span>规定了缴存比例/)
  assert.match(html, /data-article="第十八条"/)
  assert.doesNotMatch(html, /answer-article">第 十 八 条/)
  assert.match(html, /<code>\[资料1\]第18条<\/code>/)
  assert.match(html, /\[资料9\]<span class="answer-article">第18条<\/span>/)
})

test('hiding citation location removes only its own parentheses', () => {
  const html = formatAnswer('[资料1]（第18条）；（资料来源：[资料2]，第十八条）。', sources)
  assert.equal(html.replace(/<[^>]*>/g, ''), '资料1；（资料来源：资料2）。')
  assert.equal((html.match(/data-article=/g) || []).length, 2)
})

test('missing originals open evidence while unknown citation numbers remain plain', () => {
  const html = formatAnswer('见[资料1]、[资料9]和[0]。', [{ title: '无链接原件' }])
  assert.match(html, /href="#policy-evidence"/)
  assert.match(html, /\[资料9\]/)
  assert.match(html, /\[0\]/)
  assert.equal((html.match(/<a /g) || []).length, 1)
})

test('discarding malformed source records never shifts the server citation numbers', () => {
  const normalized = getPolicySources({ sources: [null, { url: policyUrl, excerpt: '第十八条 原文' }, {}, { title: '另一份' }] })
  assert.equal(normalized.length, 2)
  assert.deepEqual(normalized.map(source => source.citation_index), [1, 3])
  const html = formatAnswer('[资料1] [资料2] [资料4]', normalized)
  assert.match(html, /\[资料1\]/)
  assert.match(html, /data-source-index="0"/)
  assert.match(html, /data-source-index="1"/)
  assert.deepEqual(groupPolicySources(normalized).map(group => group.citationNumbers), [[2], [4]])
})

test('HTML and unsafe URLs cannot become executable links or attributes', () => {
  const html = formatAnswer('<img src=x onerror=alert(1)> **依据[资料1]** [危险](javascript:alert(1))', [
    { title: '" onclick="alert(1)', url: 'javascript:alert(1)', path: '//evil.test/path' }
  ])
  assert.match(html, /&lt;img/)
  assert.doesNotMatch(html, /<img|href="javascript:|href="\/\/evil| onclick="/)
  assert.match(html, /<strong>依据<a /)
  assert.match(html, /href="#policy-evidence"/)
  assert.equal(getPolicySourceUrl({ url: 'https://name:secret@gov.cn/a' }), '')
})

test('inline code and code fences preserve literal citations; table cells can cite', () => {
  const html = formatAnswer('`[资料1]`\n\n```text\n[资料1]\n```\n\n| 条款 | 依据 |\n| --- | --- |\n| **第18条** | [资料1] |', sources)
  assert.match(html, /<code>\[资料1\]<\/code>/)
  assert.match(html, /<pre><code>\[资料1\]<\/code><\/pre>/)
  assert.match(html, /<table>/)
  assert.match(html, /<strong><span class="answer-article">第18条<\/span><\/strong>/)
  assert.equal((html.match(/data-source-index=/g) || []).length, 1)
})

test('model-supplied citation markdown cannot replace a real source with another URL', () => {
  const html = formatAnswer('[资料1](https://wrong.test/other)', sources)
  assert.match(html, /href="https:\/\/www\.gov\.cn\/zhengce\/policy\.htm"/)
  assert.doesNotMatch(html, /wrong\.test/)
})

test('compound policy lists keep later paragraph numbers after bullets and blank lines', () => {
  const answer = '1. **缴存条件**\n- 职工与单位按规定缴存。[资料1]\n\n2. **提取条件**\n- 购买、建造或翻建自住住房。\n- 核对相应材料。\n\n3. **贷款条件**\n- 以原文与受理要求为准。\n\n4. **办理材料**\n- 提供真实材料。\n\n5. **政策依据**\n- 资料来源：[资料1]，第18条。'
  const html = formatAnswer(answer, sources)
  assert.deepEqual([...html.matchAll(/<ol(?: start="(\d+)")?>/g)].map(match => match[1] || '1'), ['1', '2', '3', '4', '5'])
  assert.equal((html.match(/<ul>/g) || []).length, 5)
  assert.match(html, /<ol start="2"><li><strong>提取条件<\/strong>/)
  assert.match(html, /data-article="第18条"/)
})

test('article labels remain indivisible text units in paragraphs, emphasis and table cells', () => {
  const html = formatAnswer('根据第11条、第 十 八 条和**第十九条**办理。\n\n| 依据 | 说明 |\n| --- | --- |\n| 第18条 | 正文 |', sources)
  assert.match(html, /<span class="answer-article">第11条<\/span>/)
  assert.match(html, /<span class="answer-article">第 十 八 条<\/span>/)
  assert.match(html, /<strong><span class="answer-article">第十九条<\/span><\/strong>/)
  assert.match(html, /<td><span class="answer-article">第18条<\/span><\/td>/)
})

test('article wrapping never rewrites generated link attributes, code or escaped HTML into markup', () => {
  const html = formatAnswer('<img title="第11条" onerror="alert(1)"> 见[资料1]，第18条。`第11条` [原文第十八条](https://www.gov.cn/policy.htm)', sources)
  assert.doesNotMatch(html, /<img|onerror="alert/)
  assert.match(html, /data-article="第18条"/)
  assert.match(html, /<code>第11条<\/code>/)
  assert.match(html, /href="https:\/\/www\.gov\.cn\/zhengce\/policy\.htm" data-source-index="0"/)
  assert.doesNotMatch(html, /(?:href|aria-label|data-article)="[^"]*<span/)
})
