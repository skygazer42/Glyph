"""
DSL 相关端点
包含 DSL 生成、保存、测试等功能
"""

import logging
from fastapi import APIRouter, Depends, HTTPException

from app.api.schemas import (
    GenerateDSLRequest,
    GenerateDSLResponse,
    SaveDSLRequest,
    SaveDSLResponse,
    TestDSLRequest,
    TestDSLResponse,
    ListDSLResponse,
    GetDSLResponse
)
from app.api.deps import (
    get_dsl_generator,
    get_dsl_extractor,
    get_document_parser,
    get_policy_engine
)
from app.agents.dsl_generator.dsl_generator import DSLGenerator
from app.agents.dsl_generator.dsl_extractor import DSLExtractor
from app.agents.dsl_generator.document_parser import DocumentParser
from app.agents.dsl_generator.rule_engine import PolicyEngine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/generate", response_model=GenerateDSLResponse)
async def generate_dsl(
    request: GenerateDSLRequest,
    dsl_generator: DSLGenerator = Depends(get_dsl_generator),
    dsl_extractor: DSLExtractor = Depends(get_dsl_extractor),
    doc_parser: DocumentParser = Depends(get_document_parser)
):
    """
    从文本生成 DSL

    Args:
        request: 包含政策文本的请求

    Returns:
        生成的 DSL 数据和 YAML 内容
    """
    try:
        # 预处理文本
        processed = doc_parser.preprocess_text(request.text)

        # 提取结构化数据
        dsl_data = dsl_extractor.extract(
            request.text,
            processed.get('metadata', {})
        )

        logger.debug(f"提取的 DSL 数据: {dsl_data}")

        # 生成 YAML（自动检测模板）
        yaml_content = dsl_generator.generate(
            dsl_data,
            auto_detect=True,
            context=processed.get('metadata', {})
        )

        logger.info("DSL 生成成功")

        return GenerateDSLResponse(
            success=True,
            dsl_data=dsl_data,
            yaml_content=yaml_content
        )

    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"DSL 生成失败: {error_detail}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/save", response_model=SaveDSLResponse)
async def save_dsl(
    request: SaveDSLRequest,
    dsl_generator: DSLGenerator = Depends(get_dsl_generator),
    policy_engine: PolicyEngine = Depends(get_policy_engine)
):
    """
    保存 DSL 到文件

    Args:
        request: 包含规则 ID、YAML 内容的请求

    Returns:
        保存结果
    """
    try:
        filename = request.filename or f"{request.rule_id}.yaml"
        file_path = dsl_generator.save(request.yaml_content, filename)

        # 重新加载规则引擎
        policy_engine.reload_rules()

        logger.info(f"DSL 已保存: {file_path}")

        return SaveDSLResponse(
            success=True,
            file_path=str(file_path),
            rule_id=request.rule_id
        )

    except Exception as e:
        logger.error(f"DSL 保存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=ListDSLResponse)
async def list_dsl(
    policy_engine: PolicyEngine = Depends(get_policy_engine)
):
    """
    获取所有 DSL 规则列表

    Returns:
        规则列表
    """
    try:
        policy_engine.reload_rules()
        rules = policy_engine.list_rules()

        logger.info(f"获取规则列表，共 {len(rules)} 条")

        return ListDSLResponse(
            success=True,
            rules=rules,
            total=len(rules)
        )

    except Exception as e:
        logger.error(f"获取规则列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{rule_id}", response_model=GetDSLResponse)
async def get_dsl(
    rule_id: str,
    policy_engine: PolicyEngine = Depends(get_policy_engine)
):
    """
    获取 DSL 规则详情

    Args:
        rule_id: 规则 ID

    Returns:
        规则详细信息
    """
    try:
        rule = policy_engine.get_rule_info(rule_id)
        if not rule:
            raise HTTPException(status_code=404, detail="规则不存在")

        logger.info(f"获取规则详情: {rule_id}")

        return GetDSLResponse(
            success=True,
            rule=rule
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取规则详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/test", response_model=TestDSLResponse)
async def test_dsl(
    request: TestDSLRequest,
    policy_engine: PolicyEngine = Depends(get_policy_engine)
):
    """
    测试 DSL 规则

    Args:
        request: 包含规则 ID 和测试输入数据

    Returns:
        测试结果
    """
    try:
        result = policy_engine.execute(request.rule_id, request.inputs)

        logger.info(f"规则 {request.rule_id} 测试完成")

        return TestDSLResponse(
            success=True,
            result=result
        )

    except Exception as e:
        logger.error(f"规则测试失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
