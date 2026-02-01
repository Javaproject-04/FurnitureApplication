from flask import Blueprint, render_template, session, redirect, flash, request
from db import get_db
from datetime import datetime

order_bp = Blueprint("order", __name__)

@order_bp.route("/cart")
def cart():
    cart_dict = session.get("cart", {})
    
    if not cart_dict:
        return render_template("cart.html", cart_items=[], total=0)
    
    db = get_db()
    cart_items = []
    total = 0
    
    for product_id, quantity in cart_dict.items():
        product = db.execute("SELECT * FROM products WHERE id = ?", (int(product_id),)).fetchone()
        if product:
            item_total = product["price"] * quantity
            total += item_total
            cart_items.append({
                "id": product["id"],
                "name": product["name"],
                "description": product["description"],
                "price": product["price"],
                "image_url": product["image_url"],
                "quantity": quantity,
                "total": item_total
            })
    
    return render_template("cart.html", cart_items=cart_items, total=total)


@order_bp.route("/update-cart/<int:pid>", methods=["POST"])
def update_cart(pid):
    cart = session.get("cart", {})
    action = request.form.get("action")
    
    if action == "remove":
        cart.pop(str(pid), None)
        flash("Item removed from cart!", "success")
    elif action == "decrease":
        if str(pid) in cart:
            if cart[str(pid)] > 1:
                cart[str(pid)] -= 1
            else:
                cart.pop(str(pid), None)
                flash("Item removed from cart!", "success")
    elif action == "increase":
        cart[str(pid)] = cart.get(str(pid), 0) + 1
    
    session["cart"] = cart
    return redirect("/cart")


def _apply_coupon(db, code, total):
    """Validate coupon and return (coupon_row, discount_amount) or (None, 0)."""
    if not code or total <= 0:
        return None, 0.0
    c = db.execute(
        "SELECT * FROM coupons WHERE UPPER(TRIM(code)) = ? AND is_active = 1",
        (code.strip().upper(),)
    ).fetchone()
    if not c:
        return None, 0.0
    if c["discount_type"] == "percent":
        discount = round(total * float(c["discount_value"]) / 100.0, 2)
    else:
        discount = min(float(c["discount_value"]), total)
        discount = round(discount, 2)
    return c, discount


@order_bp.route("/checkout", methods=["GET"])
def checkout():
    if "user_id" not in session:
        flash("Please login to checkout.", "error")
        return redirect("/login")

    cart_dict = session.get("cart", {})
    
    if not cart_dict:
        flash("Your cart is empty!", "error")
        return redirect("/products")

    db = get_db()
    cart_items = []
    total = 0
    
    for product_id, quantity in cart_dict.items():
        product = db.execute("SELECT * FROM products WHERE id = ?", (int(product_id),)).fetchone()
        if product:
            item_total = product["price"] * quantity
            total += item_total
            cart_items.append({
                "product": product,
                "quantity": quantity,
                "total": item_total
            })
    
    upi_qr = db.execute("SELECT * FROM upi_qr WHERE id = 1").fetchone()

    # Coupon: apply if ?coupon=CODE
    coupon_code = request.args.get("coupon", "").strip()
    applied_coupon = None
    discount_amount = 0.0
    total_after = total
    if coupon_code:
        c, d = _apply_coupon(db, coupon_code, total)
        if c:
            applied_coupon = c
            discount_amount = d
            total_after = round(total - d, 2)
        else:
            flash("Invalid or inactive coupon code.", "error")

    return render_template(
        "checkout.html",
        cart_items=cart_items,
        total=total,
        total_after=total_after,
        upi_qr=upi_qr,
        applied_coupon=applied_coupon,
        discount_amount=discount_amount,
    )


@order_bp.route("/place-order", methods=["POST"])
def place_order():
    if "user_id" not in session:
        flash("Please login to place an order.", "error")
        return redirect("/login")

    cart_dict = session.get("cart", {})
    
    if not cart_dict:
        flash("Your cart is empty!", "error")
        return redirect("/products")

    payment_method = request.form.get("payment_method", "cod").strip()
    
    # Validate payment method
    # Keep it simple: COD + UPI (no netbanking)
    valid_payment_methods = ["cod", "upi"]
    if payment_method not in valid_payment_methods:
        payment_method = "cod"
    
    # Get contact details
    contact_mobile = request.form.get("contact_mobile", "").strip()
    contact_address = request.form.get("contact_address", "").strip()
    
    # Validate contact details
    if not contact_mobile or not contact_address:
        flash("Mobile number and delivery address are required!", "error")
        return redirect("/checkout")
    
    # Validate mobile number format (10 digits)
    if not contact_mobile.isdigit() or len(contact_mobile) != 10:
        flash("Please enter a valid 10-digit mobile number!", "error")
        return redirect("/checkout")

    db = get_db()
    cart_items = []
    total = 0
    
    for product_id, quantity in cart_dict.items():
        product = db.execute("SELECT * FROM products WHERE id = ?", (int(product_id),)).fetchone()
        if product:
            item_total = product["price"] * quantity
            total += item_total
            cart_items.append({
                "product": product,
                "quantity": quantity,
                "total": item_total
            })

    # Coupon: re-validate and compute final total
    coupon_code = request.form.get("coupon_code", "").strip()
    coupon_row, discount_amount = _apply_coupon(db, coupon_code, total)
    total_final = round(total - discount_amount, 2)
    coupon_id = coupon_row["id"] if coupon_row else None

    # Advance is 5% of final total for UPI
    advance_amount = round(total_final * 0.05, 2) if payment_method == "upi" else None

    payment_proof_url = None
    if payment_method == "upi":
        proof = request.files.get("payment_proof")
        if not proof or not proof.filename:
            flash("Please upload UPI payment screenshot to place the order.", "error")
            return redirect("/checkout")
        from werkzeug.utils import secure_filename
        import os
        import time
        filename = secure_filename(proof.filename)
        filename = str(int(time.time())) + "_upi_proof_" + filename
        upload_dir = os.path.join("static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        filepath = os.path.join(upload_dir, filename)
        proof.save(filepath)
        payment_proof_url = "/" + filepath.replace("\\", "/")

    if payment_method == "upi":
        payment_status = "awaiting_verification"
    else:
        payment_status = "pending"

    try:
        res = db.execute(
            """INSERT INTO orders (user_id, total, status, payment_method, payment_status,
               advance_amount, payment_proof_url, coupon_id, discount_amount, 
               contact_mobile, contact_address, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session["user_id"],
                total_final,
                "pending",
                payment_method,
                payment_status,
                advance_amount,
                payment_proof_url,
                coupon_id,
                discount_amount,
                contact_mobile,
                contact_address,
                datetime.now().isoformat(timespec="seconds"),
                datetime.now().isoformat(timespec="seconds"),
            )
        )
        order_id = res.lastrowid

        # Add order items
        for item in cart_items:
            db.execute(
                "INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)",
                (order_id, item["product"]["id"], item["quantity"], item["product"]["price"])
            )

        db.commit()
        session["cart"] = {}
        flash(f"Order placed successfully! Order ID: #{order_id}", "success")
        return redirect("/orders")
    except Exception as e:
        db.rollback()
        flash("An error occurred while placing your order. Please try again.", "error")
        return redirect("/cart")


@order_bp.route("/orders")
def orders():
    if "user_id" not in session:
        flash("Please login to view your orders.", "error")
        return redirect("/login")

    db = get_db()
    orders = db.execute(
        "SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (session["user_id"],)
    ).fetchall()
    
    # Define order status stages
    status_stages = {
        "pending": {"label": "Order Placed", "icon": "📦", "order": 1},
        "accepted": {"label": "Order Accepted", "icon": "✅", "order": 2},
        "processing": {"label": "Processing", "icon": "⚙️", "order": 3},
        "shipped": {"label": "Shipped", "icon": "🚚", "order": 4},
        "delivered": {"label": "Delivered", "icon": "🎉", "order": 5},
        "completed": {"label": "Completed", "icon": "✅", "order": 5},
        "cancelled": {"label": "Cancelled", "icon": "❌", "order": 0}
    }
    
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
        
        # Determine current stage
        current_status = order["status"].lower()
        current_stage = status_stages.get(current_status, {"label": current_status.title(), "icon": "📦", "order": 0})
        
        orders_with_items.append({
            "order": order,
            "order_items": items,
            "status_stages": status_stages,
            "current_stage": current_stage
        })
    
    return render_template("orders.html", orders_with_items=orders_with_items)


@order_bp.route("/rate-product/<int:product_id>", methods=["POST"])
def rate_product(product_id):
    if "user_id" not in session:
        flash("Please login to rate products.", "error")
        return redirect("/login")

    rating = request.form.get("rating", "").strip()
    comment = request.form.get("comment", "").strip()

    try:
        rating_int = int(rating)
        if rating_int < 1 or rating_int > 5:
            raise ValueError()
    except Exception:
        flash("Invalid rating. Please choose 1 to 5.", "error")
        return redirect("/orders")

    db = get_db()

    # Only allow rating if user has purchased this product
    purchased = db.execute(
        """SELECT 1
           FROM orders o
           JOIN order_items oi ON oi.order_id = o.id
           WHERE o.user_id = ? AND oi.product_id = ?
           LIMIT 1""",
        (session["user_id"], product_id),
    ).fetchone()

    if not purchased:
        flash("You can only rate products you purchased.", "error")
        return redirect("/orders")

    try:
        db.execute(
            """INSERT INTO product_reviews (user_id, product_id, rating, comment)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, product_id) DO UPDATE SET
                 rating=excluded.rating,
                 comment=excluded.comment,
                 created_at=CURRENT_TIMESTAMP""",
            (session["user_id"], product_id, rating_int, comment or None),
        )
        db.commit()
        flash("Thanks! Your rating was saved.", "success")
    except Exception:
        db.rollback()
        flash("Could not save rating. Please try again.", "error")

    return redirect("/orders")


@order_bp.route("/cancel-order/<int:order_id>", methods=["POST"])
def cancel_order(order_id):
    if "user_id" not in session:
        flash("Please login to cancel orders.", "error")
        return redirect("/login")
    
    db = get_db()
    
    # Check if order exists and belongs to user
    order = db.execute(
        "SELECT * FROM orders WHERE id = ? AND user_id = ?",
        (order_id, session["user_id"])
    ).fetchone()
    
    if not order:
        flash("Order not found!", "error")
        return redirect("/orders")
    
    # Only allow cancellation if order is not delivered, completed, or already cancelled
    status = order["status"].lower()
    if status in ["delivered", "completed", "cancelled"]:
        flash(f"Cannot cancel order. Order status: {status.title()}", "error")
        return redirect("/orders")
    
    try:
        # Update order status to cancelled
        db.execute(
            "UPDATE orders SET status = ?, updated_at = ? WHERE id = ?",
            ("cancelled", datetime.now().isoformat(timespec="seconds"), order_id)
        )
        db.commit()
        flash(f"Order #{order_id} has been cancelled successfully!", "success")
    except Exception as e:
        db.rollback()
        flash("An error occurred while cancelling the order. Please try again.", "error")
    
    return redirect("/orders")
