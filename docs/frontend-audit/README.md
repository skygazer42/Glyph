# 全部前端逐行与写法审核

按指定的 frontend-coding-guidelines 1.6.0，主智能体与2个现有子智能体已复核 `F:/Glyph/web` 全部37个维护文件。重点是标准写法、规范命名与表达，保留必要边界防护。当前采用的适用规则没有已知未修复违反。

人工逐行覆盖36文件、9736行，包含保留的模板、脚本、样式和配置；另核对生成锁文件2910行的完整JSON结构、根声明及212个非根依赖对象。全部37文件均有完整范围与最终哈希。审核累计修改36个原有文件，新增1个包内检查脚本；前一写法专项调整17文件；本次继续查漏修改6文件，其余31文件核对保留。

## 当前证据

- [全文件覆盖及137条规则逐区判断](F:/Glyph/docs/frontend-audit/line-review.json)：基础层17文件、组件15文件、页面5文件；按实际合同区分适用、项目取舍和不适用。
- [写法证据单](F:/Glyph/docs/frontend-audit/writing-evidence.json)：385条具体模式、48条实际采用规则、109条固定原文证据、466段当前代码；skill官方核对器通过。
- [逐标识符记录](F:/Glyph/docs/frontend-audit/identifier-review.json)：277项记录、287段代码；本次39个新增声明逐项核对含义、项目词汇、先例与作用域。
- [本次基础复核](F:/Glyph/docs/frontend-audit/continuation-core.json)、[组件复核](F:/Glyph/docs/frontend-audit/continuation-components.json)、[页面复核](F:/Glyph/docs/frontend-audit/continuation-views.json)、[交叉复核](F:/Glyph/docs/frontend-audit/continuation-cross-review.md)。
- 历史阶段：[基础写法复核](F:/Glyph/docs/frontend-audit/writing-pass-core.json)、[组件写法复核](F:/Glyph/docs/frontend-audit/writing-pass-components.json)、[页面写法复核](F:/Glyph/docs/frontend-audit/writing-pass-views.json)。
- [文件清单](F:/Glyph/docs/frontend-audit/file-manifest.json)、[验证结果](F:/Glyph/docs/frontend-audit/validation.json)、[构建合同依据](F:/Glyph/docs/frontend-audit/build-contract-evidence.json)。

## 每文件写法结论

下表汇总既有写法专项；“保留”同样经过完整阅读与适用规范复核。本次继续查漏的6文件另列于下。

| 文件 | 本轮 | 写法修正或保留依据 |
| --- | --- | --- |
| [web/Dockerfile](F:/Glyph/web/Dockerfile) | 保留 | 构建步骤直接表达阶段职责；check 在 build 前执行。 |
| [web/index.html](F:/Glyph/web/index.html) | 保留 | HTML 双引号、2 空格层级，保留入口合同。 |
| [web/nginx.conf](F:/Glyph/web/nginx.conf) | 保留 | 统一层级缩进及声明分号，保留指令和变量合同。 |
| [web/package-lock.json](F:/Glyph/web/package-lock.json) | 保留 | 保留生成格式；完整结构、根声明和212个非根依赖对象分别核对。 |
| [web/package.json](F:/Glyph/web/package.json) | 保留 | 明确 ESM、Node 范围与包内 check；沿用 npm 字段名。 |
| [web/scripts/check.mjs](F:/Glyph/web/scripts/check.mjs) | 保留 | 具名递归收集、const 绑定、完整控制块及按语言检查。 |
| [web/src/App.vue](F:/Glyph/web/src/App.vue) | 调整 | 多属性逐行、CSS 列表分行，删除复述导航动作的注释。 |
| [web/src/api/index.js](F:/Glyph/web/src/api/index.js) | 保留 | 按传输字段解构，参数默认值与字符串/数组数量条件明确。 |
| [web/src/api/request.js](F:/Glyph/web/src/api/request.js) | 保留 | 响应与重试配置解构、完整分支；保留必要取消清理边界。 |
| [web/src/components/AppFooter.vue](F:/Glyph/web/src/components/AppFooter.vue) | 保留 | 保留清楚的计算属性、语义布局与逐声明 CSS。 |
| [web/src/components/BackToTop.vue](F:/Glyph/web/src/components/BackToTop.vue) | 保留 | 保留具名滚动动作与单一监听所有者。 |
| [web/src/components/BreadcrumbNav.vue](F:/Glyph/web/src/components/BreadcrumbNav.vue) | 调整 | 多属性分行；路径与 crumbs 保持局部计算。 |
| [web/src/components/CodeEditor.vue](F:/Glyph/web/src/components/CodeEditor.vue) | 调整 | 多属性分行；已声明字符串显式判断空值。 |
| [web/src/components/EmptyState.vue](F:/Glyph/web/src/components/EmptyState.vue) | 调整 | 多属性分行，保留简单状态映射。 |
| [web/src/components/FileUploader.vue](F:/Glyph/web/src/components/FileUploader.vue) | 调整 | 多属性分行，成功/失败与文件大小早退写完整块。 |
| [web/src/components/MobileMenu.vue](F:/Glyph/web/src/components/MobileMenu.vue) | 调整 | 多属性分行，保留既有公开主题与导航合同。 |
| [web/src/components/QuickNav.vue](F:/Glyph/web/src/components/QuickNav.vue) | 调整 | 多属性分行，保留简单链接数据与布局。 |
| [web/src/components/SearchBar.vue](F:/Glyph/web/src/components/SearchBar.vue) | 调整 | 多属性分行、完整搜索守卫、明确空查询条件。 |
| [web/src/components/SessionManager.vue](F:/Glyph/web/src/components/SessionManager.vue) | 调整 | 多属性分行、完整早退块、明确字符串草稿条件。 |
| [web/src/components/SkeletonLoader.vue](F:/Glyph/web/src/components/SkeletonLoader.vue) | 调整 | 多属性分行，保留清楚的数量及组件属性合同。 |
| [web/src/components/SystemAnnouncement.vue](F:/Glyph/web/src/components/SystemAnnouncement.vue) | 调整 | 多属性分行，保留局部阅读状态及存储边界。 |
| [web/src/components/Text2SQLResult.vue](F:/Glyph/web/src/components/Text2SQLResult.vue) | 调整 | 完整计算分支、显式零值判断，删除重复的零值回退。 |
| [web/src/components/ThemeToggle.vue](F:/Glyph/web/src/components/ThemeToggle.vue) | 调整 | 多属性分行，复用计算后的动作名称。 |
| [web/src/components/index.js](F:/Glyph/web/src/components/index.js) | 保留 | 保留三个真实出口，不增加转发层。 |
| [web/src/composables/useLocalStorage.js](F:/Glyph/web/src/composables/useLocalStorage.js) | 保留 | 按实际重绑定选择 const/let；保留缓存边界与共享事实。 |
| [web/src/composables/useTheme.js](F:/Glyph/web/src/composables/useTheme.js) | 保留 | 共享事实与消费者监听分工清楚；保留短作用域可读名称。 |
| [web/src/main.js](F:/Glyph/web/src/main.js) | 保留 | 解构注册键值，for..of 表达副作用，不引入 wrapper。 |
| [web/src/router/index.js](F:/Glyph/web/src/router/index.js) | 保留 | 路由数据共置、直接导出实例，保留公开路由名。 |
| [web/src/stores/app.js](F:/Glyph/web/src/stores/app.js) | 保留 | ref/computed 与具名动作分工明确，定时器确需 let。 |
| [web/src/styles/global.css](F:/Glyph/web/src/styles/global.css) | 保留 | 全局覆盖职责明确，列表分行、块缩进与声明分号统一。 |
| [web/src/styles/variables.css](F:/Glyph/web/src/styles/variables.css) | 保留 | 按用途共置 token，复合值分行，主题值不变。 |
| [web/src/views/AgentChat.vue](F:/Glyph/web/src/views/AgentChat.vue) | 调整 | 字符串长度显式判断、稳定字段解构/简写，引用与会话名称明确。 |
| [web/src/views/DSLGenerator.vue](F:/Glyph/web/src/views/DSLGenerator.vue) | 调整 | 筛选使用 const 和早返回；输入与查询条件表达空字符串。 |
| [web/src/views/HomePage.vue](F:/Glyph/web/src/views/HomePage.vue) | 保留 | 现有声明、简单模板表达式、属性及 CSS 排版符合选定规范。 |
| [web/src/views/KnowledgeBase.vue](F:/Glyph/web/src/views/KnowledgeBase.vue) | 调整 | 筛选 const/早返回，文档、统计、上传索引与分页参数按职责命名。 |
| [web/src/views/KnowledgeGraph.vue](F:/Glyph/web/src/views/KnowledgeGraph.vue) | 调整 | nextLayer 表达遍历层，tooltip 解构重复读取，hop 事件使用具名处理器。 |
| [web/vite.config.js](F:/Glyph/web/vite.config.js) | 保留 | 原生 ESM 导入和跨平台别名路径，配置对象保持直接。 |

## 本次继续查漏

两个现有子智能体分别完整复核15个组件层文件和5个页面，主智能体复核17个基础文件。新增13条写法证据及39个声明命名记录；删除7个脚本整对象绑定、迁出1个模板回调参数，其中4条旧命名记录已退役，不将删除变量绑定到其他代码。

| 文件 | 本次修正 |
| --- | --- |
| [web/src/components/BreadcrumbNav.vue](F:/Glyph/web/src/components/BreadcrumbNav.vue) | 在computed现有分支内解构title/icon并使用属性简写，保持路由响应式读取。 |
| [web/src/components/FileUploader.vue](F:/Glyph/web/src/components/FileUploader.vue) | 待完成UID守卫之后解构uid/name/size，上传记录使用属性简写，事件继续传原始file。 |
| [web/src/views/AgentChat.vue](F:/Glyph/web/src/views/AgentChat.vue) | 引用和路由元数据按稳定字段解构；流式/非流式结果在原请求身份守卫后解构，保留真值分支及消息结构。 |
| [web/src/views/DSLGenerator.vue](F:/Glyph/web/src/views/DSLGenerator.vue) | 双守卫后解构生成结果及规则字段；上传事件参数解构，保留text真值判断及赋值顺序。 |
| [web/src/views/KnowledgeBase.vue](F:/Glyph/web/src/views/KnowledgeBase.vue) | 上传事件解构response/file；具名百分比formatter承担原模板计算，输出舍入保持。 |
| [web/src/views/KnowledgeGraph.vue](F:/Glyph/web/src/views/KnowledgeGraph.vue) | computed内部解构统计；规范化边端点和节点选项局部解构及属性简写；保留原始图输入兼容归一化。 |

全部23个变化摘录核对原职责，7个自动映射范围手工缩窄；其余位移摘录先验证原始字节和旧摘录一致。新增声明的Babel绑定清单按真实行/列核对，逐文件声明数量差额也与39新增、7删除相符。规则推荐项保留理由见各分区报告，未把所有属性访问机械改为解构。

最终62项回归、check、静态入口、生产构建、官方来源/代码绑定及全记录校验均通过；另对照1001个滑块输入输出、引用/路由样例和统计computed替换响应性。全部Vue样式保持原字节。继续保留既有大chunk提示与下述运行验证边界。

## 验证与范围

62项现有回归全部通过：基础14、组件19、页面29；Node顶层TAP为16项，两个runner分别含组件与页面用例。`npm run check`、审计静态入口、生产构建及作用域diff空白检查通过。构建转换2299模块，保留原有大于500kB的chunk提示。没有新增依赖、提交或部署。

纯排版已对照修改前快照：App渲染及脚本AST不变、CSS选择器/声明/值/顺序不变；组件14个样式块原字节不变，页面CSS非空行不变。字符串判断、解构及重命名逐项复核，不把AST相等或测试通过当作写法审查的替代。

证据迁移先校验旧文件与摘录哈希，再按忽略空白的token顺序映射，随后核对真实职责。补齐或缩窄20条旧记录，另退役2条无法以当前摘录证明的历史删除记录；其中一条原误绑表单标签规则到应用挂载ID，已移出当前证据。最终位置以统一写法和命名记录为准。旧阶段JSON明确标为 historicalOnly，并保留各自快照身份；前一写法阶段的当前绑定冻结到continuation-before.json，不刷新更早阶段的历史依据。

上一轮实际浏览器验证过Enter导航、app-main返回顶部、禁用上传、能力限制通知、Tab/Shift+Tab、可见焦点和方向键选项卡。截图：[交互](F:/Glyph/docs/frontend-audit/line-review-browser.jpg)、[键盘](F:/Glyph/docs/frontend-audit/keyboard-review-browser.png)。写法专项及本次继续查漏均未重跑浏览器。

静态检查是语法解析、Vue/SFC与样式编译，不等同于未配置的ESLint或TypeScript检查。人工阅读与代码哈希也不是程序语义的形式化证明。真实后端成功链路、Docker/nginx与Node18运行环境未验证。node_modules、dist、.vite及第三方实现不属于自有源码范围；并发的后端/Python改动未触碰。

```powershell
node --test docs/frontend-audit/core-regression.test.mjs docs/frontend-audit/components-regression.test.mjs docs/frontend-audit/views-regression.test.mjs
node docs/frontend-audit/static-validation.mjs
cd F:/Glyph/web
npm run check
npm run build
python -X utf8 C:/Users/luke/.codex/skills/frontend-coding-guidelines/references/evidence/verify_evidence.py --workspace F:/Glyph --ledger F:/Glyph/docs/frontend-audit/writing-evidence.json
```
