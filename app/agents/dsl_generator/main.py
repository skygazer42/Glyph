"""
Command-line interface for the DSL pipeline.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import typer

from app.agents.dsl_generator.pipeline import DSLPipeline
from app.agents.dsl_generator.rule_engine import PolicyEngine

app = typer.Typer(help="面向企业的 DSL 运维工具集。")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


@app.callback()
def global_options(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="输出更多调试日志"),
) -> None:
    """全局开关."""
    _configure_logging(verbose)
    ctx.obj = {"verbose": verbose}


def _build_pipeline(
    data_dir: Path,
    output_dir: Path,
    use_project_config: bool,
    use_llama_parser: bool,
    llama_reader_config: Optional[Dict[str, Any]],
) -> DSLPipeline:
    return DSLPipeline(
        data_dir=str(data_dir),
        output_dir=str(output_dir),
        use_project_config=use_project_config,
        use_llama_index_parser=use_llama_parser,
        llama_reader_kwargs=llama_reader_config,
    )


def _echo_result(payload: Dict[str, Any]) -> None:
    status = payload.get("status")
    typer.echo(f"[{status}] {payload.get('file')}")
    if payload.get("dsl_file"):
        typer.echo(f"  DSL: {payload['dsl_file']}")
    if payload.get("errors"):
        typer.echo(f"  Errors: {payload['errors']}")


def _load_inputs(payload: str) -> Dict[str, Any]:
    candidate = Path(payload)
    if candidate.exists():
        return json.loads(candidate.read_text(encoding="utf-8"))
    return json.loads(payload)


def _load_optional_json(payload: Optional[str]) -> Optional[Dict[str, Any]]:
    if payload is None:
        return None
    return _load_inputs(payload)


@app.command("document")
def process_document(
    path: Path = typer.Argument(..., exists=True, help="待转换的文档路径"),
    output_dir: Path = typer.Option(Path("rules"), "--output-dir", "-o", help="DSL 输出目录"),
    use_project_config: bool = typer.Option(False, "--use-project-config", help="启用 config.settings 中的 LLM 配置"),
    save: bool = typer.Option(True, "--save/--dry-run", help="是否落盘 DSL 文件"),
    use_llama_parser: bool = typer.Option(False, "--use-llama-parser/--no-use-llama-parser", help="使用 llama_index 读取文档"),
    llama_reader_config: Optional[str] = typer.Option(None, "--llama-reader-config", help="传递给 llama_index SimpleDirectoryReader 的 JSON 配置或文件路径"),
) -> None:
    """转换单个文档."""
    pipeline = _build_pipeline(
        path.parent,
        output_dir,
        use_project_config,
        use_llama_parser,
        _load_optional_json(llama_reader_config),
    )
    result = pipeline.process_document(str(path), save=save)
    _echo_result(result)


@app.command("directory")
def process_directory(
    source_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="需要批量转换的目录"),
    output_dir: Path = typer.Option(Path("rules"), "--output-dir", "-o", help="DSL 输出目录"),
    use_project_config: bool = typer.Option(False, "--use-project-config", help="启用 config.settings 中的 LLM 配置"),
    use_llama_parser: bool = typer.Option(False, "--use-llama-parser/--no-use-llama-parser", help="使用 llama_index 读取文档"),
    llama_reader_config: Optional[str] = typer.Option(None, "--llama-reader-config", help="传递给 llama_index SimpleDirectoryReader 的 JSON 配置或文件路径"),
) -> None:
    """批量转换目录下的所有文档."""
    pipeline = _build_pipeline(
        source_dir,
        output_dir,
        use_project_config,
        use_llama_parser,
        _load_optional_json(llama_reader_config),
    )
    results = pipeline.process_directory(str(source_dir))
    for item in results:
        _echo_result(item)


@app.command("test-rule")
def test_rule(
    rule_id: str = typer.Argument(..., help="要执行的规则 ID"),
    inputs: str = typer.Argument(..., help="JSON 字符串，或指向 JSON 文件的路径"),
    rule_dir: Path = typer.Option(Path("rules"), "--rule-dir", help="已生成 DSL 的目录"),
) -> None:
    """执行已有 DSL 规则并查看输出."""
    payload = _load_inputs(inputs)
    engine = PolicyEngine(rule_dir=str(rule_dir))
    result = engine.execute(rule_id, payload)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


# Backwards compatibility
DSLPipeline = DSLPipeline

__all__ = ["DSLPipeline", "app"]


if __name__ == "__main__":
    app()
