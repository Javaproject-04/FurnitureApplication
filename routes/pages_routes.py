"""Static content pages: About, Contact, FAQ, Policies."""

from flask import Blueprint, render_template

from db import get_db

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/about")
def about():
    return render_template("about.html")


@pages_bp.route("/contact")
def contact():
    contact_info = get_db().execute("SELECT * FROM contact_info LIMIT 1").fetchone()
    return render_template("contact.html", contact_info=contact_info)


@pages_bp.route("/faq")
def faq():
    return render_template("faq.html")


@pages_bp.route("/return-policy")
def return_policy():
    return render_template("return_policy.html")


@pages_bp.route("/shipping-policy")
def shipping_policy():
    return render_template("shipping_policy.html")


@pages_bp.route("/cancellation-policy")
def cancellation_policy():
    return render_template("cancellation_policy.html")


@pages_bp.route("/privacy-policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@pages_bp.route("/terms-conditions")
def terms_conditions():
    return render_template("terms_conditions.html")


@pages_bp.route("/refund-policy")
def refund_policy():
    return render_template("refund_policy.html")
