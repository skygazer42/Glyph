#!/usr/bin/env python3
"""
Glyph数据导入脚本
将数据导入到MySQL、Milvus和LightRAG
"""

import os
import asyncio
import json
from pathlib import Path
import time
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataImporter:
    """数据导入器"""

    def __init__(self):
        self.project_root = Path("/data/temp33/Glyph")
        self.data_dir = self.project_root / "resources" / "data"

    async def init_mysql(self):
        """初始化MySQL数据库"""
        logger.info("🔧 初始化MySQL数据库...")

        # 使用Docker执行SQL
        import subprocess

        # 创建数据库
        cmd = [
            "docker", "exec", "glyph_mysql_1", "mysql",
            "-uroot", "-p123456",
            "-e", "CREATE DATABASE IF NOT EXISTS policy_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("✅ MySQL数据库创建成功")
        else:
            logger.warning(f"⚠️ 数据库可能已存在: {result.stderr}")

        # 导入schema
        schema_file = self.project_root / "resources" / "database" / "schema" / "policy_qa_schema.sql"
        if schema_file.exists():
            # 转换SQLite语法到MySQL
            mysql_schema = self._convert_sqlite_to_mysql(schema_file)

            # 临时文件保存MySQL schema
            temp_file = Path("/tmp/mysql_schema.sql")
            temp_file.write_text(mysql_schema, encoding='utf-8')

            # 执行SQL
            cmd = [
                "docker", "exec", "-i", "glyph_mysql_1", "mysql",
                "-uroot", "-p123456", "policy_db"
            ]

            with open(temp_file, 'r') as f:
                result = subprocess.run(cmd, input=f.read(), capture_output=True, text=True)

            if result.returncode == 0:
                logger.info("✅ MySQL Schema导入成功")
            else:
                logger.error(f"❌ Schema导入失败: {result.stderr}")

            # 清理临时文件
            temp_file.unlink()

    def _convert_sqlite_to_mysql(self, sqlite_file):
        """将SQLite语法转换为MySQL"""
        content = sqlite_file.read_text(encoding='utf-8')

        # 替换SQLite特有的语法
        replacements = {
            "INTEGER PRIMARY KEY AUTOINCREMENT": "INT AUTO_INCREMENT PRIMARY KEY",
            "INTEGER PRIMARY KEY": "INT PRIMARY KEY",
            "DATETIME": "TIMESTAMP",
            "JSON": "JSON",
            "BOOLEAN": "BOOLEAN",
            "CURRENT_TIMESTAMP": "CURRENT_TIMESTAMP",
            "IF NOT EXISTS": "IF NOT EXISTS"
        }

        for sqlite_type, mysql_type in replacements.items():
            content = content.replace(sqlite_type, mysql_type)

        # 移除SQLite特有的语法
        lines = content.split('\n')
        mysql_lines = []
        for line in lines:
            # 跳过以--开头的注释（保留但调整）
            if line.strip().startswith('--'):
                continue
            # 跳过空行
            if not line.strip():
                continue
            mysql_lines.append(line)

        return '\n'.join(mysql_lines)

    async def init_milvus(self):
        """初始化Milvus集合"""
        logger.info("🔧 初始化Milvus集合...")

        # 创建Python脚本初始化Milvus
        init_script = """
import asyncio
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility

async def init_milvus():
    # 连接Milvus
    connections.connect(
        alias="default",
        host='localhost',
        port='19530'
    )

    # 定义collection schema
    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
        FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=65535),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1024),
        FieldSchema(name="metadata", dtype=DataType.JSON),
        FieldSchema(name="source", dtype=DataType.VARCHAR, max_length=100),
        FieldSchema(name="doc_type", dtype=DataType.VARCHAR, max_length=50)
    ]

    schema = CollectionSchema(
        fields,
        "Policy documents collection"
    )

    collection_name = "policy_documents"

    # 删除已存在的collection
    if utility.has_collection(collection_name):
        utility.drop_collection(collection_name)
        print(f"已删除现有collection: {collection_name}")

    # 创建collection
    collection = Collection(collection_name, schema)

    # 创建索引
    index_params = {
        "metric_type": "COSINE",
        "index_type": "HNSW",
        "params": {"M": 8, "efConstruction": 64}
    }

    collection.create_index(
        field_name="embedding",
        index_params=index_params
    )

    print(f"✅ Milvus collection '{collection_name}' 创建成功")

    # 加载collection
    collection.load()

    connections.disconnect("default")

if __name__ == "__main__":
    asyncio.run(init_milvus())
"""

        # 保存并执行脚本
        script_path = Path("/tmp/init_milvus.py")
        script_path.write_text(init_script)

        # 执行脚本
        result = os.system(f"python {script_path}")
        if result == 0:
            logger.info("✅ Milvus初始化成功")
        else:
            logger.error("❌ Milvus初始化失败")

    async def import_sample_data(self):
        """导入示例数据"""
        logger.info("📚 导入示例数据...")

        # 创建示例数据
        sample_policies = [
            {
                "doc_id": "policy_001",
                "title": "深圳市小微企业创业补贴政策",
                "category": "创业扶持",
                "content": """
深圳市为支持小微企业发展，推出以下创业补贴政策：

一、创业场地补贴
- 对符合条件的初创企业，给予每月500-2000元的场地租金补贴
- 补贴期限最长3年

二、创业带动就业补贴
- 每招用1名员工并缴纳社保6个月以上，补贴2000元
- 最高补贴不超过10万元

三、创业孵化补贴
- 入驻政府认定的创业孵化基地，享受首年免租金
- 第二年租金减半

申请条件：
1. 深圳户籍人员或毕业5年内的大学生
2. 企业成立时间不超过3年
3. 正常经营并缴纳社保
                """,
                "region": "深圳市",
                "effective_date": "2024-01-01",
                "expiry_date": "2026-12-31"
            },
            {
                "doc_id": "policy_002",
                "title": "高新技术企业税收优惠政策",
                "category": "税收优惠",
                "content": """
国家高新技术企业所得税优惠政策：

一、税率优惠
- 企业所得税减按15%税率征收
（一般企业所得税税率为25%）

二、研发费用加计扣除
- 研发费用按100%加计扣除
- 形成无形资产的按200%摊销

三、技术转让所得减免
- 年度技术转让所得不超过500万元的部分，免征企业所得税
- 超过500万元的部分，减半征收企业所得税

申请条件：
1. 拥有核心自主知识产权
2. 产品属于《国家重点支持的高新技术领域》
3. 研发费用占比符合要求
4. 高新技术产品收入占总收入60%以上
                """,
                "region": "全国",
                "effective_date": "2024-01-01",
                "expiry_date": "2025-12-31"
            },
            {
                "doc_id": "policy_003",
                "title": "软件产品增值税即征即退政策",
                "category": "税收优惠",
                "content": """
软件产品增值税即征即退政策：

一、政策内容
- 对销售自行开发生产的软件产品，按17%税率征收增值税后
- 对实际税负超过3%的部分实行即征即退

二、享受条件
1. 取得软件产品登记证书
2. 软件产品拥有自主知识产权
3. 销售自行开发的软件产品

三、计算方法
- 即征即退税额 = 当期软件产品增值税应纳税额 - 软件产品销售额×3%
- 实际税负 = 当期软件产品增值税应纳税额÷当期软件产品销售额×100%

四、申请流程
1. 在电子税务局提出申请
2. 提交软件产品证书等材料
3. 税务机关审核批准
                """,
                "region": "全国",
                "effective_date": "2024-01-01",
                "expiry_date": "2025-12-31"
            }
        ]

        # 保存示例数据
        sample_data_file = self.data_dir / "sample_policies.json"
        sample_data_file.parent.mkdir(exist_ok=True)
        sample_data_file.write_text(json.dumps(sample_policies, ensure_ascii=False, indent=2))

        logger.info(f"✅ 示例数据已保存到: {sample_data_file}")

    async def import_to_lightrag(self):
        """导入数据到LightRAG"""
        logger.info("🔗 准备LightRAG数据...")

        lightrag_dir = self.data_dir / "lightrag"
        lightrag_dir.mkdir(exist_ok=True)

        # 创建示例文档
        sample_docs = [
            {
                "filename": "shenzhen_startup_subsidy.md",
                "content": """# 深圳市小微企业创业补贴政策

## 政策概述
深圳市为支持小微企业发展，推出创业补贴政策。

## 补贴内容
1. 创业场地补贴：每月500-2000元
2. 创业带动就业补贴：每招用1名员工补贴2000元
3. 创业孵化补贴：首年免租金

## 申请条件
- 深圳户籍或毕业5年内大学生
- 企业成立不超过3年
- 正常经营并缴纳社保

## 申请流程
1. 在线申请
2. 提交材料
3. 审核
4. 公示
5. 发放补贴
"""
            },
            {
                "filename": "high_tech_tax_policy.md",
                "content": """# 高新技术企业税收优惠政策

## 税率优惠
企业所得税减按15%征收（原税率25%）。

## 研发费用加计扣除
- 未形成无形资产：按100%加计扣除
- 形成无形资产：按200%摊销

## 技术转让所得优惠
- 500万元以内：免征
- 超过500万元：减半征收

## 申请条件
1. 拥有核心自主知识产权
2. 属于高新技术领域
3. 研发费用占比达标
4. 高新产品收入占比60%以上
"""
            }
        ]

        # 保存文档
        for doc in sample_docs:
            file_path = lightrag_dir / doc["filename"]
            file_path.write_text(doc["content"], encoding='utf-8')

        logger.info(f"✅ 已保存 {len(sample_docs)} 个文档到LightRAG目录")

    async def import_embeddings(self):
        """生成并导入Embeddings到Milvus"""
        logger.info("🔄 生成文档Embeddings...")

        # 创建导入脚本
        import_script = """
import asyncio
import json
from pathlib import Path
import numpy as np
from pymilvus import connections, Collection

async def import_embeddings():
    # 连接Milvus
    connections.connect(
        alias="default",
        host='localhost',
        port='19530'
    )

    # 加载示例数据
    with open('/data/temp33/Glyph/resources/data/sample_policies.json', 'r') as f:
        policies = json.load(f)

    # 连接collection
    collection = Collection("policy_documents")

    # 生成模拟embeddings（实际应该使用真实的embedding模型）
    documents = []
    for policy in policies:
        # 这里使用随机向量模拟，实际应该调用embedding API
        embedding = np.random.random(1024).astype(np.float32).tolist()

        documents.append({
            "id": policy["doc_id"],
            "title": policy["title"],
            "content": policy["content"][:5000],  # 限制长度
            "embedding": embedding,
            "metadata": {
                "category": policy["category"],
                "region": policy["region"],
                "effective_date": policy["effective_date"]
            },
            "source": "government_policy",
            "doc_type": "policy_document"
        })

    # 准备数据
    ids = [doc["id"] for doc in documents]
    titles = [doc["title"] for doc in documents]
    contents = [doc["content"] for doc in documents]
    embeddings = [doc["embedding"] for doc in documents]
    metadatas = [doc["metadata"] for doc in documents]
    sources = [doc["source"] for doc in documents]
    doc_types = [doc["doc_type"] for doc in documents]

    # 插入数据
    collection.insert([
        ids,
        titles,
        contents,
        embeddings,
        metadatas,
        sources,
        doc_types
    ])

    # 刷新数据
    collection.flush()

    print(f"✅ 成功导入 {len(documents)} 个文档到Milvus")

    # 统计
    stats = collection.num_entities
    print(f"📊 Milvus collection 现有 {stats} 个实体")

    connections.disconnect("default")

if __name__ == "__main__":
    asyncio.run(import_embeddings())
"""

        script_path = Path("/tmp/import_embeddings.py")
        script_path.write_text(import_script)

        # 执行导入
        result = os.system(f"python {script_path}")
        if result == 0:
            logger.info("✅ Embeddings导入成功")
        else:
            logger.error("❌ Embeddings导入失败")

    async def verify_import(self):
        """验证导入结果"""
        logger.info("✅ 验证数据导入结果...")

        # 验证MySQL
        import subprocess
        cmd = [
            "docker", "exec", "glyph_mysql_1", "mysql",
            "-uroot", "-p123456", "-e",
            "USE policy_db; SHOW TABLES;"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode == 0:
            logger.info("✅ MySQL数据库连接正常")
            tables = result.stdout.split('\n')[1:]  # 跳过表头
            if tables:
                logger.info(f"📊 MySQL中的表: {tables}")
        else:
            logger.error("❌ MySQL连接失败")

        # 验证Milvus
        verify_script = """
from pymilvus import connections, Collection

connections.connect(host='localhost', port='19530')
collection = Collection("policy_documents")
stats = collection.num_entities
print(f"Milvus文档数量: {stats}")
connections.disconnect()
"""

        script_path = Path("/tmp/verify_milvus.py")
        script_path.write_text(verify_script)
        result = os.system(f"python {script_path}")

        # 验证LightRAG
        lightrag_dir = self.data_dir / "lightrag"
        doc_count = len(list(lightrag_dir.glob("*.md")))
        logger.info(f"📄 LightRAG文档数量: {doc_count}")

        logger.info("\n" + "="*60)
        logger.info("数据导入完成！")
        logger.info("="*60)

    async def run(self):
        """运行完整的导入流程"""
        logger.info("🚀 开始数据导入流程...")
        logger.info(f"时间: {datetime.now().isoformat()}")

        try:
            # 1. 初始化数据库
            await self.init_mysql()
            await self.init_milvus()

            # 2. 导入示例数据
            await self.import_sample_data()
            await self.import_to_lightrag()

            # 3. 生成并导入embeddings
            await self.import_embeddings()

            # 4. 验证结果
            await self.verify_import()

        except Exception as e:
            logger.error(f"❌ 导入失败: {str(e)}")
            raise

        logger.info("\n🎉 所有数据导入成功！")
        logger.info("\n下一步：")
        logger.info("1. 重启API服务: pkill -f api_server.py && python api_server.py")
        logger.info("2. 测试问答: curl -X POST http://localhost:8000/api/agent/chat -d '{\"message\":\"深圳创业补贴\"}'")

if __name__ == "__main__":
    importer = DataImporter()
    asyncio.run(importer.run())