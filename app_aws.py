from flask import Flask, render_template, request, redirect, url_for, session
import os
import uuid
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------------------------------------
# Flask App Configuration
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "furnishfusion_secret_key")

# -------------------------------------------------
# AWS Configuration
# -------------------------------------------------
AWS_REGION = "us-east-1"

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
sns = boto3.client("sns", region_name=AWS_REGION)

# -------------------------------------------------
# DynamoDB Tables (must exist in AWS)
# -------------------------------------------------
users_table = dynamodb.Table("FF_Users")
admins_table = dynamodb.Table("FF_Admins")
products_table = dynamodb.Table("FF_Products")
orders_table = dynamodb.Table("FF_Orders")

# -------------------------------------------------
# SNS Topic ARN
# -------------------------------------------------
SNS_TOPIC_ARN = "arn:aws:sns:us-east-1:203918855127:furnishfusion_topic"

# -------------------------------------------------
# File Upload Configuration
# -------------------------------------------------
UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# -------------------------------------------------
# Helper: Send SNS Notification
# -------------------------------------------------
def send_notification(subject, message):
    """
    Sends notification using AWS SNS.
    Failure should not break application flow.
    """
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
    except ClientError as e:
        print("SNS Error:", e)


# =================================================
# PUBLIC ROUTES
# =================================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/about")
def about():
    return render_template("about.html")


# =================================================
# USER AUTHENTICATION
# =================================================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Check if user already exists
        if "Item" in users_table.get_item(Key={"username": username}):
            return "User already exists"

        hashed_password = generate_password_hash(password)

        users_table.put_item(Item={
            "username": username,
            "password": hashed_password
        })

        send_notification(
            "New User Signup",
            f"{username} registered on FurnishFusion"
        )

        return redirect(url_for("login"))

    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        response = users_table.get_item(Key={"username": username})

        if "Item" in response and check_password_hash(
            response["Item"]["password"], password
        ):
            session["user"] = username
            return redirect(url_for("home"))

        return "Invalid credentials"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# =================================================
# USER DASHBOARD & PRODUCTS
# =================================================
@app.route("/home")
def home():
    if "user" not in session:
        return redirect(url_for("login"))

    products = products_table.scan().get("Items", [])
    return render_template("home.html", products=products)


@app.route("/products")
def products():
    products = products_table.scan().get("Items", [])
    return render_template("products.html", products=products)


# =================================================
# ORDER PLACEMENT
# =================================================
@app.route("/order/<product_id>")
def place_order(product_id):
    if "user" not in session:
        return redirect(url_for("login"))

    order_id = str(uuid.uuid4())

    orders_table.put_item(Item={
        "order_id": order_id,
        "username": session["user"],
        "product_id": product_id,
        "status": "PLACED"
        # TODO: Add address, payment_mode, timestamp
    })

    send_notification(
        "New Order",
        f"Order {order_id} placed by {session['user']}"
    )

    return redirect(url_for("home"))


# =================================================
# ADMIN AUTHENTICATION
# =================================================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        response = admins_table.get_item(Key={"username": username})

        if "Item" in response and check_password_hash(
            response["Item"]["password"], password
        ):
            session["admin"] = username
            return redirect(url_for("admin_dashboard"))

        return "Invalid admin credentials"

    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("index"))


# =================================================
# ADMIN DASHBOARD
# =================================================
@app.route("/admin/dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    products = products_table.scan().get("Items", [])
    orders = orders_table.scan().get("Items", [])

    return render_template(
        "admin_dashboard.html",
        products=products,
        orders=orders
    )


# =================================================
# ADMIN: ADD PRODUCT
# =================================================
@app.route("/admin/add-product", methods=["GET", "POST"])
def add_product():
    if "admin" not in session:
        return redirect(url_for("admin_login"))

    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        description = request.form["description"]
        image = request.files["image"]

        image_name = secure_filename(image.filename)
        image.save(os.path.join(app.config["UPLOAD_FOLDER"], image_name))

        product_id = str(uuid.uuid4())

        products_table.put_item(Item={
            "product_id": product_id,
            "name": name,
            "price": price,
            "description": description,
            "image": image_name
            # TODO: Add category, stock, rating
        })

        send_notification(
            "New Product Added",
            f"{name} added to FurnishFusion"
        )

        return redirect(url_for("admin_dashboard"))

    return render_template("add_product.html")


# =================================================
# APP ENTRY POINT
# =================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
