from flask import Blueprint, render_template, request, redirect, session, flash
from db import get_db

user_bp = Blueprint("user", __name__)

@user_bp.route("/register", methods=["GET", "POST"])
def register():
    # If user is already logged in, redirect to dashboard
    if "user_id" in session:
        return redirect("/dashboard")
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        # Validation
        if not name or not email or not password:
            flash("All fields are required!", "error")
            return render_template("register.html")
        
        if len(password) < 6:
            flash("Password must be at least 6 characters long!", "error")
            return render_template("register.html")
        
        db = get_db()
        
        # Check if email already exists
        existing_user = db.execute(
            "SELECT * FROM users WHERE email = ?", 
            (email,)
        ).fetchone()
        
        if existing_user:
            flash("Email already registered! Please login instead.", "error")
            return render_template("register.html")
        
        try:
            # Insert new user
            db.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, password)
            )
            db.commit()
            flash("Registration successful! Please login.", "success")
            return redirect("/login")
        except Exception as e:
            db.rollback()
            flash("An error occurred during registration. Please try again.", "error")
            return render_template("register.html")
    
    return render_template("register.html")


@user_bp.route("/login", methods=["GET", "POST"])
def login():
    # If user is already logged in, redirect to dashboard
    if "user_id" in session:
        return redirect("/dashboard")
    
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        
        # Validation
        if not email or not password:
            flash("Email and password are required!", "error")
            return render_template("login.html")
        
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email = ? AND password = ?",
            (email, password)
        ).fetchone()
        
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect("/dashboard")
        else:
            flash("Invalid email or password. Please try again.", "error")
            return render_template("login.html")
    
    return render_template("login.html")


@user_bp.route("/dashboard")
def dashboard():
    # Check if user is logged in
    if "user_id" not in session:
        flash("Please login to access your dashboard.", "error")
        return redirect("/login")
    
    db = get_db()
    user_id = session["user_id"]
    
    # Get user information
    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    
    # Get user's order count
    order_count = db.execute(
        "SELECT COUNT(*) as count FROM orders WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    
    # Get recent orders
    recent_orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
        (user_id,)
    ).fetchall()
    
    # Get total spent
    total_spent = db.execute(
        "SELECT COALESCE(SUM(total), 0) as total FROM orders WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    
    # Get contact information
    contact_info = db.execute("SELECT * FROM contact_info LIMIT 1").fetchone()
    
    return render_template(
        "dashboard.html",
        user=user,
        order_count=order_count["count"] if order_count else 0,
        recent_orders=recent_orders,
        total_spent=total_spent["total"] if total_spent else 0,
        contact_info=contact_info
    )


@user_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.", "success")
    return redirect("/login")
