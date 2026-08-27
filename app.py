import os
import hashlib
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "sales_product.db")
DATABASE_TIMEOUT = float(os.environ.get("DATABASE_TIMEOUT", "30"))
RESET_TOKEN_MINUTES = int(os.environ.get("RESET_TOKEN_MINUTES", "15"))

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-this-secret"),
    DATABASE=DATABASE,
    DATABASE_TIMEOUT=DATABASE_TIMEOUT,
    RESET_TOKEN_MINUTES=RESET_TOKEN_MINUTES,
)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(
            app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
        )
        g.db.row_factory = sqlite3.Row
    return g.db


def init_db():
    db = sqlite3.connect(
        app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
    )
    try:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token_hash TEXT NOT NULL UNIQUE,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_reset_tokens_user_id
                ON password_reset_tokens(user_id);
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sku TEXT NOT NULL COLLATE NOCASE UNIQUE,
                price_cents INTEGER NOT NULL CHECK (price_cents >= 0),
                product_group TEXT NOT NULL DEFAULT 'General',
                category TEXT,
                brand TEXT,
                description TEXT,
                unit TEXT NOT NULL DEFAULT 'piece',
                cost_price_cents INTEGER CHECK (cost_price_cents >= 0),
                tax_rate REAL NOT NULL DEFAULT 0 CHECK (tax_rate >= 0 AND tax_rate <= 100),
                stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
                reorder_level INTEGER NOT NULL DEFAULT 0 CHECK (reorder_level >= 0),
                supplier TEXT,
                barcode TEXT COLLATE NOCASE,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_products_sku ON products(sku);
            CREATE TABLE IF NOT EXISTS app_settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL CHECK (setting_value IN ('0', '1'))
            );
            INSERT OR IGNORE INTO app_settings (setting_key, setting_value)
                VALUES ('show_sales_app', '1'), ('show_products', '1'), ('show_customers', '1');
            """
        )
        existing_columns = {
            row[1] for row in db.execute("PRAGMA table_info(products)").fetchall()
        }
        product_columns = {
            "product_group": "TEXT NOT NULL DEFAULT 'General'",
            "category": "TEXT",
            "brand": "TEXT",
            "description": "TEXT",
            "unit": "TEXT NOT NULL DEFAULT 'piece'",
            "cost_price_cents": "INTEGER",
            "tax_rate": "REAL NOT NULL DEFAULT 0",
            "stock_quantity": "INTEGER NOT NULL DEFAULT 0",
            "reorder_level": "INTEGER NOT NULL DEFAULT 0",
            "supplier": "TEXT",
            "barcode": "TEXT",
            "status": "TEXT NOT NULL DEFAULT 'active'",
        }
        for column, definition in product_columns.items():
            if column not in existing_columns:
                db.execute(f"ALTER TABLE products ADD COLUMN {column} {definition}")
        db.execute("CREATE INDEX IF NOT EXISTS idx_products_group ON products(product_group)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode)")
        db.commit()
    finally:
        db.close()


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if session.get("user_id") is None:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


VALID_PRODUCT_UNITS = {"piece", "box", "kg", "litre", "service"}
VALID_PRODUCT_STATUSES = {"active", "inactive"}


PRODUCT_FIELD_MESSAGE_MAP = {
    "name": [
        "Product name is required.",
        "Product name must be between 2 and 120 characters.",
    ],
    "sku": [
        "SKU is required.",
        "SKU format is invalid.",
    ],
    "price": [
        "Selling price is required.",
        "Selling price must be 0 or greater.",
        "Selling price must be a valid number.",
    ],
    "product_group": [
        "Product group is required.",
        "Product group must be between 2 and 80 characters.",
    ],
    "unit": [
        "Unit is required.",
    ],
    "category": [
        "Category must be between 2 and 80 characters.",
    ],
    "brand": [
        "Brand must be between 2 and 80 characters.",
    ],
    "description": [
        "Description cannot exceed 500 characters.",
    ],
    "cost_price": [
        "Cost price cannot be negative.",
        "Cost price must be a valid number.",
    ],
    "tax_rate": [
        "Tax rate must be between 0 and 100.",
        "Tax rate must be a valid number.",
    ],
    "stock_quantity": [
        "Opening stock cannot be negative.",
        "Opening stock must be a valid whole number.",
    ],
    "reorder_level": [
        "Reorder level cannot be negative.",
        "Reorder level must be a valid whole number.",
    ],
    "supplier": [
        "Supplier must be between 2 and 120 characters.",
    ],
    "barcode": [
        "Barcode format is invalid.",
    ],
    "status": [
        "Status must be active or inactive.",
    ],
}

REGISTER_FIELD_MESSAGE_MAP = {
    "username": [
        "Username is required.",
        "Username must be between 3 and 50 characters.",
    ],
    "email": [
        "Email is required.",
        "Enter a valid email address.",
        "Email must be 120 characters or fewer.",
    ],
    "password": [
        "Password is required.",
        "Password must be at least 8 characters.",
    ],
    "confirm_password": [
        "Confirm password is required.",
        "Passwords do not match.",
    ],
}


def get_field_errors(errors, field_map):
    if not errors:
        return {}

    field_errors = {}
    for field_name, allowed_messages in field_map.items():
        for message in errors:
            if message in allowed_messages:
                field_errors[field_name] = message
                break
    return field_errors


def validate_register_payload(payload):
    errors = []
    data = {key: (value.strip() if isinstance(value, str) else value) for key, value in (payload or {}).items()}

    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", "")).strip()
    confirm_password = str(data.get("confirm_password", "")).strip()

    if not username:
        errors.append("Username is required.")
    elif not (3 <= len(username) <= 50):
        errors.append("Username must be between 3 and 50 characters.")

    if not email:
        errors.append("Email is required.")
    elif not re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", email):
        errors.append("Enter a valid email address.")
    elif len(email) > 120:
        errors.append("Email must be 120 characters or fewer.")

    if not password:
        errors.append("Password is required.")
    elif len(password) < 8:
        errors.append("Password must be at least 8 characters.")

    if not confirm_password:
        errors.append("Confirm password is required.")
    elif password and password != confirm_password:
        errors.append("Passwords do not match.")

    return errors or None


def validate_product_payload(payload):
    errors = []
    data = {key: (value.strip() if isinstance(value, str) else value) for key, value in (payload or {}).items()}

    name = str(data.get("name", "")).strip()
    sku = str(data.get("sku", "")).strip()
    price_raw = str(data.get("price", "")).strip()
    product_group = str(data.get("product_group", "")).strip()
    category = str(data.get("category", "")).strip()
    brand = str(data.get("brand", "")).strip()
    description = str(data.get("description", "")).strip()
    unit = str(data.get("unit", "")).strip()
    cost_price_raw = str(data.get("cost_price", "")).strip()
    tax_rate_raw = str(data.get("tax_rate", "")).strip()
    stock_quantity_raw = str(data.get("stock_quantity", "")).strip()
    reorder_level_raw = str(data.get("reorder_level", "")).strip()
    supplier = str(data.get("supplier", "")).strip()
    barcode = str(data.get("barcode", "")).strip()
    status = str(data.get("status", "")).strip()

    if not name:
        errors.append("Product name is required.")
    elif not (2 <= len(name) <= 120):
        errors.append("Product name must be between 2 and 120 characters.")

    if not sku:
        errors.append("SKU is required.")
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._\-/ ]{0,59}", sku):
        errors.append("SKU format is invalid.")

    if not price_raw:
        errors.append("Selling price is required.")
    else:
        try:
            price_value = float(price_raw)
            if price_value < 0:
                errors.append("Selling price must be 0 or greater.")
        except ValueError:
            errors.append("Selling price must be a valid number.")

    if not product_group:
        errors.append("Product group is required.")
    elif not (2 <= len(product_group) <= 80):
        errors.append("Product group must be between 2 and 80 characters.")

    if not unit:
        errors.append("Unit is required.")
    elif unit not in VALID_PRODUCT_UNITS:
        errors.append("Unit is required.")

    if category and not (2 <= len(category) <= 80):
        errors.append("Category must be between 2 and 80 characters.")

    if brand and not (2 <= len(brand) <= 80):
        errors.append("Brand must be between 2 and 80 characters.")

    if description and len(description) > 500:
        errors.append("Description cannot exceed 500 characters.")

    if cost_price_raw:
        try:
            cost_price_value = float(cost_price_raw)
            if cost_price_value < 0:
                errors.append("Cost price cannot be negative.")
        except ValueError:
            errors.append("Cost price must be a valid number.")

    if tax_rate_raw:
        try:
            tax_rate_value = float(tax_rate_raw)
            if not 0 <= tax_rate_value <= 100:
                errors.append("Tax rate must be between 0 and 100.")
        except ValueError:
            errors.append("Tax rate must be a valid number.")

    if stock_quantity_raw:
        try:
            stock_quantity_value = int(stock_quantity_raw)
            if stock_quantity_value < 0:
                errors.append("Opening stock cannot be negative.")
        except ValueError:
            errors.append("Opening stock must be a valid whole number.")

    if reorder_level_raw:
        try:
            reorder_value = int(reorder_level_raw)
            if reorder_value < 0:
                errors.append("Reorder level cannot be negative.")
        except ValueError:
            errors.append("Reorder level must be a valid whole number.")

    if supplier and not (2 <= len(supplier) <= 120):
        errors.append("Supplier must be between 2 and 120 characters.")

    if barcode:
        if not re.fullmatch(r"[A-Za-z0-9\-]{6,80}", barcode):
            errors.append("Barcode format is invalid.")

    if status and status not in VALID_PRODUCT_STATUSES:
        errors.append("Status must be active or inactive.")

    return errors or None


def hash_reset_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_app_settings():
    settings = {
        "show_sales_app": True,
        "show_products": True,
        "show_customers": True,
    }
    rows = get_db().execute(
        "SELECT setting_key, setting_value FROM app_settings"
    ).fetchall()
    for row in rows:
        if row["setting_key"] in settings:
            settings[row["setting_key"]] = row["setting_value"] == "1"
    return settings


@app.context_processor
def inject_app_settings():
    if session.get("user_id"):
        return {"app_settings": get_app_settings()}
    return {"app_settings": {}}


@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=("GET", "POST"))
def register():
    form_data = request.form.to_dict() if request.method == "POST" else {}

    if request.method == "POST":
        validation_errors = validate_register_payload(form_data)
        field_errors = get_field_errors(validation_errors or [], REGISTER_FIELD_MESSAGE_MAP)
        if validation_errors:
            for error in validation_errors:
                flash(error, "danger")
            return render_template("register.html", form_data=form_data, field_errors=field_errors)

        username = form_data.get("username", "").strip()
        email = form_data.get("email", "").strip().lower()
        password = form_data.get("password", "")
        confirm_password = form_data.get("confirm_password", "")
        error = None

        if error is None:
            write_db = None
            try:
                write_db = sqlite3.connect(
                    app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
                )
                write_db.execute(
                    "INSERT INTO users (username, password, email, created_at) VALUES (?, ?, ?, ?)",
                    (
                        username,
                        generate_password_hash(password),
                        email,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                write_db.commit()
            except sqlite3.IntegrityError:
                error = "That username is already registered."
            except sqlite3.OperationalError:
                error = "The database is busy. Please try again in a moment."
            finally:
                if write_db is not None:
                    write_db.close()

        if error:
            flash(error, "danger")
            return render_template("register.html", form_data=form_data, field_errors={})

        flash("Account created successfully. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form_data={}, field_errors={})


@app.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, password FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user is None or not check_password_hash(user["password"], password):
            flash("Incorrect username or password.", "danger")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Welcome back!", "success")
            return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/forgot-password", methods=("GET", "POST"))
def forgot_password():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        user = get_db().execute(
            "SELECT id FROM users WHERE username = ? AND email = ?",
            (username, email),
        ).fetchone()

        if user is None:
            flash("We could not find an account with those details.", "danger")
        else:
            reset_token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=app.config["RESET_TOKEN_MINUTES"])
            write_db = None
            reset_created = False
            try:
                write_db = sqlite3.connect(
                    app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
                )
                write_db.execute(
                    "DELETE FROM password_reset_tokens WHERE user_id = ? AND used_at IS NULL",
                    (user["id"],),
                )
                write_db.execute(
                    "INSERT INTO password_reset_tokens "
                    "(user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    (
                        user["id"],
                        hash_reset_token(reset_token),
                        expires_at.isoformat(),
                        now.isoformat(),
                    ),
                )
                write_db.commit()
                reset_created = True
            except sqlite3.OperationalError:
                flash("The database is busy. Please try again in a moment.", "danger")
            finally:
                if write_db is not None:
                    write_db.close()

            if reset_created:
                reset_url = url_for("reset_password", token=reset_token, _external=True)
                flash(reset_url, "reset-link")

    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=("GET", "POST"))
def reset_password(token):
    token_hash = hash_reset_token(token)
    token_record = get_db().execute(
        "SELECT id FROM password_reset_tokens "
        "WHERE token_hash = ? AND used_at IS NULL AND expires_at > ?",
        (token_hash, datetime.now(timezone.utc).isoformat()),
    ).fetchone()

    if token_record is None:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
        elif password != confirm_password:
            flash("Passwords do not match.", "danger")
        else:
            write_db = None
            try:
                write_db = sqlite3.connect(
                    app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
                )
                write_db.execute("BEGIN IMMEDIATE")
                current_token = write_db.execute(
                    "SELECT user_id FROM password_reset_tokens "
                    "WHERE id = ? AND token_hash = ? AND used_at IS NULL AND expires_at > ?",
                    (
                        token_record["id"],
                        token_hash,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                ).fetchone()
                if current_token is None:
                    write_db.rollback()
                    flash("This password reset link is invalid or has expired.", "danger")
                else:
                    write_db.execute(
                        "UPDATE users SET password = ? WHERE id = ?",
                        (generate_password_hash(password), current_token[0]),
                    )
                    write_db.execute(
                        "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                        (datetime.now(timezone.utc).isoformat(), token_record["id"]),
                    )
                    write_db.commit()
                    flash("Password reset successfully. You can now log in.", "success")
                    return redirect(url_for("login"))
            except sqlite3.OperationalError:
                flash("The database is busy. Please try again in a moment.", "danger")
            finally:
                if write_db is not None:
                    write_db.close()

    return render_template("reset_password.html")


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", username=session["username"])


@app.route("/products/new", methods=("GET", "POST"))
@login_required
def add_product():
    form_data = request.form.to_dict() if request.method == "POST" else {}

    if request.method == "POST":
        validation_errors = validate_product_payload(form_data)
        field_errors = get_field_errors(validation_errors or [], PRODUCT_FIELD_MESSAGE_MAP)
        if validation_errors:
            for error in validation_errors:
                flash(error, "danger")
            return render_template("add_product.html", form_data=form_data, field_errors=field_errors)

        name = form_data.get("name", "").strip()
        sku = form_data.get("sku", "").strip()
        price = form_data.get("price", "").strip()
        product_group = form_data.get("product_group", "General").strip()
        category = form_data.get("category", "").strip()
        brand = form_data.get("brand", "").strip()
        description = form_data.get("description", "").strip()
        unit = form_data.get("unit", "piece").strip()
        cost_price = form_data.get("cost_price", "").strip()
        tax_rate = form_data.get("tax_rate", "0").strip()
        stock_quantity = form_data.get("stock_quantity", "0").strip()
        reorder_level = form_data.get("reorder_level", "0").strip()
        supplier = form_data.get("supplier", "").strip()
        barcode = form_data.get("barcode", "").strip()
        status = form_data.get("status", "active").strip()
        error = None

        try:
            price_cents = round(float(price) * 100)
            cost_price_cents = round(float(cost_price) * 100) if cost_price else None
            tax_rate_value = float(tax_rate)
            stock_quantity_value = int(stock_quantity)
            reorder_level_value = int(reorder_level)
            if (
                price_cents < 0
                or cost_price_cents is not None and cost_price_cents < 0
                or tax_rate_value < 0
                or tax_rate_value > 100
                or stock_quantity_value < 0
                or reorder_level_value < 0
            ):
                raise ValueError
        except ValueError:
            error = "Enter valid non-negative prices, tax, and stock values."

        if error is None:
            write_db = None
            try:
                write_db = sqlite3.connect(
                    app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
                )
                write_db.execute(
                    "INSERT INTO products (name, sku, price_cents, product_group, category, brand, description, unit, cost_price_cents, tax_rate, stock_quantity, reorder_level, supplier, barcode, status, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        name, sku, price_cents, product_group, category or None,
                        brand or None, description or None, unit, cost_price_cents,
                        tax_rate_value, stock_quantity_value, reorder_level_value,
                        supplier or None, barcode or None, status,
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
                write_db.commit()
            except sqlite3.IntegrityError:
                error = "That SKU is already registered."
            except sqlite3.OperationalError:
                error = "The database is busy. Please try again in a moment."
            finally:
                if write_db is not None:
                    write_db.close()

        if error:
            flash(error, "danger")
            return render_template("add_product.html", form_data=form_data, field_errors={})

        flash("Product added successfully.", "success")
        return redirect(url_for("add_product"))

    return render_template("add_product.html", form_data={}, field_errors={})


@app.route("/sales-app")
@login_required
def sales_app():
    return render_template("sales_app.html")


@app.route("/settings", methods=("GET", "POST"))
@login_required
def settings():
    setting_keys = ("show_sales_app", "show_products", "show_customers")
    if request.method == "POST":
        write_db = None
        try:
            write_db = sqlite3.connect(
                app.config["DATABASE"], timeout=app.config["DATABASE_TIMEOUT"]
            )
            for key in setting_keys:
                value = "1" if request.form.get(key) == "on" else "0"
                write_db.execute(
                    "INSERT INTO app_settings (setting_key, setting_value) VALUES (?, ?) "
                    "ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value",
                    (key, value),
                )
            write_db.commit()
            flash("Navigation settings saved.", "success")
        except sqlite3.OperationalError:
            flash("The database is busy. Please try again in a moment.", "danger")
        finally:
            if write_db is not None:
                write_db.close()
        return redirect(url_for("settings"))

    return render_template("settings.html", settings=get_app_settings())


@app.route("/customers")
@login_required
def customers():
    return render_template("coming_soon.html", section="Customers")


@app.route("/sales")
@login_required
def sales():
    return render_template("coming_soon.html", section="Sales")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


init_db()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1")
