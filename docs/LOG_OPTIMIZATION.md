# 日志优化说明

## 问题描述

在运行 API 服务器时,健康检查端点 `/api/health` 或 `/health` 会产生大量重复的访问日志:

```
INFO:     127.0.0.1:54808 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:48270 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:48278 - "GET /api/health HTTP/1.1" 200 OK
...
```

这些日志会淹没其他重要的日志信息,影响日志可读性。

## 解决方案

通过添加 Python logging 过滤器来过滤掉健康检查端点的访问日志。

### 实现位置

1. **app/main.py** (第32-48行)
2. **api_server.py** (第15-38行)

### 核心代码

```python
class HealthCheckFilter(logging.Filter):
    """过滤健康检查端点的访问日志"""

    def filter(self, record: logging.LogRecord) -> bool:
        # 过滤包含 /health 或 /api/health 的日志
        message = record.getMessage()
        return not any(
            pattern in message
            for pattern in ["/health", "GET /api/health", "GET /health"]
        )


# 应用过滤器到 uvicorn 的 access logger
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
```

### 工作原理

1. **创建过滤器类**: 继承 `logging.Filter`
2. **实现 filter 方法**: 返回 `False` 表示过滤掉该日志
3. **模式匹配**: 检查日志消息中是否包含健康检查端点的路径
4. **应用过滤器**: 添加到 `uvicorn.access` logger

### 过滤的模式

- `/health` - 简单路径
- `/api/health` - API 前缀路径
- `GET /health` - 完整请求日志
- `GET /api/health` - 完整请求日志

## 效果对比

### 优化前

```
INFO:     127.0.0.1:54808 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:48270 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:48278 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:48284 - "POST /api/agent/chat HTTP/1.1" 200 OK
INFO:     127.0.0.1:40850 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:52454 - "GET /api/health HTTP/1.1" 200 OK
INFO:     127.0.0.1:37808 - "GET /api/health HTTP/1.1" 200 OK
```

### 优化后

```
INFO:     127.0.0.1:48284 - "POST /api/agent/chat HTTP/1.1" 200 OK
```

只显示实际的业务请求,健康检查日志被过滤。

## 验证

启动服务器后,发送健康检查请求:

```bash
# 发送健康检查请求
curl http://localhost:8000/api/health

# 查看日志
# 应该不会看到 health check 的日志
```

发送业务请求:

```bash
# 发送业务请求
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "测试查询"}'

# 查看日志
# 应该能看到这个请求的日志
```

## 自定义配置

如果需要调整过滤规则,可以修改 `HealthCheckFilter.filter` 方法:

### 示例1: 只在生产环境过滤

```python
import os

class HealthCheckFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # 只在生产环境过滤
        if os.getenv("ENVIRONMENT") != "production":
            return True

        message = record.getMessage()
        return not any(
            pattern in message
            for pattern in ["/health", "GET /api/health"]
        )
```

### 示例2: 过滤多个端点

```python
class HealthCheckFilter(logging.Filter):
    """过滤多个监控端点的访问日志"""

    FILTERED_PATTERNS = [
        "/health",
        "/api/health",
        "/metrics",      # Prometheus 指标
        "/readiness",    # Kubernetes 就绪探针
        "/liveness",     # Kubernetes 存活探针
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(pattern in message for pattern in self.FILTERED_PATTERNS)
```

### 示例3: 定期显示一次健康检查

```python
import time

class HealthCheckFilter(logging.Filter):
    """每隔N秒显示一次健康检查日志"""

    def __init__(self, interval_seconds: int = 60):
        super().__init__()
        self.interval = interval_seconds
        self.last_shown = 0

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()

        # 如果不是健康检查,正常显示
        if not any(p in message for p in ["/health", "/api/health"]):
            return True

        # 如果是健康检查,判断是否需要显示
        now = time.time()
        if now - self.last_shown >= self.interval:
            self.last_shown = now
            return True  # 显示这一次

        return False  # 过滤掉


# 使用: 每60秒显示一次健康检查日志
logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter(interval_seconds=60))
```

## 其他日志优化建议

### 1. 调整日志级别

在 `.env` 中配置:

```bash
# 生产环境使用 WARNING 或 ERROR
LOG_LEVEL=WARNING

# 开发环境使用 INFO 或 DEBUG
LOG_LEVEL=INFO
```

在代码中使用:

```python
import os

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level))
```

### 2. 使用结构化日志

安装 `python-json-logger`:

```bash
pip install python-json-logger
```

配置:

```python
from pythonjsonlogger import jsonlogger

handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter('%(asctime)s %(name)s %(levelname)s %(message)s')
handler.setFormatter(formatter)
logging.getLogger().addHandler(handler)
```

### 3. 日志轮转

使用 `RotatingFileHandler`:

```python
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler(
    'app.log',
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
logging.getLogger().addHandler(handler)
```

### 4. 异步日志

使用 `QueueHandler` 避免日志阻塞:

```python
from logging.handlers import QueueHandler, QueueListener
import queue

log_queue = queue.Queue()
queue_handler = QueueHandler(log_queue)

file_handler = logging.FileHandler('app.log')
listener = QueueListener(log_queue, file_handler)

logging.getLogger().addHandler(queue_handler)
listener.start()
```

## 监控和告警

即使过滤了日志,仍然建议使用监控系统跟踪健康检查:

### Prometheus 示例

```python
from prometheus_client import Counter

health_check_counter = Counter(
    'health_check_requests_total',
    'Total health check requests'
)

@app.get("/api/health")
async def health_check():
    health_check_counter.inc()
    return {"status": "healthy"}
```

### 自定义监控

```python
import time
from collections import deque

class HealthCheckMonitor:
    def __init__(self, window_seconds: int = 60):
        self.requests = deque()
        self.window = window_seconds

    def record(self):
        now = time.time()
        self.requests.append(now)
        # 清理过期记录
        cutoff = now - self.window
        while self.requests and self.requests[0] < cutoff:
            self.requests.popleft()

    def get_rate(self) -> float:
        """返回每秒请求数"""
        if not self.requests:
            return 0.0
        return len(self.requests) / self.window


monitor = HealthCheckMonitor()

@app.get("/api/health")
async def health_check():
    monitor.record()
    return {"status": "healthy"}

@app.get("/api/metrics")
async def metrics():
    return {"health_check_rate": monitor.get_rate()}
```

## 总结

通过添加日志过滤器:

✅ **减少日志噪音**: 过滤掉重复的健康检查日志
✅ **提升可读性**: 只显示重要的业务日志
✅ **保持功能**: 健康检查功能不受影响
✅ **灵活配置**: 可根据需求自定义过滤规则
✅ **零性能开销**: 过滤器在日志输出前执行,不影响业务逻辑

日志优化是生产环境必不可少的配置,合理的日志策略能显著提升系统的可维护性!
