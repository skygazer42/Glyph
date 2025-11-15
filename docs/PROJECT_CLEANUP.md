# 项目目录清理说明

## 清理概述

对项目根目录进行了清理,将测试和工具脚本移动到 `scripts/` 目录,保持根目录简洁。

## 清理前后对比

### 清理前 (根目录文件)

```
├── AGENTS.md
├── analyze_results.py          ← 测试分析脚本
├── api_server.py
├── check_env.py                ← 环境检查脚本
├── check_loggers.py            ← 日志检查脚本
├── CLAUDE.md
├── create_tables.py
├── docker-compose.yaml
├── .env
├── .env.example
├── .gitignore
├── pytest.ini
├── QUICKSTART.md
├── README.md
├── requirements.txt
└── test_early_stop.py          ← 测试脚本
```

### 清理后 (根目录文件)

```
├── AGENTS.md                   ← Agent 说明文档
├── api_server.py               ← 主服务器入口
├── CLAUDE.md                   ← Claude 使用说明
├── create_tables.py            ← 数据库初始化脚本
├── docker-compose.yaml         ← Docker 配置
├── Dockerfile                  ← Docker 镜像构建
├── .env.example                ← 环境变量示例
├── .gitignore                  ← Git 忽略规则
├── pytest.ini                  ← Pytest 配置
├── QUICKSTART.md               ← 快速开始文档
├── README.md                   ← 主文档
└── requirements.txt            ← Python 依赖
```

**结果**: 根目录更加清爽,只保留核心配置和入口文件!

## 移动的文件

已移动到 `scripts/` 目录:

| 文件 | 原位置 | 新位置 | 用途 |
|------|--------|--------|------|
| `analyze_results.py` | 根目录 | `scripts/` | 分析测试结果 |
| `check_env.py` | 根目录 | `scripts/` | 检查环境变量 |
| `check_loggers.py` | 根目录 | `scripts/` | 检查日志配置 |

## 保留在根目录的文件

### 必要的启动文件

1. **api_server.py** - FastAPI 服务器主入口
   ```bash
   python api_server.py
   ```

2. **create_tables.py** - 数据库表初始化
   ```bash
   python create_tables.py
   ```

### 配置文件

1. **docker-compose.yaml** - Docker 编排配置
2. **Dockerfile** - Docker 镜像构建
3. **requirements.txt** - Python 依赖管理
4. **.env.example** - 环境变量模板
5. **pytest.ini** - 测试配置

### 文档文件

1. **README.md** - 主文档
2. **QUICKSTART.md** - 快速开始
3. **AGENTS.md** - Agent 说明
4. **CLAUDE.md** - Claude 使用说明

## .gitignore 更新

新增了以下忽略规则:

```gitignore
# 测试结果文件
test_results*.json
test_results*.md
analyze_results.py
test_*.py
!tests/**/*.py  # 保留 tests 目录下的测试文件

# 临时测试脚本
check_*.py
test_early_stop.py
```

这些规则确保:
- ✅ 测试结果文件不会被提交
- ✅ 临时测试脚本不会被提交
- ✅ 但保留 `tests/` 目录下的正式测试文件

## 目录结构优化

### 推荐的目录组织

```
Glyph/
├── app/                        # 应用源码
│   ├── agents/                 # Agent 实现
│   ├── api/                    # API 端点
│   ├── core/                   # 核心功能
│   ├── models/                 # 数据模型
│   └── ...
├── scripts/                    # 工具脚本 ✨
│   ├── analyze_results.py      # 测试分析
│   ├── check_env.py            # 环境检查
│   ├── check_loggers.py        # 日志检查
│   ├── embed_documents.py      # 文档嵌入
│   ├── ingest_policy_docs.py   # 数据导入
│   └── ...
├── tests/                      # 单元测试
├── docs/                       # 详细文档
├── resources/                  # 资源文件
│   ├── data/                   # 数据文件
│   ├── dsl/                    # DSL 规则
│   └── ...
├── api_server.py               # 主入口 ✨
├── create_tables.py            # 数据库初始化 ✨
├── docker-compose.yaml         # Docker 配置 ✨
├── requirements.txt            # 依赖清单 ✨
└── README.md                   # 主文档 ✨
```

## 使用指南

### 运行主服务

```bash
# 直接运行
python api_server.py

# 或使用 Docker
docker-compose up -d
```

### 使用工具脚本

所有工具脚本都在 `scripts/` 目录:

```bash
# 检查环境配置
python scripts/check_env.py

# 分析测试结果
python scripts/analyze_results.py test_results.json

# 检查日志配置
python scripts/check_loggers.py

# 导入政策文档
python scripts/ingest_policy_docs.py --source resources/data/process

# 嵌入文档
python scripts/embed_documents.py

# 注册 Text2SQL 连接
python scripts/register_text2sql_connection.py
```

### 初始化数据库

```bash
# 创建数据库表
python create_tables.py
```

## 清理的好处

### 1. 更清晰的项目结构 ✨

**优点**:
- 新用户一眼就能看到核心文件
- 减少根目录的混乱
- 更专业的项目组织

**效果**:
```
根目录文件数量: 15+ → 12
测试/工具文件: 根目录 → scripts/
```

### 2. 更好的版本控制 🔧

**优点**:
- `.gitignore` 明确忽略测试文件
- 避免提交临时测试脚本
- 保持仓库整洁

### 3. 更易于维护 📚

**优点**:
- 工具脚本集中管理
- 测试脚本易于查找
- 文档结构清晰

### 4. 更符合最佳实践 ⭐

遵循 Python 项目标准结构:
- ✅ 根目录只放核心文件
- ✅ 脚本放在 `scripts/` 或 `bin/`
- ✅ 测试放在 `tests/`
- ✅ 文档放在 `docs/`

## 迁移指南

如果你有脚本引用了旧位置的文件,需要更新路径:

### 更新引用

**旧路径**:
```python
# 之前
import analyze_results
from check_env import check_mysql_vars
```

**新路径**:
```python
# 现在
import scripts.analyze_results
from scripts.check_env import check_mysql_vars
```

或使用相对导入:
```python
import sys
sys.path.insert(0, 'scripts')
import analyze_results
```

### 更新 shell 脚本

**旧命令**:
```bash
python analyze_results.py test_results.json
```

**新命令**:
```bash
python scripts/analyze_results.py test_results.json
```

## 进一步优化建议

### 1. 创建 Makefile

简化常用命令:

```makefile
# Makefile
.PHONY: run test clean install

run:
	python api_server.py

test:
	pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

install:
	pip install -r requirements.txt

init-db:
	python create_tables.py

check-env:
	python scripts/check_env.py
```

使用:
```bash
make run        # 运行服务器
make test       # 运行测试
make clean      # 清理临时文件
make install    # 安装依赖
make init-db    # 初始化数据库
make check-env  # 检查环境
```

### 2. 添加 setup.py

使项目可安装:

```python
# setup.py
from setuptools import setup, find_packages

setup(
    name="glyph",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open('requirements.txt')
        if line.strip() and not line.startswith('#')
    ],
    entry_points={
        'console_scripts': [
            'glyph-server=api_server:main',
            'glyph-init-db=create_tables:main',
        ],
    },
)
```

安装后可以直接使用:
```bash
pip install -e .
glyph-server    # 运行服务器
glyph-init-db   # 初始化数据库
```

### 3. 添加 .dockerignore

优化 Docker 构建:

```dockerignore
# .dockerignore
__pycache__/
*.py[cod]
*$py.class
.git/
.gitignore
.venv/
venv/
.vscode/
.idea/
*.md
tests/
docs/
scripts/
resources/data/lightrag/
resources/data/milvus/
*.log
test_results*
```

### 4. 添加 scripts/README.md

说明各个脚本的用途:

```markdown
# Scripts 目录

## 工具脚本说明

| 脚本 | 用途 | 示例 |
|------|------|------|
| analyze_results.py | 分析测试结果 | `python scripts/analyze_results.py test.json` |
| check_env.py | 检查环境变量 | `python scripts/check_env.py` |
| check_loggers.py | 检查日志配置 | `python scripts/check_loggers.py` |
| embed_documents.py | 嵌入文档 | `python scripts/embed_documents.py` |
| ingest_policy_docs.py | 导入政策文档 | `python scripts/ingest_policy_docs.py` |

## 使用方式

所有脚本都在项目根目录运行:

\`\`\`bash
cd /path/to/Glyph
python scripts/<script_name>.py [args]
\`\`\`
```

## 总结

通过这次清理:

✅ **根目录更清爽**: 从 15+ 文件减少到 12 个核心文件
✅ **结构更清晰**: 工具脚本集中在 `scripts/` 目录
✅ **更易维护**: 文件分类明确,易于查找
✅ **更专业**: 符合 Python 项目最佳实践
✅ **更易协作**: 新成员能快速理解项目结构

项目现在拥有清晰、专业、易于维护的目录结构! 🎉
