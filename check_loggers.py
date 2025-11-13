import logging
import sys
sys.path.insert(0, ".")

from app.agents.service import AgentService

print("所有已配置的loggers:")
for name in sorted(logging.root.manager.loggerDict):
    logger = logging.getLogger(name)
    if logger.handlers or logger.level != logging.NOTSET:
        print(f"  {name}: handlers={len(logger.handlers)}, level={logger.level}, propagate={logger.propagate}")

print("\nRoot logger:")
print(f"  handlers={len(logging.root.handlers)}, level={logging.root.level}")
