# DSL Pipeline CLI

`scripts/dsl_ops.py` (或 `python -m agents.dsl_generator.main`) 提供了统一的企业级 DSL 运维入口，核心命令如下：

| 命令 | 说明 | 示例 |
| ---- | ---- | ---- |
| `document PATH` | 解析单个文档并生成 DSL | `python scripts/dsl_ops.py document data/guize/以旧换新.docx -o rules --use-llama-parser` |
| `directory DIR` | 批量处理目录下的所有文档 | `python scripts/dsl_ops.py directory data/guize -o rules --use-llama-parser --llama-reader-config llama_reader.json` |
| `test-rule RULE_ID INPUTS` | 执行已生成的 DSL 规则，`INPUTS` 可以是 JSON 字符串或文件路径 | `python scripts/dsl_ops.py test-rule Rule_济南_Appliance_2025 '{"price":5000,"energy_level":1,"category":"空调"}'` |

常用选项：

- `--output-dir/-o`：指定 DSL 输出目录，默认为 `rules`。
- `--use-project-config`：启用 `config.settings` 中定义的 LLM/环境配置。
- `--use-llama-parser/--no-use-llama-parser`：切换是否使用 `llama_index` 体系来提取文档。
- `--llama-reader-config`：通过 JSON 字符串或文件传入 `SimpleDirectoryReader` 的参数（如 `{"num_workers": 4}`）。
- `--save/--dry-run`：在 `document` 命令中控制是否落盘 DSL 文件。
- `--verbose/-v`：打印调试日志。

该 CLI 会自动调用 `agents.dsl_generator.pipeline.DSLPipeline`，并在 `test-rule` 命令中使用 `PolicyEngine` 对规则进行验证，输出完整的 JSON 结果与追踪信息，方便在 CI/CD 或运维脚本中对 DSL 生命周期进行管理。*** End Patch*** End Patch
