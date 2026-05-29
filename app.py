import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv()


from flask import Flask, render_template, request, jsonify, send_file, session, redirect
import pymysql
pymysql.install_as_MySQLdb()

from flask_mysqldb import MySQL
from flask_session import Session

from openai import OpenAI
import bcrypt

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from werkzeug.utils import secure_filename


# ---------------------------
# APP INIT
# ---------------------------
app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "botalyst_secret")

# FIXED ENV (IMPORTANT)
app.config["MYSQL_HOST"] = os.getenv("MYSQL_HOST")
app.config["MYSQL_USER"] = os.getenv("MYSQL_USER")
app.config["MYSQL_PASSWORD"] = os.getenv("MYSQL_PASSWORD")
app.config["MYSQL_DB"] = os.getenv("MYSQL_DB")
app.config["MYSQL_PORT"] = int(os.getenv("MYSQL_PORT", 3306))

# Session
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
Session(app)

# DB
mysql = MySQL(app)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Folders
UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"
CHARTS_FOLDER = os.path.join("static", "charts")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(CHARTS_FOLDER, exist_ok=True)


# ---------------------------
# ROUTES
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/login")
def login_page():
    return render_template("login.html")


@app.route("/signup")
def signup_page():
    return render_template("signup.html")


@app.route("/user")
def user_page():
    if not session.get("user_logged_in"):
        return redirect("/")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()
    cur.execute("SELECT full_name, email FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()

    return render_template(
        "user.html",
        user_id=user_id,
        full_name=user[0] if user else "User",
        email=user[1] if user else ""
    )


@app.route("/api/logout")
def logout():
    session.clear()
    return redirect("/")


# ---------------------------
# DB TEST
# ---------------------------
@app.route("/test-db")
def test_db():
    cur = mysql.connection.cursor()
    cur.execute("SHOW TABLES")
    return str(cur.fetchall())


# ---------------------------
# SIGNUP
# ---------------------------
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json

    full_name = data.get("full_name")
    email = data.get("email")
    mobile = data.get("mobile")
    password = data.get("password")

    if not full_name or not mobile or not password:
        return jsonify({"success": False, "message": "Missing fields"}), 400

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    try:
        cur = mysql.connection.cursor()

        cur.execute("SELECT id FROM users WHERE mobile=%s OR email=%s", (mobile, email))
        if cur.fetchone():
            return jsonify({"success": False, "message": "User exists"}), 409

        cur.execute("""
            INSERT INTO users (full_name, email, mobile, password_hash, is_verified)
            VALUES (%s, %s, %s, %s, %s)
        """, (full_name, email, mobile, password_hash, False))

        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True}), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# LOGIN
# ---------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    login_id = data.get("login_id")
    password = data.get("password")

    try:
        cur = mysql.connection.cursor()

        cur.execute(
            "SELECT id, password_hash FROM users WHERE email=%s OR mobile=%s",
            (login_id, login_id)
        )
        user = cur.fetchone()
        cur.close()

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        user_id, hash_pw = user

        if bcrypt.checkpw(password.encode(), hash_pw.encode()):
            session["user_logged_in"] = True
            session["user_id"] = user_id
            return jsonify({"success": True, "user_id": user_id})

        return jsonify({"success": False, "message": "Wrong password"}), 401

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# CHAT
# ---------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    message = data.get("message")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are BotAlyst for data science only."},
                {"role": "user", "content": message}
            ],
            temperature=0.3
        )

        return jsonify({
            "success": True,
            "reply": response.choices[0].message.content
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# UPLOAD
# ---------------------------
@app.route("/api/upload", methods=["POST"])
def upload():
    user_id = request.form.get("user_id")
    file = request.files.get("file")

    if not file:
        return jsonify({"success": False}), 400

    filename = secure_filename(file.filename)
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO user_files (user_id, file_name, file_path, file_type)
        VALUES (%s, %s, %s, %s)
    """, (user_id, filename, path, filename.split(".")[-1]))

    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True, "file_name": filename})


# ---------------------------
# REPORT
# ---------------------------
@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    data = request.json
    user_id = data.get("user_id")
    file_name = data.get("file_name")

    path = os.path.join(UPLOAD_FOLDER, file_name)

    if not os.path.exists(path):
        return jsonify({"success": False, "message": "File not found"}), 404

    df = pd.read_csv(path) if file_name.endswith(".csv") else pd.read_excel(path)

    report = f"""
BOTALYST REPORT
Rows: {df.shape[0]}
Columns: {df.shape[1]}
Missing:
{df.isnull().sum()}
"""

    report_name = f"report_{user_id}_{file_name}.txt"
    report_path = os.path.join(REPORT_FOLDER, report_name)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO user_reports (user_id, report_name, report_path)
        VALUES (%s, %s, %s)
    """, (user_id, report_name, report_path))

    mysql.connection.commit()
    cur.close()

    return jsonify({"success": True, "report_name": report_name})


# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)