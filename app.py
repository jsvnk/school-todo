import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy

# -------------------------------------------------
# KONFIGURACIJA
# -------------------------------------------------
app = Flask(__name__)

# Skrivni ključ za seje (session). V produkciji ga nastavi kot env var SECRET_KEY.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-dev-secret")

# Hardcodan uporabnik (zaenkrat samo en):
APP_USERNAME = os.getenv("APP_USERNAME", "jsvnk")
APP_PASSWORD = os.getenv("APP_PASSWORD", "pikapolonica")

# DATABASE_URL bo nastavljen v oblaku (PostgreSQL).
# Lokalno, če ni nastavljena, uporabimo SQLite datoteko.
db_url = os.getenv("DATABASE_URL", "sqlite:///tasks.db")

# Nekateri providerji uporabljajo "postgres://", SQLAlchemy hoče "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Predefinirani tipi nalog
TASK_TYPES = [
    "Kviz iz vaj",
    "Kviz iz teorije",
    "Vaja",
    "Kolokvij",
    "Izpit",
    "Test iz vaj",
]


# -------------------------------------------------
# MODEL: naloga
# -------------------------------------------------
class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)        # naslov naloge
    task_type = db.Column(db.String(50), nullable=False)     # npr. "naloga", "kolokvij", "kviz"
    subject = db.Column(db.String(100), nullable=False)      # predmet (Matematika, Fizika ...)
    due_date = db.Column(db.Date, nullable=False)            # rok (datum)
    description = db.Column(db.Text)                         # opis, link na ucilnice
    is_done = db.Column(db.Boolean, default=False)           # ali je opravljena

    def is_overdue(self):
        return (not self.is_done) and self.due_date < datetime.today().date()

    def is_soon(self):
        # "kmalu" = danes ali jutri
        today = datetime.today().date()
        delta = (self.due_date - today).days
        return (not self.is_done) and (0 <= delta <= 1)


# -------------------------------------------------
# INITIALIZACIJA BAZE
# -------------------------------------------------
with app.app_context():
    db.create_all()


# -------------------------------------------------
# POMOŽNE FUNKCIJE ZA LOGIN
# -------------------------------------------------

def is_logged_in() -> bool:
    return session.get("logged_in", False)


def require_login(endpoint_name: str) -> bool:
    """Ali je treba biti prijavljen za dostop do endpointa."""
    public_endpoints = {"login", "static"}
    return endpoint_name not in public_endpoints


@app.before_request
def check_login():
    # Če endpoint ni znan (npr. 404), preskočimo
    endpoint = request.endpoint
    if not endpoint:
        return

    if require_login(endpoint) and not is_logged_in():
        return redirect(url_for("login"))


# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.route("/")
def index():
    show_done = request.args.get("show_done", "0") == "1"
    subject_filter = request.args.get("subject", "")

    # seznam vseh predmetov za filter (distinct)
    subjects = [s[0] for s in db.session.query(Task.subject).distinct().order_by(Task.subject).all()]

    query = Task.query.order_by(Task.due_date.asc())
    if subject_filter:
        query = query.filter(Task.subject == subject_filter)
    if not show_done:
        query = query.filter(Task.is_done.is_(False))

    tasks = query.all()
    return render_template(
        "index.html",
        tasks=tasks,
        show_done=show_done,
        subjects=subjects,
        subject_filter=subject_filter,
    )


@app.route("/add", methods=["GET", "POST"])
def add_task():
    if request.method == "POST":
        title = request.form["title"].strip()
        task_type = request.form["task_type"].strip()
        subject = request.form["subject"].strip()
        due_date_str = request.form["due_date"]
        description = request.form.get("description", "").strip()

        # HTML <input type="date"> vrne "YYYY-MM-DD"
        due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()

        task = Task(
            title=title,
            task_type=task_type,
            subject=subject,
            due_date=due_date,
            description=description,
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("add_task.html", task=None, task_types=TASK_TYPES)


@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)

    if request.method == "POST":
        task.title = request.form["title"].strip()
        task.task_type = request.form["task_type"].strip()
        task.subject = request.form["subject"].strip()
        due_date_str = request.form["due_date"]
        task.description = request.form.get("description", "").strip()

        task.due_date = datetime.strptime(due_date_str, "%Y-%m-%d").date()

        db.session.commit()
        return redirect(url_for("index"))

    # za GET vrnemo formo z že izpolnjenimi podatki
    return render_template("add_task.html", task=task, task_types=TASK_TYPES)


@app.route("/delete/<int:task_id>", methods=["POST"])
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/done/<int:task_id>")
def mark_done(task_id):
    task = Task.query.get_or_404(task_id)
    task.is_done = True
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/undo/<int:task_id>")
def mark_undone(task_id):
    task = Task.query.get_or_404(task_id)
    task.is_done = False
    db.session.commit()
    return redirect(url_for("index"))


# --------- AUTH (hardcodan uporabnik) ---------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if username == APP_USERNAME and password == APP_PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        else:
            error = "Napačno uporabniško ime ali geslo."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    # Lokalni development server
    app.run(debug=True)
    app.run(debug=True)
