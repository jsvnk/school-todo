import os
from datetime import datetime

from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------------------------------
# KONFIGURACIJA
# -------------------------------------------------
app = Flask(__name__)

# Skrivni ključ za seje (session). V produkciji ga nastavi kot env var SECRET_KEY.
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-this-dev-secret")

# DATABASE_URL bo nastavljen v oblaku (PostgreSQL).
# Lokalno, če ni nastavljena, uporabimo SQLite datoteko.
db_url = os.getenv("DATABASE_URL", "sqlite:///tasks.db")

# Nekateri providerji uporabljajo "postgres://", SQLAlchemy hoče "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"  # če ni prijavljen, ga preusmeri na /login


# -------------------------------------------------
# MODELI
# -------------------------------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Task(db.Model):
    # ime tabele bo "task" (da ostane isto kot prej)
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)        # naslov naloge
    task_type = db.Column(db.String(50), nullable=False)     # npr. "naloga", "kolokvij", "kviz"
    subject = db.Column(db.String(100), nullable=False)      # predmet (Matematika, Fizika ...)
    due_date = db.Column(db.Date, nullable=False)            # rok (datum)
    description = db.Column(db.Text)                         # opis, link na ucilnice
    is_done = db.Column(db.Boolean, default=False)           # ali je opravljena

    # uporabnik, ki mu naloga pripada
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    user = db.relationship("User", backref="tasks")

    def is_overdue(self):
        return (not self.is_done) and self.due_date < datetime.today().date()

    def is_soon(self):
        # "kmalu" = danes ali jutri
        today = datetime.today().date()
        delta = (self.due_date - today).days
        return (not self.is_done) and (0 <= delta <= 1)


@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))


# -------------------------------------------------
# INITIALIZACIJA BAZE
# -------------------------------------------------
with app.app_context():
    db.create_all()


# -------------------------------------------------
# ROUTES
# -------------------------------------------------

@app.route("/")
@login_required
def index():
    show_done = request.args.get("show_done", "0") == "1"

    query = Task.query.filter_by(user_id=current_user.id).order_by(Task.due_date.asc())
    if not show_done:
        query = query.filter(Task.is_done.is_(False))

    tasks = query.all()
    return render_template("index.html", tasks=tasks, show_done=show_done)


@app.route("/add", methods=["GET", "POST"])
@login_required
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
            user_id=current_user.id,
        )
        db.session.add(task)
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("add_task.html")


@app.route("/done/<int:task_id>")
@login_required
def mark_done(task_id):
    task = Task.query.get_or_404(task_id)
    # za vsak slučaj: dovolimo spreminjati samo svoje naloge
    if task.user_id != current_user.id:
        return redirect(url_for("index"))

    task.is_done = True
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/undo/<int:task_id>")
@login_required
def mark_undone(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return redirect(url_for("index"))

    task.is_done = False
    db.session.commit()
    return redirect(url_for("index"))


# --------- AUTH ---------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        if not username or not password:
            return render_template("register.html", error="Uporabniško ime in geslo sta obvezna.")

        existing = User.query.filter_by(username=username).first()
        if existing:
            return render_template("register.html", error="Uporabniško ime že obstaja.")

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        login_user(user)
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()

        user = User.query.filter_by(username=username).first()
        if user is None or not user.check_password(password):
            return render_template("login.html", error="Napačno uporabniško ime ali geslo.")

        login_user(user)
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


if __name__ == "__main__":
    # Lokalni development server
    app.run(debug=True)
    app.run(debug=True)
