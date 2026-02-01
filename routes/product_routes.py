from flask import Blueprint, render_template, session, redirect, flash, request
from db import get_db

product_bp = Blueprint("product", __name__)

@product_bp.route("/products")
def products():
    db = get_db()
    
    # Get filter parameters
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    min_rating = request.args.get('min_rating', type=float)
    category = request.args.get('category', type=str)
    sort = request.args.get('sort', type=str)  # 'rating_desc' | 'price_asc' | 'price_desc' | None
    
    # Build query (use user reviews for rating)
    query = """
        SELECT
            p.*,
            COALESCE(AVG(r.rating), 0) AS avg_rating,
            COUNT(r.id) AS rating_count
        FROM products p
        LEFT JOIN product_reviews r ON r.product_id = p.id
        WHERE 1=1
    """
    params = []
    
    if min_price is not None:
        query += " AND p.price >= ?"
        params.append(min_price)
    
    if max_price is not None:
        query += " AND p.price <= ?"
        params.append(max_price)
    
    if category:
        query += " AND p.category = ?"
        params.append(category)
    
    # Filter by avg rating (HAVING after GROUP BY; add param after category)
    having = ""
    if min_rating is not None:
        having = " HAVING COALESCE(AVG(r.rating), 0) >= ? "
        params.append(min_rating)
    
    query += " GROUP BY p.id "
    query += having

    if sort == "rating_desc":
        query += " ORDER BY avg_rating DESC, rating_count DESC, p.created_at DESC"
    elif sort == "price_asc":
        query += " ORDER BY p.price ASC, p.created_at DESC"
    elif sort == "price_desc":
        query += " ORDER BY p.price DESC, p.created_at DESC"
    else:
        query += " ORDER BY p.created_at DESC"
    
    products = db.execute(query, tuple(params)).fetchall()
    
    # Get all unique categories for filter dropdown
    categories = db.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category").fetchall()
    category_list = [cat['category'] for cat in categories]
    
    # Get price range for slider
    price_range = db.execute("SELECT MIN(price) as min_price, MAX(price) as max_price FROM products").fetchone()
    min_price_db = price_range['min_price'] or 0
    max_price_db = price_range['max_price'] or 100000

    # Wishlist ids for logged-in user
    wishlist_ids = []
    if session.get("user_id"):
        rows = db.execute("SELECT product_id FROM wishlist WHERE user_id = ?", (session["user_id"],)).fetchall()
        wishlist_ids = [r["product_id"] for r in rows]
    
    return render_template(
        "products.html", 
        products=products,
        categories=category_list,
        min_price_db=min_price_db,
        max_price_db=max_price_db,
        wishlist_ids=wishlist_ids,
        current_filters={
            'min_price': min_price,
            'max_price': max_price,
            'min_rating': min_rating,
            'category': category,
            'sort': sort
        }
    )


@product_bp.route("/add-to-wishlist/<int:pid>", methods=["POST"])
def add_to_wishlist(pid):
    if "user_id" not in session:
        flash("Please login to add items to wishlist.", "error")
        return redirect(request.referrer or "/products")
    db = get_db()
    product = db.execute("SELECT id FROM products WHERE id = ?", (pid,)).fetchone()
    if not product:
        flash("Product not found.", "error")
        return redirect("/products")
    try:
        db.execute("INSERT OR IGNORE INTO wishlist (user_id, product_id) VALUES (?, ?)", (session["user_id"], pid))
        db.commit()
        flash("Added to wishlist!", "success")
    except Exception:
        db.rollback()
        flash("Could not add to wishlist.", "error")
    return redirect(request.referrer or "/products")


@product_bp.route("/remove-from-wishlist/<int:pid>", methods=["POST"])
def remove_from_wishlist(pid):
    if "user_id" not in session:
        return redirect(request.referrer or "/products")
    db = get_db()
    db.execute("DELETE FROM wishlist WHERE user_id = ? AND product_id = ?", (session["user_id"], pid))
    db.commit()
    flash("Removed from wishlist.", "success")
    return redirect(request.referrer or "/products")


@product_bp.route("/wishlist")
def wishlist():
    if "user_id" not in session:
        flash("Please login to view your wishlist.", "error")
        return redirect("/login")
    db = get_db()
    products = db.execute("""
        SELECT p.*, COALESCE(AVG(r.rating), 0) AS avg_rating, COUNT(r.id) AS rating_count
        FROM wishlist w
        JOIN products p ON p.id = w.product_id
        LEFT JOIN product_reviews r ON r.product_id = p.id
        WHERE w.user_id = ?
        GROUP BY p.id
        ORDER BY w.created_at DESC
    """, (session["user_id"],)).fetchall()
    return render_template("wishlist.html", products=products)


@product_bp.route("/add-to-cart/<int:pid>", methods=["POST"])
def add_to_cart(pid):
    # Check if product exists
    db = get_db()
    product = db.execute("SELECT * FROM products WHERE id = ?", (pid,)).fetchone()
    
    if not product:
        flash("Product not found!", "error")
        return redirect("/products")
    
    # Initialize cart as dict if not exists
    cart = session.get("cart", {})
    
    # Add or increment product in cart
    if str(pid) in cart:
        cart[str(pid)] += 1
    else:
        cart[str(pid)] = 1
    
    session["cart"] = cart
    flash(f"{product['name']} added to cart!", "success")
    return redirect("/products")
