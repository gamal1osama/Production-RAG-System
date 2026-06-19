from dotenv import dotenv_values

config = dotenv_values(".env")

# Flower configuration
port = 5555
max_tasks = 10000
auto_refresh = True
# db = 'flower.db' # SQLite database file for presist storage

# Auththentication
basic_auth = [f'admin:{config["CELERY_FLOWER_PASSWORD"]}'] 
