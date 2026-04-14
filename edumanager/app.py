"""
EduManage Pro — Student Management System
Production-ready Flask application.

Run locally:     python app.py
Run production:  gunicorn -w 2 -b 0.0.0.0:8000 app:app

Environment variables:
    SECRET_KEY   — Flask session secret (required in production)
    DATA_FILE    — Path to data.json  (default: ./data.json next to app.py)
    PORT         — Port to listen on  (default: 5000)
    DEBUG        — "true" to enable debug mode
    HTTPS        — "true" to set SESSION_COOKIE_SECURE
"""

import os, json, csv, io, uuid, logging
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, jsonify,
    session, redirect, url_for,
)

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.config.update(
    SECRET_KEY             = os.environ.get("SECRET_KEY", "CHANGE-ME-IN-PRODUCTION"),
    SESSION_COOKIE_HTTPONLY= True,
    SESSION_COOKIE_SAMESITE= "Lax",
    SESSION_COOKIE_SECURE  = os.environ.get("HTTPS","false").lower() == "true",
    MAX_CONTENT_LENGTH     = 5 * 1024 * 1024,   # 5 MB upload limit
)

DATA_FILE = os.environ.get(
    "DATA_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json"),
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ── Security headers ──────────────────────────────────────────────────────────
@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"]        = "SAMEORIGIN"
    resp.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    return resp

# ── Auth helpers ──────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def wrapped(*a, **kw):
        if "user" not in session:
            return (jsonify({"error":"Unauthorized"}), 401) if request.is_json else redirect(url_for("index"))
        return f(*a, **kw)
    return wrapped

def role_required(*roles):
    def dec(f):
        @wraps(f)
        def wrapped(*a, **kw):
            if "user" not in session:
                return jsonify({"error":"Unauthorized"}), 401
            if session["user"]["role"] not in roles:
                return jsonify({"error":"Forbidden"}), 403
            return f(*a, **kw)
        return wrapped
    return dec

# ── Data helpers ──────────────────────────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    _init_data()
    return load_data()

def save_data(data):
    os.makedirs(os.path.dirname(os.path.abspath(DATA_FILE)), exist_ok=True)
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_FILE)          # atomic write — never corrupts on crash

def new_id(prefix=""):
    return prefix + str(uuid.uuid4())[:8].upper()

def att_pct(a):
    t = a.get("total") or (a.get("present",0) + a.get("absent",0) + a.get("late",0))
    return round(a.get("present",0) / t * 100) if t else 0

def letter_grade(pct):
    if pct >= 90: return "O",   10.0
    if pct >= 80: return "A+",   9.0
    if pct >= 70: return "A",    8.0
    if pct >= 60: return "B+",   7.0
    if pct >= 50: return "B",    6.0
    if pct >= 40: return "C",    5.0
    return "F", 0.0

def calc_sgpa(results, subjects):
    sub_map = {s["id"]: s for s in subjects}
    totals  = {}
    for r in results:
        sid = r["subject_id"]
        sub = sub_map.get(sid)
        if not sub: continue
        if sid not in totals:
            totals[sid] = {"earned":0,"max":0,"credits":sub["credits"]}
        totals[sid]["earned"] += r["marks_obtained"]
        totals[sid]["max"]    += r["max_marks"]
    pts = cred = 0
    for d2 in totals.values():
        if not d2["max"]: continue
        _, gp = letter_grade(round(d2["earned"]/d2["max"]*100))
        pts  += gp * d2["credits"]
        cred += d2["credits"]
    return (round(pts/cred, 2), cred) if cred else (0.0, 0)

# ── Seed data ─────────────────────────────────────────────────────────────────
DEFAULT_DATA = {
    "users": {
        "admin@school.edu":   {"password":"admin123",   "role":"admin",   "name":"Admin User",       "id":"admin_1"},
        "rajesh@school.edu":  {"password":"teacher123", "role":"teacher", "name":"Dr. Rajesh Kumar",  "id":"TCH-001"},
        "meera@school.edu":   {"password":"teacher123", "role":"teacher", "name":"Prof. Meera Nair",  "id":"TCH-002"},
        "suresh@school.edu":  {"password":"teacher123", "role":"teacher", "name":"Dr. Suresh Iyer",   "id":"TCH-003"},
        "lakshmi@school.edu": {"password":"teacher123", "role":"teacher", "name":"Prof. Lakshmi Rao", "id":"TCH-004"},
        "ananya@school.edu":  {"password":"student123", "role":"student", "name":"Ananya Sharma",     "id":"STU-001"},
        "rohan@school.edu":   {"password":"student123", "role":"student", "name":"Rohan Mehta",       "id":"STU-002"},
        "priya@school.edu":   {"password":"student123", "role":"student", "name":"Priya Patel",       "id":"STU-003"},
    },
    "departments": [
        {"id":"DEPT-01","name":"Computer Science","code":"CS","hod":"TCH-001"},
        {"id":"DEPT-02","name":"Information Technology","code":"IT","hod":"TCH-003"},
        {"id":"DEPT-03","name":"Business Administration","code":"BA","hod":"TCH-004"},
    ],
    "teachers": [
        {"id":"TCH-001","name":"Dr. Rajesh Kumar","email":"rajesh@school.edu","phone":"+91 91234 56789","dept_id":"DEPT-01","specialization":"Data Structures & Algorithms","exp":12,"joined":"2012-07-01"},
        {"id":"TCH-002","name":"Prof. Meera Nair","email":"meera@school.edu","phone":"+91 81234 56789","dept_id":"DEPT-01","specialization":"Database Systems","exp":8,"joined":"2016-07-01"},
        {"id":"TCH-003","name":"Dr. Suresh Iyer","email":"suresh@school.edu","phone":"+91 71234 56789","dept_id":"DEPT-02","specialization":"Networks & Security","exp":15,"joined":"2009-07-01"},
        {"id":"TCH-004","name":"Prof. Lakshmi Rao","email":"lakshmi@school.edu","phone":"+91 61234 56789","dept_id":"DEPT-03","specialization":"Management Studies","exp":10,"joined":"2014-07-01"},
    ],
    "courses": [
        {"id":"CRS-001","name":"B.Tech Computer Science","code":"BTCS","dept_id":"DEPT-01","duration_sems":8,"credits_total":180,"description":"4-year undergraduate CS program"},
        {"id":"CRS-002","name":"B.Tech Information Technology","code":"BTIT","dept_id":"DEPT-02","duration_sems":8,"credits_total":160,"description":"4-year undergraduate IT program"},
        {"id":"CRS-003","name":"Master of Business Administration","code":"MBA","dept_id":"DEPT-03","duration_sems":4,"credits_total":120,"description":"2-year MBA program"},
        {"id":"CRS-004","name":"Master of Computer Applications","code":"MCA","dept_id":"DEPT-01","duration_sems":4,"credits_total":120,"description":"2-year MCA program"},
    ],
    "subjects": [
        {"id":"SUB-001","name":"Engineering Mathematics I","code":"BTCS101","course_id":"CRS-001","semester":1,"credits":4,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-002","name":"Programming Fundamentals","code":"BTCS102","course_id":"CRS-001","semester":1,"credits":4,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-003","name":"Digital Logic","code":"BTCS103","course_id":"CRS-001","semester":1,"credits":3,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-004","name":"Communication Skills","code":"BTCS104","course_id":"CRS-001","semester":1,"credits":2,"teacher_id":"TCH-004","type":"elective","max_marks":100,"passing_marks":40},
        {"id":"SUB-005","name":"Engineering Mathematics II","code":"BTCS201","course_id":"CRS-001","semester":2,"credits":4,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-006","name":"Data Structures","code":"BTCS202","course_id":"CRS-001","semester":2,"credits":4,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-007","name":"Object Oriented Programming","code":"BTCS203","course_id":"CRS-001","semester":2,"credits":3,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-008","name":"Database Management Systems","code":"BTCS301","course_id":"CRS-001","semester":3,"credits":4,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-009","name":"Operating Systems","code":"BTCS302","course_id":"CRS-001","semester":3,"credits":3,"teacher_id":"TCH-003","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-010","name":"Computer Networks","code":"BTCS303","course_id":"CRS-001","semester":3,"credits":3,"teacher_id":"TCH-003","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-011","name":"Software Engineering","code":"BTCS304","course_id":"CRS-001","semester":3,"credits":3,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-012","name":"Mathematics for IT","code":"BTIT101","course_id":"CRS-002","semester":1,"credits":4,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-013","name":"Introduction to Programming","code":"BTIT102","course_id":"CRS-002","semester":1,"credits":4,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-014","name":"Web Technologies","code":"BTIT103","course_id":"CRS-002","semester":1,"credits":3,"teacher_id":"TCH-003","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-015","name":"Network Security","code":"BTIT201","course_id":"CRS-002","semester":2,"credits":4,"teacher_id":"TCH-003","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-016","name":"Database Systems","code":"BTIT202","course_id":"CRS-002","semester":2,"credits":4,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-017","name":"Management Principles","code":"MBA101","course_id":"CRS-003","semester":1,"credits":4,"teacher_id":"TCH-004","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-018","name":"Financial Accounting","code":"MBA102","course_id":"CRS-003","semester":1,"credits":4,"teacher_id":"TCH-004","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-019","name":"Business Communication","code":"MBA103","course_id":"CRS-003","semester":1,"credits":3,"teacher_id":"TCH-004","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-020","name":"Marketing Management","code":"MBA201","course_id":"CRS-003","semester":2,"credits":4,"teacher_id":"TCH-004","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-021","name":"Operations Research","code":"MBA202","course_id":"CRS-003","semester":2,"credits":3,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-022","name":"Advanced Mathematics","code":"MCA101","course_id":"CRS-004","semester":1,"credits":4,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-023","name":"Advanced Programming","code":"MCA102","course_id":"CRS-004","semester":1,"credits":4,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-024","name":"System Analysis & Design","code":"MCA103","course_id":"CRS-004","semester":1,"credits":3,"teacher_id":"TCH-002","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-025","name":"Algorithms","code":"MCA201","course_id":"CRS-004","semester":2,"credits":4,"teacher_id":"TCH-001","type":"core","max_marks":100,"passing_marks":40},
        {"id":"SUB-026","name":"Cloud Computing","code":"MCA202","course_id":"CRS-004","semester":2,"credits":3,"teacher_id":"TCH-003","type":"elective","max_marks":100,"passing_marks":40},
    ],
    "students": [
        {"id":"STU-001","name":"Ananya Sharma","email":"ananya@school.edu","phone":"+91 98765 43210","dob":"2002-03-15","course_id":"CRS-001","current_sem":3,"city":"Mumbai","state":"Maharashtra","roll":"BTCS2022001","admission_year":2022},
        {"id":"STU-002","name":"Rohan Mehta","email":"rohan@school.edu","phone":"+91 87654 32109","dob":"2001-11-20","course_id":"CRS-002","current_sem":2,"city":"Delhi","state":"Delhi","roll":"BTIT2022001","admission_year":2022},
        {"id":"STU-003","name":"Priya Patel","email":"priya@school.edu","phone":"+91 76543 21098","dob":"2002-07-08","course_id":"CRS-004","current_sem":2,"city":"Ahmedabad","state":"Gujarat","roll":"MCA2023001","admission_year":2023},
        {"id":"STU-004","name":"Karan Singh","email":"karan@school.edu","phone":"+91 65432 10987","dob":"2001-01-25","course_id":"CRS-003","current_sem":2,"city":"Bengaluru","state":"Karnataka","roll":"MBA2023001","admission_year":2023},
        {"id":"STU-005","name":"Sneha Gupta","email":"sneha@school.edu","phone":"+91 54321 09876","dob":"2003-05-12","course_id":"CRS-001","current_sem":3,"city":"Pune","state":"Maharashtra","roll":"BTCS2022002","admission_year":2022},
        {"id":"STU-006","name":"Arjun Nair","email":"arjun@school.edu","phone":"+91 43210 98765","dob":"2002-09-30","course_id":"CRS-002","current_sem":2,"city":"Chennai","state":"Tamil Nadu","roll":"BTIT2022002","admission_year":2022},
        {"id":"STU-007","name":"Divya Sharma","email":"divya@school.edu","phone":"+91 32109 87654","dob":"2003-01-18","course_id":"CRS-001","current_sem":1,"city":"Jaipur","state":"Rajasthan","roll":"BTCS2023001","admission_year":2023},
    ],
    "results": [
        {"id":"R001","student_id":"STU-001","subject_id":"SUB-001","semester":1,"exam_type":"internal","marks_obtained":38,"max_marks":40,"graded_by":"TCH-001","date":"2022-09-15","status":"Pass"},
        {"id":"R002","student_id":"STU-001","subject_id":"SUB-001","semester":1,"exam_type":"end","marks_obtained":52,"max_marks":60,"graded_by":"TCH-001","date":"2022-11-20","status":"Pass"},
        {"id":"R003","student_id":"STU-001","subject_id":"SUB-002","semester":1,"exam_type":"internal","marks_obtained":35,"max_marks":40,"graded_by":"TCH-002","date":"2022-09-16","status":"Pass"},
        {"id":"R004","student_id":"STU-001","subject_id":"SUB-002","semester":1,"exam_type":"end","marks_obtained":55,"max_marks":60,"graded_by":"TCH-002","date":"2022-11-21","status":"Pass"},
        {"id":"R005","student_id":"STU-001","subject_id":"SUB-003","semester":1,"exam_type":"internal","marks_obtained":32,"max_marks":40,"graded_by":"TCH-001","date":"2022-09-17","status":"Pass"},
        {"id":"R006","student_id":"STU-001","subject_id":"SUB-003","semester":1,"exam_type":"end","marks_obtained":48,"max_marks":60,"graded_by":"TCH-001","date":"2022-11-22","status":"Pass"},
        {"id":"R007","student_id":"STU-001","subject_id":"SUB-004","semester":1,"exam_type":"internal","marks_obtained":18,"max_marks":20,"graded_by":"TCH-004","date":"2022-09-18","status":"Pass"},
        {"id":"R008","student_id":"STU-001","subject_id":"SUB-004","semester":1,"exam_type":"end","marks_obtained":72,"max_marks":80,"graded_by":"TCH-004","date":"2022-11-23","status":"Pass"},
        {"id":"R009","student_id":"STU-001","subject_id":"SUB-005","semester":2,"exam_type":"internal","marks_obtained":36,"max_marks":40,"graded_by":"TCH-001","date":"2023-03-10","status":"Pass"},
        {"id":"R010","student_id":"STU-001","subject_id":"SUB-005","semester":2,"exam_type":"end","marks_obtained":50,"max_marks":60,"graded_by":"TCH-001","date":"2023-05-20","status":"Pass"},
        {"id":"R011","student_id":"STU-001","subject_id":"SUB-006","semester":2,"exam_type":"internal","marks_obtained":39,"max_marks":40,"graded_by":"TCH-001","date":"2023-03-12","status":"Pass"},
        {"id":"R012","student_id":"STU-001","subject_id":"SUB-006","semester":2,"exam_type":"end","marks_obtained":58,"max_marks":60,"graded_by":"TCH-001","date":"2023-05-22","status":"Pass"},
        {"id":"R013","student_id":"STU-001","subject_id":"SUB-007","semester":2,"exam_type":"internal","marks_obtained":33,"max_marks":40,"graded_by":"TCH-002","date":"2023-03-14","status":"Pass"},
        {"id":"R014","student_id":"STU-001","subject_id":"SUB-007","semester":2,"exam_type":"end","marks_obtained":49,"max_marks":60,"graded_by":"TCH-002","date":"2023-05-24","status":"Pass"},
        {"id":"R015","student_id":"STU-001","subject_id":"SUB-008","semester":3,"exam_type":"internal","marks_obtained":37,"max_marks":40,"graded_by":"TCH-002","date":"2023-09-15","status":"Pass"},
        {"id":"R016","student_id":"STU-001","subject_id":"SUB-009","semester":3,"exam_type":"internal","marks_obtained":28,"max_marks":40,"graded_by":"TCH-003","date":"2023-09-17","status":"Fail"},
        {"id":"R017","student_id":"STU-001","subject_id":"SUB-010","semester":3,"exam_type":"internal","marks_obtained":34,"max_marks":40,"graded_by":"TCH-003","date":"2023-09-19","status":"Pass"},
        {"id":"R018","student_id":"STU-001","subject_id":"SUB-011","semester":3,"exam_type":"internal","marks_obtained":36,"max_marks":40,"graded_by":"TCH-001","date":"2023-09-21","status":"Pass"},
        {"id":"R019","student_id":"STU-005","subject_id":"SUB-001","semester":1,"exam_type":"internal","marks_obtained":40,"max_marks":40,"graded_by":"TCH-001","date":"2022-09-15","status":"Pass"},
        {"id":"R020","student_id":"STU-005","subject_id":"SUB-001","semester":1,"exam_type":"end","marks_obtained":58,"max_marks":60,"graded_by":"TCH-001","date":"2022-11-20","status":"Pass"},
        {"id":"R021","student_id":"STU-005","subject_id":"SUB-002","semester":1,"exam_type":"internal","marks_obtained":38,"max_marks":40,"graded_by":"TCH-002","date":"2022-09-16","status":"Pass"},
        {"id":"R022","student_id":"STU-005","subject_id":"SUB-002","semester":1,"exam_type":"end","marks_obtained":57,"max_marks":60,"graded_by":"TCH-002","date":"2022-11-21","status":"Pass"},
        {"id":"R023","student_id":"STU-005","subject_id":"SUB-005","semester":2,"exam_type":"internal","marks_obtained":40,"max_marks":40,"graded_by":"TCH-001","date":"2023-03-10","status":"Pass"},
        {"id":"R024","student_id":"STU-005","subject_id":"SUB-005","semester":2,"exam_type":"end","marks_obtained":59,"max_marks":60,"graded_by":"TCH-001","date":"2023-05-20","status":"Pass"},
        {"id":"R025","student_id":"STU-002","subject_id":"SUB-012","semester":1,"exam_type":"internal","marks_obtained":30,"max_marks":40,"graded_by":"TCH-001","date":"2022-09-15","status":"Pass"},
        {"id":"R026","student_id":"STU-002","subject_id":"SUB-012","semester":1,"exam_type":"end","marks_obtained":42,"max_marks":60,"graded_by":"TCH-001","date":"2022-11-20","status":"Pass"},
        {"id":"R027","student_id":"STU-002","subject_id":"SUB-013","semester":1,"exam_type":"internal","marks_obtained":28,"max_marks":40,"graded_by":"TCH-002","date":"2022-09-16","status":"Fail"},
        {"id":"R028","student_id":"STU-002","subject_id":"SUB-013","semester":1,"exam_type":"end","marks_obtained":44,"max_marks":60,"graded_by":"TCH-002","date":"2022-11-21","status":"Pass"},
        {"id":"R029","student_id":"STU-003","subject_id":"SUB-022","semester":1,"exam_type":"internal","marks_obtained":25,"max_marks":40,"graded_by":"TCH-001","date":"2023-09-15","status":"Fail"},
        {"id":"R030","student_id":"STU-003","subject_id":"SUB-022","semester":1,"exam_type":"end","marks_obtained":38,"max_marks":60,"graded_by":"TCH-001","date":"2023-11-20","status":"Fail"},
        {"id":"R031","student_id":"STU-003","subject_id":"SUB-023","semester":1,"exam_type":"internal","marks_obtained":32,"max_marks":40,"graded_by":"TCH-002","date":"2023-09-16","status":"Pass"},
        {"id":"R032","student_id":"STU-003","subject_id":"SUB-023","semester":1,"exam_type":"end","marks_obtained":47,"max_marks":60,"graded_by":"TCH-002","date":"2023-11-21","status":"Pass"},
    ],
    "attendance": {
        "STU-001":{"SUB-008":{"present":22,"absent":2,"late":1,"total":25},"SUB-009":{"present":18,"absent":5,"late":2,"total":25},"SUB-010":{"present":23,"absent":1,"late":1,"total":25},"SUB-011":{"present":21,"absent":3,"late":1,"total":25}},
        "STU-002":{"SUB-015":{"present":20,"absent":4,"late":1,"total":25},"SUB-016":{"present":22,"absent":2,"late":1,"total":25}},
        "STU-003":{"SUB-025":{"present":19,"absent":4,"late":2,"total":25},"SUB-026":{"present":21,"absent":3,"late":1,"total":25}},
        "STU-004":{"SUB-020":{"present":15,"absent":8,"late":2,"total":25},"SUB-021":{"present":17,"absent":6,"late":2,"total":25}},
        "STU-005":{"SUB-008":{"present":24,"absent":1,"late":0,"total":25},"SUB-009":{"present":22,"absent":2,"late":1,"total":25},"SUB-010":{"present":25,"absent":0,"late":0,"total":25},"SUB-011":{"present":23,"absent":1,"late":1,"total":25}},
        "STU-006":{"SUB-015":{"present":18,"absent":5,"late":2,"total":25},"SUB-016":{"present":20,"absent":3,"late":2,"total":25}},
        "STU-007":{"SUB-001":{"present":20,"absent":3,"late":2,"total":25},"SUB-002":{"present":22,"absent":2,"late":1,"total":25},"SUB-003":{"present":19,"absent":4,"late":2,"total":25},"SUB-004":{"present":24,"absent":1,"late":0,"total":25}},
    },
    "exams": [
        {"id":"EXM-001","name":"Internal Assessment I","course_id":"CRS-001","semester":3,"date":"2023-09-15","exam_type":"internal","conducted_by":"TCH-001","status":"completed"},
        {"id":"EXM-002","name":"Mid Semester Exam","course_id":"CRS-001","semester":3,"date":"2023-10-20","exam_type":"mid","conducted_by":"TCH-001","status":"completed"},
        {"id":"EXM-003","name":"End Semester Exam","course_id":"CRS-001","semester":3,"date":"2023-11-30","exam_type":"end","conducted_by":"admin_1","status":"upcoming"},
        {"id":"EXM-004","name":"Internal Assessment I","course_id":"CRS-002","semester":2,"date":"2023-09-16","exam_type":"internal","conducted_by":"TCH-003","status":"completed"},
        {"id":"EXM-005","name":"Internal Assessment I","course_id":"CRS-004","semester":2,"date":"2023-09-15","exam_type":"internal","conducted_by":"TCH-001","status":"completed"},
    ],
}

def _init_data():
    save_data(DEFAULT_DATA)
    log.info("Initialized default data at %s", DATA_FILE)

# ── Routes: Auth ──────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    body  = request.get_json(silent=True) or {}
    email = body.get("email","").strip().lower()
    pw    = body.get("password","").strip()
    if not email or not pw:
        return jsonify({"ok":False,"msg":"Email and password required"}), 400
    d    = load_data()
    user = d["users"].get(email)
    if not user or user["password"] != pw:
        return jsonify({"ok":False,"msg":"Invalid email or password"}), 401
    session["user"] = {"email":email,"role":user["role"],"name":user["name"],"id":user["id"]}
    log.info("Login: %s (%s)", email, user["role"])
    return jsonify({"ok":True,"role":user["role"]})

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("app.html", user=session["user"])

@app.route("/health")
def health():
    return jsonify({"status":"ok","app":"EduManage Pro"})

# ── Routes: Password management ───────────────────────────────────────────────
@app.route("/api/change-password", methods=["POST"])
@login_required
def change_own_password():
    """Any logged-in user can change their own password."""
    d    = load_data()
    u    = session["user"]
    body = request.get_json(silent=True) or {}
    current = body.get("current_password","").strip()
    new_pw  = body.get("new_password","").strip()
    confirm = body.get("confirm_password","").strip()

    if not current or not new_pw or not confirm:
        return jsonify({"ok":False,"msg":"All fields are required"}), 400
    if new_pw != confirm:
        return jsonify({"ok":False,"msg":"New passwords do not match"}), 400
    if len(new_pw) < 6:
        return jsonify({"ok":False,"msg":"Password must be at least 6 characters"}), 400

    user = d["users"].get(u["email"])
    if not user or user["password"] != current:
        return jsonify({"ok":False,"msg":"Current password is incorrect"}), 401

    d["users"][u["email"]]["password"] = new_pw
    save_data(d)
    log.info("Password changed by user: %s", u["email"])
    return jsonify({"ok":True,"msg":"Password changed successfully"})


@app.route("/api/admin/change-password", methods=["POST"])
@login_required
@role_required("admin")
def admin_change_password():
    """Admin can reset any user's password without knowing the current one."""
    d    = load_data()
    body = request.get_json(silent=True) or {}
    email  = body.get("email","").strip().lower()
    new_pw = body.get("new_password","").strip()
    confirm= body.get("confirm_password","").strip()

    if not email or not new_pw or not confirm:
        return jsonify({"ok":False,"msg":"All fields are required"}), 400
    if new_pw != confirm:
        return jsonify({"ok":False,"msg":"Passwords do not match"}), 400
    if len(new_pw) < 6:
        return jsonify({"ok":False,"msg":"Password must be at least 6 characters"}), 400
    if email not in d["users"]:
        return jsonify({"ok":False,"msg":"User not found"}), 404

    d["users"][email]["password"] = new_pw
    save_data(d)
    log.info("Admin %s reset password for: %s", session["user"]["email"], email)
    return jsonify({"ok":True,"msg":f"Password updated for {d['users'][email]['name']}"})


@app.route("/api/admin/users")
@login_required
@role_required("admin")
def admin_list_users():
    """Returns all user accounts (without passwords) for the admin panel."""
    d = load_data()
    return jsonify([{
        "email": email,
        "name":  u["name"],
        "role":  u["role"],
        "id":    u["id"],
    } for email, u in d["users"].items()])

# ── Routes: Stats ─────────────────────────────────────────────────────────────
@app.route("/api/stats")
@login_required
def api_stats():
    d = load_data()
    flat = [att_pct(a) for sm in d["attendance"].values() for a in sm.values()]
    avg  = round(sum(flat)/len(flat)) if flat else 0
    res  = d["results"]
    pr   = round(sum(1 for r in res if r["status"]=="Pass")/len(res)*100) if res else 0
    low  = sum(1 for s in d["students"] if any(att_pct(a)<75 for a in d["attendance"].get(s["id"],{}).values()))
    return jsonify({"students":len(d["students"]),"teachers":len(d["teachers"]),"courses":len(d["courses"]),
                    "subjects":len(d["subjects"]),"departments":len(d["departments"]),
                    "results_count":len(res),"avg_att":avg,"pass_rate":pr,"low_att":low})

# ── Routes: Departments ───────────────────────────────────────────────────────
@app.route("/api/departments")
@login_required
def api_departments():
    d = load_data()
    tm = {t["id"]:t["name"] for t in d["teachers"]}
    out = []
    for dept in d["departments"]:
        tchs = [t for t in d["teachers"] if t["dept_id"]==dept["id"]]
        crss = [c for c in d["courses"]   if c["dept_id"]==dept["id"]]
        stus = [s for s in d["students"]  if any(c["id"]==s["course_id"] for c in crss)]
        out.append({**dept,"teacher_count":len(tchs),"course_count":len(crss),
                    "student_count":len(stus),"hod_name":tm.get(dept.get("hod",""),"—")})
    return jsonify(out)

# ── Routes: Teachers ──────────────────────────────────────────────────────────
@app.route("/api/teachers", methods=["GET"])
@login_required
def api_teachers():
    d = load_data()
    q  = request.args.get("q","").lower()
    di = request.args.get("dept_id","")
    dm = {dep["id"]:dep["name"] for dep in d["departments"]}
    ts = d["teachers"]
    if q:  ts = [t for t in ts if q in t["name"].lower() or q in t.get("specialization","").lower()]
    if di: ts = [t for t in ts if t["dept_id"]==di]
    return jsonify([{**t,"dept_name":dm.get(t["dept_id"],"—"),
                     "subject_count":len([s for s in d["subjects"] if s["teacher_id"]==t["id"]]),
                     "subjects":[{"id":s["id"],"name":s["name"],"code":s["code"],"course_id":s["course_id"]}
                                 for s in d["subjects"] if s["teacher_id"]==t["id"]]} for t in ts])

@app.route("/api/teachers", methods=["POST"])
@login_required
@role_required("admin")
def add_teacher():
    d = load_data(); body = request.get_json(silent=True) or {}
    if not body.get("name"): return jsonify({"ok":False,"msg":"Name required"}), 400
    tid = new_id("TCH-")
    t   = {"id":tid,"name":body["name"],"email":body.get("email",""),"phone":body.get("phone",""),
           "dept_id":body.get("dept_id",""),"specialization":body.get("specialization",""),
           "exp":int(body.get("exp",0)),"joined":datetime.now().strftime("%Y-%m-%d")}
    d["teachers"].append(t)
    if body.get("email") and body["email"] not in d["users"]:
        d["users"][body["email"]] = {"password":"teacher123","role":"teacher","name":body["name"],"id":tid}
    save_data(d); return jsonify({"ok":True,"teacher":t})

@app.route("/api/teachers/<tid>", methods=["DELETE"])
@login_required
@role_required("admin")
def delete_teacher(tid):
    d = load_data(); d["teachers"]=[t for t in d["teachers"] if t["id"]!=tid]; save_data(d); return jsonify({"ok":True})

# ── Routes: Courses ───────────────────────────────────────────────────────────
@app.route("/api/courses")
@login_required
def api_courses():
    d = load_data(); dm = {dep["id"]:dep["name"] for dep in d["departments"]}
    return jsonify([{**c,"dept_name":dm.get(c["dept_id"],"—"),
                     "subject_count":len([s for s in d["subjects"] if s["course_id"]==c["id"]]),
                     "student_count":len([s for s in d["students"] if s["course_id"]==c["id"]]),
                     "actual_credits":sum(s["credits"] for s in d["subjects"] if s["course_id"]==c["id"]),
                     "semesters":sorted(set(s["semester"] for s in d["subjects"] if s["course_id"]==c["id"]))}
                    for c in d["courses"]])

# ── Routes: Subjects ──────────────────────────────────────────────────────────
@app.route("/api/subjects", methods=["GET"])
@login_required
def api_subjects():
    d  = load_data()
    ci = request.args.get("course_id",""); ti = request.args.get("teacher_id",""); si = request.args.get("semester","")
    tm = {t["id"]:t["name"] for t in d["teachers"]}; cm = {c["id"]:c["name"] for c in d["courses"]}
    ss = d["subjects"]
    if ci: ss = [s for s in ss if s["course_id"]==ci]
    if ti: ss = [s for s in ss if s["teacher_id"]==ti]
    if si: ss = [s for s in ss if str(s["semester"])==si]
    return jsonify([{**s,"teacher_name":tm.get(s["teacher_id"],"Unassigned"),"course_name":cm.get(s["course_id"],"—")} for s in ss])

@app.route("/api/subjects", methods=["POST"])
@login_required
@role_required("admin")
def add_subject():
    d = load_data(); body = request.get_json(silent=True) or {}
    if not body.get("name"): return jsonify({"ok":False,"msg":"Name required"}), 400
    s = {"id":new_id("SUB-"),"name":body["name"],"code":body.get("code",""),
         "course_id":body.get("course_id",""),"semester":int(body.get("semester",1)),
         "credits":int(body.get("credits",3)),"teacher_id":body.get("teacher_id",""),
         "type":body.get("type","core"),"max_marks":int(body.get("max_marks",100)),
         "passing_marks":int(body.get("passing_marks",40))}
    d["subjects"].append(s); save_data(d); return jsonify({"ok":True,"subject":s})

@app.route("/api/subjects/<sid>", methods=["PUT"])
@login_required
@role_required("admin")
def update_subject(sid):
    d = load_data(); body = request.get_json(silent=True) or {}
    for s in d["subjects"]:
        if s["id"]==sid:
            for k in ("teacher_id","name","code","type"):
                if k in body: s[k]=body[k]
            for k in ("credits","semester","max_marks","passing_marks"):
                if k in body: s[k]=int(body[k])
            break
    else: return jsonify({"ok":False,"msg":"Not found"}), 404
    save_data(d); return jsonify({"ok":True})

@app.route("/api/subjects/<sid>", methods=["DELETE"])
@login_required
@role_required("admin")
def delete_subject(sid):
    d = load_data(); d["subjects"]=[s for s in d["subjects"] if s["id"]!=sid]; save_data(d); return jsonify({"ok":True})

# ── Routes: Students ──────────────────────────────────────────────────────────
@app.route("/api/students", methods=["GET"])
@login_required
def api_students():
    d  = load_data(); q=request.args.get("q","").lower(); ci=request.args.get("course_id","")
    cm = {c["id"]:c["name"] for c in d["courses"]}
    ss = d["students"]
    if q:  ss=[s for s in ss if q in s["name"].lower() or q in s["id"].lower() or q in s.get("roll","").lower()]
    if ci: ss=[s for s in ss if s["course_id"]==ci]
    out=[]
    for s in ss:
        ad=d["attendance"].get(s["id"],{}); pcts=[att_pct(a) for a in ad.values()]
        mr=[r for r in d["results"] if r["student_id"]==s["id"]]
        sg,_=calc_sgpa(mr,d["subjects"]) if mr else (0.0,0)
        out.append({**s,"course_name":cm.get(s["course_id"],"—"),"avg_att":round(sum(pcts)/len(pcts)) if pcts else 0,"cgpa":sg})
    return jsonify(out)

@app.route("/api/students/<sid>", methods=["GET"])
@login_required
def get_student(sid):
    u=session["user"]
    if u["role"]=="student" and u["id"]!=sid: return jsonify({"error":"Forbidden"}), 403
    d=load_data(); s=next((x for x in d["students"] if x["id"]==sid),None)
    if not s: return jsonify({"error":"Not found"}), 404
    cm={c["id"]:c for c in d["courses"]}; tm={t["id"]:t["name"] for t in d["teachers"]}
    course=cm.get(s["course_id"],{}); csubs=[sub for sub in d["subjects"] if sub["course_id"]==s["course_id"]]
    sems=sorted(set(sub["semester"] for sub in csubs)); mr=[r for r in d["results"] if r["student_id"]==sid]
    ad=d["attendance"].get(sid,{}); semester_data=[]
    for sem in sems:
        ss2=[sub for sub in csubs if sub["semester"]==sem]; sr=[r for r in mr if r["semester"]==sem]
        sgpa,cred=calc_sgpa(sr,ss2); sds=[]
        for sub in ss2:
            sub_rs=[r for r in sr if r["subject_id"]==sub["id"]]
            e=sum(r["marks_obtained"] for r in sub_rs); mx=sum(r["max_marks"] for r in sub_rs)
            pct=round(e/mx*100) if mx else None; g,gp=letter_grade(pct) if pct is not None else ("—",0)
            st2="Pass" if pct is not None and pct>=sub["passing_marks"] else ("Fail" if pct is not None else "Pending")
            sa=ad.get(sub["id"],{})
            sds.append({"subject_id":sub["id"],"name":sub["name"],"code":sub["code"],"credits":sub["credits"],
                        "type":sub["type"],"teacher":tm.get(sub["teacher_id"],"—"),"results":sub_rs,
                        "total_earned":e,"total_max":mx,"pct":pct,"grade":g,"grade_point":gp,"status":st2,
                        "att":sa,"att_pct":att_pct(sa) if sa else None})
        sl="Completed" if sem<s["current_sem"] else ("Current" if sem==s["current_sem"] else "Upcoming")
        semester_data.append({"semester":sem,"subjects":sds,"sgpa":sgpa,"credits_earned":cred,"status":sl})
    comp=[sd for sd in semester_data if sd["status"]=="Completed"]
    tc=sum(sd["credits_earned"] for sd in comp); tp=sum(sd["sgpa"]*sd["credits_earned"] for sd in comp)
    cgpa=round(tp/tc,2) if tc else 0.0
    return jsonify({**s,"course":course,"course_name":cm.get(s["course_id"],{}).get("name","—"),"semester_data":semester_data,"cgpa":cgpa})

@app.route("/api/students", methods=["POST"])
@login_required
@role_required("admin")
def add_student():
    d=load_data(); body=request.get_json(silent=True) or {}
    if not body.get("name"): return jsonify({"ok":False,"msg":"Name required"}), 400
    sid=new_id("STU-")
    s={"id":sid,"name":body["name"],"email":body.get("email",""),"phone":body.get("phone",""),
       "dob":body.get("dob",""),"course_id":body.get("course_id",""),"current_sem":int(body.get("current_sem",1)),
       "city":body.get("city",""),"state":body.get("state",""),"roll":body.get("roll",""),
       "admission_year":int(body.get("admission_year",datetime.now().year))}
    d["students"].append(s); d["attendance"][sid]={}
    if body.get("email") and body["email"] not in d["users"]:
        d["users"][body["email"]]={"password":"student123","role":"student","name":body["name"],"id":sid}
    save_data(d); return jsonify({"ok":True,"student":s})

@app.route("/api/students/<sid>", methods=["DELETE"])
@login_required
@role_required("admin")
def delete_student(sid):
    d=load_data(); d["students"]=[s for s in d["students"] if s["id"]!=sid]
    d["attendance"].pop(sid,None); d["results"]=[r for r in d["results"] if r["student_id"]!=sid]
    save_data(d); return jsonify({"ok":True})

# ── Routes: Results ───────────────────────────────────────────────────────────
@app.route("/api/results", methods=["GET"])
@login_required
def api_results():
    d=load_data(); u=session["user"]
    sti=request.args.get("student_id",""); sui=request.args.get("subject_id","")
    sem=request.args.get("semester",""); ti=request.args.get("teacher_id","")
    if u["role"]=="student": sti=u["id"]
    rs=d["results"]
    if sti: rs=[r for r in rs if r["student_id"]==sti]
    if sui: rs=[r for r in rs if r["subject_id"]==sui]
    if sem: rs=[r for r in rs if str(r["semester"])==sem]
    if ti:
        my={s["id"] for s in d["subjects"] if s["teacher_id"]==ti}; rs=[r for r in rs if r["subject_id"] in my]
    sm={s["id"]:s for s in d["subjects"]}; stm={s["id"]:s["name"] for s in d["students"]}; tm={t["id"]:t["name"] for t in d["teachers"]}
    out=[]
    for r in rs:
        sub=sm.get(r["subject_id"],{}); pct=round(r["marks_obtained"]/r["max_marks"]*100) if r["max_marks"] else 0
        g,gp=letter_grade(pct)
        out.append({**r,"subject_name":sub.get("name","—"),"subject_code":sub.get("code","—"),
                    "student_name":stm.get(r["student_id"],"—"),"graded_by_name":tm.get(r.get("graded_by",""),"—"),
                    "pct":pct,"grade":g,"grade_point":gp})
    return jsonify(out)

@app.route("/api/results", methods=["POST"])
@login_required
@role_required("admin","teacher")
def add_result():
    d=load_data(); body=request.get_json(silent=True) or {}; u=session["user"]
    sub=next((s for s in d["subjects"] if s["id"]==body.get("subject_id","")),None)
    if not sub: return jsonify({"ok":False,"msg":"Subject not found"}), 400
    if u["role"]=="teacher" and sub["teacher_id"]!=u["id"]:
        return jsonify({"ok":False,"msg":"You can only grade your assigned subjects"}), 403
    mk=int(body.get("marks_obtained",0)); mx=int(body.get("max_marks",sub["max_marks"]))
    pct=round(mk/mx*100) if mx else 0
    r={"id":new_id("R"),"student_id":body.get("student_id",""),"subject_id":sub["id"],
       "semester":body.get("semester",sub["semester"]),"exam_type":body.get("exam_type","internal"),
       "marks_obtained":mk,"max_marks":mx,"graded_by":u["id"],
       "date":body.get("date",datetime.now().strftime("%Y-%m-%d")),
       "status":"Pass" if pct>=sub["passing_marks"] else "Fail"}
    d["results"].append(r); save_data(d); return jsonify({"ok":True,"result":r})

# ── Routes: Attendance ────────────────────────────────────────────────────────
@app.route("/api/attendance", methods=["GET"])
@login_required
def api_attendance():
    d=load_data(); u=session["user"]
    sti=request.args.get("student_id",""); sui=request.args.get("subject_id","")
    if u["role"]=="student": sti=u["id"]
    if sti:
        at=d["attendance"].get(sti,{}); sm={s["id"]:s for s in d["subjects"]}
        return jsonify([{"subject_id":sid,"subject_name":sm.get(sid,{}).get("name","—"),
                         "subject_code":sm.get(sid,{}).get("code","—"),"semester":sm.get(sid,{}).get("semester",0),
                         "credits":sm.get(sid,{}).get("credits",0),"att":a,"pct":att_pct(a)} for sid,a in at.items()])
    if sui:
        return jsonify([{"student_id":s["id"],"student_name":s["name"],
                         "att":d["attendance"].get(s["id"],{}).get(sui,{"present":0,"absent":0,"late":0,"total":0}),
                         "pct":att_pct(d["attendance"].get(s["id"],{}).get(sui,{}))} for s in d["students"]])
    cm={c["id"]:c["name"] for c in d["courses"]}
    return jsonify([{"student_id":s["id"],"student_name":s["name"],"course_name":cm.get(s["course_id"],"—"),
                     "current_sem":s["current_sem"],
                     "avg_att":round(sum(att_pct(a) for a in d["attendance"].get(s["id"],{}).values())/
                               max(len(d["attendance"].get(s["id"],{})),1)),
                     "subjects":d["attendance"].get(s["id"],{}),"subject_count":len(d["attendance"].get(s["id"],{}))}
                    for s in d["students"]])

@app.route("/api/attendance", methods=["POST"])
@login_required
@role_required("admin","teacher")
def mark_attendance():
    d=load_data(); body=request.get_json(silent=True) or {}; u=session["user"]
    sub_id=body.get("subject_id",""); records=body.get("records",[])
    if u["role"]=="teacher":
        sub=next((s for s in d["subjects"] if s["id"]==sub_id),None)
        if not sub or sub["teacher_id"]!=u["id"]:
            return jsonify({"ok":False,"msg":"You can only mark attendance for your subjects"}), 403
    for rec in records:
        sid=rec.get("student_id",""); st=rec.get("status","present")
        if sid not in d["attendance"]: d["attendance"][sid]={}
        if sub_id not in d["attendance"][sid]: d["attendance"][sid][sub_id]={"present":0,"absent":0,"late":0,"total":0}
        a=d["attendance"][sid][sub_id]; k="present" if st=="present" else ("absent" if st=="absent" else "late")
        a[k]+=1; a["total"]=a["present"]+a["absent"]+a["late"]
    save_data(d); return jsonify({"ok":True})

# ── Routes: Exams ─────────────────────────────────────────────────────────────
@app.route("/api/exams", methods=["GET"])
@login_required
def api_exams():
    d=load_data(); u=session["user"]
    cm={c["id"]:c["name"] for c in d["courses"]}; tm={t["id"]:t["name"] for t in d["teachers"]}
    exs=d["exams"]
    if u["role"]=="teacher":
        mc={s["course_id"] for s in d["subjects"] if s["teacher_id"]==u["id"]}; exs=[e for e in exs if e["course_id"] in mc]
    return jsonify([{**e,"course_name":cm.get(e["course_id"],"—"),"conducted_by_name":tm.get(e.get("conducted_by",""),"Admin")} for e in exs])

@app.route("/api/exams", methods=["POST"])
@login_required
@role_required("admin")
def add_exam():
    d=load_data(); body=request.get_json(silent=True) or {}
    e={"id":new_id("EXM-"),"name":body.get("name",""),"course_id":body.get("course_id",""),
       "semester":int(body.get("semester",1)),"date":body.get("date",""),
       "exam_type":body.get("exam_type","internal"),"conducted_by":session["user"]["id"],
       "status":body.get("status","upcoming")}
    d["exams"].append(e); save_data(d); return jsonify({"ok":True,"exam":e})

# ── Routes: Analytics ─────────────────────────────────────────────────────────
@app.route("/api/analytics")
@login_required
def api_analytics():
    d=load_data(); rs=d["results"]; stus=d["students"]
    pr=round(sum(1 for r in rs if r["status"]=="Pass")/len(rs)*100) if rs else 0
    return jsonify({"pass_rate":pr,"monthly_att":[72,75,78,74,80,77],"monthly_pass":[65,70,72,68,76,80],
                    "months":["Jul","Aug","Sep","Oct","Nov","Dec"],
                    "course_dist":[{"name":c["name"],"code":c["code"],"count":sum(1 for s in stus if s["course_id"]==c["id"])} for c in d["courses"]]})

# ── Routes: CSV Import ────────────────────────────────────────────────────────
@app.route("/api/import/students", methods=["POST"])
@login_required
@role_required("admin")
def import_students():
    d=load_data(); f=request.files.get("file")
    if not f: return jsonify({"ok":False,"msg":"No file"}), 400
    try: reader=csv.DictReader(io.StringIO(f.read().decode("utf-8")))
    except Exception: return jsonify({"ok":False,"msg":"Cannot parse CSV"}), 400
    n=0
    for row in reader:
        sid=row.get("student_id","").strip()
        if sid and not any(s["id"]==sid for s in d["students"]):
            d["students"].append({"id":sid,"name":row.get("name","").strip(),"email":row.get("email","").strip(),
                                   "phone":row.get("phone","").strip(),"dob":row.get("dob","").strip(),
                                   "course_id":row.get("course_id","").strip(),"current_sem":int(row.get("current_sem","1") or 1),
                                   "city":row.get("city","").strip(),"state":row.get("state","").strip(),
                                   "roll":row.get("roll","").strip(),"admission_year":int(row.get("admission_year",datetime.now().year) or datetime.now().year)})
            d["attendance"][sid]={}; n+=1
    save_data(d); return jsonify({"ok":True,"imported":n})

@app.route("/api/import/results", methods=["POST"])
@login_required
@role_required("admin")
def import_results():
    d=load_data(); f=request.files.get("file")
    if not f: return jsonify({"ok":False,"msg":"No file"}), 400
    try: reader=csv.DictReader(io.StringIO(f.read().decode("utf-8")))
    except Exception: return jsonify({"ok":False,"msg":"Cannot parse CSV"}), 400
    scm={s["code"]:s for s in d["subjects"]}; n=0
    for row in reader:
        sub=scm.get(row.get("subject_code","").strip()); stu=row.get("student_id","").strip()
        if sub and stu:
            mk=int(row.get("marks",0) or 0); mx=int(row.get("max_marks",sub["max_marks"]) or sub["max_marks"])
            pct=round(mk/mx*100) if mx else 0
            d["results"].append({"id":new_id("R"),"student_id":stu,"subject_id":sub["id"],"semester":sub["semester"],
                                  "exam_type":row.get("exam_type","internal").strip(),"marks_obtained":mk,"max_marks":mx,
                                  "graded_by":row.get("teacher_id","").strip(),
                                  "date":row.get("date",datetime.now().strftime("%Y-%m-%d")).strip(),
                                  "status":"Pass" if pct>=sub["passing_marks"] else "Fail"}); n+=1
    save_data(d); return jsonify({"ok":True,"imported":n})

# ── Error handlers ────────────────────────────────────────────────────────────
@app.errorhandler(404)
def not_found(e):
    return (jsonify({"error":"Not found"}),404) if request.is_json else (render_template("login.html"),404)

@app.errorhandler(500)
def server_error(e):
    log.exception("500"); return (jsonify({"error":"Internal server error"}),500) if request.is_json else (render_template("login.html"),500)

@app.errorhandler(413)
def too_large(e): return jsonify({"error":"File too large (max 5 MB)"}), 413

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not os.path.exists(DATA_FILE):
        _init_data()
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("DEBUG","false").lower() == "true"
    log.info("EduManage Pro starting on port %d (debug=%s)", port, debug)
    app.run(host="0.0.0.0", port=port, debug=debug)
