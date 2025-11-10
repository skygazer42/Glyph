"""
系统监控模块
提供实时监控、指标收集、告警管理等功能
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Callable, Optional
from collections import deque, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
import json

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """指标数据"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'name': self.name,
            'value': self.value,
            'timestamp': self.timestamp.isoformat(),
            'tags': self.tags
        }


@dataclass
class Alert:
    """告警"""
    level: str  # INFO, WARNING, ERROR, CRITICAL
    message: str
    timestamp: datetime
    metric: Metric
    threshold: float

    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            'level': self.level,
            'message': self.message,
            'timestamp': self.timestamp.isoformat(),
            'metric': self.metric.to_dict(),
            'threshold': self.threshold
        }


class SystemMonitor:
    """
    系统监控器

    功能:
    1. 指标收集与存储
    2. 阈值监控
    3. 告警触发
    4. 统计计算
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

        # 指标存储 (指标名 -> 指标历史)
        self.metrics = defaultdict(lambda: deque(maxlen=1000))

        # 告警管理器
        self.alert_manager = AlertManager()

        # 健康检查器
        self.health_checker = HealthChecker()

        # 告警阈值配置
        self.thresholds = self.config.get('thresholds', {
            'response_time': {'warning': 1.0, 'error': 3.0, 'critical': 5.0},
            'error_rate': {'warning': 0.05, 'error': 0.1, 'critical': 0.2},
            'queue_size': {'warning': 100, 'error': 500, 'critical': 1000},
            'memory_usage': {'warning': 0.7, 'error': 0.85, 'critical': 0.95},
            'cpu_usage': {'warning': 0.7, 'error': 0.85, 'critical': 0.95}
        })

        # 监控状态
        self.monitoring = False
        self._monitor_task = None

    async def start(self):
        """启动监控"""
        if self.monitoring:
            return

        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("系统监控已启动")

    async def stop(self):
        """停止监控"""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("系统监控已停止")

    async def _monitoring_loop(self):
        """监控主循环"""
        interval = self.config.get('interval', 60)  # 默认60秒

        while self.monitoring:
            try:
                # 收集系统指标
                await self._collect_system_metrics()

                # 等待下一个周期
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"监控循环异常: {e}")

    async def _collect_system_metrics(self):
        """收集系统指标"""
        import psutil

        # CPU使用率
        cpu_percent = psutil.cpu_percent(interval=1)
        await self.record_metric('system.cpu_usage', cpu_percent / 100)

        # 内存使用率
        memory = psutil.virtual_memory()
        await self.record_metric('system.memory_usage', memory.percent / 100)

        # 磁盘使用率
        disk = psutil.disk_usage('/')
        await self.record_metric('system.disk_usage', disk.percent / 100)

        # 网络IO
        net_io = psutil.net_io_counters()
        await self.record_metric('system.network_sent_bytes', net_io.bytes_sent)
        await self.record_metric('system.network_recv_bytes', net_io.bytes_recv)

    async def record_metric(self, name: str, value: float, tags: Dict[str, str] = None):
        """
        记录指标

        Args:
            name: 指标名称
            value: 指标值
            tags: 标签字典
        """
        metric = Metric(
            name=name,
            value=value,
            timestamp=datetime.now(),
            tags=tags or {}
        )

        # 存储指标
        self.metrics[name].append(metric)

        # 检查阈值
        await self._check_threshold(metric)

    async def _check_threshold(self, metric: Metric):
        """检查指标是否超过阈值"""
        # 获取指标的阈值配置
        metric_key = metric.name.split('.')[-1]  # 取最后一部分作为键
        thresholds = self.thresholds.get(metric_key)

        if not thresholds:
            return

        # 检查各级别阈值
        if metric.value >= thresholds.get('critical', float('inf')):
            await self.alert_manager.send_alert(Alert(
                level='CRITICAL',
                message=f"{metric.name} 达到临界值: {metric.value:.2f}",
                timestamp=datetime.now(),
                metric=metric,
                threshold=thresholds['critical']
            ))
        elif metric.value >= thresholds.get('error', float('inf')):
            await self.alert_manager.send_alert(Alert(
                level='ERROR',
                message=f"{metric.name} 达到错误阈值: {metric.value:.2f}",
                timestamp=datetime.now(),
                metric=metric,
                threshold=thresholds['error']
            ))
        elif metric.value >= thresholds.get('warning', float('inf')):
            await self.alert_manager.send_alert(Alert(
                level='WARNING',
                message=f"{metric.name} 达到警告阈值: {metric.value:.2f}",
                timestamp=datetime.now(),
                metric=metric,
                threshold=thresholds['warning']
            ))

    def get_metrics(self, name: str, duration: timedelta = None) -> List[Metric]:
        """
        获取指标历史

        Args:
            name: 指标名称
            duration: 时间范围

        Returns:
            指标列表
        """
        metrics = list(self.metrics[name])

        if duration:
            cutoff = datetime.now() - duration
            metrics = [m for m in metrics if m.timestamp >= cutoff]

        return metrics

    def get_statistics(self, name: str, duration: timedelta = None) -> Dict[str, float]:
        """
        获取指标统计

        Args:
            name: 指标名称
            duration: 时间范围

        Returns:
            统计信息字典
        """
        metrics = self.get_metrics(name, duration)

        if not metrics:
            return {}

        values = [m.value for m in metrics]

        return {
            'count': len(values),
            'min': min(values),
            'max': max(values),
            'avg': sum(values) / len(values),
            'sum': sum(values),
            'p50': self._percentile(values, 50),
            'p90': self._percentile(values, 90),
            'p95': self._percentile(values, 95),
            'p99': self._percentile(values, 99)
        }

    @staticmethod
    def _percentile(values: List[float], p: int) -> float:
        """计算百分位数"""
        if not values:
            return 0.0

        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * p / 100
        f = int(k)
        c = f + 1 if f + 1 < len(sorted_values) else f

        if f == c:
            return sorted_values[f]

        return sorted_values[f] + (k - f) * (sorted_values[c] - sorted_values[f])

    def get_dashboard_data(self) -> Dict[str, Any]:
        """获取监控面板数据"""
        now = datetime.now()
        last_hour = timedelta(hours=1)
        last_day = timedelta(days=1)

        return {
            'timestamp': now.isoformat(),
            'system': {
                'cpu': self.get_statistics('system.cpu_usage', last_hour),
                'memory': self.get_statistics('system.memory_usage', last_hour),
                'disk': self.get_statistics('system.disk_usage', last_hour)
            },
            'queries': {
                'total_today': self._count_metric('query.total', last_day),
                'success_rate': self._calculate_success_rate(last_hour),
                'avg_response_time': self.get_statistics('query.duration', last_hour).get('avg', 0)
            },
            'alerts': {
                'total': len(self.alert_manager.alert_history),
                'critical': len([a for a in self.alert_manager.alert_history if a.level == 'CRITICAL']),
                'error': len([a for a in self.alert_manager.alert_history if a.level == 'ERROR']),
                'warning': len([a for a in self.alert_manager.alert_history if a.level == 'WARNING'])
            }
        }

    def _count_metric(self, name: str, duration: timedelta) -> int:
        """统计指标数量"""
        metrics = self.get_metrics(name, duration)
        return len(metrics)

    def _calculate_success_rate(self, duration: timedelta) -> float:
        """计算成功率"""
        success_metrics = self.get_metrics('query.success', duration)
        error_metrics = self.get_metrics('query.error', duration)

        total = len(success_metrics) + len(error_metrics)
        if total == 0:
            return 1.0

        return len(success_metrics) / total


class AlertManager:
    """
    告警管理器
    负责告警的发送、抑制、聚合
    """

    def __init__(self):
        self.alert_channels: List[AlertChannel] = []
        self.alert_history = deque(maxlen=1000)

        # 告警抑制规则 (指标:级别 -> 最后告警时间)
        self.suppression_rules = {}

        # 抑制窗口 (默认5分钟内相同告警只发送一次)
        self.suppression_window = timedelta(minutes=5)

    def add_channel(self, channel: 'AlertChannel'):
        """添加告警通道"""
        self.alert_channels.append(channel)
        logger.info(f"添加告警通道: {channel.__class__.__name__}")

    async def send_alert(self, alert: Alert):
        """
        发送告警

        Args:
            alert: 告警对象
        """
        # 检查是否需要抑制
        if self._should_suppress(alert):
            logger.debug(f"告警被抑制: {alert.message}")
            return

        # 保存到历史
        self.alert_history.append(alert)

        # 发送到所有通道
        for channel in self.alert_channels:
            try:
                await channel.send(alert)
            except Exception as e:
                logger.error(f"发送告警失败: {e}")

    def _should_suppress(self, alert: Alert) -> bool:
        """检查是否应该抑制告警"""
        key = f"{alert.metric.name}:{alert.level}"
        last_alert_time = self.suppression_rules.get(key)

        if last_alert_time:
            if (datetime.now() - last_alert_time) < self.suppression_window:
                return True

        # 更新抑制规则
        self.suppression_rules[key] = datetime.now()
        return False

    def get_recent_alerts(self, limit: int = 10) -> List[Alert]:
        """获取最近的告警"""
        return list(self.alert_history)[-limit:]


class AlertChannel:
    """告警通道基类"""

    async def send(self, alert: Alert):
        """发送告警"""
        raise NotImplementedError


class LogAlertChannel(AlertChannel):
    """日志告警通道"""

    def __init__(self):
        self.logger = logging.getLogger('alerts')
        self.logger.setLevel(logging.INFO)

        # 配置文件处理器
        log_dir = Path("logs/alerts")
        log_dir.mkdir(parents=True, exist_ok=True)

        fh = logging.FileHandler(
            log_dir / f"alerts_{datetime.now().strftime('%Y%m%d')}.log",
            encoding='utf-8'
        )
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(message)s'
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    async def send(self, alert: Alert):
        """发送告警到日志"""
        if alert.level == 'CRITICAL':
            self.logger.critical(alert.message)
        elif alert.level == 'ERROR':
            self.logger.error(alert.message)
        elif alert.level == 'WARNING':
            self.logger.warning(alert.message)
        else:
            self.logger.info(alert.message)


class ConsoleAlertChannel(AlertChannel):
    """控制台告警通道"""

    async def send(self, alert: Alert):
        """发送告警到控制台"""
        level_icons = {
            'CRITICAL': '🔴',
            'ERROR': '🟠',
            'WARNING': '🟡',
            'INFO': '🔵'
        }

        icon = level_icons.get(alert.level, '⚪')
        print(f"\n{icon} [{alert.level}] {alert.message}")
        print(f"   时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"   指标: {alert.metric.name} = {alert.metric.value:.2f}")
        print(f"   阈值: {alert.threshold:.2f}")


class EmailAlertChannel(AlertChannel):
    """邮件告警通道"""

    def __init__(self, smtp_config: Dict[str, Any]):
        """
        Args:
            smtp_config: SMTP配置
                - host: SMTP服务器
                - port: 端口
                - username: 用户名
                - password: 密码
                - from_addr: 发件人
                - to_addrs: 收件人列表
        """
        self.smtp_config = smtp_config

    async def send(self, alert: Alert):
        """发送告警邮件"""
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        try:
            # 构建邮件
            msg = MIMEMultipart()
            msg['From'] = self.smtp_config['from_addr']
            msg['To'] = ', '.join(self.smtp_config['to_addrs'])
            msg['Subject'] = f"[{alert.level}] 系统告警: {alert.metric.name}"

            # 邮件正文
            body = f"""
告警级别: {alert.level}
告警消息: {alert.message}
指标名称: {alert.metric.name}
指标值: {alert.metric.value:.2f}
告警阈值: {alert.threshold:.2f}
时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            """

            msg.attach(MIMEText(body, 'plain'))

            # 发送邮件
            with smtplib.SMTP(self.smtp_config['host'], self.smtp_config['port']) as server:
                server.starttls()
                server.login(self.smtp_config['username'], self.smtp_config['password'])
                server.send_message(msg)

            logger.info(f"告警邮件已发送: {alert.message}")

        except Exception as e:
            logger.error(f"发送告警邮件失败: {e}")


class HealthChecker:
    """
    健康检查器
    检查系统各组件的健康状态
    """

    def __init__(self):
        self.checks: Dict[str, Callable] = {}

    def register_check(self, name: str, check_func: Callable):
        """
        注册健康检查

        Args:
            name: 检查名称
            check_func: 检查函数 (异步函数，返回 Dict 或抛出异常)
        """
        self.checks[name] = check_func
        logger.info(f"注册健康检查: {name}")

    async def check_all(self) -> Dict[str, Any]:
        """执行所有健康检查"""
        results = {}

        for name, check_func in self.checks.items():
            try:
                result = await check_func()
                results[name] = {
                    'status': 'healthy',
                    'details': result
                }
            except Exception as e:
                results[name] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }

        # 判断整体状态
        overall_status = 'healthy' if all(
            r['status'] == 'healthy' for r in results.values()
        ) else 'unhealthy'

        return {
            'status': overall_status,
            'checks': results,
            'timestamp': datetime.now().isoformat()
        }


# ==================== 使用示例 ====================

async def example_usage():
    """使用示例"""

    # 创建监控器
    monitor = SystemMonitor(config={
        'interval': 10,  # 10秒收集一次系统指标
        'thresholds': {
            'response_time': {'warning': 1.0, 'error': 3.0, 'critical': 5.0},
            'error_rate': {'warning': 0.05, 'error': 0.1, 'critical': 0.2}
        }
    })

    # 添加告警通道
    monitor.alert_manager.add_channel(LogAlertChannel())
    monitor.alert_manager.add_channel(ConsoleAlertChannel())

    # 注册健康检查
    async def check_database():
        # 模拟数据库检查
        return {'connected': True, 'latency': 0.05}

    async def check_milvus():
        # 模拟Milvus检查
        return {'connected': True, 'collections': 5}

    monitor.health_checker.register_check('database', check_database)
    monitor.health_checker.register_check('milvus', check_milvus)

    # 启动监控
    await monitor.start()

    try:
        # 模拟业务指标记录
        for i in range(10):
            # 记录查询响应时间
            await monitor.record_metric('query.duration', 0.5 + i * 0.3)

            # 记录查询成功
            await monitor.record_metric('query.success', 1)

            await asyncio.sleep(1)

        # 获取统计信息
        stats = monitor.get_statistics('query.duration', timedelta(minutes=5))
        print("\n查询响应时间统计:")
        print(f"  平均值: {stats['avg']:.2f}秒")
        print(f"  P95: {stats['p95']:.2f}秒")
        print(f"  P99: {stats['p99']:.2f}秒")

        # 执行健康检查
        health = await monitor.health_checker.check_all()
        print(f"\n系统健康状态: {health['status']}")
        for name, result in health['checks'].items():
            print(f"  {name}: {result['status']}")

        # 获取监控面板数据
        dashboard = monitor.get_dashboard_data()
        print(f"\n监控面板数据:")
        print(json.dumps(dashboard, indent=2, ensure_ascii=False))

    finally:
        # 停止监控
        await monitor.stop()


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(example_usage())
