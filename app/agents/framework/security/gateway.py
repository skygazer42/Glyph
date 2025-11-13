"""
安全网关 - 系统安全的第一道防线
实现认证、授权、限流、输入验证、内容过滤、审计日志等功能
"""

import os
import re
import jwt
import time
import hashlib
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from app.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class User:
    """用户模型"""
    id: str
    username: str
    roles: List[str]
    permissions: List[str]
    metadata: Dict[str, Any] = None


@dataclass
class SecurityContext:
    """安全上下文"""
    user: User
    timestamp: datetime
    ip_address: str
    user_agent: str
    request_id: str


class SecurityGateway:
    """
    安全网关 - 统一的安全检查入口

    功能:
    1. 身份认证 (JWT)
    2. 授权检查 (RBAC)
    3. 速率限制 (令牌桶)
    4. 输入验证 (防注入)
    5. 内容过滤 (敏感词)
    6. 审计日志
    """

    def __init__(self):
        self.auth_manager = AuthenticationManager()
        self.authz_manager = AuthorizationManager()
        self.rate_limiter = RateLimiter()
        self.input_validator = InputValidator()
        self.content_filter = ContentFilter()
        self.audit_logger = AuditLogger()

    async def process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理请求的完整安全检查流程

        Args:
            request: 请求数据，包含:
                - token: JWT令牌
                - query: 查询文本
                - action: 操作类型 (可选)
                - ip_address: IP地址
                - user_agent: 用户代理

        Returns:
            验证通过的请求数据

        Raises:
            SecurityError: 安全检查失败
        """
        request_id = self._generate_request_id()

        try:
            # 1. 身份验证
            logger.info(f"[{request_id}] 开始身份验证")
            user = await self.auth_manager.authenticate(request)
            if not user:
                self.audit_logger.log_auth_failure(request, request_id)
                raise AuthenticationError("身份验证失败：令牌无效或已过期")

            # 2. 速率限制
            logger.info(f"[{request_id}] 检查速率限制 - 用户: {user.id}")
            if not await self.rate_limiter.check_limit(user.id):
                self.audit_logger.log_rate_limit(user.id, request_id)
                raise RateLimitError("请求过于频繁，请稍后再试")

            # 3. 授权检查
            action = request.get('action', 'query:read')
            logger.info(f"[{request_id}] 检查授权 - 用户: {user.id}, 操作: {action}")
            if not await self.authz_manager.authorize(user, action):
                self.audit_logger.log_authz_failure(user.id, action, request_id)
                raise AuthorizationError(f"无权执行操作: {action}")

            # 4. 输入验证
            query = request.get('query', '')
            logger.info(f"[{request_id}] 验证输入 - 长度: {len(query)}")
            validated_input = await self.input_validator.validate(query)
            if not validated_input['valid']:
                self.audit_logger.log_invalid_input(
                    user.id, query, validated_input['reason'], request_id
                )
                raise ValidationError(f"输入验证失败: {validated_input['reason']}")

            # 5. 内容过滤
            logger.info(f"[{request_id}] 过滤内容")
            filtered_query = await self.content_filter.filter(validated_input['query'])

            # 6. 审计日志
            await self.audit_logger.log_request(
                user.id, filtered_query, request, request_id
            )

            # 构建安全上下文
            security_context = SecurityContext(
                user=user,
                timestamp=datetime.now(),
                ip_address=request.get('ip_address', 'unknown'),
                user_agent=request.get('user_agent', 'unknown'),
                request_id=request_id
            )

            logger.info(f"[{request_id}] 安全检查通过")

            return {
                'user': user,
                'query': filtered_query,
                'original_request': request,
                'security_context': security_context,
                'request_id': request_id
            }

        except SecurityError:
            raise
        except Exception as e:
            logger.error(f"[{request_id}] 安全检查异常: {e}")
            raise SecurityError(f"安全检查失败: {str(e)}")

    @staticmethod
    def _generate_request_id() -> str:
        """生成唯一请求ID"""
        timestamp = str(time.time()).encode()
        return hashlib.sha256(timestamp).hexdigest()[:16]


class AuthenticationManager:
    """
    身份认证管理器
    支持JWT令牌验证和会话管理
    """

    def __init__(self):
        self.jwt_secret = os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
        self.jwt_algorithm = 'HS256'
        self.token_expire_time = timedelta(hours=24)

        # 会话存储 (生产环境应使用Redis)
        self.session_store = {}

    async def authenticate(self, request: Dict[str, Any]) -> Optional[User]:
        """
        验证用户身份

        Args:
            request: 包含token的请求

        Returns:
            验证成功返回User对象，否则返回None
        """
        token = request.get('token')
        if not token:
            logger.warning("请求缺少token")
            return None

        try:
            # 验证JWT
            payload = self._verify_jwt(token)
            user_id = payload.get('user_id')

            if not user_id:
                logger.warning("JWT payload缺少user_id")
                return None

            # 检查会话
            session = self.session_store.get(user_id)
            if session:
                if session['expires_at'] < datetime.now():
                    logger.info(f"用户 {user_id} 会话已过期")
                    del self.session_store[user_id]
                    return None

            # 构建用户对象
            user = User(
                id=user_id,
                username=payload.get('username', 'unknown'),
                roles=payload.get('roles', ['guest']),
                permissions=payload.get('permissions', []),
                metadata=payload.get('metadata', {})
            )

            logger.info(f"用户 {user.username} 认证成功")
            return user

        except jwt.ExpiredSignatureError:
            logger.warning("JWT令牌已过期")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT令牌无效: {e}")
            return None
        except Exception as e:
            logger.error(f"认证异常: {e}")
            return None

    def _verify_jwt(self, token: str) -> Dict:
        """验证JWT令牌"""
        return jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])

    def create_token(self, user: User) -> str:
        """
        创建JWT令牌

        Args:
            user: 用户对象

        Returns:
            JWT令牌字符串
        """
        payload = {
            'user_id': user.id,
            'username': user.username,
            'roles': user.roles,
            'permissions': user.permissions,
            'exp': datetime.utcnow() + self.token_expire_time,
            'iat': datetime.utcnow()
        }

        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)

        # 创建会话
        self.session_store[user.id] = {
            'token': token,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + self.token_expire_time
        }

        return token


class AuthorizationManager:
    """
    授权管理器 - 基于角色的访问控制(RBAC)
    """

    def __init__(self):
        # 角色-权限映射
        self.role_permissions = {
            'admin': ['*'],  # 管理员拥有所有权限
            'user': [
                'query:read',
                'policy:read',
                'calculation:execute',
                'comparison:execute',
                'dsl:read',
                'knowledge:read'
            ],
            'analyst': [
                'query:read',
                'policy:read',
                'policy:write',
                'calculation:execute',
                'comparison:execute',
                'dsl:read',
                'dsl:write',
                'knowledge:read',
                'knowledge:write'
            ],
            'guest': [
                'query:read',
                'policy:read'
            ]
        }

    async def authorize(self, user: User, action: str) -> bool:
        """
        检查用户是否有权限执行操作

        Args:
            user: 用户对象
            action: 操作标识 (格式: resource:operation)

        Returns:
            True表示有权限，False表示无权限
        """
        if not action:
            return True

        # 检查用户的所有角色
        for role in user.roles:
            permissions = self.role_permissions.get(role, [])

            # 管理员拥有所有权限
            if '*' in permissions:
                logger.debug(f"用户 {user.username} 是管理员，授权通过")
                return True

            # 检查具体权限
            if action in permissions:
                logger.debug(f"用户 {user.username} 拥有权限 {action}")
                return True

            # 检查通配符权限 (例如: policy:*)
            resource = action.split(':')[0]
            wildcard = f"{resource}:*"
            if wildcard in permissions:
                logger.debug(f"用户 {user.username} 拥有通配符权限 {wildcard}")
                return True

        logger.warning(f"用户 {user.username} 无权执行操作 {action}")
        return False

    def add_role_permission(self, role: str, permission: str):
        """添加角色权限"""
        if role not in self.role_permissions:
            self.role_permissions[role] = []

        if permission not in self.role_permissions[role]:
            self.role_permissions[role].append(permission)
            logger.info(f"为角色 {role} 添加权限 {permission}")

    def remove_role_permission(self, role: str, permission: str):
        """移除角色权限"""
        if role in self.role_permissions:
            if permission in self.role_permissions[role]:
                self.role_permissions[role].remove(permission)
                logger.info(f"从角色 {role} 移除权限 {permission}")


class RateLimiter:
    """
    速率限制器 - 令牌桶算法
    支持多级限制：每秒、每分钟、每小时、每天
    """

    def __init__(self):
        # 令牌桶
        self.buckets = defaultdict(lambda: {
            'tokens': 100,  # 初始令牌数
            'last_update': time.time(),
            'capacity': 100,  # 桶容量
            'refill_rate': 10  # 每秒补充令牌数
        })

        # 不同时间窗口的限制
        self.time_windows = defaultdict(lambda: defaultdict(list))

        # 限制配置
        self.limits = {
            'per_second': 10,
            'per_minute': 60,
            'per_hour': 1000,
            'per_day': 10000
        }

    async def check_limit(self, user_id: str) -> bool:
        """
        检查是否超过速率限制

        Args:
            user_id: 用户ID

        Returns:
            True表示未超限，False表示已超限
        """
        now = time.time()

        # 1. 令牌桶检查
        if not self._check_token_bucket(user_id, now):
            logger.warning(f"用户 {user_id} 超过令牌桶限制")
            return False

        # 2. 时间窗口检查
        if not self._check_time_windows(user_id, now):
            logger.warning(f"用户 {user_id} 超过时间窗口限制")
            return False

        return True

    def _check_token_bucket(self, user_id: str, now: float) -> bool:
        """令牌桶算法检查"""
        bucket = self.buckets[user_id]

        # 更新令牌
        time_passed = now - bucket['last_update']
        bucket['tokens'] = min(
            bucket['capacity'],
            bucket['tokens'] + time_passed * bucket['refill_rate']
        )
        bucket['last_update'] = now

        # 消耗令牌
        if bucket['tokens'] >= 1:
            bucket['tokens'] -= 1
            return True

        return False

    def _check_time_windows(self, user_id: str, now: float) -> bool:
        """时间窗口检查"""
        windows = self.time_windows[user_id]

        # 清理过期记录
        windows['second'] = [t for t in windows['second'] if now - t < 1]
        windows['minute'] = [t for t in windows['minute'] if now - t < 60]
        windows['hour'] = [t for t in windows['hour'] if now - t < 3600]
        windows['day'] = [t for t in windows['day'] if now - t < 86400]

        # 检查各时间窗口
        if len(windows['second']) >= self.limits['per_second']:
            return False
        if len(windows['minute']) >= self.limits['per_minute']:
            return False
        if len(windows['hour']) >= self.limits['per_hour']:
            return False
        if len(windows['day']) >= self.limits['per_day']:
            return False

        # 记录本次请求
        windows['second'].append(now)
        windows['minute'].append(now)
        windows['hour'].append(now)
        windows['day'].append(now)

        return True

    def get_usage(self, user_id: str) -> Dict[str, int]:
        """获取用户的当前使用情况"""
        now = time.time()
        windows = self.time_windows[user_id]

        # 清理过期记录
        windows['second'] = [t for t in windows['second'] if now - t < 1]
        windows['minute'] = [t for t in windows['minute'] if now - t < 60]
        windows['hour'] = [t for t in windows['hour'] if now - t < 3600]
        windows['day'] = [t for t in windows['day'] if now - t < 86400]

        return {
            'per_second': len(windows['second']),
            'per_minute': len(windows['minute']),
            'per_hour': len(windows['hour']),
            'per_day': len(windows['day']),
            'tokens_remaining': int(self.buckets[user_id]['tokens'])
        }


class InputValidator:
    """
    输入验证器
    防止各种注入攻击和恶意输入
    """

    def __init__(self):
        self.max_query_length = 2000
        self.max_tokens = 1500

        # 危险模式
        self.dangerous_patterns = [
            # XSS攻击
            (r'<script[^>]*>.*?</script>', 'XSS攻击'),
            (r'javascript:', 'JavaScript注入'),
            (r'on\w+\s*=', '事件处理器注入'),

            # SQL注入
            (r'(union|select|insert|update|delete|drop|create|alter)\s+', 'SQL注入'),
            (r'[;\'].*(-{2}|#)', 'SQL注释注入'),

            # 命令注入
            (r'[;\|\&\$\`]', '命令注入'),
            (r'\$\(.*\)', '命令替换'),

            # 路径遍历
            (r'\.\./', '路径遍历'),
            (r'%2e%2e/', 'URL编码路径遍历'),
        ]

    async def validate(self, query: str) -> Dict[str, Any]:
        """
        验证输入查询

        Args:
            query: 输入查询文本

        Returns:
            验证结果字典 {'valid': bool, 'query': str, 'reason': str}
        """
        # 空值检查
        if not query or not query.strip():
            return {
                'valid': False,
                'reason': '查询不能为空'
            }

        # 长度检查
        if len(query) > self.max_query_length:
            return {
                'valid': False,
                'reason': f'查询长度超过限制 ({self.max_query_length}字符)'
            }

        # 危险模式检查
        for pattern, attack_type in self.dangerous_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                logger.warning(f"检测到{attack_type}: {query[:100]}")
                return {
                    'valid': False,
                    'reason': f'检测到潜在的{attack_type}'
                }

        # Unicode字符检查
        try:
            query.encode('utf-8')
        except UnicodeEncodeError:
            return {
                'valid': False,
                'reason': '包含非法字符'
            }

        # 控制字符检查
        if any(ord(c) < 32 and c not in '\n\r\t' for c in query):
            return {
                'valid': False,
                'reason': '包含控制字符'
            }

        return {
            'valid': True,
            'query': query.strip()
        }


class ContentFilter:
    """
    内容过滤器
    过滤敏感词和不当内容
    """

    def __init__(self):
        self.sensitive_words = self._load_sensitive_words()

    async def filter(self, text: str) -> str:
        """
        过滤敏感内容

        Args:
            text: 输入文本

        Returns:
            过滤后的文本
        """
        filtered = text

        # 敏感词替换
        for word in self.sensitive_words:
            if word in filtered:
                filtered = filtered.replace(word, '*' * len(word))
                logger.info(f"过滤敏感词: {word}")

        return filtered

    def _load_sensitive_words(self) -> List[str]:
        """
        加载敏感词库
        生产环境应从文件或数据库加载
        """
        # 示例敏感词列表
        words = []

        # 尝试从文件加载
        sensitive_words_file = Path("config/sensitive_words.txt")
        if sensitive_words_file.exists():
            with open(sensitive_words_file, 'r', encoding='utf-8') as f:
                words = [line.strip() for line in f if line.strip()]

        return words


class AuditLogger:
    """
    审计日志记录器
    记录所有安全相关事件
    """

    def __init__(self):
        self.log_dir = settings.system.logs_dir / "audit"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.setup_logger()

    def setup_logger(self):
        """配置日志记录器"""
        self.logger = logging.getLogger('audit')
        self.logger.setLevel(logging.INFO)

        # 按日期分割的文件处理器
        log_file = self.log_dir / f"audit_{datetime.now().strftime('%Y%m%d')}.log"
        fh = logging.FileHandler(log_file, encoding='utf-8')

        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    async def log_request(self, user_id: str, query: str, request: Dict, request_id: str):
        """记录正常请求"""
        self.logger.info(
            f"REQUEST | ID={request_id} | USER={user_id} | "
            f"QUERY={query[:100]} | IP={request.get('ip_address', 'unknown')}"
        )

    def log_auth_failure(self, request: Dict, request_id: str):
        """记录认证失败"""
        token = request.get('token', 'None')
        token_preview = token[:20] if token and token != 'None' else 'None'

        self.logger.warning(
            f"AUTH_FAILURE | ID={request_id} | "
            f"IP={request.get('ip_address', 'unknown')} | TOKEN={token_preview}"
        )

    def log_authz_failure(self, user_id: str, action: str, request_id: str):
        """记录授权失败"""
        self.logger.warning(
            f"AUTHZ_FAILURE | ID={request_id} | USER={user_id} | ACTION={action}"
        )

    def log_rate_limit(self, user_id: str, request_id: str):
        """记录速率限制"""
        self.logger.warning(
            f"RATE_LIMIT | ID={request_id} | USER={user_id}"
        )

    def log_invalid_input(self, user_id: str, query: str, reason: str, request_id: str):
        """记录无效输入"""
        self.logger.warning(
            f"INVALID_INPUT | ID={request_id} | USER={user_id} | "
            f"REASON={reason} | QUERY={query[:100]}"
        )


# ==================== 异常类 ====================

class SecurityError(Exception):
    """安全相关异常的基类"""
    pass


class AuthenticationError(SecurityError):
    """身份验证失败"""
    pass


class AuthorizationError(SecurityError):
    """授权失败"""
    pass


class RateLimitError(SecurityError):
    """速率限制"""
    pass


class ValidationError(SecurityError):
    """验证失败"""
    pass


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""

    # 初始化安全网关
    gateway = SecurityGateway()

    # 创建测试用户令牌
    test_user = User(
        id='user123',
        username='testuser',
        roles=['user'],
        permissions=[]
    )
    token = gateway.auth_manager.create_token(test_user)

    # 模拟请求
    request = {
        'token': token,
        'query': '济南市家电补贴政策是什么？',
        'action': 'query:read',
        'ip_address': '192.168.1.100',
        'user_agent': 'Mozilla/5.0'
    }

    try:
        # 处理请求
        validated_request = await gateway.process_request(request)

        print("✓ 安全检查通过")
        print(f"用户: {validated_request['user'].username}")
        print(f"查询: {validated_request['query']}")
        print(f"请求ID: {validated_request['request_id']}")

        # 执行业务逻辑...

    except SecurityError as e:
        print(f"✗ 安全检查失败: {e}")


if __name__ == '__main__':
    import asyncio
    asyncio.run(example_usage())
