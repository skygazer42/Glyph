"""Package discovery must work before application dependencies are loaded."""

import subprocess
import sys
from pathlib import Path


def test_package_imports_do_not_require_application_dependencies():
    source = """
import importlib

for name in (
    "app", "app.core", "app.config", "app.models", "app.schemas", "app.utils",
    "app.knowledge", "app.persistence", "app.persistence.crud", "app.agents",
    "app.agents.service", "app.agents.chatdb", "app.agents.dsl_generator",
    "app.agents.framework.common", "app.agents.framework.core",
):
    importlib.import_module(name)
"""
    result = subprocess.run(
        [sys.executable, "-E", "-S", "-c", source],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
