# import os
# from dotenv import load_dotenv

# import os

# class Config:
#     SECRET_KEY = os.getenv("SECRET_KEY")
#     MYSQL_HOST = os.getenv("MYSQL_HOST")
#     MYSQL_USER = os.getenv("MYSQL_USER")
#     MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
#     MYSQL_DB = os.getenv("MYSQL_DB")

#     OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


# load_dotenv()

# class Config:
#     SECRET_KEY = os.getenv("SECRET_KEY", "botalyst_secret_key")

#     MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
#     MYSQL_USER = os.getenv("MYSQL_USER", "root")
#     MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
#     MYSQL_DB = os.getenv("MYSQL_DB", "botalyst_db")


import os
from flask import Flask
from flask_mysqldb import MySQL

app = Flask(__name__)

# Railway mein jo MYSQL_URL dala hai, wahan se details utha raha hai
# Agar aapne sirf MYSQL_URL dala hai, toh code ko thoda modify karna padega:
app.config['MYSQL_HOST'] = os.environ.get('MYSQLHOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQLUSER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQLPASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQLDATABASE')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQLPORT', 3306))

mysql = MySQL(app)

