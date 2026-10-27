import os
import re
import hmac
import secrets
from functools import wraps

from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, abort)
from werkzeug.security import generate_password_hash, check_password_hash
from mysql.connector import pooling, Error

CLASSES = ["8A", "8B", "9A", "9B", "10A"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "change-me-in-production"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE", "0") == "1",
)

pool = pooling.MySQLConnectionPool(
    pool_name="sms",
    pool_size=5,
    host=os.environ.get("DB_HOST", "localhost"),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USER", "root"),
    password=os.environ.get("DB_PASSWORD", "Root123"),
    database=os.environ.get("DB_NAME", "student_management"),
)


def db(sql, args=(), one=False, write=False):
    """Run one parameterised query. Returns rows, one row, or the new id."""
    conn = pool.get_connection()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, args)
        if write:
            conn.commit()
            return cur.lastrowid
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def ensure_admin():
    if not db("SELECT id FROM users LIMIT 1", one=True):
        user = os.environ.get("ADMIN_USER", "admin")
        pw = os.environ.get("ADMIN_PASS", "Admin@123")
        db("INSERT INTO users (username, password_hash, role) VALUES (%s,%s,'admin')",
           (user, generate_password_hash(pw)), write=True)
        print(f"Created first admin '{user}'. Change this password before going live.")


# ---------- security helpers ----------
@app.before_request
def check_csrf():
    if request.method == "POST":
        sent = request.form.get("csrf_token", "").encode()
        if not hmac.compare_digest(sent, session.get("csrf", "").encode()):
            abort(400)


@app.context_processor
def inject_globals():
    session.setdefault("csrf", secrets.token_hex(16))
    return {"csrf_token": session["csrf"], "CLASSES": CLASSES}


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    @login_required
    def wrapper(*a, **kw):
        if session.get("role") != "admin":
            abort(403)
        return f(*a, **kw)
    return wrapper


# ---------- auth ----------
@app.route("/")
def index():
    return redirect(url_for("dashboard"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = db("SELECT * FROM users WHERE username=%s",
               (request.form.get("username", "").strip(),), one=True)
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(user=u["username"], role=u["role"], csrf=secrets.token_hex(16))
            return redirect(url_for("dashboard"))
        flash("Username or password is incorrect.", "bad")
    return render_template("login.html")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- pages ----------
@app.route("/dashboard")
@login_required
def dashboard():
    total = db("SELECT COUNT(*) AS n FROM students", one=True)["n"]
    per_class = db("SELECT class_name, COUNT(*) AS n FROM students GROUP BY class_name ORDER BY class_name")
    recent = db("SELECT * FROM students ORDER BY created_at DESC, id DESC LIMIT 5")
    return render_template("dashboard.html", total=total, per_class=per_class, recent=recent)


@app.route("/students")
@login_required
def view_students():
    q = request.args.get("q", "").strip()
    cls = request.args.get("cls", "")
    sql, args = "SELECT * FROM students WHERE 1=1", []
    if q:
        sql += " AND (name LIKE %s OR roll_no LIKE %s OR email LIKE %s)"
        args += [f"%{q}%"] * 3
    if cls:
        sql += " AND class_name=%s"
        args.append(cls)
    rows = db(sql + " ORDER BY class_name, name", args)
    return render_template("view_students.html", students=rows, q=q, cls=cls)


def read_form():
    f = {k: request.form.get(k, "").strip()
         for k in ("roll_no", "name", "class_name", "email", "phone", "guardian")}
    err = None
    if not f["name"]:
        err = "Enter the student's full name."
    elif not f["roll_no"]:
        err = "Enter a roll number."
    elif f["class_name"] not in CLASSES:
        err = "Choose a class from the list."
    elif f["email"] and not EMAIL_RE.match(f["email"]):
        err = "Enter a valid email, like name@school.org."
    elif f["phone"] and not re.fullmatch(r"\+?\d{7,15}", f["phone"]):
        err = "Phone must be 7 to 15 digits."
    return f, err


@app.route("/students/add", methods=["GET", "POST"])
@login_required
def add_student():
    if request.method == "POST":
        f, err = read_form()
        if not err:
            try:
                db("INSERT INTO students (roll_no,name,class_name,email,phone,guardian) "
                   "VALUES (%(roll_no)s,%(name)s,%(class_name)s,%(email)s,%(phone)s,%(guardian)s)",
                   f, write=True)
                flash(f"Added {f['name']}.", "ok")
                return redirect(url_for("view_students"))
            except Error as e:
                if e.errno != 1062:
                    raise
                err = f"Roll {f['roll_no']} is already used in class {f['class_name']}."
        flash(err, "bad")
        return render_template("add_student.html", student=f)
    return render_template("add_student.html", student={})


@app.route("/students/<int:sid>/edit", methods=["GET", "POST"])
@login_required
def edit_student(sid):
    s = db("SELECT * FROM students WHERE id=%s", (sid,), one=True)
    if not s:
        abort(404)
    if request.method == "POST":
        f, err = read_form()
        f["id"] = sid
        if not err:
            try:
                db("UPDATE students SET roll_no=%(roll_no)s, name=%(name)s, class_name=%(class_name)s, "
                   "email=%(email)s, phone=%(phone)s, guardian=%(guardian)s WHERE id=%(id)s",
                   f, write=True)
                flash("Saved changes.", "ok")
                return redirect(url_for("view_students"))
            except Error as e:
                if e.errno != 1062:
                    raise
                err = f"Roll {f['roll_no']} is already used in class {f['class_name']}."
        flash(err, "bad")
        return render_template("edit_student.html", student=f)
    return render_template("edit_student.html", student=s)


@app.route("/students/<int:sid>/delete", methods=["POST"])
@admin_required
def delete_student(sid):
    db("DELETE FROM students WHERE id=%s", (sid,), write=True)
    flash("Student deleted.", "ok")
    return redirect(url_for("view_students"))


@app.errorhandler(403)
def forbidden(_):
    return render_template("login.html", denied=True), 403


ensure_admin()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
