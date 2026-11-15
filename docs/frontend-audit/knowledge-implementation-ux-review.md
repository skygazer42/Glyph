# 正式知识库独立体验走查

日期：2026-11-15。模式：只读任务走查 / 开放探索；产品工作区，不打审美分。页面：`http://127.0.0.1:3001/knowledge`。视口：桌面 1440×900、手机 390×844。

## 产品理解与自主任务

这是给政策资料维护者使用的知识库工作区：导入原始文档，核对提取正文和来源，试切正文，再保存用于后续解析与入库的处理方案。页面将“保存方案”“解析”“入库”分别呈现。

我自主选择的主要任务是：导入一份自己的 TXT，确认原文与正文一致，调整切块参数，保存方案，并通过刷新核对真实保留结果。相关风险探针是：在手机视口模拟保存请求网络失败，检查修改是否保留、是否误报成功，以及能否直接重试。

结论：主要任务完成；所走路径未遇到卡住或走错。发现 1 项轻度恢复文案问题。没有观察到保存伪成功或已保存参数丢失。

## 实际操作路径与结果

| 步骤 | 看到什么 → 为什么这样操作 | 实际结果与证据 |
| --- | --- | --- |
| 从资料列表选择“导入资料” | 导入是从原始政策资料开始的明确主动作。 | 打开导入对话框；文件类型、大小上限和保存范围可见。[桌面入口](../../.oil-ui/knowledge-implementation/ux/01-desktop-entry.png)、[已选文件](../../.oil-ui/knowledge-implementation/ux/02-import-dialog.png) |
| 选择自己的 `glyph-ux-20261115-knowledge-walkthrough.txt`，点击“上传资料” | TXT 可直接读取，适合安全核对完整流程。 | 显示已完成、文档 ID、147 个正文字符和处理方案已保存。资料计数由 5 变为 6。[上传结果](../../.oil-ui/knowledge-implementation/ux/03-upload-result.png) |
| 展开“查看上传结果”，再从资料列表打开自己的文档 | 上传结果提示可在资料列表打开工作区，因此按该入口继续。 | 工作区显示正确文件名、410 B、1 页。原文预览完整显示自建的六行测试文字。[原文预览](../../.oil-ui/knowledge-implementation/ux/04-document-selected.png) |
| 查看解析结果，再查看本页切块 | 要核对提取正文与来源，再判断条款边界。 | 原始文本和解析正文并排；自建文字一致，显示 147 字符。切块预览有来源页与字符偏移。[正文对照](../../.oil-ui/knowledge-implementation/ux/05-parsed-text.png)、[默认切块](../../.oil-ui/knowledge-implementation/ux/07-chunk-default.png) |
| 将目标长度改为 120、重叠改为 15，生成预览并查看索引方案 | 当前参数可直接调整；先看预览，再确认方案。 | 显示 2 个预览块、119 字符的首块，索引方案标记“有未保存修改”。[自定义预览](../../.oil-ui/knowledge-implementation/ux/08-chunk-custom.png)、[待保存方案](../../.oil-ui/knowledge-implementation/ux/09-index-unsaved.png) |
| 保存方案，再刷新同一 URL | 核对“保存”是否真的持久化，而不只看反馈。 | 保存后显示“已保存并读回核对”。刷新仍处在同一文档索引页，保留 120/15 和保存时间。临时切块预览明确显示待更新，不冒充持久化结果。[保存成功](../../.oil-ui/knowledge-implementation/ux/10-plan-saved.png)、[刷新读回](../../.oil-ui/knowledge-implementation/ux/11-refresh-readback.png) |
| 切到 390×844，打开切块页并展开参数 | 手机上继续处理同一文档，检查能否找到参数与正文。 | 文件名换行可读，四步状态与 Tab 可见；参数默认折叠，切块使用紧凑选择。没有观察到该页面根宽超出 390 px。[手机索引页](../../.oil-ui/knowledge-implementation/ux/12-mobile-index.png)、[手机切块页](../../.oil-ui/knowledge-implementation/ux/13-mobile-chunk-top.png)、[展开参数](../../.oil-ui/knowledge-implementation/ux/14-mobile-chunk-edit.png) |
| 手机将参数改为 110/10，生成预览；仅在本次隔离浏览器阻断保存请求 | 方案调整紧接保存，网络失败最可能导致对保存状态的误判。 | 页面保留 110/10、同一文档、未保存状态和可重试的保存按钮；解析与入库按钮仍禁用。失败提示只有“Network Error”。[失败状态](../../.oil-ui/knowledge-implementation/ux/15-mobile-save-failed.png) |
| 解除网络阻断，直接重试保存，再刷新 | 检查不重新填写是否就能恢复，以及成功结果是否真实保留。 | 重试成功，错误消失；刷新仍保留 110/10 和 `2026/11/15 19:12:01` 保存时间。[重试成功](../../.oil-ui/knowledge-implementation/ux/16-mobile-save-retry.png)、[手机刷新读回](../../.oil-ui/knowledge-implementation/ux/17-mobile-refresh-readback.png) |

## 关键问题

### P3：保存失败反馈暴露英文网络错误，恢复动作需要用户自行推断

- **触发 / 位置**：手机索引方案页，调整参数后点击“保存处理方案”，隔离浏览器将该保存请求模拟为网络失败。
- **预期**：在保存按钮附近说明保存失败、修改仍保留，并给出可操作的重试指引。
- **观察事实 / 实际**：按钮下方保留“方案有修改，等待保存”，再显示红色英文 `Network Error`。当前参数 110/10 确实保留；同一按钮可重试，重试及刷新读回成功。[证据](../../.oil-ui/knowledge-implementation/ux/15-mobile-save-failed.png)
- **影响**：轻度犹豫。中文工作区的普通资料维护者需要自行理解英文错误，并判断下一步是否可以直接重试；未形成任务阻断或数据丢失。
- **原因推断**：可能将网络层错误原文直接用于用户反馈；未阅读实现源码，不能据此确认技术原因。
- **最小修复 / 完成标准**：保留现有状态和重试行为，将错误改成例如“保存失败，网络连接异常。修改已保留，请检查网络后重试。”在相同失败场景中，用户能就地理解保存结果与恢复办法。

## 应保留的做法

保存、解析和入库边界清楚；方案未保存时禁用后续处理。失败后保留修改，恢复网络后可直接重试；成功后有读回反馈，刷新也能核对相同参数和时间。

## 边界、清理与未验证项

- 只操作自建 TXT 的导入、预览和方案；没有对现有用户文件执行解析或入库，没有执行 embed、MinerU 或外部向量请求。浏览器还配置了对解析、入库和 embed 路径的阻断保护。
- 使用 skill 的 `scripts/chrome.mjs` 启动独立临时配置的 Chrome，通过 CDP 操作真实页面与取图；已关闭浏览器并由该工具清理临时 profile。没有读取产品业务源码或其他评审结论。截图为实际视口画面，没有进行自动截图 lint。
- 通过 `DELETE /api/knowledge/documents/glyph-ux-20261115-knowledge-walkthrough.txt` 删除且仅删除自建文档；服务返回 `success: true / 文档已删除`。随后列表 `total: 5`，自建文档已不存在。[清理证据](../../.oil-ui/knowledge-implementation/ux/cleanup-evidence.json)
- 未验证真实解析、实际入库、知识检索召回、多页 PDF/DOCX、批量上传、真机软键盘及触觉。上述能力受本轮安全范围限制，不作通过判断。
- 本轮是首轮只读诊断，未修改业务代码，未进入修正循环。
