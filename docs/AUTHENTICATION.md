# 员工认证与公众会话

员工工作台使用服务端验证的登录 Cookie。公众咨询无需登录，但只能读取自己持有会话凭证的对话。页面入口或 `X-Client-Audience` 只能选择入口，不能授予员工权限。

## 配置员工账号

项目不提供默认账号、密码或签名密钥，也不会在缺少配置时自动生成账号。在部署环境设置以下变量，再重启后端：

| 环境变量 | 用途 | 默认值 |
| --- | --- | --- |
| `SECURITY__API_DEFAULT_USERNAME` | 当前部署的员工账号 | 未配置 |
| `SECURITY__API_DEFAULT_PASSWORD` | 员工登录密码 | 未配置 |
| `SECURITY__API_DEFAULT_FULLNAME` | 员工显示名称 | `Administrator` |
| `SECURITY__JWT_SECRET_KEY` | Cookie 与公众会话的签名密钥，至少 32 个 UTF-8 字节 | 未配置 |
| `SECURITY__JWT_ALGORITHM` | 签名算法，支持 `HS256`、`HS384`、`HS512` | `HS256` |
| `SECURITY__JWT_ACCESS_TOKEN_EXP_MINUTES` | 员工登录有效期，正整数分钟 | `60` |
| `SECURITY__AUTH_COOKIE_SECURE` | 仅通过 HTTPS 发送员工 Cookie | `false`，便于 localhost 开发 |
| `SECURITY__PUBLIC_SESSION_EXP_HOURS` | 公众单个会话凭证有效期，正整数小时 | `24` |

密码应由部署者自行设置。签名密钥应使用密码学随机值；例如可在可信终端使用 `python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成，并通过部署环境的密钥配置保存，不要提交到仓库。生产环境使用 HTTPS，并设置 `SECURITY__AUTH_COOKIE_SECURE=true`。

缺少员工账号、密码或合格的签名密钥时，员工登录与员工接口返回 `503`，中文错误指出需要配置的变量。公众会话签发与验证也需要签名密钥，但不要求员工账号。`SECURITY__DISABLE_AUTH` 仅属于旧入口；新员工认证不会受它影响。

当前账号从环境配置读入内存，没有新增账号表或数据库迁移。修改账号或密码后需要重启后端；更换签名密钥会使已签发的员工 Cookie 和公众会话凭证失效。

## 登录接口

本地查看前端时，可在独立端口运行 `.venv\Scripts\python.exe -m uvicorn scripts.frontend_access:app --host 127.0.0.1 --port 8018 --env-file .env.auth.local`，并在 `web/.env.local` 设置 `GLYPH_API_PROXY_TARGET=http://127.0.0.1:8018` 后重启 Vite。`.env.auth.local` 使用上面的真实账号与签名配置，属于忽略提交的本机文件。此入口复用正式登录、Cookie和CSRF校验，允许已登录工作人员读取仓库现有GraphML及试算规则草稿；资料处理、模型问答、规则生成/保存等未启动接口明确返回503。它不提供假资料、假问答或假生成结果。完整后端可用后将代理指回对应端口。

- `POST /api/auth/login`：JSON 请求体为 `{"username": "员工账号", "password": "员工密码"}`。错误账号、错误密码与停用账号统一返回 `401`。
- `GET /api/auth/session`：校验员工 Cookie，返回当前账号、有效期和 CSRF token；没有有效登录时返回 `401`。
- `POST /api/auth/logout`：携带员工 Cookie 与 `X-CSRF-Token`。验证通过后清除 Cookie，返回 `{"success": true}`。

登录与读取当前会话的响应结构为：

```json
{
  "user": {"username": "员工账号", "full_name": "显示名称"},
  "expires_at": "有效期的 ISO 8601 时间",
  "csrf_token": "当前会话的请求校验值"
}
```

认证 JWT 仅通过 `glyph_staff_session` Cookie 发送，不出现在响应 JSON，也不存入 localStorage。Cookie 设置 `HttpOnly`、`SameSite=Strict`、`Path=/api`，没有跨域 Domain；`Secure` 由上述环境变量控制。前后端应使用同源访问或同源 API 代理。

员工写请求必须带当前会话返回的 `X-CSRF-Token`；`GET`、`HEAD`、`OPTIONS` 不要求该请求头。服务端验证签名、到期时间、`aud`、`purpose`、员工角色以及账号仍然存在且未停用。登录态响应使用 `Cache-Control: no-store`。关闭浏览器以外的客户端仍可能持有已复制的 Cookie：当前无服务端会话撤销表，退出登录只清除此浏览器的 Cookie，复制件会在到期或签名密钥轮换时失效。

## 对话权限

共享聊天接口默认使用公众权限；员工聊天必须发送 `X-Client-Audience: staff`，并同时通过员工 Cookie 与写请求的 CSRF 校验。其他 audience 值会被拒绝。

员工对话保存在 `staff:<用户名 SHA-256 前 24 位>:session_<标识>` 命名空间；只能读取当前员工的命名空间。公众新对话保存在随机的 `public:<UUID>` 标识下，返回给客户端的 `session_id` 是具有 `consultation` audience、purpose 和有效期的签名凭证。客户端后续必须继续发送该凭证，不能改用内部存储标识。

公众无 Cookie 或 CSRF 初始化步骤。凭证只授权单个公众对话，无法列举所有历史、访问员工对话或使用员工管理功能。原始任意会话 ID、伪造凭证、过期凭证和用于读取历史的无签名临时 ID 都会被拒绝；前端 `session_...` 临时 ID 只用于发起新对话。凭证属于持有者即可使用的访问凭证，分享它也会分享对应对话的访问权。

`/api/agent/sessions` 及单条会话读取、消息读取、删除接口仅供工作人员使用，并校验账号命名空间。公众咨询记录在浏览器本机读取，不通过这些GET接口恢复。公众凭证仅在聊天POST请求体和SSE事件中传递，不放入URL路径或查询参数。公众提交业务数据库连接、Text2SQL模式或用户资料ID时返回403；即便模型选择相关工具，服务层也会拒绝私有工具调用。

知识库、知识图谱、规则管理与数据库连接API整体需要工作人员登录；健康检查保持公开。公众问答仍检索现有政策语料，本次没有新增“内部语料/公开语料”的发布审批或按文档授权能力。

## 浏览器记录与附件

公众记录继续使用原有localStorage键；工作人员记录以用户名分区保存在sessionStorage，显式退出清理本标签页当前账号缓存与资料/规则内存状态。公众记录和其他账号的缓存不会一起删除。原来未区分身份的本机记录不自动归属某个工作人员，旧记录如含内部内容，应由实际使用者确认后清理。

新公众附件存入 `uploads/attachments/public`，随机UUID下载URL不列举，但持有URL的人可下载，不适合上传内部或敏感资料。工作人员附件存入独立账号目录，`/api/uploads/staff` 上传与下载均验证身份。两类上传都限制支持的文件扩展名和实际10MB上限，模型附件路径只接受当前入口所属目录。原平铺附件不删除、不自动分配归属，也不再由公众下载路由提供；需要重新上传到正确入口。

## 本次验证状态

按用户要求暂不执行测试。已新增认证、主API挂载、公众/工作人员会话、SSE、附件隔离与前端缓存/安全返回地址回归源码，均未运行；未执行lint、构建或数据库检查。随后已通过本地真实账号进入工作台，R20挂载的只读图谱可显示仓库GraphML；这不代表正式完整后端、所有权限回归或草稿计算接口已通过联调。

历史数据不执行自动迁移。没有员工所有者信息的旧会话不会自动划入某个员工账号；旧的原始公众会话 ID 也不会成为有效的访问凭证。

密码使用标准库 PBKDF2-HMAC-SHA256、随机盐和 600,000 次迭代；只涉及当前内存配置账号，没有为不存在的持久化旧密码添加迁移逻辑。依据：[Python 3.10 hashlib 文档](https://docs.python.org/3.10/library/hashlib.html#hashlib.pbkdf2_hmac)、[OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html#pbkdf2)。
