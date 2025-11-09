"""
政务智能问答数据库初始化脚本
负责创建数据库、导入初始数据、生成Schema提示
"""

import sqlite3
import json
import os
from pathlib import Path
from datetime import datetime
import sys

# 添加项目路径
sys.path.append(str(Path(__file__).parent.parent.parent))


class PolicyQADatabaseInitializer:
    """政务问答数据库初始化器"""

    def __init__(self, db_path="database/policy_qa.db"):
        """初始化数据库路径"""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None
        self.cursor = None

    def connect(self):
        """连接数据库"""
        self.conn = sqlite3.connect(str(self.db_path))
        self.cursor = self.conn.cursor()
        print(f"[OK] 已连接到数据库: {self.db_path}")

    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            print("[OK] 数据库连接已关闭")

    def create_schema(self, schema_file="database/schema/policy_qa_schema.sql"):
        """执行Schema SQL文件创建表结构"""
        schema_path = Path(schema_file)
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema文件不存在: {schema_path}")

        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()

        # 直接执行整个SQL脚本
        try:
            self.cursor.executescript(schema_sql)
        except sqlite3.Error as e:
            print(f"[WARNING] 执行SQL脚本时出错: {e}")
            raise

        self.conn.commit()
        print("[OK] 数据库表结构创建完成")

    def insert_schema_hints(self):
        """插入Schema提示数据，帮助LLM理解表结构"""
        hints = [
            # policy_documents 表提示
            ("policy_documents", "doc_id", "description", "文档唯一标识符，格式如：jn_car_2025_001"),
            ("policy_documents", "category", "description", "政策分类：汽车消费补贴/家电以旧换新/消费券/数码产品补贴"),
            ("policy_documents", "category", "example", "汽车消费补贴"),
            ("policy_documents", "status", "description", "文档状态：active(有效)/expired(过期)/draft(草稿)"),
            ("policy_documents", "effective_date", "description", "政策生效日期"),
            ("policy_documents", "expiry_date", "description", "政策失效日期，NULL表示长期有效"),

            # policy_entities 表提示
            ("policy_entities", "entity_type", "description", "实体类型：补贴金额/申请条件/时间期限/办理流程/申请材料"),
            ("policy_entities", "entity_value", "description", "实体的具体值"),
            ("policy_entities", "entity_unit", "description", "实体单位：元/天/件/次"),

            # policy_qa_pairs 表提示
            ("policy_qa_pairs", "difficulty_level", "description", "问题难度等级：1(简单)-5(复杂)"),
            ("policy_qa_pairs", "query_type", "description", "查询类型：informational(信息查询)/procedural(流程查询)/eligibility(资格查询)"),
            ("policy_qa_pairs", "verified", "description", "是否经过人工验证"),
            ("policy_qa_pairs", "use_count", "description", "该问答对被使用的次数"),
            ("policy_qa_pairs", "feedback_score", "description", "用户反馈评分(0-5分)"),

            # policy_tags 表提示
            ("policy_tags", "tag_type", "description", "标签类型：领域/对象/场景"),
            ("policy_tags", "tag_type", "example", "领域"),
            ("policy_tags", "weight", "description", "标签权重，用于相关性计算"),

            # query_history 表提示
            ("query_history", "response_time_ms", "description", "响应时间(毫秒)"),
            ("query_history", "feedback", "description", "用户反馈：positive(正面)/negative(负面)/neutral(中性)"),

            # policy_relationships 表提示
            ("policy_relationships", "relationship_type", "description", "政策关系类型：补充/替代/依赖/相关"),

            # policy_change_log 表提示
            ("policy_change_log", "change_type", "description", "变更类型：created(创建)/updated(更新)/expired(过期)/superseded(被取代)"),
        ]

        insert_sql = """
            INSERT OR REPLACE INTO schema_hints (table_name, column_name, hint_type, hint_text, language)
            VALUES (?, ?, ?, ?, 'zh')
        """

        self.cursor.executemany(insert_sql, hints)
        self.conn.commit()
        print(f"[OK] 已插入 {len(hints)} 条Schema提示")

    def import_qa_pairs(self):
        """导入QA对数据"""
        # 先运行seed脚本生成JSON
        import subprocess
        os.chdir("database/seed_data")
        result = subprocess.run(['python', 'generate_qa_data.py'], capture_output=True, text=True, encoding='utf-8')
        print(result.stdout)
        os.chdir("../..")

        # 读取生成的JSON文件
        json_file = "database/seed_data/policy_qa_初始数据.json"
        if not os.path.exists(json_file):
            print(f"[WARNING] JSON文件不存在: {json_file}")
            return

        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        qa_pairs = data['qa_pairs']

        insert_sql = """
            INSERT INTO policy_qa_pairs
            (question, answer, category, keywords, difficulty_level, query_type, verified, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """

        for qa in qa_pairs:
            metadata = json.dumps({
                "source": "seed_data",
                "imported_at": datetime.now().isoformat()
            })

            self.cursor.execute(insert_sql, (
                qa['question'],
                qa['answer'],
                qa['category'],
                qa['keywords'],
                qa['difficulty_level'],
                qa['query_type'],
                qa['verified'],
                metadata
            ))

        self.conn.commit()
        print(f"[OK] 已导入 {len(qa_pairs)} 个QA对")

    def import_policy_documents(self, data_dir="data/process"):
        """导入政策文档数据"""
        from glob import glob

        md_files = glob(f"{data_dir}/**/*.md", recursive=True)
        print(f"[INFO] 找到 {len(md_files)} 个Markdown文件")

        insert_sql = """
            INSERT INTO policy_documents
            (doc_id, title, category, sub_category, source_file, content, publish_date, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        count = 0
        for md_file in md_files:
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 提取标题（第一行的#标题）
                lines = content.strip().split('\n')
                title = lines[0].replace('#', '').strip() if lines else "未命名文档"

                # 判断分类
                if '汽车' in md_file or '车辆' in md_file or '购车' in md_file:
                    category = "汽车消费补贴"
                elif '家电' in md_file or '以旧换新' in md_file:
                    category = "家电以旧换新"
                elif '消费券' in md_file or '泉城购' in md_file:
                    category = "消费券"
                elif '手机' in md_file or '平板' in md_file or '智能手表' in md_file:
                    category = "数码产品补贴"
                else:
                    category = "通用政策"

                # 生成doc_id
                doc_id = f"doc_{count + 1:04d}"

                # 提取发布日期（从文件名中）
                import re
                date_match = re.search(r'(\d{6})_\d{6}\.md$', md_file)
                publish_date = None
                if date_match:
                    date_str = date_match.group(1)
                    # 转换为 YYYY-MM-DD 格式
                    publish_date = f"20{date_str[:2]}-{date_str[2:4]}-{date_str[4:6]}"

                metadata = json.dumps({
                    "source_file": md_file,
                    "file_size": len(content),
                    "imported_at": datetime.now().isoformat()
                })

                self.cursor.execute(insert_sql, (
                    doc_id,
                    title,
                    category,
                    None,  # sub_category
                    md_file,
                    content,
                    publish_date,
                    "active",
                    metadata
                ))

                count += 1

            except Exception as e:
                print(f"[WARNING] 导入文件失败 {md_file}: {e}")

        self.conn.commit()
        print(f"[OK] 已导入 {count} 个政策文档")

    def create_sample_tags(self):
        """创建示例标签数据"""
        tags = [
            ("doc_0001", "汽车", "领域", 1.0),
            ("doc_0001", "补贴", "对象", 1.0),
            ("doc_0001", "新能源", "场景", 0.8),
            ("doc_0001", "济南市", "地域", 1.0),
        ]

        insert_sql = "INSERT INTO policy_tags (doc_id, tag_name, tag_type, weight) VALUES (?, ?, ?, ?)"
        self.cursor.executemany(insert_sql, tags)
        self.conn.commit()
        print(f"[OK] 已创建 {len(tags)} 个示例标签")

    def generate_statistics(self):
        """生成数据统计信息"""
        print("\n" + "=" * 60)
        print("数据库统计信息")
        print("=" * 60)

        # QA对统计
        self.cursor.execute("SELECT COUNT(*) FROM policy_qa_pairs")
        qa_count = self.cursor.fetchone()[0]
        print(f"QA对总数: {qa_count}")

        self.cursor.execute("SELECT category, COUNT(*) FROM policy_qa_pairs GROUP BY category")
        for row in self.cursor.fetchall():
            print(f"  - {row[0]}: {row[1]} 个")

        # 文档统计
        self.cursor.execute("SELECT COUNT(*) FROM policy_documents")
        doc_count = self.cursor.fetchone()[0]
        print(f"\n政策文档总数: {doc_count}")

        self.cursor.execute("SELECT category, COUNT(*) FROM policy_documents GROUP BY category")
        for row in self.cursor.fetchall():
            print(f"  - {row[0]}: {row[1]} 个")

        # Schema提示统计
        self.cursor.execute("SELECT COUNT(*) FROM schema_hints")
        hints_count = self.cursor.fetchone()[0]
        print(f"\nSchema提示总数: {hints_count}")

        print("=" * 60)

    def initialize_all(self):
        """执行完整的初始化流程"""
        try:
            print("\n" + "=" * 60)
            print("开始初始化政务智能问答数据库")
            print("=" * 60 + "\n")

            # 1. 连接数据库
            self.connect()

            # 2. 创建表结构
            print("\n[1/6] 创建数据库表结构...")
            self.create_schema()

            # 3. 插入Schema提示
            print("\n[2/6] 插入Schema提示...")
            self.insert_schema_hints()

            # 4. 导入QA对
            print("\n[3/6] 导入QA对数据...")
            self.import_qa_pairs()

            # 5. 导入政策文档
            print("\n[4/6] 导入政策文档...")
            self.import_policy_documents()

            # 6. 创建示例标签
            print("\n[5/6] 创建示例标签...")
            self.create_sample_tags()

            # 7. 生成统计信息
            print("\n[6/6] 生成统计信息...")
            self.generate_statistics()

            print("\n" + "=" * 60)
            print("[OK] 数据库初始化完成！")
            print("=" * 60)
            print(f"数据库位置: {self.db_path.absolute()}")
            print("=" * 60 + "\n")

        except Exception as e:
            print(f"\n[ERROR] 初始化失败: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.close()


def main():
    """主函数"""
    initializer = PolicyQADatabaseInitializer()
    initializer.initialize_all()


if __name__ == "__main__":
    main()
