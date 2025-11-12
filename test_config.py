from dotenv import load_dotenv
load_dotenv('.env', override=True)

from app.config.app_config import settings
print(f'MySQL Host: {settings.database.mysql_host}')
print(f'MySQL Port: {settings.database.mysql_port}')
print(f'MySQL User: {settings.database.mysql_user}')
print(f'MySQL DB: {settings.database.mysql_db}')
