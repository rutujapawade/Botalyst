import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "botalyst_secret")

    MYSQL_HOST = os.getenv("MYSQLHOST")
    MYSQL_USER = os.getenv("MYSQLUSER")
    MYSQL_PASSWORD = os.getenv("MYSQLPASSWORD")
    MYSQL_DB = os.getenv("MYSQLDATABASE")
    MYSQL_PORT = int(os.getenv("MYSQLPORT", 3306))

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")