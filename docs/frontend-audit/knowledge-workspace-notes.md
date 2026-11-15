# 文档工作区实现记录

已授权原型：`.oil-ui/glyph-directions/round-09/modules/knowledge.html`。以四视图的清和浅白布局、信息层级和三栏切块为视觉基准，项目外壳沿用 WorkspaceLayout。

| 原型里的东西 | 项目里现成的 | 怎么做 |
| --- | --- | --- |
| 蓝色、正文、次级文字、分隔线、底色与圆角 | `--wb-blue/ink/muted/line/tint/surface/radius/font` | 用现成的 |
| 返回、原文件、分页、缩放、刷新、保存 | Element Plus Button、既有图标包 | 现成的加一个变体 |
| 四视图导航与键盘切换 | Element Plus Tabs | 现成的加一个变体 |
| 解析器、边界、页码和数值输入 | Element Plus Form、Select、InputNumber | 现成的加一个变体 |
| 原页预览、解析对照与来源信息 | 服务端 workspace 的实际页和正文 | 新建组件：KnowledgeDocumentWorkspace |
| 配置、切块列表、正文及重叠标记 | 服务端 chunks/preview；局部派生状态 | 新建组件：同一文档工作区内组合 |
| 索引方案、保存、解析、入库 | 现有 knowledgeApi 请求客户端 | 现成的加一个变体 |
| 不可用 OCR / 分级索引 | workspace capabilities | 用现成的：禁用控件并说明用途和能力限制 |
| 失败、进行中、未保存、空正文 | 局部页面状态、Element Plus 控件 | 现成的加一个变体 |
| 手机参数摘要、紧凑切块选择与原页对照 | 原生按钮、Element Plus Select / Checkbox | 现成的加一个变体 |

不新增依赖。实现文件限独立 SFC 与专属 CSS，不迁移原型样本、脚本或整段样式。

## 状态与交互计划

1. workspace 持有服务端事实；配置为当前文档的局部草稿；视图和页码由父组件路由 props 持有。
2. 文档切换取消只读请求并使用请求身份拒绝旧响应；写操作响应也核对文档身份。载入不触发解析或入库。
3. 首次进入切块调用服务端只读预览，配置改变即使旧预览失效；重新生成以旧块实际字符偏移维持阅读锚点。
4. 保存带 source_version 和 revision，成功后重读 workspace 核验；提交期间继续修改的草稿不被读回覆盖，失败保留草稿。
5. 解析和入库仅明确按钮触发；入库阻止重复提交与已入库提交，不自动重试。没有逐页映射时展示真实全文和说明。
6. 保留实际页面、来源与字符单位，不根据原型造页码、原始路径或 token 数量。
7. 手机切块预览成功后将配置折叠为可展开的参数摘要，并用既有 Select 紧凑选择实际切块；正文搜索、字符/来源/偏移/重叠信息仍保留。桌面维持配置、列表、正文三栏。

## 已采用规范

沿用项目 Vue 3 script setup、JavaScript 两空格/单引号/无分号、Element Plus、Axios 业务 API、`--wb-*` 变量。已读取并离线核验 VUE-007/008、STA-001/002、ASY-001/002、API-001、ERR-001/002 的包内固定 GitHub 原文。Vue 宏直接声明父子合同；派生筛选/统计由 computed 得到；草稿与服务器事实分离；过期成功/失败均不回写当前文档；成功反馈以服务端结果为准。

## 验证

- `npm run check`：通过，覆盖 Vue SFC、脚本/模板编译、CSS 语法与依赖清单一致性。项目没有配置 lint、typecheck 或语义静态分析器，未称其通过。
- `npm run build`：通过。保留项目既有大体积 bundle 警告，不在本任务扩展改构建配置。
- 使用已安装 Vue/compiler-sfc 运行 8 项隔离状态验证：初入切块只读预览、载入不触发解析/入库、配置变化立即失效、重切按字符锚点定位、旧文档/预览响应不覆盖、保存读回保留提交期间的新草稿、保存失败保留输入、Unicode overlap 与无映射页码、入库双版本参数和防重复/读回。8 项通过；这是响应式状态与 API stub 验证，不等同于真实后端或浏览器挂载测试。
- 浏览器并排核对、真实文件与真实接口回归由父任务统一执行；本子任务未独立声称视觉还原完成。
- 父任务的 [浏览器与真实接口回归结果](../../.oil-ui/knowledge-implementation/verification/result.json) 记录 `passed: true`、29 项检查通过、运行时异常为 0。覆盖手机原页适应宽度、解析正文优先且原页可展开、成功预览后折叠配置、紧凑切换真实切块、折叠后可展开编辑等实际行为。失败保存、部分导入配置和检索失败通过任务隔离请求验证；测试没有执行用户向量入库，不能据此声称真实向量服务可用。

## 命名核对

项目未安装 TypeScript 编译器，不新增工具依赖；逐项人工核对脚本声明、模板别名和 CSS 业务类。外部导入保持 Vue、Element Plus 图标包和 `knowledgeApi` 原名。命名先例取 `entity`/`collection`/`entity-id`、`state-predicate`、`read-view`、`load-action`、`input-handler`、`counter-update`、`display-label` 与 `listener-lifecycle`；仅采用角色表达，不移植原仓库的领域名词或架构层。

| 实际声明 | 业务含义与项目词依据 | 命名角色 |
| --- | --- | --- |
| props / emit / readingViews / configKeys | 父子约定、四视图与 processing-config 六个明确字段 | 公开合同 / collection |
| workspace / config / preview | workspace 服务端事实、局部方案草稿与服务端只读预览 | entity |
| loading / saving / parsing / embedding / previewLoading | 当前文档各请求的真实进行中状态 | state-predicate |
| loadError / saveError / previewError / operationError / saveMessage / operationMessage | 对应请求的失败与已确认结果文案 | display-label |
| chunkQuery / selectedChunkId / chunkListElement | 局部正文过滤、真实块身份与滚动容器节点 | entity-id / display-element |
| zoom / sourceInfoOpen / compareSource / imageError | 阅读缩放、来源展开、对照开关与图像失败 | state-predicate / entity |
| chunkConfigOpen | 当前文档切块配置的展开状态；新文档初始化为展开，服务端预览成功后设为收起，只在手机样式中折叠配置正文 | state-predicate |
| sourceTextSummary | 根据实际 `pages[].has_text/text` 与 `parsed.available` 派生的来源说明；明确区分原页可复制文字与已解析的处理正文 | read-view / display-label |
| documentGeneration / previewGeneration / loadController / previewController / readingAnchor | 文档/预览请求代次、取消句柄、实际字符偏移锚点 | counter-update / listener-lifecycle / entity |
| activeView / pages / currentPageIndex / currentPage / previousPage / nextPage | 路由视图与服务端页集合的派生读取 | read-view / collection |
| capabilities / formatLabel / exactPageMapping / parsedText / parserLabel | 返回能力与真实格式、正文映射、解析器展示 | read-view / display-label |
| configDirty / chunkConfigKey / configError / busy / canPreview / previewValid | 草稿与基线差异、字符参数身份、校验与真实版本一致性 | state-predicate / display-label |
| filteredChunks / selectedChunk / selectedChunkText / processingSteps | 从事实和查询派生的块集合、所选块、Unicode 分段、流程说明 | read-view / collection |
| navigate / selectChunk | 将控件输入映射为父页导航或真实块选择 | input-handler |
| selectChunkById / chunkId / item | 紧凑选择控件传入真实块 ID，在当前过滤集合查到对应块后复用 `selectChunk`；`item` 为这次局部查找中的块对象，不是位置序号 | input-handler / entity-id / entity |
| characterCount / formatBytes / formatDate / pageLabel / errorMessage | 字符数量、大小、时间、已知页与请求错误展示 | derived-count / display-label |
| timestamp | `formatDate` 中完成秒转毫秒后的日期输入值；数值 Unix 秒转换后交给 Date，ISO 字符串和毫秒数值保持兼容 | entity / display-label |
| assertSuccess / copyConfig / currentDocument | 确认接口结果、仅复制方案字段、核对文档代次和身份 | state-predicate / entity |
| readWorkspace / loadDocument / refreshDocument / generatePreview | 读取工作区、初始化、保留草稿刷新、生成服务端真实预览 | load-action |
| saveConfig / runDocumentOperation / parseDocument / embedDocument | CAS 写入、明确处理动作编排、既有 parse/embed API 合同 | 业务动作合同 |
| view / page / text / bytes / value / chunk / error / fallback / response / source / key / generation / docId / controller / sourcePage / step / parser / chunks | 每个函数/回调或模板局部参数均对应四视图、实际页、正文、大小、方案键、接口结果、请求代次或真实文档身份；没有把位置当持久 ID | 短作用域业务值 / entity / collection / entity-id |
| query / characters / overlap / date / detail / requestGeneration / previous / anchor / payload / anchored / selected / submitted / verified / latest / readError / operation / running / versions / previousDraft / preserveDraft | 局部过滤词、Unicode 数组、真实重叠、格式化值、请求错误、预览代次、旧/新块、实际字符锚点、传输字段、提交/读回快照、刷新保留条件和操作身份；语义与计算/副作用一致 | read-view / entity / state-predicate / load-action |

模板类名前缀统一 `kdw-`，只服务当前文档工作区；布局类按 source / parsed / chunks / index 与 pane / tools / text 等真实职责命名。没有 Controller/Store/Service 等新增架构角色。

手机新增的 `kdw-mobile-config-toggle` 表达展开配置动作，`kdw-chunk-config-form` 是被该按钮通过 `aria-controls` 指向的现有表单，`is-collapsed` 对应真实展开状态；`kdw-mobile-chunk-select` 是既有 Select 的手机容器，不创建另一份块选择事实。`--kdw-page-zoom` 仅传入 `zoom / 100` 的无单位比例：桌面与手机各自用现有阅读容器计算图像宽度，不保存第二份缩放值。`ArrowUp` / `ArrowDown` 直接沿用既有图标包的公开名称。

## 与原型的已知工程适配

- 外壳、字体和主题使用项目现有 `--wb-*`，不会拷贝原型 shell。
- 实际解析不保证逐页映射，因此明确展示完整正文与映射说明；原页仍可独立翻阅。
- OCR 和分级构建按真实能力禁用，说明用途与当前接口边界。
- 索引侧栏包含主动解析、入库与刷新状态操作；保存方案不自动执行。
- 不带原型政策样本、年份、地区、预估向量数、伪页码或 token 参数。

## 手机阅读与真实来源说明

- 原文初始和重置缩放仍为 100%。手机按阅读容器的可用宽度计算图像，默认两侧纸张边界可见；增大比例后保留横向滚动查看细节。桌面保留原来的 440px 基准。
- 解析正文位于 DOM 阅读顺序的前面；手机首次进入默认不勾选“对照原页”，勾选后在正文之后提供实际原页。桌面通过现有 Grid 保留原页左侧、正文右侧的并列关系。默认对照状态在组件初始化时判断，用户的后续选择保留；没有添加全局视口监听。
- 预览成功只将 `chunkConfigOpen` 设为收起，手机样式据此隐藏配置正文；桌面仍完整显示配置。手机保留参数摘要、完整正文搜索和匹配数量，现有 Select 使用真实块 ID 选择，选中块全文紧接其后；字符数、页码、偏移及重叠图例保持可达。
- 原文存在可复制文字而 `parsed.available` 为 false 时，来源说明为“原页含 N 字符的可复制文字；处理正文尚待解析”，入口为“核对解析方案”。只有已存在处理正文才提供“查看解析结果”，不以原页文字状态冒充解析成功。
- `modified` 的 Unix 秒数值转换后格式化，ISO `saved_at` 和毫秒数值保持兼容。秒、毫秒、ISO、0、无效时间输入的针对性验证与修复后的 `npm run check` 已通过。
- 解析版本变化会使旧预览失效，保留现有“重新生成预览”入口，没有将此分支改为自动重试。

网络错误文案修复：`errorMessage` 优先保留后端字符串 `detail/message`；Axios `ERR_NETWORK` 与完整的 `Network Error` / `NetworkError` 消息转换为“网络连接异常，当前输入已保留，请检查连接后重试。”；`ECONNABORTED` / `ETIMEDOUT` 使用调用方既有中文 fallback。业务 Error 消息与结构化 detail 的 fallback 行为保持原合同。9 项针对性错误文案验证及 `npm run check` 通过；根任务另行执行真实浏览器断网复验。没有新增状态、控件、命名或依赖。

## 写法与实际代码快照

以下 schemaVersion 2 证据单已使用包内 verify_evidence.py 验证 registryIntegrity、declaredMapping 和 codeBinding；这不代替业务语义审查。

```json
{
  "schemaVersion": 2,
  "profile": "Project Vue 3 script setup, JavaScript two spaces/single quotes/no semicolons, Element Plus, existing knowledgeApi and --wb-* theme.",
  "entries": [
    {
      "target": "KnowledgeDocumentWorkspace.vue#document-state-and-operations",
      "pattern": "Explicit Vue props/events; server facts separated from drafts and mobile disclosure state; computed projections and source copy; request identity and cancellation; confirmed writes retain in-flight edits and failures.",
      "rules": [
        "VUE-007",
        "VUE-008",
        "STA-001",
        "STA-002",
        "ASY-001",
        "ASY-002",
        "API-001",
        "ERR-001",
        "ERR-002"
      ],
      "evidence": [
        "GH-0a84f9d66236",
        "GH-0f7ef099b84d",
        "GH-10399a8dd8fe",
        "GH-4a69f98e7916",
        "GH-59986d4350fd",
        "GH-61004077a103",
        "GH-637f39d62266",
        "GH-7ae021267ab1",
        "GH-84eb502e0944",
        "GH-94ed95795b44",
        "GH-98d9378c63bd",
        "GH-9a665a51e565",
        "GH-a7ae1bb268f2",
        "GH-acf24c165a84",
        "GH-b448ddd3ea72",
        "GH-b63208846f39",
        "GH-b7cfa40bc504",
        "GH-c96b1f8ac83a",
        "GH-d517fbc5263f",
        "GH-edeb0a8f0e30",
        "GH-f4b588fb7c57"
      ],
      "code": [
        {
          "path": "web/src/components/knowledge/KnowledgeDocumentWorkspace.vue",
          "startLine": 179,
          "endLine": 522,
          "fileSha256": "f40459b550ab34d221390aa16a7375bd4a96b59d32d6cdc967bdf025b8a04887",
          "excerptSha256": "3aee71cf4d5f93635e03732cb61f38cd3a8a9045e7450bf07553ad3a236b5e92"
        }
      ]
    },
    {
      "target": "knowledge-workspace.css#component-layout-and-mobile-reading",
      "pattern": "Component-owned kdw namespace; role-based classes; existing Grid for desktop comparison and three panes, Flex for mobile reading order; mobile image scale and disclosure/select variants share the existing theme.",
      "rules": [
        "CSS-001",
        "CSS-002",
        "LAY-001"
      ],
      "evidence": [
        "GH-169648b4b126",
        "GH-cc48b8f7da80",
        "GH-df6bddfbd34e",
        "GH-fdbd965d81bc"
      ],
      "code": [
        {
          "path": "web/src/styles/knowledge-workspace.css",
          "startLine": 1,
          "endLine": 218,
          "fileSha256": "be5e9e2477f19229b9d34b668038414239cf8483c49dd51bd54176ad0d683d99",
          "excerptSha256": "be5e9e2477f19229b9d34b668038414239cf8483c49dd51bd54176ad0d683d99"
        }
      ]
    }
  ]
}
```
