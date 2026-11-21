import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { createRequire } from 'node:module'
import { fileURLToPath } from 'node:url'
import { relative, resolve } from 'node:path'

const web = fileURLToPath(new URL('../', import.meta.url))
const workspace = resolve(web, '..')
const require = createRequire(resolve(web, 'package.json'))
const { parse, compileScript, compileTemplate, compileStyle } = require('@vue/compiler-sfc')
const { parse: parseJavaScript } = require('@babel/parser')
const { parse: parseHtml } = require('@vue/compiler-dom')
const postcss = require('postcss')
const sourceFiles = []

function collect(directory) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) {
      collect(path)
    } else {
      sourceFiles.push(path)
    }
  }
}
collect(resolve(web, 'src'))
collect(resolve(web, 'scripts'))
sourceFiles.push(resolve(web, 'vite.config.js'), resolve(web, 'index.html'))
sourceFiles.sort()

const counts = {
  vue: 0,
  applicationJavaScript: 0,
  configJavaScript: 0,
  toolingJavaScript: 0,
  css: 0,
  html: 0,
  svg: 0,
  sfcStyleBlocks: 0,
  packageJson: 1,
  lockJson: 1
}
const checked = []
for (const path of sourceFiles) {
  const source = readFileSync(path, 'utf8')
  const filename = relative(workspace, path).replaceAll('\\', '/')
  if (path.endsWith('.vue')) {
    const { descriptor, errors } = parse(source, { filename })
    assert.equal(errors.length, 0, `${filename}: SFC parse ${errors}`)
    const script = compileScript(descriptor, { id: filename })
    parseJavaScript(script.content, { sourceType: 'module' })
    const template = compileTemplate({
      filename,
      id: filename,
      source: descriptor.template.content,
      compilerOptions: { bindingMetadata: script.bindings }
    })
    assert.equal(template.errors.length, 0, `${filename}: template ${template.errors}`)
    parseJavaScript(template.code, { sourceType: 'module' })
    for (const style of descriptor.styles) {
      assert.ok(!style.lang || style.lang === 'css', `${filename}: unsupported style language ${style.lang}`)
      postcss.parse(style.content, { from: filename })
      const result = compileStyle({
        filename,
        id: 'data-v-static-check',
        source: style.content,
        scoped: style.scoped
      })
      assert.equal(result.errors.length, 0, `${filename}: style ${result.errors}`)
      counts.sfcStyleBlocks++
    }
    counts.vue++
  } else if (path.endsWith('.js') || path.endsWith('.mjs')) {
    parseJavaScript(source, { sourceType: 'module' })
    if (path === resolve(web, 'vite.config.js')) {
      counts.configJavaScript++
    } else if (path.endsWith('.mjs')) {
      counts.toolingJavaScript++
    } else {
      counts.applicationJavaScript++
    }
  } else if (path.endsWith('.css')) {
    postcss.parse(source, { from: filename })
    counts.css++
  } else if (path.endsWith('.html') || path.endsWith('.svg')) {
    const errors = []
    parseHtml(source, { onError: error => errors.push(error) })
    assert.equal(errors.length, 0, `${filename}: markup parser ${errors}`)
    if (path.endsWith('.svg')) {
      counts.svg++
    } else {
      counts.html++
    }
  } else {
    throw new Error(`Maintained source is not covered by a parser: ${filename}`)
  }
  checked.push(filename)
}

const manifest = JSON.parse(readFileSync(resolve(web, 'package.json'), 'utf8'))
const lock = JSON.parse(readFileSync(resolve(web, 'package-lock.json'), 'utf8'))
assert.ok(lock.packages?.[''], 'Package lock must describe the root package')
assert.equal(lock.name, manifest.name)
assert.equal(lock.version, manifest.version)
assert.equal(lock.packages[''].name, manifest.name)
assert.equal(lock.packages[''].version, manifest.version)
for (const field of ['dependencies', 'devDependencies', 'optionalDependencies', 'engines']) {
  assert.deepEqual(lock.packages[''][field] ?? {}, manifest[field] ?? {}, `package/lock ${field} specifications differ`)
}
console.log(JSON.stringify({
  result: 'passed',
  counts,
  maintainedSourceFiles: checked.length,
  checked,
  packageLockConsistency: 'root name/version, dependency specifications and engines match',
  limits: [
    'Static syntax and Vue compilation checks; no configured lint, typecheck, or semantic static analyzer is present.',
    'PostCSS parses syntax and Vue scoped-style compilation; this does not validate browser CSS support, computed styles, accessibility, or layout.',
    'HTML and SVG are parsed with the installed Vue DOM parser; this is not a full HTML or SVG conformance validator.',
    'Package/lock checks compare root package declarations; they do not audit transitive dependencies or prove installed package integrity.',
    'No browser mount, external API calls, runtime behavior, or backend files are exercised by this script.',
    'Generated node_modules, dist, and .vite caches are intentionally excluded.'
  ]
}, null, 2))
