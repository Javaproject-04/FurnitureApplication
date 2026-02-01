import sqlite3
from flask import g

DATABASE = 'furnishfusion.db'

def get_db():
    """Get database connection"""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    """Initialize database with tables"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create products table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image_url TEXT,
            category TEXT,
            rating REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add category and rating columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN category TEXT")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN rating REAL DEFAULT 0.0")
    except:
        pass
    
    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            total REAL NOT NULL,
            status TEXT DEFAULT 'pending',
            payment_method TEXT DEFAULT 'cod',
            payment_status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Add payment and tracking columns if they don't exist (for existing databases)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_method TEXT DEFAULT 'cod'")
    except:
        pass
    
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_status TEXT DEFAULT 'pending'")
    except:
        pass
    
    # NOTE: SQLite ALTER TABLE has restrictions around non-constant defaults.
    # Add columns in a migration-safe way (no DEFAULT expressions here).
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN updated_at TEXT")
    except Exception:
        pass

    # Optional: backfill updated_at for existing rows if column exists
    try:
        cursor.execute("UPDATE orders SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)")
    except Exception:
        pass

    # UPI QR + payment proof support (added safely for existing DBs)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN advance_amount REAL")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN payment_proof_url TEXT")
    except Exception:
        pass
    
    # Create order_items table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER DEFAULT 1,
            price REAL NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # User ratings (users rate products, not admin)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS product_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Store a single UPI QR code (admin managed)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS upi_qr (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            image_url TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    try:
        cursor.execute("INSERT OR IGNORE INTO upi_qr (id, image_url) VALUES (1, NULL)")
    except Exception:
        pass

    # Wishlist (user_id, product_id)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS wishlist (
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, product_id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')

    # Coupons: code, discount_type ('percent'|'fixed'), discount_value, is_active (1=active, 0=deleted/inactive)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            discount_type TEXT NOT NULL CHECK(discount_type IN ('percent','fixed')),
            discount_value REAL NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Order discount (for applied coupon)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN coupon_id INTEGER REFERENCES coupons(id)")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN discount_amount REAL DEFAULT 0")
    except Exception:
        pass
    
    # Contact details for orders (mobile and address)
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN contact_mobile TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE orders ADD COLUMN contact_address TEXT")
    except Exception:
        pass
    
    # Create admins table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create contact_info table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contact_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT,
            state TEXT,
            zip_code TEXT,
            country TEXT,
            website TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default contact info if none exists
    cursor.execute("SELECT COUNT(*) as count FROM contact_info")
    contact_count = cursor.fetchone()[0]
    
    if contact_count == 0:
        cursor.execute(
            """INSERT INTO contact_info 
               (company_name, email, phone, address, city, state, zip_code, country, website) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("FurnishFusion", "info@furnishfusion.com", "+91 1234567890", 
             "123 Furniture Street", "Mumbai", "Maharashtra", "400001", "India", 
             "https://www.furnishfusion.com")
        )
    
    # Create default admin if no admins exist
    cursor.execute("SELECT COUNT(*) as count FROM admins")
    admin_count = cursor.fetchone()[0]
    
    if admin_count == 0:
        # Default admin credentials: admin / admin123
        cursor.execute(
            "INSERT INTO admins (username, email, password) VALUES (?, ?, ?)",
            ("admin", "admin@furnishfusion.com", "admin123")
        )
    
    # Add sample products if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM products")
    product_count = cursor.fetchone()[0]
    
    if product_count == 0:
        sample_products = [
            ("Modern Sofa Set", "Comfortable 3-seater sofa with matching cushions. Perfect for your living room.", 45000.00, "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=500"),
            ("Wooden Dining Table", "Elegant 6-seater dining table made from premium oak wood.", 35000.00, "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500"),
            ("Ergonomic Office Chair", "Comfortable office chair with lumbar support and adjustable height.", 12000.00, "https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?w=500"),
            ("Queen Size Bed Frame", "Sturdy metal bed frame with modern design. Includes headboard.", 28000.00, "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=500"),
            ("Bookshelf Unit", "5-tier bookshelf with adjustable shelves. Perfect for organizing your space.", 15000.00, "https://images.unsplash.com/photo-1594620302200-9a762244a094?w=500"),
            ("Coffee Table", "Glass top coffee table with wooden legs. Modern and elegant design.", 18000.00, "https://images.unsplash.com/photo-1532372320572-cda25653a26d?w=500"),
            ("Wardrobe Cabinet", "Spacious 3-door wardrobe with mirror. Ample storage space.", 42000.00, "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500"),
            ("Study Desk", "Compact study desk with drawers. Perfect for home office.", 22000.00, "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500"),
        ]
        
        cursor.executemany(
            "INSERT INTO products (name, description, price, image_url) VALUES (?, ?, ?, ?)",
            sample_products
        )
    
    conn.commit()
    conn.close()

def close_db(e=None):
    """Close database connection"""
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()
