import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import test from 'node:test'
import vm from 'node:vm'

const require = createRequire(new URL('../../web/package.json', import.meta.url))
const vue = require('vue')
const { renderToString } = require('@vue/server-renderer')
const { parse } = require('@vue/compiler-sfc')
const { compile } = require('@vue/compiler-dom')
const source = readFileSync(new URL('../../web/src/views/DSLGenerator.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const form = descriptor.template.content.match(/<el-form id="rule-test-form"[\s\S]*?<\/el-form>/)[0]
const render = new Function('Vue', compile(form, { mode: 'function', prefixIdentifiers: true }).code)(vue)

async function renderFields(specs) {
  const application = vue.createSSRApp({
    data: () => ({ testInputSpecs: specs, testForm: { inputs: {} }, testing: false }),
    methods: { formatParamLabel: name => name, executeTest() {} },
    render
  })
  application.component('ElForm', { render() { return vue.h('form', this.$slots.default?.()) } })
  application.component('ElFormItem', {
    props: ['label'],
    render() { return vue.h('label', [this.label, this.$slots.default?.()]) }
  })
  application.component('ElSelect', {
    render() { return vue.h('select', this.$attrs, this.$slots.default?.()) }
  })
  application.component('ElOption', {
    props: ['label', 'value'],
    render() { return vue.h('option', { value: this.value, 'data-value-type': typeof this.value }, this.label) }
  })
  for (const name of ['ElInput', 'ElInputNumber']) {
    application.component(name, { render() { return vue.h('input', this.$attrs) } })
  }
  return renderToString(application)
}

test('rule-provided Chinese labels, help and typed choices render in the actual form', async () => {
  const html = await renderFields([
    { name: 'eligibility_confirmed', label: '资格已核实', type: 'bool', description: '须由主管部门核实', options: [{ label: '是', value: true }, { label: '否', value: false }] },
    { name: 'payment_year', label: '测算口径', type: 'int', description: '0为总额', options: [{ label: '总额', value: 0 }, { label: '第一年', value: 1 }] }
  ])
  assert.match(html, /aria-label="资格已核实"/)
  assert.match(html, /须由主管部门核实/)
  assert.match(html, /value="false" data-value-type="boolean"/)
  assert.match(html, /value="0" data-value-type="number"/)
  assert.equal((html.match(/<select/g) || []).length, 2)
})

test('legacy fields keep fallback names and boolean controls', async () => {
  const html = await renderFields([{ name: 'price', type: 'float' }, { name: 'confirmed', type: 'bool' }])
  assert.match(html, /aria-label="price"/)
  assert.match(html, /value="false" data-value-type="boolean"/)
  assert.match(html, /<input/)
})

test('new estimate and review statuses have distinct Chinese meanings', () => {
  const body = descriptor.scriptSetup.content.match(/const testStatusText = computed\(\(\) => \{([\s\S]*?)\n\}\)/)[1]
  for (const [status, expected] of [
    ['CALCULATED', '金额测算完成（需审核）'],
    ['MANUAL_REVIEW', '需主管部门人工核实'],
    ['SUSPENDED', '该业务当前暂停办理'],
    ['INVALID_INPUT', '输入未通过校验']
  ]) {
    const text = vm.runInNewContext(`(() => { ${body} })()`, { testResult: { value: { status } } })
    assert.equal(text, expected)
  }
})
