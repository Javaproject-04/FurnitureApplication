"""
Budget Planner module for FurnishFusion.
Splits user budget by room type and recommends products from the database.
No external AI/ML libraries - rule-based detection only.
"""

import re
from db import get_db

# ---------------------------------------------------------------------------
# Budget split rules: room_type -> { category_name: percentage }
# ---------------------------------------------------------------------------
BUDGET_RULES = {
    "bedroom": {
        "Bed": 60,
        "Mattress": 25,
        "Side Table": 15,
    },
    "living_room": {
        "Sofa": 60,
        "Center Table": 20,
        "TV Unit": 20,
    },
    "office": {
        "Chair": 50,
        "Desk": 40,
        "Storage": 10,
    },
}

# ---------------------------------------------------------------------------
# Keywords to map budget category -> product search terms (name/category LIKE)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "Bed": ["bed", "bed frame", "queen", "king", "single bed", "double bed"],
    "Mattress": ["mattress", "bed"],
    "Side Table": ["side table", "side-table", "bedside", "nightstand", "coffee table", "table"],
    "Sofa": ["sofa", "couch", "settee", "set"],
    "Center Table": ["coffee table", "center table", "centre table", "table"],
    "TV Unit": ["tv", "entertainment", "cabinet", "unit", "wardrobe"],
    "Chair": ["chair", "ergonomic", "office"],
    "Desk": ["desk", "study", "table"],
    "Storage": ["storage", "shelf", "bookcase", "cabinet", "wardrobe", "bookshelf"],
}


def detect_budget(text: str) -> float | None:
    """
    Extract budget amount from user input.
    Handles formats like: 50000, 50,000, 50k, 50 thousand, Rs 50000, ₹50000.
    """
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    # Remove currency symbols and normalize
    normalized = re.sub(r"[\s,]", "", text.lower())
    normalized = normalized.replace("rs", "").replace("₹", "").replace("inr", "")
    # Match numbers followed by k/thousand/lac/lakh
    match_k = re.search(r"(\d+(?:\.\d+)?)\s*k(?:ilo)?", normalized, re.I)
    if match_k:
        return float(match_k.group(1)) * 1000
    match_lac = re.search(r"(\d+(?:\.\d+)?)\s*(?:lac|lakh)", normalized, re.I)
    if match_lac:
        return float(match_lac.group(1)) * 100000
    match_thou = re.search(r"(\d+(?:\.\d+)?)\s*thousand", normalized, re.I)
    if match_thou:
        return float(match_thou.group(1)) * 1000
    # Plain number
    match_num = re.search(r"(\d+(?:\.\d+)?)", normalized)
    if match_num:
        return float(match_num.group(1))
    return None


def detect_room_type(text: str) -> str | None:
    """Detect room type from user input using keywords."""
    if not text or not isinstance(text, str):
        return None
    t = text.lower().strip()
    if any(kw in t for kw in ["bedroom", "bed room", "bed-room"]):
        return "bedroom"
    if any(kw in t for kw in ["living room", "livingroom", "living-room", "hall", "sitting"]):
        return "living_room"
    if any(kw in t for kw in ["office", "study", "work room", "workroom"]):
        return "office"
    return None


def get_category_budget(total_budget: float, category: str, pct: float) -> float:
    """Calculate allocated budget for a category."""
    return round(total_budget * (pct / 100), 2)


def find_products_for_category(db, category_name: str, max_budget: float, limit: int = 3) -> list:
    """
    Query products matching category keywords and within budget.
    Returns list of dicts with id, name, price, image_url, description.
    """
    keywords = CATEGORY_KEYWORDS.get(category_name, [category_name.lower()])
    # Build OR conditions for name and category
    conditions = []
    params = []
    for kw in keywords:
        conditions.append("(LOWER(p.name) LIKE ? OR (p.category IS NOT NULL AND LOWER(p.category) LIKE ?))")
        params.extend([f"%{kw}%", f"%{kw}%"])
    where_clause = " OR ".join(conditions)
    query = f"""
        SELECT p.id, p.name, p.price, p.image_url, p.description
        FROM products p
        WHERE ({where_clause}) AND p.price <= ?
        ORDER BY p.price DESC
        LIMIT ?
    """
    params.extend([max_budget, limit])
    rows = db.execute(query, tuple(params)).fetchall()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "price": float(r["price"]) if r["price"] else 0,
            "image_url": r["image_url"] or "",
            "description": (r["description"] or "")[:150],
        }
        for r in rows
    ]


def run_budget_planner(user_input: str) -> dict:
    """
    Main entry: parse input, compute budget split, fetch recommendations.
    Returns structured dict for API response.
    """
    budget = detect_budget(user_input)
    room = detect_room_type(user_input)
    if budget is None or budget <= 0:
        return {
            "success": False,
            "error": "Could not detect a valid budget from your message. Try: \"I have 50000 to furnish my bedroom\"",
            "total_budget": None,
            "room_type": room,
            "categories": [],
        }
    if room is None:
        return {
            "success": False,
            "error": "Could not detect room type. Please mention bedroom, living room, or office.",
            "total_budget": budget,
            "room_type": None,
            "categories": [],
        }
    rules = BUDGET_RULES.get(room, {})
    if not rules:
        return {
            "success": False,
            "error": f"No budget rules defined for room: {room}",
            "total_budget": budget,
            "room_type": room,
            "categories": [],
        }
    db = get_db()
    categories_out = []
    for cat_name, pct in rules.items():
        cat_budget = get_category_budget(budget, cat_name, pct)
        products = find_products_for_category(db, cat_name, cat_budget, limit=3)
        fallback_msg = None
        if not products:
            fallback_msg = f"No product found under ₹{cat_budget:,.2f} for {cat_name}. Try increasing your budget or browse our catalog."
        categories_out.append({
            "category": cat_name,
            "percentage": pct,
            "allocated_budget": cat_budget,
            "products": products,
            "fallback_message": fallback_msg,
        })
    room_label = room.replace("_", " ").title()
    return {
        "success": True,
        "total_budget": budget,
        "room_type": room,
        "room_label": room_label,
        "categories": categories_out,
        "raw_input": user_input,
    }
