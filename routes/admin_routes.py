from flask import Blueprint, render_template, request, redirect, session, flash, url_for, current_app
from db import get_db
from werkzeug.utils import secure_filename
import os

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'gif', 'webp'}

admin_bp = Blueprint("admin", __name__)

def admin_required(f):
    """Decorator to require admin login"""
    def decorated_function(*args, **kwargs):
        if "admin_id" not in session:
            flash("Admin access required. Please login as admin.", "error")
            return redirect("/admin/login")
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function


@admin_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    # If admin is already logged in, redirect to admin dashboard
    if "admin_id" in session:
        return redirect("/admin/dashboard")
    
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        
        # Validation
        if not username or not password:
            flash("Username and password are required!", "error")
            return render_template("admin_login.html")
        
        db = get_db()
        admin = db.execute(
            "SELECT * FROM admins WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        
        if admin:
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            session["admin_email"] = admin["email"]
            flash(f"Welcome, {admin['username']}!", "success")
            return redirect("/admin/dashboard")
        else:
            flash("Invalid username or password. Please try again.", "error")
            return render_template("admin_login.html")
    
    return render_template("admin_login.html")


@admin_bp.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    
    # Get statistics
    total_products = db.execute("SELECT COUNT(*) as count FROM products").fetchone()["count"]
    total_orders = db.execute("SELECT COUNT(*) as count FROM orders").fetchone()["count"]
    total_users = db.execute("SELECT COUNT(*) as count FROM users").fetchone()["count"]
    total_revenue = db.execute("SELECT COALESCE(SUM(total), 0) as total FROM orders").fetchone()["total"]
    
    # Get recent orders
    recent_orders = db.execute(
        """SELECT o.*, u.name as user_name, u.email as user_email 
           FROM orders o 
           JOIN users u ON o.user_id = u.id 
           ORDER BY o.created_at DESC LIMIT 10"""
    ).fetchall()
    
    # Get recent products
    recent_products = db.execute(
        "SELECT * FROM products ORDER BY created_at DESC LIMIT 5"
    ).fetchall()
    
    return render_template(
        "admin_dashboard.html",
        total_products=total_products,
        total_orders=total_orders,
        total_users=total_users,
        total_revenue=total_revenue,
        recent_orders=recent_orders,
        recent_products=recent_products
    )


@admin_bp.route("/admin/products")
@admin_required
def admin_products():
    db = get_db()
    products = db.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
    return render_template("admin_products.html", products=products)


@admin_bp.route("/admin/products/add", methods=["GET", "POST"])
@admin_required
def add_product():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()
        price = request.form.get("price", "").strip()
        image_url = request.form.get("image_url", "").strip()
        category = request.form.get("category", "").strip()
        rating = request.form.get("rating", "").strip()
        
        # Validation
        if not name or not price:
            flash("Name and price are required!", "error")
            return render_template("admin_add_product.html")
        
        try:
            price = float(price)
            if price <= 0:
                raise ValueError("Price must be positive")
        except ValueError:
            flash("Invalid price. Please enter a valid number.", "error")
            return render_template("admin_add_product.html")
        
        # Validate and set rating
        if rating:
            try:
                rating = float(rating)
                if rating < 0 or rating > 5:
                    rating = 0.0
            except ValueError:
                rating = 0.0
        else:
            rating = 0.0
        
        # Auto-detect category if not provided
        if not category:
            from utils import detect_category
            category = detect_category(name)
        
        # Handle file upload
        uploaded_file = request.files.get('image_file')
        if uploaded_file and uploaded_file.filename:
            if allowed_file(uploaded_file.filename):
                filename = secure_filename(uploaded_file.filename)
                # Add timestamp to make filename unique
                import time
                filename = str(int(time.time())) + '_' + filename
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                uploaded_file.save(filepath)
                # Use the uploaded file path
                image_url = url_for('static', filename=f'uploads/{filename}')
            else:
                flash("Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP", "error")
                return render_template("admin_add_product.html")
        
        db = get_db()
        try:
            db.execute(
                "INSERT INTO products (name, description, price, image_url, category, rating) VALUES (?, ?, ?, ?, ?, ?)",
                (name, description, price, image_url, category, rating)
            )
            db.commit()
            flash(f"Product '{name}' added successfully! Category: {category}", "success")
            return redirect("/admin/products")
        except Exception as e:
            db.rollback()
            flash("An error occurred while adding the product. Please try again.", "error")
            return render_template("admin_add_product.html")
    
    return render_template("admin_add_product.html")


@admin_bp.route("/admin/products/delete/<int:product_id>", methods=["POST"])
@admin_required
def delete_product(product_id):
    db = get_db()
    
    # Check if product exists
    product = db.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    
    if not product:
        flash("Product not found!", "error")
        return redirect("/admin/products")
    
    try:
        # Check if product is in any orders
        order_items = db.execute(
            "SELECT COUNT(*) as count FROM order_items WHERE product_id = ?",
            (product_id,)
        ).fetchone()
        
        if order_items["count"] > 0:
            flash("Cannot delete product that has been ordered. You can hide it instead.", "error")
            return redirect("/admin/products")
        
        db.execute("DELETE FROM products WHERE id = ?", (product_id,))
        db.commit()
        flash(f"Product '{product['name']}' deleted successfully!", "success")
    except Exception as e:
        db.rollback()
        flash("An error occurred while deleting the product.", "error")
    
    return redirect("/admin/products")


@admin_bp.route("/admin/orders")
@admin_required
def admin_orders():
    db = get_db()
    
    # Get all orders with user information
    orders = db.execute(
        """SELECT o.*, u.name as user_name, u.email as user_email 
           FROM orders o 
           JOIN users u ON o.user_id = u.id 
           ORDER BY o.created_at DESC"""
    ).fetchall()
    
    # Get order items for each order
    orders_with_items = []
    for order in orders:
        items = db.execute(
            """SELECT oi.*, p.name, p.description 
               FROM order_items oi 
               JOIN products p ON oi.product_id = p.id 
               WHERE oi.order_id = ?""",
            (order["id"],)
        ).fetchall()
        orders_with_items.append({
            "order": order,
            "order_items": items
        })
    
    return render_template("admin_orders.html", orders_with_items=orders_with_items)


@admin_bp.route("/admin/orders/update-status/<int:order_id>", methods=["POST"])
@admin_required
def update_order_status(order_id):
    from datetime import datetime
    new_status = request.form.get("status", "").strip().lower()
    
    if new_status not in ["pending", "accepted", "processing", "shipped", "delivered", "completed", "cancelled"]:
        flash("Invalid status!", "error")
        return redirect("/admin/orders")
    
    db = get_db()
    
    # Check if order exists
    order = db.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    
    if not order:
        flash("Order not found!", "error")
        return redirect("/admin/orders")
    
    try:
        # Update order status and timestamp
        db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, datetime.now().isoformat(timespec="seconds"), order_id)
        )
        
        # If order is delivered or completed, mark payment as completed if COD
        if new_status in ["delivered", "completed"] and order["payment_method"] == "cod":
            db.execute(
                "UPDATE orders SET payment_status = ? WHERE id = ?",
                ("completed", order_id)
            )
        
        db.commit()
        
        status_messages = {
            "accepted": "Order accepted successfully!",
            "cancelled": "Order cancelled successfully!",
            "processing": "Order status updated to processing!",
            "shipped": "Order marked as shipped!",
            "delivered": "Order marked as delivered!",
            "completed": "Order marked as completed!",
            "pending": "Order status reset to pending!"
        }
        
        flash(status_messages.get(new_status, "Order status updated!"), "success")
    except Exception as e:
        db.rollback()
        flash("An error occurred while updating the order status.", "error")
    
    return redirect("/admin/orders")


@admin_bp.route("/admin/contact/qr", methods=["POST"])
@admin_required
def save_upi_qr():
    db = get_db()
    uploaded_file = request.files.get("qr_file")
    image_url = request.form.get("qr_image_url", "").strip()
    if uploaded_file and uploaded_file.filename:
        if not allowed_file(uploaded_file.filename):
            flash("Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP", "error")
            return redirect("/admin/contact")
        import time
        filename = str(int(time.time())) + "_upi_qr_" + secure_filename(uploaded_file.filename)
        filepath = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
        uploaded_file.save(filepath)
        image_url = url_for("static", filename=f"uploads/{filename}")
    if not image_url:
        flash("Please upload a QR image or provide an image URL.", "error")
        return redirect("/admin/contact")
    try:
        db.execute("UPDATE upi_qr SET image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1", (image_url,))
        db.commit()
        flash("UPI QR updated successfully!", "success")
    except Exception:
        db.rollback()
        flash("Failed to update UPI QR.", "error")
    return redirect("/admin/contact")


@admin_bp.route("/admin/contact/coupon/add", methods=["POST"])
@admin_required
def add_coupon():
    db = get_db()
    code = request.form.get("code", "").strip().upper()
    discount_type = request.form.get("discount_type", "percent").strip()
    discount_value = request.form.get("discount_value", "").strip()
    if not code or not discount_value:
        flash("Coupon code and discount value are required.", "error")
        return redirect("/admin/contact")
    if discount_type not in ("percent", "fixed"):
        discount_type = "percent"
    try:
        val = float(discount_value)
        if val <= 0 or (discount_type == "percent" and val > 100):
            raise ValueError("invalid")
    except ValueError:
        flash("Invalid discount value.", "error")
        return redirect("/admin/contact")
    try:
        db.execute(
            "INSERT INTO coupons (code, discount_type, discount_value, is_active) VALUES (?, ?, ?, 1)",
            (code, discount_type, val)
        )
        db.commit()
        flash(f"Coupon {code} added.", "success")
    except Exception:
        db.rollback()
        flash("Coupon code may already exist or invalid.", "error")
    return redirect("/admin/contact")


@admin_bp.route("/admin/contact/coupon/<int:cid>/toggle", methods=["POST"])
@admin_required
def toggle_coupon(cid):
    db = get_db()
    try:
        row = db.execute("SELECT is_active FROM coupons WHERE id = ?", (cid,)).fetchone()
        if row:
            new = 0 if row["is_active"] else 1
            db.execute("UPDATE coupons SET is_active = ? WHERE id = ?", (new, cid))
            db.commit()
            flash("Coupon status updated.", "success")
    except Exception:
        db.rollback()
        flash("Could not update coupon.", "error")
    return redirect("/admin/contact")


@admin_bp.route("/admin/contact/coupon/<int:cid>/delete", methods=["POST"])
@admin_required
def delete_coupon(cid):
    db = get_db()
    try:
        db.execute("DELETE FROM coupons WHERE id = ?", (cid,))
        db.commit()
        flash("Coupon deleted.", "success")
    except Exception:
        db.rollback()
        flash("Could not delete coupon.", "error")
    return redirect("/admin/contact")


@admin_bp.route("/admin/contact", methods=["GET", "POST"])
@admin_required
def manage_contact():
    db = get_db()
    
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()
        city = request.form.get("city", "").strip()
        state = request.form.get("state", "").strip()
        zip_code = request.form.get("zip_code", "").strip()
        country = request.form.get("country", "").strip()
        website = request.form.get("website", "").strip()
        
        # Validation
        if not company_name or not email or not phone or not address:
            flash("Company name, email, phone, and address are required!", "error")
            contact_info = db.execute("SELECT * FROM contact_info LIMIT 1").fetchone()
            upi_qr = db.execute("SELECT * FROM upi_qr WHERE id = 1").fetchone()
            coupons = db.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
            return render_template("admin_contact.html", contact_info=contact_info, upi_qr=upi_qr, coupons=coupons)
        
        try:
            # Check if contact info exists
            existing = db.execute("SELECT * FROM contact_info LIMIT 1").fetchone()
            
            if existing:
                # Update existing
                db.execute(
                    """UPDATE contact_info SET 
                       company_name=?, email=?, phone=?, address=?, city=?, 
                       state=?, zip_code=?, country=?, website=?, 
                       updated_at=CURRENT_TIMESTAMP 
                       WHERE id=?""",
                    (company_name, email, phone, address, city, state, zip_code, country, website, existing["id"])
                )
            else:
                # Insert new
                db.execute(
                    """INSERT INTO contact_info 
                       (company_name, email, phone, address, city, state, zip_code, country, website) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (company_name, email, phone, address, city, state, zip_code, country, website)
                )
            
            db.commit()
            flash("Contact details updated successfully!", "success")
            return redirect("/admin/contact")
        except Exception as e:
            db.rollback()
            flash("An error occurred while updating contact details. Please try again.", "error")
            contact_info = db.execute("SELECT * FROM contact_info LIMIT 1").fetchone()
            upi_qr = db.execute("SELECT * FROM upi_qr WHERE id = 1").fetchone()
            coupons = db.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
            return render_template("admin_contact.html", contact_info=contact_info, upi_qr=upi_qr, coupons=coupons)
    
    # GET - contact, UPI QR, coupons
    contact_info = db.execute("SELECT * FROM contact_info LIMIT 1").fetchone()
    upi_qr = db.execute("SELECT * FROM upi_qr WHERE id = 1").fetchone()
    coupons = db.execute("SELECT * FROM coupons ORDER BY id DESC").fetchall()
    return render_template("admin_contact.html", contact_info=contact_info, upi_qr=upi_qr, coupons=coupons)


@admin_bp.route("/admin/logout")
def admin_logout():
    session.pop("admin_id", None)
    session.pop("admin_username", None)
    session.pop("admin_email", None)
    flash("You have been logged out successfully.", "success")
    return redirect("/admin/login")
