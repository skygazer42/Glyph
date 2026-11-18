# Glyph PowerShell 初始化脚本
# 更现代化的Windows初始化选项

param(
    [switch]$NoPrompt,
    [switch]$AutoStart
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Glyph PowerShell 初始化脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 获取脚本目录
$ROOT_DIR = Split-Path -Parent $PSScriptRoot
Set-Location $ROOT_DIR

Write-Host "工作目录: $(Get-Location)" -ForegroundColor Green

# 检查Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Python未安装或不在PATH中" -ForegroundColor Red
    exit 1
}

# 处理.env文件
if (!(Test-Path ".env")) {
    if (Test-Path ".env.example") {
        Copy-Item ".env.example" ".env"
        Write-Host "✅ 已创建.env文件" -ForegroundColor Green
        Write-Host "⚠️  请编辑.env文件，填入API Keys：" -ForegroundColor Yellow
        Write-Host "   - LLM_API_KEY" -ForegroundColor Cyan
        Write-Host "   - EMBEDDING_DASHSCOPE_API_KEY" -ForegroundColor Cyan

        if (-not $NoPrompt) {
            Write-Host "按Enter继续..." -ForegroundColor Blue
            Read-Host
        }
    } else {
        Write-Host "❌ 未找到.env.example文件" -ForegroundColor Red
        exit 1
    }
}

# 定义初始化步骤
$steps = @(
    @{Name="创建数据库表"; Script="python -m scripts.create_tables"; Critical=$true},
    @{Name="初始化MySQL数据"; Script="python -m scripts.seed_mysql_text2sql"; Critical=$false},
    @{Name="同步Text2SQL模式"; Script="python -m scripts.sync_text2sql_schema"; Critical=$false},
    @{Name="初始化Milvus集合"; Script="python -m scripts.init_milvus"; Critical=$true},
    @{Name="嵌入文档到Milvus"; Script="python -m scripts.embed_process_documents --input-dir resources\data\process"; Critical=$false},
    @{Name="初始化LightRAG"; Script="python -m scripts.seed_lightrag --input-dir resources\data\process"; Critical=$false}
)

# 执行步骤
for ($i = 0; $i -lt $steps.Count; $i++) {
    $step = $steps[$i]
    Write-Host "[$($i+1)/$($steps.Count)] $($step.Name)..." -ForegroundColor Blue

    try {
        Invoke-Expression $step.Script
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $($step.Name)完成" -ForegroundColor Green
        } elseif ($step.Critical) {
            Write-Host "❌ $($step.Name)失败" -ForegroundColor Red
            exit 1
        } else {
            Write-Host "⚠️  $($step.Name)失败（可继续）" -ForegroundColor Yellow
        }
    } catch {
        if ($step.Critical) {
            Write-Host "❌ $($step.Name)异常: $_" -ForegroundColor Red
            exit 1
        } else {
            Write-Host "⚠️  $($step.Name)异常（可继续）" -ForegroundColor Yellow
        }
    }
}

# 检查LlamaIndex
$hybridEnabled = python -c "
from app.config.app_config import settings
print(settings.system.hybrid_retrieval_enabled)
"
if ($LASTEXITCODE -ne 0) {
    throw "读取混合检索配置失败"
}

if ($hybridEnabled -eq "True") {
    Write-Host "[构建LlamaIndex索引..." -ForegroundColor Blue
    try {
        python -m scripts.embed_documents --data-dir resources\data\process --storage-dir resources\storage\hierarchical --no-llm
        if ($LASTEXITCODE -ne 0) {
            throw "LlamaIndex 构建命令失败，退出码：$LASTEXITCODE"
        }
        Write-Host "✅ LlamaIndex构建完成" -ForegroundColor Green
    } catch {
        Write-Host "⚠️  LlamaIndex构建失败" -ForegroundColor Yellow
    }
} else {
    Write-Host "跳过LlamaIndex构建" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🎉 数据初始化完成！" -ForegroundColor Green
Write-Host ""
Write-Host "下一步：" -ForegroundColor Cyan
Write-Host "  python api_server.py" -ForegroundColor White
Write-Host "  uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload" -ForegroundColor White
Write-Host ""
Write-Host "服务地址: http://localhost:8000" -ForegroundColor Green
Write-Host "API文档: http://localhost:8000/docs" -ForegroundColor Green

if ($AutoStart -or (-not $NoPrompt -and (Read-Host "是否启动API服务？(Y/N)") -eq "Y")) {
    Write-Host "启动API服务..." -ForegroundColor Blue
    python api_server.py
}
