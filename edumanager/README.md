# EduManage Pro

A production-ready Student Management System built with **Python Flask**.

---

## ⚡ Quick start (local)

```bash
# 1. Clone / unzip the project
cd edumanage_deploy

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run
python app.py
```

Open **http://localhost:5000**

---

## 🔐 Demo login accounts

| Role    | Email                 | Password     |
|---------|-----------------------|--------------|
| Admin   | admin@school.edu      | admin123     |
| Teacher | rajesh@school.edu     | teacher123   |
| Teacher | meera@school.edu      | teacher123   |
| Student | ananya@school.edu     | student123   |
| Student | rohan@school.edu      | student123   |

---

## 🚀 Deploy to the cloud

### Option A — Render (recommended, free tier)

1. Push code to a GitHub repository
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your repo — Render detects `render.yaml` automatically
4. Click **Deploy** — done in ~2 minutes

The `render.yaml` already configures:
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn -w 2 -b 0.0.0.0:$PORT app:app`
- Auto-generated `SECRET_KEY`
- 1 GB persistent disk for `data.json`

### Option B — Railway

1. Push code to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variable: `SECRET_KEY` = any long random string
4. Railway uses `railway.toml` — deploy is automatic

### Option C — Heroku

```bash
heroku create your-app-name
heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
git push heroku main
```

### Option D — Fly.io

```bash
fly launch           # follow prompts
fly secrets set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
fly deploy
```

---

## ⚙️ Environment variables

| Variable     | Required | Default                     | Description                        |
|--------------|----------|-----------------------------|-------------------------------------|
| `SECRET_KEY` | **Yes**  | `CHANGE-ME-IN-PRODUCTION`  | Flask session signing secret        |
| `DATA_FILE`  | No       | `./data.json` (next to app) | Path to the JSON database           |
| `PORT`       | No       | `5000`                      | Port the server listens on          |
| `DEBUG`      | No       | `false`                     | Set `true` for development only     |
| `HTTPS`      | No       | `false`                     | Set `true` to enable secure cookies |

> ⚠️ **Never deploy with the default `SECRET_KEY`.**  
> Generate one with: `python -c "import secrets; print(secrets.token_hex(32))"`

---

## 🗂 Project structure

```
edumanage_deploy/
├── app.py              ← Flask app (all routes + business logic)
├── requirements.txt    ← Python dependencies
├── Procfile            ← Heroku/Render/Railway process file
├── render.yaml         ← Render one-click config
├── railway.toml        ← Railway config
├── .gitignore
├── README.md
├── data.json           ← JSON database (auto-created on first run)
└── templates/
    ├── login.html
    └── app.html
```

---

## 📡 API endpoints

All endpoints (except `/`, `/login`, `/logout`, `/health`) require a valid session.

| Method | Route                       | Role           | Description                          |
|--------|-----------------------------|----------------|--------------------------------------|
| GET    | `/health`                   | Public         | Health check for uptime monitors     |
| POST   | `/login`                    | Public         | JSON `{email, password}`             |
| GET    | `/api/stats`                | All            | Dashboard statistics                 |
| GET    | `/api/students`             | Admin/Teacher  | List students (filter: `q`, `course_id`) |
| GET    | `/api/students/<id>`        | All*           | Student detail + semester results    |
| POST   | `/api/students`             | Admin          | Enrol new student                    |
| DELETE | `/api/students/<id>`        | Admin          | Delete student                       |
| GET    | `/api/teachers`             | All            | List teachers                        |
| POST   | `/api/teachers`             | Admin          | Add teacher                          |
| DELETE | `/api/teachers/<id>`        | Admin          | Remove teacher                       |
| GET    | `/api/courses`              | All            | List courses with subject counts     |
| GET    | `/api/subjects`             | All            | List subjects (filter: `course_id`, `teacher_id`) |
| POST   | `/api/subjects`             | Admin          | Add subject to a course              |
| PUT    | `/api/subjects/<id>`        | Admin          | Edit subject / reassign teacher      |
| DELETE | `/api/subjects/<id>`        | Admin          | Remove subject                       |
| GET    | `/api/results`              | All*           | List results (students see own only) |
| POST   | `/api/results`              | Admin/Teacher  | Grade a result (live pass/fail calc) |
| GET    | `/api/attendance`           | All*           | Attendance data                      |
| POST   | `/api/attendance`           | Admin/Teacher  | Mark attendance for a subject        |
| GET    | `/api/exams`                | All            | Exam schedule                        |
| POST   | `/api/exams`                | Admin          | Schedule an exam                     |
| GET    | `/api/departments`          | All            | Department list with stats           |
| GET    | `/api/analytics`            | All            | Charts and trend data                |
| POST   | `/api/import/students`      | Admin          | CSV bulk import of students          |
| POST   | `/api/import/results`       | Admin          | CSV bulk import of results           |

*Students are restricted to their own data only.

---

## 🏗 Production notes

- **Data storage**: `data.json` is an atomic file — writes use a `.tmp` file + `os.replace()` to prevent corruption on crash.
- **Concurrency**: With `gunicorn -w 2`, both workers share the same `data.json`. This is safe for low traffic. For high traffic, switch to SQLite or PostgreSQL.
- **Passwords**: Plain text passwords are used for the demo. For production, hash them with `werkzeug.security.generate_password_hash`.
- **Sessions**: Server-side Flask sessions signed with `SECRET_KEY`. Set `HTTPS=true` to enable secure cookies when behind HTTPS.
- **Upload limit**: CSV files are capped at 5 MB via `MAX_CONTENT_LENGTH`.
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` added to every response.

---

## 📊 Grade scale (10-point)

| % Range | Grade | GP  |
|---------|-------|-----|
| ≥ 90    | O     | 10  |
| ≥ 80    | A+    | 9   |
| ≥ 70    | A     | 8   |
| ≥ 60    | B+    | 7   |
| ≥ 50    | B     | 6   |
| ≥ 40    | C     | 5   |
| < 40    | F     | 0   |

**SGPA** = Σ(GP × Credits) ÷ Σ Credits per semester  
**CGPA** = Σ(SGPA × Sem Credits) ÷ Total Credits (completed semesters only)
