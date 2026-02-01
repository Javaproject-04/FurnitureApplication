"""Budget Planner chatbot routes for FurnishFusion."""

from flask import Blueprint, render_template, request, jsonify

from budget_planner import run_budget_planner

budget_bp = Blueprint("budget", __name__)


@budget_bp.route("/budget-planner", methods=["GET"])
def budget_planner_page():
    """Serve the chatbot UI page."""
    return render_template("budget_planner.html")


@budget_bp.route("/budget-planner", methods=["POST"])
def budget_planner_api():
    """
    Accept JSON: { "message": "I have 50000 to furnish my bedroom" }
    Return structured response with budget split and product recommendations.
    """
    data = request.get_json(silent=True) or {}
    user_input = (data.get("message") or "").strip()
    if not user_input:
        return jsonify({
            "success": False,
            "error": "Please provide a message.",
            "total_budget": None,
            "room_type": None,
            "categories": [],
        }), 400
    result = run_budget_planner(user_input)
    return jsonify(result)
