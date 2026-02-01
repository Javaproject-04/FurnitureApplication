"""Utility functions for FurnishFusion"""

def detect_category(product_name):
    """Automatically detect category based on product name"""
    name_lower = product_name.lower()
    
    # Bed categories
    if any(word in name_lower for word in ['single bed', 'single-bed', 'singlebed']):
        return 'Beds - Single Bed'
    elif any(word in name_lower for word in ['double bed', 'double-bed', 'doublebed']):
        return 'Beds - Double Bed'
    elif any(word in name_lower for word in ['master bed', 'master-bed', 'masterbed', 'king bed', 'king-bed']):
        return 'Beds - Master Bed'
    elif any(word in name_lower for word in ['sofa cum bed', 'sofa-cum-bed', 'sofacumbed', 'sofa bed', 'sofa-bed']):
        return 'Beds - Sofa Cum Bed'
    elif any(word in name_lower for word in ['bed', 'mattress']):
        return 'Beds - Other'
    
    # Sofa categories
    elif any(word in name_lower for word in ['sofa', 'couch', 'settee']):
        return 'Sofas'
    
    # Dining categories
    elif any(word in name_lower for word in ['dining table', 'dining-table', 'diningtable', 'dining']):
        return 'Dining'
    
    # Office/Study categories
    elif any(word in name_lower for word in ['office chair', 'office-chair', 'officechair', 'ergonomic']):
        return 'Office - Chairs'
    elif any(word in name_lower for word in ['study desk', 'study-desk', 'studydesk', 'office desk', 'office-desk']):
        return 'Office - Desks'
    elif any(word in name_lower for word in ['office', 'study']):
        return 'Office - Other'
    
    # Storage categories
    elif any(word in name_lower for word in ['wardrobe', 'cabinet', 'closet']):
        return 'Storage - Wardrobes'
    elif any(word in name_lower for word in ['bookshelf', 'book shelf', 'book-shelf', 'shelf']):
        return 'Storage - Shelves'
    elif any(word in name_lower for word in ['storage', 'drawer']):
        return 'Storage - Other'
    
    # Tables
    elif any(word in name_lower for word in ['coffee table', 'coffee-table', 'coffeetable', 'side table', 'side-table']):
        return 'Tables - Coffee Tables'
    elif any(word in name_lower for word in ['table']):
        return 'Tables - Other'
    
    # Chairs
    elif any(word in name_lower for word in ['chair']):
        return 'Chairs'
    
    # Default
    else:
        return 'Furniture - Other'
