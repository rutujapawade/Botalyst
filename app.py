# from dotenv import load_dotenv
# load_dotenv()   # ✅ MUST be first
# import os
# from flask import (
#     Flask, render_template, request, jsonify,
#     send_file, session, redirect
# )
# from openai import OpenAI
# from config import Config
# import random
# from datetime import datetime, timedelta
# import bcrypt
# import pandas as pd
# import matplotlib
# matplotlib.use("Agg")
# import matplotlib.pyplot as plt
# import os
# from werkzeug.utils import secure_filename
# from flask_mysqldb import MySQL
# from flask_session import Session
import os
from flask import Flask, render_template, request, jsonify, session, redirect, send_file
from flask_mysqldb import MySQL
from flask_session import Session
from openai import OpenAI
import bcrypt
import random
import pandas as pd
from datetime import datetime, timedelta
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from werkzeug.utils import secure_filename

app = Flask(__name__)

# --- CONFIGURATION ---
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "botalyst_secret_key")
# Railway ke variables
app.config['MYSQL_HOST'] = os.environ.get('MYSQLHOST')
app.config['MYSQL_USER'] = os.environ.get('MYSQLUSER')
app.config['MYSQL_PASSWORD'] = os.environ.get('MYSQLPASSWORD')
app.config['MYSQL_DB'] = os.environ.get('MYSQLDATABASE')
app.config['MYSQL_PORT'] = int(os.environ.get('MYSQLPORT', 3306))

# Session config
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

# Initialize
Session(app)
mysql = MySQL(app)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Folders
UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"
CHARTS_FOLDER = os.path.join("static", "charts")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(CHARTS_FOLDER, exist_ok=True)


# ---------------------------
# APP CONFIG

# app = Flask(__name__)
# app.config.from_object(Config)
# # ✅ Initialize OpenAI client
# client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))



# Session config
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

mysql = MySQL(app)

# folders
UPLOAD_FOLDER = "uploads"
REPORT_FOLDER = "reports"
CHARTS_FOLDER = os.path.join("static", "charts")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(REPORT_FOLDER, exist_ok=True)
os.makedirs(CHARTS_FOLDER, exist_ok=True)


# ---------------------------
# PAGES
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

@app.route('/test-db')
def test_db():
    cur = mysql.connection.cursor()
    cur.execute("SHOW TABLES")
    data = cur.fetchall()
    return str(data)


@app.route("/user")
def user_page():
    if not session.get("user_logged_in"):
        return redirect("/")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()
    cur.execute("SELECT full_name, email FROM users WHERE id=%s", (user_id,))
    user = cur.fetchone()
    cur.close()

    full_name = user[0] if user else "User"
    email = user[1] if user else ""

    return render_template("user.html", user_id=user_id, full_name=full_name, email=email)




@app.route("/api/logout")
def user_logout():
    session.clear()
    return redirect("/")



@app.route("/admin-login")
def admin_login_page():
    return render_template("admin_login.html")


@app.route("/admin")
def admin_page():
    if not session.get("admin_logged_in"):
        return redirect("/admin-login")
    return render_template("admin.html")


@app.route("/result/<int:user_id>/<file_name>")
def result_page(user_id, file_name):
    file_path = os.path.join(UPLOAD_FOLDER, file_name)

    if not os.path.exists(file_path):
        return "File not found", 404

    # read file
    if file_name.endswith(".csv"):
        df = pd.read_csv(file_path)
    elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
        df = pd.read_excel(file_path)
    else:
        return "Only CSV/Excel supported", 400

    # summary
    summary = (
        f"Rows: {df.shape[0]}\n"
        f"Columns: {df.shape[1]}\n\n"
        f"Missing Values:\n{df.isnull().sum()}"
    )

    # charts
    charts = []
    numeric_cols = df.select_dtypes(include=["int64", "float64"]).columns.tolist()

    for col in numeric_cols[:3]:
        plt.figure()
        df[col].dropna().hist()
        chart_name = f"{user_id}_{col}.png"
        chart_path = os.path.join(CHARTS_FOLDER, chart_name)
        plt.savefig(chart_path)
        plt.close()
        charts.append(chart_name)

    # latest report name
    cur = mysql.connection.cursor()
    cur.execute(
        "SELECT report_name FROM user_reports WHERE user_id=%s ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    rep = cur.fetchone()
    cur.close()

    report_name = rep[0] if rep else ""

    return render_template(
        "result.html",
        summary=summary,
        charts=charts,
        report_name=report_name
    )


# ---------------------------
# USER AUTH APIs
# ---------------------------
@app.route("/api/signup", methods=["POST"])
def signup():
    data = request.json

    full_name = data.get("full_name")
    email = data.get("email")
    mobile = data.get("mobile")
    password = data.get("password")

    if not full_name or not mobile or not password:
        return jsonify({"success": False, "message": "Full name, mobile and password are required"}), 400

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE mobile=%s OR email=%s", (mobile, email))
        existing = cur.fetchone()

        if existing:
            cur.close()
            return jsonify({"success": False, "message": "User already exists"}), 409

        cur.execute(
            "INSERT INTO users (full_name, email, mobile, password_hash, is_verified) VALUES (%s, %s, %s, %s, %s)",
            (full_name, email, mobile, password_hash, False)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "Signup successful"}), 201

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/login", methods=["POST"])
def login():
    data = request.json
    login_id = data.get("login_id")  # email or mobile
    password = data.get("password")

    if not login_id or not password:
        return jsonify({"success": False, "message": "Login ID and password required"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE email=%s OR mobile=%s", (login_id, login_id))
        user = cur.fetchone()
        cur.close()

        if not user:
            return jsonify({"success": False, "message": "User not found"}), 404

        user_id, password_hash = user

        if bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8")):
            session["user_logged_in"] = True
            session["user_id"] = user_id
            ip = request.remote_addr
            user_agent = request.headers.get("User-Agent")

            cur = mysql.connection.cursor()
            cur.execute(
                "INSERT INTO user_logins (user_id, ip_address, user_agent) VALUES (%s, %s, %s)",
                (user_id, ip, user_agent)
            )
            mysql.connection.commit()
            cur.close()

            # return jsonify({"success": True, "message": "Login successful", "user_id": user_id}), 200


            return jsonify({"success": True, "message": "Login successful", "user_id": user_id}), 200
        else:
            return jsonify({"success": False, "message": "Invalid password"}), 401

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# OTP APIs
# ---------------------------
@app.route("/api/send-otp", methods=["POST"])
def send_otp():
    data = request.json
    mobile = data.get("mobile")
    purpose = data.get("purpose")  # signup/reset

    if not mobile or purpose not in ["signup", "reset"]:
        return jsonify({"success": False, "message": "Mobile and valid purpose required"}), 400

    otp = str(random.randint(100000, 999999))
    expires_at = datetime.now() + timedelta(minutes=5)

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO otps (mobile, otp_code, purpose, expires_at) VALUES (%s, %s, %s, %s)",
            (mobile, otp, purpose, expires_at)
        )
        mysql.connection.commit()
        cur.close()

        # for testing return OTP
        return jsonify({"success": True, "message": "OTP sent successfully", "otp": otp}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/verify-otp", methods=["POST"])
def verify_otp():
    data = request.json
    mobile = data.get("mobile")
    otp = data.get("otp")
    purpose = data.get("purpose")

    if not mobile or not otp or purpose not in ["signup", "reset"]:
        return jsonify({"success": False, "message": "Mobile, otp and valid purpose required"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, expires_at, is_used
            FROM otps
            WHERE mobile=%s AND otp_code=%s AND purpose=%s
            ORDER BY id DESC LIMIT 1
        """, (mobile, otp, purpose))

        record = cur.fetchone()

        if not record:
            cur.close()
            return jsonify({"success": False, "message": "Invalid OTP"}), 400

        otp_id, expires_at, is_used = record

        if is_used:
            cur.close()
            return jsonify({"success": False, "message": "OTP already used"}), 400

        if datetime.now() > expires_at:
            cur.close()
            return jsonify({"success": False, "message": "OTP expired"}), 400

        cur.execute("UPDATE otps SET is_used=TRUE WHERE id=%s", (otp_id,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "OTP verified successfully"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/mark-verified", methods=["POST"])
def mark_verified():
    data = request.json
    mobile = data.get("mobile")

    if not mobile:
        return jsonify({"success": False, "message": "Mobile required"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET is_verified=TRUE WHERE mobile=%s", (mobile,))
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "User verified successfully"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.json
    mobile = data.get("mobile")
    new_password = data.get("new_password")

    if not mobile or not new_password:
        return jsonify({"success": False, "message": "Mobile and new_password required"}), 400

    try:
        new_password_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        cur = mysql.connection.cursor()
        cur.execute("UPDATE users SET password_hash=%s WHERE mobile=%s", (new_password_hash, mobile))
        mysql.connection.commit()

        if cur.rowcount == 0:
            cur.close()
            return jsonify({"success": False, "message": "User not found"}), 404

        cur.close()
        return jsonify({"success": True, "message": "Password reset successful"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# CHAT + HISTORY APIs
# ---------------------------
@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    user_id = data.get("user_id")
    message = data.get("message")

    if not user_id or not message:
        return jsonify({"success": False, "message": "Invalid input"}), 400

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are BotAlyst, an AI assistant specialized ONLY in "
                        "Data Analytics, Data Science, Engineering, Python, SQL, "
                        "Pandas, Machine Learning, and statistics. "
                        "If a question is outside these topics, politely refuse."
                    )
                },
                {"role": "user", "content": message}
            ],
            temperature=0.3
        )

        bot_reply = response.choices[0].message.content

        return jsonify({
            "success": True,
            "reply": bot_reply
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500


@app.route("/api/new-chat", methods=["POST"])
def new_chat():
    session.pop("active_project_id", None)
    return jsonify({"success": True, "message": "New chat started"}), 200


@app.route("/api/project/<int:project_id>/messages", methods=["GET"])
def get_project_messages(project_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT sender, message, created_at
            FROM chat_messages
            WHERE project_id=%s
            ORDER BY created_at ASC
        """, (project_id,))
        rows = cur.fetchall()
        cur.close()

        messages = []
        for r in rows:
            messages.append({
                "sender": r[0],
                "message": r[1],
                "time": str(r[2])
            })

        return jsonify({"success": True, "messages": messages}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/history/<int:user_id>", methods=["GET"])
def get_history(user_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, project_title, created_at, is_pinned
            FROM user_projects
            WHERE user_id=%s AND is_archived=FALSE
            ORDER BY is_pinned DESC, updated_at DESC
        """, (user_id,))

        rows = cur.fetchall()
        cur.close()

        history = []
        for r in rows:
            history.append({
                "id": r[0],
                "title": r[1],
                "date": str(r[2]),
                "is_pinned": r[3]
            })

        return jsonify({"success": True, "history": history}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/update-title", methods=["PUT"])
def update_title():
    data = request.json
    project_id = data.get("project_id")
    new_title = data.get("new_title")

    if not project_id or not new_title:
        return jsonify({"success": False, "message": "project_id and new_title required"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("UPDATE user_projects SET project_title=%s WHERE id=%s", (new_title, project_id))
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "Title updated"}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# FILE UPLOAD + REPORT APIs
# ---------------------------
@app.route("/api/upload", methods=["POST"])
def upload_file():
    user_id = request.form.get("user_id")

    if "file" not in request.files:
        return jsonify({"success": False, "message": "No file found"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"success": False, "message": "No selected file"}), 400

    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(file_path)

    file_type = filename.split(".")[-1].lower()

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO user_files (user_id, file_name, file_path, file_type) VALUES (%s, %s, %s, %s)",
            (user_id, filename, file_path, file_type)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "File uploaded successfully", "file_name": filename}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/generate-report", methods=["POST"])
def generate_report():
    data = request.json
    user_id = data.get("user_id")
    file_name = data.get("file_name")

    project_id = session.get("active_project_id")


    if not user_id or not file_name:
        return jsonify({"success": False, "message": "user_id and file_name required"}), 400

    file_path = os.path.join(UPLOAD_FOLDER, file_name)

    if not os.path.exists(file_path):
        return jsonify({"success": False, "message": "File not found"}), 404

    try:
        if file_name.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_name.endswith(".xlsx") or file_name.endswith(".xls"):
            df = pd.read_excel(file_path)
        else:
            return jsonify({"success": False, "message": "Only CSV/Excel supported for report"}), 400

        report_text = ""
        report_text += "BOTALYST EDA REPORT\n"
        report_text += "====================\n\n"
        report_text += f"File: {file_name}\n"
        report_text += f"Rows: {df.shape[0]}\n"
        report_text += f"Columns: {df.shape[1]}\n\n"

        report_text += "Column Names:\n"
        report_text += ", ".join(df.columns) + "\n\n"

        report_text += "Missing Values:\n"
        report_text += str(df.isnull().sum()) + "\n\n"

        report_text += "Summary (Describe):\n"
        report_text += str(df.describe(include="all")) + "\n\n"

        report_name = f"report_{user_id}_{file_name}.txt"
        report_path = os.path.join(REPORT_FOLDER, report_name)

        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_text)

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO user_reports (user_id, project_id, report_name, report_path) VALUES (%s, %s, %s, %s)",
            (user_id, project_id, report_name, report_path)
        )

        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True, "message": "Report generated", "report_name": report_name}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/download-report/<report_name>", methods=["GET"])
def download_report(report_name):
    report_path = os.path.join(REPORT_FOLDER, report_name)

    if not os.path.exists(report_path):
        return jsonify({"success": False, "message": "Report not found"}), 404

    return send_file(report_path, as_attachment=True)


# ---------------------------
# ADMIN APIs
# ---------------------------
@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, password_hash FROM admins WHERE admin_username=%s", (username,))
        admin = cur.fetchone()
        cur.close()

        if not admin:
            return jsonify({"success": False, "message": "Admin not found"}), 404

        admin_id, stored_pass = admin

        # TEMP plain check (next step we will bcrypt hash)
        if bcrypt.checkpw(password.encode("utf-8"), stored_pass.encode("utf-8")):
            session["admin_logged_in"] = True
            session["admin_id"] = admin_id
            return jsonify({"success": True, "message": "Admin login success"}), 200
        else:
            return jsonify({"success": False, "message": "Invalid password"}), 401


    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/logout")
def admin_logout():
    session.clear()
    return redirect("/admin-login")


@app.route("/api/admin/users", methods=["GET"])
def admin_users():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, full_name, email, mobile, created_at FROM users ORDER BY created_at DESC")
        users = cur.fetchall()

        result = []
        for u in users:
            user_id = u[0]

            # ✅ Get last login info for this user
            cur.execute("""
                SELECT ip_address, login_time
                FROM user_logins
                WHERE user_id=%s
                ORDER BY login_time DESC
                LIMIT 1
            """, (user_id,))

            last_login = cur.fetchone()

            last_ip = last_login[0] if last_login else ""
            last_login_time = str(last_login[1]) if last_login else ""


            cur.execute("""
                SELECT project_title
                FROM user_projects
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT 5
            """, (user_id,))
            projects = [p[0] for p in cur.fetchall()]

            result.append({
                "id": u[0],
                "full_name": u[1],
                "email": u[2],
                "mobile": u[3],
                "created_at": str(u[4]),
                "last_ip": last_ip,
                "last_login": last_login_time,
                "projects": projects
            })

        cur.close()
        return jsonify({"success": True, "users": result}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/search", methods=["GET"])
def admin_search():
    if not session.get("admin_logged_in"):
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    q = request.args.get("q", "")

    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, full_name, email, mobile, created_at
            FROM users
            WHERE full_name LIKE %s OR email LIKE %s OR mobile LIKE %s
            ORDER BY created_at DESC
        """, (f"%{q}%", f"%{q}%", f"%{q}%"))

        users = cur.fetchall()

        result = []
        for u in users:
            user_id = u[0]

            cur.execute("""
                SELECT project_title
                FROM user_projects
                WHERE user_id=%s
                ORDER BY created_at DESC
                LIMIT 5
            """, (user_id,))
            projects = [p[0] for p in cur.fetchall()]

            result.append({
                "id": u[0],
                "full_name": u[1],
                "email": u[2],
                "mobile": u[3],
                "created_at": str(u[4]),
                "projects": projects
            })

        cur.close()
        return jsonify({"success": True, "users": result}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/delete-project/<int:project_id>", methods=["DELETE"])
def delete_project(project_id):
    try:
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM user_projects WHERE id=%s", (project_id,))
        mysql.connection.commit()
        cur.close()
        return jsonify({"success": True, "message": "Project deleted"}), 200
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route("/api/pin-chat", methods=["PUT"])
def pin_chat():
    data = request.json
    project_id = data.get("project_id")
    pin = data.get("pin")  # true / false

    if project_id is None:
        return jsonify({"success": False, "message": "project_id required"}), 400

    try:
        cur = mysql.connection.cursor()
        cur.execute(
            "UPDATE user_projects SET is_pinned=%s WHERE id=%s",
            (pin, project_id)
        )
        mysql.connection.commit()
        cur.close()

        return jsonify({"success": True}), 200

    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# ---------------------------
# RUN
# ---------------------------
if __name__ == "__main__":
    app.run(debug=True)
