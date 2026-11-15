# 知识库导入组件实现记录

实现范围：`web/src/components/knowledge/KnowledgeImportDialog.vue`。父页保持组件实例，关闭弹窗只改变 `modelValue`。不新增依赖，不调用嵌入接口。

| 原型里的东西 | 项目里现成的 | 怎么做 |
| --- | --- | --- |
| 浅色蓝、正文、边框、圆角与字体 | `variables.css` 的 `--wb-*` | 用现成的 |
| 导入弹窗、关闭与焦点恢复 | 已装 Element Plus Dialog | 现成的加一个变体 |
| 多文件选择与拖放 | 已装 Element Plus Upload | 现成的加一个变体 |
| 解析、OCR、索引表单 | 已装 Element Plus Form / Select / Tooltip | 现成的加一个变体 |
| 文件状态、存储反馈与提交操作 | 已装 Button / Icon；现有 knowledgeApi | 新建组件 |

组件合同：`modelValue`、`documents`、`capabilities` 为输入；输出 `update:modelValue`、`uploaded(docId)`、`draft-change({count,savedAt})`。`count` 是本次任务中未完成的条目数，`savedAt` 仅来自校验成功的本地存储。

状态由每条文件独立持有。原始 File 只留在内存；草稿只保存文件元数据、处理选项和服务端已返回的 docId。刷新后未上传文件必须重新选择；保存配置或解析失败保留 docId，重试不会再次上传。上传依次执行，读取工作区后带 `source_version` / `config_revision` 保存配置。非 auto 解析在用户明确提交后应用；不调用 embed。

写法规约：沿用项目 Vue 3 script setup、无分号 JavaScript 和 `knowledgeApi` 返回 body 的合同。VUE-007/008 约束模板绑定与运行时 Props/Emits；STA-001/002 将文件事实与草稿就近持有、计数派生；ASY-001/002 清理离开/卸载防护并约束异步归属；API-001、ERR-001/002 复用请求客户端，并仅以实际响应显示完成。已阅读包内固定 GitHub 原文证据。业务标识符取自文件元数据、上传/工作区 API、组件事件和批准的导入流程；不引入 store/controller/service 层。

验证结果在实现完成后补充；尚未进行真实服务写入或与原型并排截图比较。

## 验证

- `npm run check`：通过，新组件的 script setup、模板与 scoped CSS 编译通过；项目没有单独配置 lint、typecheck 或语义静态分析入口。
- `npm run build`：通过；现有图谱与主包仍有 Vite 大包提示。最终父页接入后的构建由集成者再验证。
- 8 组隔离断言：直接执行实际 script setup，注入 Vue 响应式和 API mock，覆盖格式/空文件/体积/数量/重复过滤、存储抛错与读回不一致、刷新后元数据与 File 重选、保存配置失败仅续存、解析失败刷新后仅续解析、能力缺失与已有同名资料拒绝、处理中禁止关闭/移除/重复提交。全部通过，未向真实服务写入。
- `git diff --check`：通过（本组件与本说明范围）。未与原型并排核对，未进行真实浏览器挂载/键盘/窄屏实测或付费 MinerU 调用。

## 逐项命名核对

输入与事件名 `modelValue/documents/capabilities/update:modelValue/uploaded/draft-change` 保留父子合同。导入 `computed/markRaw/onBeforeUnmount/onMounted/reactive/ref/watch/onBeforeRouteLeave`、图标与 `knowledgeApi` 保留模块公开符号。没有新增结构角色或依赖。

| 声明 | 当前含义与项目依据 | 命名先例 / 适配 |
| --- | --- | --- |
| `DRAFT_KEY/MAX_FILES/MAX_BYTES/FILE_PATTERN` | 草稿键、20 份、50 MB、四种批准格式 | 当前需求里的稳定常量；没有引入另一个配置层 |
| `entries/options/uploadRef` | 文件清单事实、处理表单、Upload 引用 | collection/entity：同类文件集合与单个配置对象分开 |
| `busy/disposed/draftDirty/planLocked/capabilitiesReady/selectedParserAvailable` | 运行、生命周期、未保存修改、已有上传方案与实际能力条件 | state-predicate：每个名字对应无副作用布尔条件 |
| `formError/storageError/storageMessage/selectionIssues/batchMessage` | 表单、存储、文件选择、本次串行提交的反馈 | entity/collection/display-label：按反馈拥有者区分，不把失败变为空列表 |
| `savedAt/nextEntryId/requestController` | 严格读回成功的时间、本地条目递增身份、当前批次取消控制器 | entity-id/listener-lifecycle：本地身份与服务端 docId 不混用 |
| `visible/parsers/pendingEntries/completedCount/missingCount/submitLabel/savedTimeLabel` | 受控可见性与只读投影 | read-view/derived-count/display-label：从 props 与文件状态推导，不再建可写副本 |
| `normalizeName/formatBytes/parserLabel/statusLabel/errorMessage/fileValidationError/validateSubmission` | 名称匹配、字节显示、标签及前置校验结果 | parse-format/read-view/display-label/state-predicate：保持输入输出方向，名称不暗示网络写入 |
| `markDraftChanged/emitDraftSummary/serializeEntry/persistDraft/restoreDraft` | 标记修改、发数量与时间、元数据序列化、校验写入、读取恢复 | input-handler/load-action：动作名字对应真实副作用；restore 不重建 File |
| `existingDocument/addFile/removeEntry/saveTask/recordWorkspace/processEntry/submitFiles` | 同名查找、文件选择与移除、草稿保存、记录工作区响应、单条与串行批次 | read-view/input-handler/load-action/destructive-action：remove 仅移除本任务记录，不调用服务端删除 |
| `beforeClose/guardUnload` 及生命周期回调 | Dialog 关闭与页面离开防护 | listener-lifecycle/input-handler：复用组件库焦点与关闭机制，原生监听同函数清理 |
| 函数局部 `name/bytes/value/entry/document/parser/item/saved/draft/file/uploadFile/workspace/result/uploaded/form/signal/error/detail/event/done` | 明确作用域内的 API 实体、文件/表单、响应、取消信号、错误与回调参数 | entity/callback-value：词来自现有请求字段、File/Upload、Dialog 与生命周期合同；不把回调值和结果混用 |
| 函数局部 `timestamp/serialized/names/restored/docId/modified/done/matching/issue/invalidParser/prefix/batch/failed` | 序列化时间/字符串、恢复集合、服务端身份、匹配/校验与批次结果 | entity-id/collection/read-view/derived-count：区分持久身份、局部匹配与派生统计 |
| 记录字段 `id/name/size/modified/file/docId/phase/stage/configSaved/appliedParser/contentLength/error/resultText/options` | 原始 File 元数据、服务端确认事实及每条处理阶段 | File 与接口字段按现有语义适配；phase/stage 不表示虚构进度；临时正文摘要不写入草稿 |
| 模板别名 `entry/parser/issue/index` 与 `import-*/file-*/save-*/draft-*` 样式名 | 文件单项、能力选项、选择反馈与本组件区域 | entity/collection；DOM/CSS 只作用本组件，不改变共享布局 |

命名先例原文：[Grafana 集合与派生数量](https://github.com/grafana/grafana/blob/504e4f23f2ef579149d85da835f99e99372d69c7/public/app/features/teams/state/selectors.ts#L4-L31)、[Grafana 实体身份与动作](https://github.com/grafana/grafana/blob/504e4f23f2ef579149d85da835f99e99372d69c7/public/app/features/teams/state/actions.ts#L59-L90)、[VueUse 监听生命周期](https://github.com/vueuse/vueuse/blob/228371cf53dddcb5c639226e060a26fd8b7c41e2/packages/core/useEventListener/index.ts#L98-L124)、[VS Code 状态判断](https://github.com/microsoft/vscode/blob/1e446dfadf588ec28b3fdba7ac083bfa1d45df3c/src/vs/base/common/async.ts#L278-L280)。本项目未安装 TypeScript，未为声明清单工具新增依赖；命名表为人工核对，不宣称 AST 自动证明。

## 最终代码证据绑定

以下是文件快照与已核验规则的对应，不代表静态工具证明运行时正确。

```json
{
  "schemaVersion": 2,
  "profile": "沿用当前 Vue 3 script setup / JavaScript 无分号格式、Element Plus、knowledgeApi 和 --wb-* 变量；不改变项目工具链。",
  "entries": [
    {
      "target": "props/events 与顶层模板绑定",
      "pattern": "运行时宏声明与项目事件合同；可变默认值使用实例工厂。",
      "rules": [
        "VUE-007",
        "VUE-008"
      ],
      "evidence": [
        "GH-0f7ef099b84d",
        "GH-10399a8dd8fe",
        "GH-a7ae1bb268f2",
        "GH-acf24c165a84",
        "GH-b7cfa40bc504"
      ],
      "code": [
        {
          "path": "web/src/components/knowledge/KnowledgeImportDialog.vue",
          "startLine": 7,
          "endLine": 15,
          "fileSha256": "7de1d7bcc211385778c27952ccba0674a89eedfc327b508b4d4bc61288fac3e8",
          "excerptSha256": "2d132eb55b6f736966128ef1a91e04d417d0cfdf5dd895ce0de6e4d18504ccf3"
        }
      ]
    },
    {
      "target": "文件事实、局部草稿与派生数量",
      "pattern": "文件列表是单一来源；未完成条目、完成数量与缺失文件数从列表计算。",
      "rules": [
        "STA-001",
        "STA-002"
      ],
      "evidence": [
        "GH-0a84f9d66236",
        "GH-637f39d62266",
        "GH-84eb502e0944",
        "GH-b448ddd3ea72",
        "GH-d517fbc5263f"
      ],
      "code": [
        {
          "path": "web/src/components/knowledge/KnowledgeImportDialog.vue",
          "startLine": 18,
          "endLine": 47,
          "fileSha256": "7de1d7bcc211385778c27952ccba0674a89eedfc327b508b4d4bc61288fac3e8",
          "excerptSha256": "372fb47b2595cb50d9691d6a7a522a08f2b57112844e4a50ceb9d13ce675c674"
        }
      ]
    },
    {
      "target": "本地草稿的失败反馈",
      "pattern": "setItem 后读取原串严格比较，失败不置成功时间；原 File 和选项保留。",
      "rules": [
        "ERR-001",
        "ERR-002"
      ],
      "evidence": [
        "GH-59986d4350fd",
        "GH-7ae021267ab1",
        "GH-c96b1f8ac83a",
        "GH-f4b588fb7c57"
      ],
      "code": [
        {
          "path": "web/src/components/knowledge/KnowledgeImportDialog.vue",
          "startLine": 84,
          "endLine": 107,
          "fileSha256": "7de1d7bcc211385778c27952ccba0674a89eedfc327b508b4d4bc61288fac3e8",
          "excerptSha256": "ed959ac3a5bcbb0b60956abd190c2c2362332c8a4878f09f522556375bd4c6f5"
        }
      ]
    },
    {
      "target": "串行上传与分阶段重试",
      "pattern": "复用 knowledgeApi；上传确认后先保存 docId，再请求工作区与保存配置，解析失败保留已上传状态。 网络连接与超时错误转换为中文，保留服务器中文细节与参数数组解释。",
      "rules": [
        "API-001",
        "ERR-001",
        "ERR-002"
      ],
      "evidence": [
        "GH-59986d4350fd",
        "GH-61004077a103",
        "GH-7ae021267ab1",
        "GH-98d9378c63bd",
        "GH-b63208846f39",
        "GH-c96b1f8ac83a",
        "GH-f4b588fb7c57"
      ],
      "code": [
        {
          "path": "web/src/components/knowledge/KnowledgeImportDialog.vue",
          "startLine": 255,
          "endLine": 335,
          "fileSha256": "7de1d7bcc211385778c27952ccba0674a89eedfc327b508b4d4bc61288fac3e8",
          "excerptSha256": "973a10e3baa8702889937d60cf43581e84bc21e00f37a624bcb585d3d32816fa"
        }
      ]
    },
    {
      "target": "离开、卸载与请求生命周期",
      "pattern": "路由离开和 beforeunload 防护；卸载终止读取/解析链，移除同一个原生监听函数。",
      "rules": [
        "ASY-001",
        "ASY-002"
      ],
      "evidence": [
        "GH-4a69f98e7916",
        "GH-94ed95795b44",
        "GH-9a665a51e565",
        "GH-edeb0a8f0e30"
      ],
      "code": [
        {
          "path": "web/src/components/knowledge/KnowledgeImportDialog.vue",
          "startLine": 337,
          "endLine": 397,
          "fileSha256": "7de1d7bcc211385778c27952ccba0674a89eedfc327b508b4d4bc61288fac3e8",
          "excerptSha256": "634a9f3529fafe0fc8a12148bb4753549afe25924c9ef1107fa233e82f98fd92"
        }
      ]
    }
  ]
}
```

视觉复核修正：禁用 Select 的已选文本使用 `--wb-muted`，保留原禁用背景、边框与 disabled 语义；分级索引提示准确限定为“当前文档处理接口未开放分级构建”。该次仅检查组件 SFC/模板/样式编译与 diff，不重新执行生产构建。

错误反馈修正：`errorMessage` 将 `ERR_NETWORK` / `Network Error` 显示为“网络连接异常，请检查连接后重试”，将连接超时显示为“请求超时，请稍后重试”；中文服务端 detail、参数数组及条目阶段前缀保持原合同。未重新 build，由集成者统一验证。
