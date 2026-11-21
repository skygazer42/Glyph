import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import vm from 'node:vm'

const require = createRequire(new URL('../../web/package.json', import.meta.url))
const { computed, ref, createSSRApp } = require('vue')
const { renderToString } = require('@vue/server-renderer')
const { parse } = require('@vue/compiler-sfc')
const { compile } = require('@vue/compiler-dom')
const source = readFileSync(new URL('../../web/src/views/DSLGenerator.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const expression = descriptor.scriptSetup.content.match(/^const testHasAmount = (.+)$/m)?.[1]
assert.ok(expression, 'Amount visibility must be derived from the actual result status')
const section = descriptor.template.content.match(/<section v-if="testResult"[\s\S]*?<\/section>/)[0]
const render = vm.runInNewContext(`(function () { ${compile(section, { prefixIdentifiers: true }).code} })()`, { Vue: require('vue') })

for (const status of ['MANUAL_REVIEW', 'INVALID_INPUT', 'INELIGIBLE', 'NOT_IN_PERIOD', 'EXPIRED', 'ERROR']) {
  const testResult = ref({ status, final_result: 0 })
  const testHasAmount = vm.runInNewContext(expression, { computed, testResult })
  const html = await renderToString(createSSRApp({ render, setup: () => ({ testResult, testHasAmount, testStatusText: status }) }))
  assert.doesNotMatch(html, /<dt>原始返回值<\/dt>/, status)
  assert.match(html, /本次未得出金额/, status)
}
for (const amount of [0, 600, '0.0']) {
  const testResult = ref({ status: 'CALCULATED', final_result: amount })
  const testHasAmount = vm.runInNewContext(expression, { computed, testResult })
  const html = await renderToString(createSSRApp({ render, setup: () => ({ testResult, testHasAmount, testStatusText: '金额测算完成' }) }))
  assert.match(html, /<dt>原始返回值<\/dt>/)
  assert.doesNotMatch(html, /本次未得出金额/)
}
console.log('Passed 9 status/amount rendering scenarios using the actual Vue template and computed expression')
