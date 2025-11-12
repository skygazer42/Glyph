import os

# 检查所有与MYSQL相关的环境变量
mysql_vars = {k: v for k, v in os.environ.items() if 'MYSQL' in k.upper() or 'DATABASE' in k.upper()}
print("MySQL/DATABASE related environment variables:")
for k, v in mysql_vars.items():
    print(f"  {k} = {v}")

# 尝试加载.env
from dotenv import load_dotenv
print("\nLoading .env file...")
load_dotenv('.env', override=True, verbose=True)

# 再次检查
mysql_vars_after = {k: v for k, v in os.environ.items() if 'MYSQL' in k.upper() or 'DATABASE' in k.upper()}
print("\nAfter loading .env:")
for k, v in mysql_vars_after.items():
    print(f"  {k} = {v}")
