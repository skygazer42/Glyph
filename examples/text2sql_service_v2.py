import asyncio
import json
from typing import Dict, List, Optional, Any, Callable, Union, Awaitable, TypeVar

from autogen_agentchat.agents import AssistantAgent, UserProxyAgent, MessageFilterAgent, MessageFilterConfig, PerSourceFilter
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.base import TaskResult
from autogen_agentchat.messages import ModelClientStreamingChunkEvent, TextMessage, UserInputRequestedEvent
from autogen_agentchat.teams import DiGraphBuilder, GraphFlow
from autogen_core import SingleThreadedAgentRuntime, TopicId, ClosureContext, MessageContext, CancellationToken
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType

from c_app.core.llms import model_client
from c_app.schemas.text2sql import (
    Text2SQLResponse, ResponseMessage, QueryMessage, SqlMessage,
    SqlExplanationMessage, SqlResultMessage, AnalysisMessage
)
from c_app.db.dbaccess import DBAccess

# 定义主题类型 - 保持与原始服务相同，用于消息发布
stream_output_topic_type = "stream_output"

# 定义智能体名称常量
QUERY_ANALYZER_NAME = "query_analyzer"
SQL_GENERATOR_NAME = "sql_generator"
SQL_EXPLAINER_NAME = "sql_explainer"
SQL_EXECUTOR_NAME = "sql_executor"
VISUALIZATION_RECOMMENDER_NAME = "visualization_recommender"
USER_PROXY_NAME = "user_proxy"

# 定义数据库类型（可配置）
DB_TYPE = "SQLite"  # 可选值: "MySQL", "PostgreSQL", "SQLite", "Oracle", "SQL Server"

# 表结构及关系的描述
db_schema_definition = """
CREATE TABLE [Album]
(
    [AlbumId] INTEGER  NOT NULL,
    [Title] NVARCHAR(160)  NOT NULL,
    [ArtistId] INTEGER  NOT NULL,
    CONSTRAINT [PK_Album] PRIMARY KEY  ([AlbumId]),
    FOREIGN KEY ([ArtistId]) REFERENCES [Artist] ([ArtistId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE [Artist]
(
    [ArtistId] INTEGER  NOT NULL,
    [Name] NVARCHAR(120),
    CONSTRAINT [PK_Artist] PRIMARY KEY  ([ArtistId])
);

CREATE TABLE [Customer]
(
    [CustomerId] INTEGER  NOT NULL,
    [FirstName] NVARCHAR(40)  NOT NULL,
    [LastName] NVARCHAR(20)  NOT NULL,
    [Company] NVARCHAR(80),
    [Address] NVARCHAR(70),
    [City] NVARCHAR(40),
    [State] NVARCHAR(40),
    [Country] NVARCHAR(40),
    [PostalCode] NVARCHAR(10),
    [Phone] NVARCHAR(24),
    [Fax] NVARCHAR(24),
    [Email] NVARCHAR(60)  NOT NULL,
    [SupportRepId] INTEGER,
    CONSTRAINT [PK_Customer] PRIMARY KEY  ([CustomerId]),
    FOREIGN KEY ([SupportRepId]) REFERENCES [Employee] ([EmployeeId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE [Employee]
(
    [EmployeeId] INTEGER  NOT NULL,
    [LastName] NVARCHAR(20)  NOT NULL,
    [FirstName] NVARCHAR(20)  NOT NULL,
    [Title] NVARCHAR(30),
    [ReportsTo] INTEGER,
    [BirthDate] DATETIME,
    [HireDate] DATETIME,
    [Address] NVARCHAR(70),
    [City] NVARCHAR(40),
    [State] NVARCHAR(40),
    [Country] NVARCHAR(40),
    [PostalCode] NVARCHAR(10),
    [Phone] NVARCHAR(24),
    [Fax] NVARCHAR(24),
    [Email] NVARCHAR(60),
    CONSTRAINT [PK_Employee] PRIMARY KEY  ([EmployeeId]),
    FOREIGN KEY ([ReportsTo]) REFERENCES [Employee] ([EmployeeId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE [Genre]
(
    [GenreId] INTEGER  NOT NULL,
    [Name] NVARCHAR(120),
    CONSTRAINT [PK_Genre] PRIMARY KEY  ([GenreId])
);

CREATE TABLE [Invoice]
(
    [InvoiceId] INTEGER  NOT NULL,
    [CustomerId] INTEGER  NOT NULL,
    [InvoiceDate] DATETIME  NOT NULL,
    [BillingAddress] NVARCHAR(70),
    [BillingCity] NVARCHAR(40),
    [BillingState] NVARCHAR(40),
    [BillingCountry] NVARCHAR(40),
    [BillingPostalCode] NVARCHAR(10),
    [Total] NUMERIC(10,2)  NOT NULL,
    CONSTRAINT [PK_Invoice] PRIMARY KEY  ([InvoiceId]),
    FOREIGN KEY ([CustomerId]) REFERENCES [Customer] ([CustomerId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE [InvoiceLine]
(
    [InvoiceLineId] INTEGER  NOT NULL,
    [InvoiceId] INTEGER  NOT NULL,
    [TrackId] INTEGER  NOT NULL,
    [UnitPrice] NUMERIC(10,2)  NOT NULL,
    [Quantity] INTEGER  NOT NULL,
    CONSTRAINT [PK_InvoiceLine] PRIMARY KEY  ([InvoiceLineId]),
    FOREIGN KEY ([InvoiceId]) REFERENCES [Invoice] ([InvoiceId])
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([TrackId]) REFERENCES [Track] ([TrackId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE [MediaType]
(
    [MediaTypeId] INTEGER  NOT NULL,
    [Name] NVARCHAR(120),
    CONSTRAINT [PK_MediaType] PRIMARY KEY  ([MediaTypeId])
);

CREATE TABLE [Playlist]
(
    [PlaylistId] INTEGER  NOT NULL,
    [Name] NVARCHAR(120),
    CONSTRAINT [PK_Playlist] PRIMARY KEY  ([PlaylistId])
);

CREATE TABLE [PlaylistTrack]
(
    [PlaylistId] INTEGER  NOT NULL,
    [TrackId] INTEGER  NOT NULL,
    CONSTRAINT [PK_PlaylistTrack] PRIMARY KEY  ([PlaylistId], [TrackId]),
    FOREIGN KEY ([PlaylistId]) REFERENCES [Playlist] ([PlaylistId])
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([TrackId]) REFERENCES [Track] ([TrackId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);

CREATE TABLE [Track]
(
    [TrackId] INTEGER  NOT NULL,
    [Name] NVARCHAR(200)  NOT NULL,
    [AlbumId] INTEGER,
    [MediaTypeId] INTEGER  NOT NULL,
    [GenreId] INTEGER,
    [Composer] NVARCHAR(220),
    [Milliseconds] INTEGER  NOT NULL,
    [Bytes] INTEGER,
    [UnitPrice] NUMERIC(10,2)  NOT NULL,
    CONSTRAINT [PK_Track] PRIMARY KEY  ([TrackId]),
    FOREIGN KEY ([AlbumId]) REFERENCES [Album] ([AlbumId])
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([GenreId]) REFERENCES [Genre] ([GenreId])
		ON DELETE NO ACTION ON UPDATE NO ACTION,
    FOREIGN KEY ([MediaTypeId]) REFERENCES [MediaType] ([MediaTypeId])
		ON DELETE NO ACTION ON UPDATE NO ACTION
);



/*******************************************************************************
   Create Primary Key Unique Indexes
********************************************************************************/

/*******************************************************************************
   Create Foreign Keys
********************************************************************************/
CREATE INDEX [IFK_AlbumArtistId] ON [Album] ([ArtistId]);

CREATE INDEX [IFK_CustomerSupportRepId] ON [Customer] ([SupportRepId]);

CREATE INDEX [IFK_EmployeeReportsTo] ON [Employee] ([ReportsTo]);

CREATE INDEX [IFK_InvoiceCustomerId] ON [Invoice] ([CustomerId]);

CREATE INDEX [IFK_InvoiceLineInvoiceId] ON [InvoiceLine] ([InvoiceId]);

CREATE INDEX [IFK_InvoiceLineTrackId] ON [InvoiceLine] ([TrackId]);

CREATE INDEX [IFK_PlaylistTrackPlaylistId] ON [PlaylistTrack] ([PlaylistId]);

CREATE INDEX [IFK_PlaylistTrackTrackId] ON [PlaylistTrack] ([TrackId]);

CREATE INDEX [IFK_TrackAlbumId] ON [Track] ([AlbumId]);

CREATE INDEX [IFK_TrackGenreId] ON [Track] ([GenreId]);

CREATE INDEX [IFK_TrackMediaTypeId] ON [Track] ([MediaTypeId]);

"""

# 初始化数据库访问
dbAccess = DBAccess()
dbAccess.connect_to_sqlite("https://vanna.ai/Chinook.sqlite")


class StreamResponseCollector:
    """流式响应收集器，用于收集智能体产生的流式输出"""

    def __init__(self):
        """初始化流式响应收集器"""
        self.responses = []
        self.callback: Optional[Callable[[Any, ResponseMessage, Any], Awaitable[None]]] = None
        self.user_input: Optional[Callable[[str, Optional[Any]], Awaitable[str]]] = None

    def set_callback(self, callback: Callable[[Any, ResponseMessage, Any], Awaitable[None]]) -> None:
        """设置回调函数

        Args:
            callback: 用于处理响应消息的异步回调函数
        """
        self.callback = callback

    def set_user_input(self, user_input: Callable[[str, Optional[Any]], Awaitable[str]]) -> None:
        """设置用户输入函数"""
        self.user_input = user_input

    async def collect(self, message: ResponseMessage):
        """收集响应消息"""
        self.responses.append(message)

        # 如果设置了回调函数，则调用回调函数
        if self.callback:
            try:
                # 直接调用回调函数，传入None作为上下文
                await self.callback(None, message, None)
            except Exception as e:
                print(f"Error in callback: {str(e)}")

        return message


class Text2SQLGraphFlow:
    """使用GraphFlow实现的Text2SQL服务"""

    def __init__(self, db_type: str = DB_TYPE, db_schema: str = None):
        """初始化Text2SQL GraphFlow服务

        Args:
            db_type: 数据库类型，默认为DB_TYPE常量
            db_schema: 数据库模式定义，默认为db_schema_definition常量
        """
        self.db_type = db_type
        self.db_schema = db_schema or db_schema_definition
        self.collector = None

    def _create_query_analyzer_agent(self, query: str = None) -> AssistantAgent:
        """创建查询分析智能体

        Args:
            query: 用户的自然语言查询，如果提供则替换提示中的[query]占位符
        """

        prompt = f"""
                    你是一名专业的数据库分析与生成SQL命令的分析专家。你的任务是深入分析用户的自然语言查询，并结合给定的数据库表结构信息，生成一份完整详细的关于生成SQL命令的分析报告。这份报告将作为后续指导另一个大模型生成精确SQL命令的关键依据。
                    **核心目标：**

                    基于用户查询和数据库结构，输出一份结构化的报告，详细描述如何将用户意图转化为SQL查询的关键步骤和考虑因素。

                    **你需要处理以下信息：**

                    * **数据库类型：** {self.db_type}
                    * **数据库结构：**
                        ```sql
                        {self.db_schema}
                        ```
                    * **用户原始问题：** {query}

                    **请按照以下步骤进行分析并生成报告：**

                    1.  **查询意图深度分析：**
                        * 详细描述用户提出的自然语言查询的核心意图。用户希望从数据库中检索或操作哪些数据？他们的最终目标是什么？
                        * 识别查询中涉及的关键概念和实体。

                    2.  **主要实体与关系识别：**
                        * 根据用户查询和数据库结构，识别出查询所涉及的主要实体（对应数据库中的表）。
                        * 分析这些实体之间的关系（例如，一对一、一对多、多对多），并确定可能需要进行的表连接。

                    3.  **所需表与字段精确确定：**
                        * 列出用户查询明确或暗示需要使用的所有表名。
                        * 列出需要从这些表中检索的所有字段名。如果需要进行计算或聚合操作，也请在此处说明。

                    4.  **潜在歧义与缺失信息识别：**
                        * 分析用户查询中可能存在的歧义或不明确之处。例如，用户是否使用了模糊的术语、未指定具体的条件、或者查询范围不清晰？
                        * 指出生成完整且准确SQL语句所需的任何缺失信息。

                    5.  **SQL操作类型与结构初步构思：**
                        * 基于对用户意图的理解，确定需要执行的SQL操作类型（例如：SELECT, INSERT, UPDATE, DELETE）。对于查询操作，需要进一步考虑是否需要聚合函数（SUM, AVG, COUNT, MAX, MIN）、分组（GROUP BY）、排序（ORDER BY）、限制结果数量（LIMIT）等。
                        * 初步构思SQL查询语句的基本结构框架，包括涉及的表、大致的连接方式和主要的条件逻辑。

                    6.  **报告输出 - 请严格按照以下格式，并确保每个标题前后有空行：**

                    # SQL 命令分析报告

                    ### 1. 用户原始问题

                    {query}

                    ### 2. 数据库类型

                    {self.db_type}

                    ### 3. 数据库结构

                    ```sql
                    {self.db_schema}
                    ```

                    ### 4. 查询意图描述

                    [对用户查询意图进行详细描述]

                    ### 5. 需要使用的表名列表

                    - [表名1]
                    - [表名2]
                    - ...

                    ### 6. 需要使用的字段列表

                    - 表名1: [字段1], [字段2], ...
                    - 表名2: [字段1], [字段2], ...
                    - ...

                    （请注明是否需要使用聚合函数，例如：`SUM(sales_amount)`）

                    ### 7. 需要的表连接描述

                    - [如果需要连接，描述连接的表以及连接条件（例如：`orders` 表通过 `user_id` 连接到 `users` 表）]
                    - [如果不需要连接，说明原因]

                    ### 8. 筛选条件描述

                    - [描述用户查询中隐含或明确要求的筛选条件 (例如：`WHERE status = '已发货'`)]
                    - [如果存在多个筛选条件，请说明它们之间的逻辑关系 (例如：AND, OR)]

                    ### 9. 分组描述

                    - [描述是否需要对结果进行分组 (GROUP BY)，以及分组的字段是什么]
                    - [说明分组后是否需要进行聚合操作]

                    ### 10. 排序描述

                    - [描述是否需要对结果进行排序 (ORDER BY)，以及排序的字段和排序方式 (ASC/DESC)]

                    ### 11. 潜在歧义与缺失信息

                    - [列出用户查询中存在的任何潜在歧义，并说明可能导致不同SQL解释的情况]
                    - [指出生成完整SQL语句所需的缺失信息，并说明需要用户提供哪些额外细节]

                    ### 12. 初步的SQL查询结构草案

                    ```sql
                    -- 基于以上分析的初步 SQL 查询结构
                    SELECT [在此处填写需要选择的字段]
                    FROM [在此处填写需要使用的表名]
                    [在此处填写需要的连接 (例如：INNER JOIN table2 ON ...)]
                    WHERE [在此处填写筛选条件]
                    [在此处填写分组 (例如：GROUP BY ...)]
                    [在此处填写排序 (例如：ORDER BY ...)]
                    [在此处填写限制结果数量 (例如：LIMIT ...)]
                    ;
                    ```
                请确保你的报告内容详尽、准确，能够清晰地反映用户查询的意图以及如何将其转化为可执行的SQL命令。这份报告的质量将直接影响后续SQL语句生成的准确性。
                注意：如果用户提出修改建议，只需要输出修改部分内容即可，不需要将整篇报告输出。
                """

        return AssistantAgent(
            name="query_analyzer",  # 内部名称，用于消息路由
            model_client=model_client,
            system_message=prompt,
            model_client_stream=True,
        )

    def _create_sql_generator_agent(self) -> AssistantAgent:
        """创建 SQL 生成智能体"""
        prompt = f"""
        你是一名专业的SQL转换专家。你的任务是基于上下文信息及SQL命令生成报告，将用户的自然语言查询转换为精确的SQL语句。

        ## 生成SQL的指导原则：

        1.  **严格遵循报告中的分析：** 仔细阅读并理解上述的SQL命令生成报告，包括查询意图、需要使用的表和字段、连接方式、筛选条件、分组和排序要求。
        2.  **生成有效的SQL语句：** 仅输出符合 {self.db_type} 数据库语法的有效SQL语句，不要添加任何额外的解释或说明。
        3.  **准确表达筛选条件：** 报告中如有筛选条件描述，务必在生成的SQL语句中准确实现。
        4.  **正确使用表连接：** 按照报告中“需要的表连接描述”进行表连接，并确保连接条件正确。
        5.  **实现分组和聚合：** 如果报告中指示需要进行分组（GROUP BY）或聚合操作（例如 SUM, COUNT, AVG），请在SQL语句中正确实现。
        6.  **实现排序：** 按照报告中“排序描述”的要求，使用 ORDER BY 子句对结果进行排序。
        7.  **考虑数据库特性：** 生成的SQL语句应符合 {self.db_type} 数据库的特定语法和函数。
        8.  **SQL格式规范：** 使用清晰可读的SQL格式，适当添加换行和缩进，以提高可读性。
        9.  **避免使用不支持的语法：** 不要使用 {self.db_type} 数据库不支持的特殊语法或函数。
        10. **仅生成SQL：** 最终输出结果必须是纯粹的SQL查询语句，没有任何额外的文本。

        特别注意：最终只生成一条您认为最符合用户查询需求的SQL语句。
        """

        return AssistantAgent(
            name="sql_generator",
            model_client=model_client,
            system_message=prompt,
            model_client_stream=True,
        )

    def _create_sql_explainer_agent(self) -> AssistantAgent:
        """创建 SQL 解释智能体"""
        prompt = f"""
        你是一名专业的SQL解释专家，你的任务是以准确、易懂的方式向非技术人员解释给定的SQL语句的含义和作用。

        ## 数据库类型
        {self.db_type}

        ## 数据库结构
        ```sql
        {self.db_schema}
        ```

        ## 规则

        1.  **使用通俗易懂的语言：** 解释应该避免使用过于专业或技术性的术语。目标是让没有任何编程或数据库知识的人也能理解。
        2.  **准确且全面地解释：** 确保解释的准确性，并覆盖SQL语句的主要功能和逻辑。
        3.  **解释关键子句：** 针对SQL语句中的每个主要子句（例如 `SELECT`, `FROM`, `WHERE`, `GROUP BY`, `ORDER BY`, `JOIN` 等）解释其作用和目的。
        4.  **说明查询结果：** 清晰地描述执行这条SQL语句后，预计会从数据库中返回什么类型的数据和结果。
        5.  **解释复杂特性：**
            * **聚合函数：** 如果SQL语句中使用了聚合函数（如 `SUM`, `AVG`, `COUNT`, `MAX`, `MIN`），解释这些函数的作用以及它们是如何计算结果的。
            * **表连接：** 如果使用了表连接（如 `JOIN`），解释为什么要进行连接，以及连接是如何根据相关字段将不同表中的数据关联起来的。可以结合数据库结构进行解释。
            * **子查询：** 如果使用了子查询（嵌套查询），解释子查询的目的以及它是如何帮助主查询获取所需数据的。
        6.  **结合数据库结构：** 在解释过程中，可以适当引用提供的数据库表结构，帮助理解表名、字段名的含义以及表之间的关系。例如，解释 `users.name` 时，可以说明 `name` 是 `users` 表中的一个字段，用于存储用户的姓名。
        7.  **保持简洁明了：** 尽量用简短的句子表达清楚意思，避免冗长的描述。解释的长度一般不超过200字。

        特别注意：你的解释应该直接针对用户问题和SQL语句，不要添加额外的内容。
        """

        return AssistantAgent(
            name="sql_explainer",
            model_client=model_client,
            system_message=prompt,
            model_client_stream=True,
        )

    def _create_sql_executor_agent(self) -> AssistantAgent:
        """创建 SQL 执行智能体"""
        prompt = """
        你是一名SQL执行专家。你的任务是执行给定的SQL语句并返回结果。

        请注意：
        1. 你将收到SQL语句和相关解释
        2. 你需要执行SQL语句并返回结果
        3. 如果执行成功，返回结果数据
        4. 如果执行失败，返回错误信息
        """

        return AssistantAgent(
            name="sql_executor",
            model_client=model_client,
            system_message=prompt,
            model_client_stream=True,
        )

    def _create_visualization_recommender_agent(self) -> AssistantAgent:
        """创建可视化推荐智能体"""
        prompt = """
        你是一名专业的数据可视化专家，负责根据提供的用户指令、SQL查询及其结果数据，推荐最合适的数据可视化方式，并给出详细的配置建议。

        ## 规则

        1. **分析SQL查询：** 理解SQL查询的目标，例如是进行趋势分析、比较不同类别的数据、展示数据分布还是显示详细数据。
        2. **分析查询结果数据结构：** 检查返回的数据包含哪些字段，它们的数据类型（数值型、分类型等），以及数据的组织方式（例如，是否包含时间序列、类别标签、数值指标等）。
        3. **基于数据结构和查询目标推荐可视化类型：**
            * 如果数据涉及**时间序列**且需要展示**趋势**，推荐 `"line"` (折线图)。
            * 如果需要**比较不同类别**的**数值大小**，推荐 `"bar"` (柱状图)。
            * 如果需要展示**各部分占总体的比例**，且类别数量不多，推荐 `"pie"` (饼图)。需要确保数值型字段是总量的一部分。
            * 如果需要展示**两个数值变量之间的关系**或**数据点的分布**，推荐 `"scatter"` (散点图)。
            * 如果数据结构复杂、细节重要，或者无法找到合适的图表类型清晰表达，推荐 `"table"` (表格)。
        4. **提供详细的可视化配置建议：** 根据选择的可视化类型，提供具体的配置参数。
            * **通用配置：** `"title"` (图表标题，应简洁明了地概括图表内容)。
            * **柱状图 (`"bar"`):**
                * `"xAxis"` (X轴字段名，通常是分类型字段)。
                * `"yAxis"` (Y轴字段名，通常是数值型字段)。
                * `"seriesName"` (系列名称，如果只有一个系列可以省略)。
            * **折线图 (`"line"`):**
                * `"xAxis"` (X轴字段名，通常是时间或有序的分类型字段)。
                * `"yAxis"` (Y轴字段名，通常是数值型字段)。
                * `"seriesName"` (系列名称，如果只有一个系列可以省略)。
            * **饼图 (`"pie"`):**
                * `"nameField"` (名称字段名，通常是分类型字段，用于显示饼图的标签)。
                * `"valueField"` (数值字段名，用于计算每个扇区的大小)。
                * `"seriesName"` (系列名称，如果只有一个系列可以省略)。
            * **散点图 (`"scatter"`):**
                * `"xAxis"` (X轴字段名，通常是数值型字段)。
                * `"yAxis"` (Y轴字段名，通常是数值型字段)。
                * `"seriesName"` (系列名称，如果只有一个系列可以省略)。
            * **表格 (`"table"`):** 不需要特定的坐标轴或系列配置，可以考虑添加 `"columns"` 字段，列出需要在表格中显示的字段名。
        5. **输出格式必须符合如下JSON格式:**

            ```json
            {
                "type": "可视化类型",
                "config": {
                    "title": "图表标题",
                    "xAxis": "X轴字段名",
                    "yAxis": "Y轴字段名",
                    "seriesName": "系列名称"
                    // 其他配置参数根据可视化类型添加
                }
            }
            ```

            对于饼图：

            ```json
            {
                "type": "pie",
                "config": {
                    "title": "图表标题",
                    "nameField": "名称字段名",
                    "valueField": "数值字段名",
                    "seriesName": "系列名称"
                }
            }
            ```

            对于表格：

            ```json
            {
                "type": "table",
                "config": {
                    "title": "数据表格",
                    "columns": ["字段名1", "字段名2", ...]
                }
            }
            ```

        ## 支持的可视化类型

        - `"bar"`: 柱状图
        - `"line"`: 折线图
        - `"pie"`: 饼图
        - `"scatter"`: 散点图
        - `"table"`: 表格(对于不适合图表的数据)
        特别注意：如果用户有对生成的图表有明确的特定要求，一定要严格遵守用户的指令。例如用户明确要求生成饼状图，就不能生成柱状图。

        重要：你的输出必须是一个有效的JSON对象，格式必须严格按照上述示例，不要添加任何额外的字段或解释。
        """

        return AssistantAgent(
            name="visualization_recommender",
            model_client=model_client,
            system_message=prompt,
            model_client_stream=True,
        )

    async def _handle_streaming_event(self, event, agent_name):
        """处理流式事件"""
        # 根据智能体名称映射到前端显示名称
        display_name = agent_name
        if agent_name == "query_analyzer":
            display_name = QUERY_ANALYZER_NAME
        elif agent_name == "sql_generator":
            display_name = SQL_GENERATOR_NAME
        elif agent_name == "sql_explainer":
            display_name = SQL_EXPLAINER_NAME
        elif agent_name == "sql_executor":
            display_name = SQL_EXECUTOR_NAME
        elif agent_name == "visualization_recommender":
            display_name = VISUALIZATION_RECOMMENDER_NAME
        elif agent_name == "user_proxy":
            display_name = USER_PROXY_NAME

        if self.collector and isinstance(event, ModelClientStreamingChunkEvent):
            await self.collector.collect(
                ResponseMessage(source=display_name, content=event.content)
            )

    async def _execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """执行SQL语句并返回结果"""
        try:
            # 清理SQL语句，移除可能的代码块标记
            clean_sql = sql.replace("```sql", "").replace("```", "").strip()
            results = dbAccess.run_sql(clean_sql)
            return results.to_dict("records")
        except Exception as e:
            # 处理执行错误
            return [{"error": str(e)}]

    async def process_query(self, query: str, collector: StreamResponseCollector = None):
        """处理自然语言查询，返回SQL和结果

        Args:
            query: 用户的自然语言查询
            collector: 可选的响应收集器，用于收集流式响应

        Returns:
            Text2SQLResponse: 包含SQL、解释和结果的响应对象
        """
        self.collector = collector

        # 创建所有智能体
        query_analyzer = self._create_query_analyzer_agent(query=query)
        sql_generator = self._create_sql_generator_agent()
        sql_explainer = self._create_sql_explainer_agent()
        sql_executor = self._create_sql_executor_agent()
        visualization_recommender = self._create_visualization_recommender_agent()

        # 如果有用户输入函数，创建用户代理智能体
        user_proxy = None
        if collector and collector.user_input:
            # 创建用户代理智能体
            # 创建一个处理用户输入的包装函数
            async def process_user_input(prompt: str, cancellation_token=None):
                # 等待用户输入，collector.user_input实际上是 text2sql.py中的user_input函数

                user_input = await collector.user_input(prompt, cancellation_token)

                # 如果用户输入APPROVE或同意，返回APPROVE
                if user_input and (user_input.strip().upper() == "APPROVE" or user_input.strip() == "同意"):
                    # 在返回前发送一个确认消息
                    if collector:
                        await collector.collect(
                            ResponseMessage(
                                source=USER_PROXY_NAME,
                                content="用户已同意分析结果，继续执行"
                            )
                        )
                    return "APPROVE"
                # 否则返回FEEDBACK加上用户输入
                else:
                    # 在返回前发送一个确认消息
                    if collector:
                        await collector.collect(
                            ResponseMessage(
                                source=USER_PROXY_NAME,
                                content=f"已收到用户反馈: {user_input}"
                            )
                        )
                    return f"FEEDBACK: {user_input}"

            # 创建用户代理智能体
            user_proxy = UserProxyAgent(
                name="user_proxy",
                input_func=process_user_input,
            )

        # 创建消息过滤器，控制每个智能体接收的消息
        # SQL生成器只需要看到查询分析结果
        filtered_sql_generator = MessageFilterAgent(
            name="sql_generator",
            wrapped_agent=sql_generator,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="query_analyzer", position="last", count=1),
                    PerSourceFilter(source="user_proxy", position="first", count=1)
                ]
            ),
        )

        # SQL解释器只需要看到SQL生成器的结果和原始查询
        filtered_sql_explainer = MessageFilterAgent(
            name="sql_explainer",
            wrapped_agent=sql_explainer,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="user", position="first", count=1),
                    PerSourceFilter(source="sql_generator", position="last", count=1)
                ]
            ),
        )

        # SQL执行器只需要看到SQL生成器的结果
        filtered_sql_executor = MessageFilterAgent(
            name="sql_executor",
            wrapped_agent=sql_executor,
            filter=MessageFilterConfig(
                per_source=[PerSourceFilter(source="sql_generator", position="last", count=1)]
            ),
        )

        # 可视化推荐器需要看到SQL执行结果和原始查询
        filtered_visualization_recommender = MessageFilterAgent(
            name="visualization_recommender",
            wrapped_agent=visualization_recommender,
            filter=MessageFilterConfig(
                per_source=[
                    PerSourceFilter(source="user", position="first", count=1),
                    PerSourceFilter(source="sql_generator", position="last", count=1),
                    PerSourceFilter(source="sql_executor", position="last", count=1)
                ]
            ),
        )

        # 构建工作流图
        builder = DiGraphBuilder()

        # 根据是否有用户代理智能体构建不同的图
        if user_proxy:
            # 添加节点
            builder.add_node(query_analyzer)
            builder.add_node(user_proxy)
            builder.add_node(filtered_sql_generator)
            builder.add_node(filtered_sql_explainer)
            builder.add_node(filtered_sql_executor)
            builder.add_node(filtered_visualization_recommender)

            # 定义执行流程，包含用户反馈循环
            # 查询分析器将结果发送给用户代理，使用无条件边
            builder.add_edge(query_analyzer, user_proxy)

            # 如果用户输入APPROVE，则继续到SQL生成器
            builder.add_edge(user_proxy, filtered_sql_generator, condition="APPROVE")

            # 如果用户输入FEEDBACK，则返回到查询分析器
            builder.add_edge(user_proxy, query_analyzer, condition="FEEDBACK")

            # SQL生成器将结果发送给SQL解释器
            builder.add_edge(filtered_sql_generator, filtered_sql_explainer)

            # SQL解释器将结果发送给SQL执行器
            builder.add_edge(filtered_sql_explainer, filtered_sql_executor)

            # SQL执行器将结果发送给可视化推荐器
            builder.add_edge(filtered_sql_executor, filtered_visualization_recommender)

            # 设置入口点
            builder.set_entry_point(query_analyzer)
        else:
            # 添加节点
            builder.add_node(query_analyzer)
            builder.add_node(filtered_sql_generator)
            builder.add_node(filtered_sql_explainer)
            builder.add_node(filtered_sql_executor)
            builder.add_node(filtered_visualization_recommender)

            # 定义执行流程，使用无条件边
            builder.add_edge(query_analyzer, filtered_sql_generator)
            builder.add_edge(filtered_sql_generator, filtered_sql_explainer)
            builder.add_edge(filtered_sql_explainer, filtered_sql_executor)
            builder.add_edge(filtered_sql_executor, filtered_visualization_recommender)

            # 设置入口点
            builder.set_entry_point(query_analyzer)

        # 构建图并创建流程
        graph = builder.build()
        flow = GraphFlow(
            participants=builder.get_participants(),
            graph=graph,
        )

        # 创建自定义处理器来拦截SQL执行步骤
        class SQLExecutionHandler:
            def __init__(self, parent):
                self.parent = parent
                self.sql = None
                self.explanation = None
                self.results = None
                self.visualization = None

            async def __call__(self, event):
                if isinstance(event, ModelClientStreamingChunkEvent) and parent.collector:
                    await parent.collector.collect(
                        ResponseMessage(source=event.source, content=event.content)
                    )
                    return
                # 捕获查询分析器的输出 - 只处理完整的文本消息
                if isinstance(event, TextMessage) and event.source == "query_analyzer":
                    if parent.collector:
                        await parent.collector.collect(
                            ResponseMessage(
                                source=event.source,
                                content="\n\n分析完成",
                                is_final=True
                            )
                        )
                    return

                # 处理用户代理智能体消息
                if isinstance(event, UserInputRequestedEvent) and event.source == "user_proxy":
                    # 发送提示消息，请求用户反馈
                    if parent.collector:
                        await parent.collector.collect(
                            ResponseMessage(
                                source=event.source,
                                content="请输入修改建议或者输入 'APPROVE' 或 '同意' 继续执行"
                            )
                        )
                    return

                # 捕获SQL生成器的输出
                if isinstance(event, TextMessage) and event.source == "sql_generator":
                    self.sql = event.content
                    if parent.collector:
                        await parent.collector.collect(
                            ResponseMessage(
                                source=event.source,
                                content="SQL语句已生成",
                                is_final=True,
                                result={"sql": self.sql}
                            )
                        )
                    return

                # 捕获SQL解释器的输出
                if isinstance(event, TextMessage) and event.source == "sql_explainer":
                    self.explanation = event.content
                    if parent.collector:
                        await parent.collector.collect(
                            ResponseMessage(
                                source=event.source,
                                content="\n\n解释完成",
                                is_final=True
                            )
                        )
                    return

                # 在SQL执行器步骤执行实际的SQL
                if isinstance(event, TextMessage) and event.source == "sql_executor":
                    if self.sql and not self.results:
                        # 执行SQL并获取结果
                        self.results = await parent._execute_sql(self.sql)
                        if parent.collector:
                            await parent.collector.collect(
                                ResponseMessage(
                                    source=event.source,
                                    content=f"SQL执行完成，获取到{len(self.results)}条结果"
                                )
                            )
                            await parent.collector.collect(
                                ResponseMessage(
                                    source=event.source,
                                    content="查询结果数据",
                                    is_final=True,
                                    result={"results": self.results}
                                )
                            )
                    return

                # 捕获可视化推荐器的输出
                if isinstance(event, TextMessage) and event.source == "visualization_recommender":
                    try:
                        # 清理JSON字符串，移除可能的标记
                        visualization_json = event.content.strip()
                        cleaned_json = visualization_json.replace("```json", "").replace("```", "").strip()
                        self.visualization = json.loads(cleaned_json)

                        # 打印可视化结果以便调试
                        print(f"\n可视化结果: {json.dumps(self.visualization, ensure_ascii=False)}")

                        # 如果是表格，则直接返回
                        if self.visualization.get("type") == "table":
                            if parent.collector:
                                await parent.collector.collect(
                                    ResponseMessage(
                                        source=event.source,
                                        content="可视化分析已完成",
                                        is_final=True
                                    )
                                )
                        else:
                            # 构建最终结果
                            # 确保可视化配置格式与 v1 版本兼容
                            visualization_config = self.visualization.get("config", {})

                            # 打印详细的可视化配置信息
                            print(f"\n可视化类型: {self.visualization.get('type', 'bar')}")
                            print(f"原始可视化配置: {json.dumps(visualization_config, ensure_ascii=False)}")

                            # 处理 v2 版本的可视化配置格式，确保与 v1 兼容
                            # 如果配置中没有必要的字段，根据可视化类型添加默认值
                            vis_type = self.visualization.get('type', 'bar')

                            # 确保配置中有 title
                            if 'title' not in visualization_config:
                                visualization_config['title'] = f'数据可视化 - {vis_type}'

                            # 根据不同的图表类型添加必要的配置
                            if vis_type in ['bar', 'line', 'scatter']:
                                # 确保有 xAxis 和 yAxis
                                if 'xAxis' not in visualization_config and self.results and len(self.results) > 0:
                                    visualization_config['xAxis'] = list(self.results[0].keys())[0]
                                if 'yAxis' not in visualization_config and self.results and len(self.results) > 0 and len(self.results[0].keys()) > 1:
                                    visualization_config['yAxis'] = list(self.results[0].keys())[1]
                            elif vis_type == 'pie':
                                # 确保有 nameField 和 valueField
                                if 'nameField' not in visualization_config and self.results and len(self.results) > 0:
                                    visualization_config['nameField'] = list(self.results[0].keys())[0]
                                if 'valueField' not in visualization_config and self.results and len(self.results) > 0 and len(self.results[0].keys()) > 1:
                                    visualization_config['valueField'] = list(self.results[0].keys())[1]

                            print(f"处理后的可视化配置: {json.dumps(visualization_config, ensure_ascii=False)}")

                            # 构建最终结果
                            final_result = Text2SQLResponse(
                                sql=self.sql,
                                explanation=self.explanation,
                                results=self.results,
                                visualization_type=self.visualization.get("type", "bar"),
                                visualization_config=visualization_config
                            )

                            if parent.collector:
                                # 打印最终结果以便调试
                                print(f"\n最终结果: {json.dumps(final_result.model_dump(), ensure_ascii=False)}")

                                # 确保结果中包含可视化配置
                                result_data = final_result.model_dump()

                                # 发送最终结果
                                await parent.collector.collect(
                                    ResponseMessage(
                                        source=event.source,
                                        content="处理完成，返回最终结果",
                                        is_final=True,
                                        result=result_data
                                    )
                                )
                    except Exception as e:
                        if parent.collector:
                            await parent.collector.collect(
                                ResponseMessage(
                                    source=event.source,
                                    content=f"处理可视化推荐时出错: {str(e)}",
                                    is_final=True
                                )
                            )

        # 创建处理器实例
        parent = self
        handler = SQLExecutionHandler(parent)

        # 运行工作流
        stream = flow.run_stream(task=query)
        async for event in stream:
            await handler(event)

        # 构建并返回最终结果
        # if handler.sql and handler.results:
        #     return Text2SQLResponse(
        #         sql=handler.sql,
        #         explanation=handler.explanation or "",
        #         results=handler.results,
        #         visualization_type=handler.visualization.get("type", "bar") if handler.visualization else None,
        #         visualization_config=handler.visualization.get("config", {}) if handler.visualization else None
        #     )
        # else:
        #     # 处理失败情况
        #     return Text2SQLResponse(
        #         sql="",
        #         explanation="处理查询时出错",
        #         results=[],
        #         visualization_type=None,
        #         visualization_config=None
        #     )


class Text2SQLService:
    """处理自然语言到SQL转换的服务类"""

    def __init__(self, db_type: str = DB_TYPE):
        """初始化Text2SQL服务

        Args:
            db_type: 数据库类型，默认为DB_TYPE常量
        """
        self.db_type = db_type
        self.graph_flow = Text2SQLGraphFlow(db_type=db_type)

    async def process_query(self, query: str, collector: StreamResponseCollector = None):
        """处理自然语言查询，返回SQL和结果

        Args:
            query: 用户的自然语言查询
            collector: 可选的响应收集器，用于收集流式响应

        Returns:
            Text2SQLResponse: 包含SQL、解释和结果的响应对象
        """
        return await self.graph_flow.process_query(query, collector)
