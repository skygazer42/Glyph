@echo off
REM Glyph Windows 初始化脚本
REM Initialize the local knowledge base using DashScope embeddings by default.
REM Steps:
REM   1. Create database tables (ORM metadata, chat history, etc.)
REM   2. Seed MySQL/Text2SQL policy data
REM   3. Sync Text2SQL schema metadata (SchemaTable/SchemaColumn/SchemaRelationship)
REM   4. Ensure Milvus collection exists
REM   5. Build LlamaIndex hierarchical index from resources/data/process
REM   6. Embed the same documents into Milvus
REM   7. Seed LightRAG (optional; skip automatically if dependencies are missing)

setlocal enabledelayedexpansion

echo ========================================
echo Glyph Windows 初始化脚本
echo ========================================
echo.

REM 获取脚本所在目录的父目录
set "ROOT_DIR=%~dp0.."
cd /d "%ROOT_DIR%"

echo 当前工作目录: %CD%
echo.

REM 检查Python是否可用
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] Python未安装或不在PATH中
    echo 请安装Python 3.9+并添加到PATH
    pause
    exit /b 1
)

REM 检查是否存在.env文件
if not exist ".env" (
    echo [警告] 未找到.env文件
    echo 正在从.env.example创建...
    if exist ".env.example" (
        copy ".env.example" ".env" >nul
        echo [成功] 已创建.env文件
        echo.
        echo [重要] 请编辑.env文件，填入必要的API Keys：
        echo   - LLM_API_KEY
        echo   - EMBEDDING_DASHSCOPE_API_KEY
        echo   - VISION__API_KEY (可选)
        echo.
        echo 编辑完成后按任意键继续...
        pause >nul
    ) else (
        echo [错误] 未找到.env.example文件
        pause
        exit /b 1
    )
)

echo 开始初始化数据...
echo.

echo 步骤 1/7: 创建数据库表
python scripts\1_create_tables.py
if errorlevel 1 (
    echo [错误] 数据库表创建失败
    pause
    exit /b 1
)
echo [完成] 数据库表创建成功
echo.

echo 步骤 2/7: 初始化MySQL数据
python scripts\2_seed_mysql_text2sql.py
if errorlevel 1 (
    echo [警告] MySQL数据初始化失败，请检查数据库连接
) else (
    echo [完成] MySQL数据初始化成功
)
echo.

echo 步骤 3/7: 同步Text2SQL模式
python scripts\7_sync_text2sql_schema.py
if errorlevel 1 (
    echo [警告] Text2SQL模式同步失败
) else (
    echo [完成] Text2SQL模式同步成功
)
echo.

echo 步骤 4/7: 初始化Milvus集合
python scripts\3_init_milvus.py
if errorlevel 1 (
    echo [错误] Milvus初始化失败，请检查Milvus服务状态
    echo 确保运行: docker-compose up -d
    pause
    exit /b 1
)
echo [完成] Milvus集合初始化成功
echo.

echo 步骤 5/7: 构建LlamaIndex索引（如果启用）
REM 检查是否启用混合检索
python -c "
import sys
sys.path.append('.')
try:
    from app.config import settings
    hybrid_enabled = getattr(getattr(settings, 'system', settings), 'hybrid_retrieval_enabled', False)
    exit(0 if hybrid_enabled else 1)
except:
    exit(1)
" >nul 2>&1

if errorlevel 1 (
    echo 跳过LlamaIndex构建（未启用混合检索）
) else (
    echo 构建LlamaIndex分层索引...
    python scripts\4_embed_documents.py --data-dir resources\data\process --storage-dir resources\storage\hierarchical --no-llm
    if errorlevel 1 (
        echo [警告] LlamaIndex构建失败，请确认API Key配置
    ) else (
        echo [完成] LlamaIndex构建成功
    )
)
echo.

echo 步骤 6/7: 嵌入文档到Milvus
python scripts\5_embed_process_documents.py --input-dir resources\data\process
if errorlevel 1 (
    echo [警告] 文档嵌入失败，请检查embedding配置
) else (
    echo [完成] 文档嵌入成功
)
echo.

echo 步骤 7/7: 初始化LightRAG（可选）
python scripts\6_seed_lightrag.py --input-dir resources\data\process
if errorlevel 1 (
    echo [警告] LightRAG初始化失败（可选，可忽略）
) else (
    echo [完成] LightRAG初始化成功
)
echo.

echo ========================================
echo ✅ 数据初始化完成！
echo ========================================
echo.
echo 下一步：
echo 1. 运行API服务: python api_server.py
echo 2. 或使用uvicorn: uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload
echo.
echo 服务将在 http://localhost:8000 启动
echo API文档地址: http://localhost:8000/docs
echo.

REM 询问是否启动服务
set /p "START_SERVICE=是否现在启动API服务？(Y/N): "
if /i "%START_SERVICE%"=="Y" (
    echo 启动API服务...
    python api_server.py
) else (
    echo 初始化完成！您可以稍后手动启动API服务。
    pause
)