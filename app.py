import os
import time
from flask import Flask, session
from models import db, Category, User, AppConfig
from dotenv import load_dotenv
from flask_compress import Compress
import cloudinary
import cloudinary.uploader
import cloudinary.api

load_dotenv()

# Import blueprints
from routes.public import public_bp
from routes.auth import auth_bp
from routes.cart import cart_bp
from routes.checkout import checkout_bp
from routes.admin import admin_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dadson-jewelry-secret-key')
app.config['TEMPLATES_AUTO_RELOAD'] = True   # always pick up template edits without server restart
app.config['COMPRESS_REGISTER'] = True
app.config['COMPRESS_MIMETYPES'] = [
    'text/html', 'text/css', 'text/javascript',
    'application/javascript', 'application/json',
    'image/svg+xml',
]
Compress(app)
app.jinja_env.add_extension('jinja2.ext.do')

# Cache static files aggressively in production (1 year), disable in debug
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0 if os.getenv('FLASK_DEBUG') else 31536000

# Database Configuration
db_url = os.getenv('DATABASE_URL')
if not db_url:
    # Default to local SQLite if DATABASE_URL is not set (useful for initial dev)
    db_url = 'sqlite:///dadson.db'
elif db_url.startswith("postgres://"):
    # Fix for newer SQLAlchemy/Heroku/Vercel postgres URLs
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 5,
    "max_overflow": 10,
}
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

# Cloudinary Config
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

db.init_app(app)

# Register Blueprints
app.register_blueprint(public_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(cart_bp)
app.register_blueprint(checkout_bp)
app.register_blueprint(admin_bp)

# Bootstrap on startup
with app.app_context():
    db.create_all()

    # Migration for new product fields
    try:
        db.session.execute(db.text('ALTER TABLE product ADD COLUMN is_best_seller BOOLEAN DEFAULT FALSE'))
        db.session.commit()
    except Exception:
        db.session.rollback()

    try:
        db.session.execute(db.text('ALTER TABLE product ADD COLUMN is_new_arrival BOOLEAN DEFAULT FALSE'))
        db.session.commit()
    except Exception:
        db.session.rollback()

    # Migration for OrderItem variation tracking
    for col, col_type in [
        ('variation_id', 'INTEGER'),
        ('variation_label', 'VARCHAR(500)'),
    ]:
        try:
            db.session.execute(db.text(f'ALTER TABLE order_item ADD COLUMN {col} {col_type}'))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Migration for SEO fields
    for col, col_type in [
        ('seo_title', 'VARCHAR(200)'),
        ('seo_description', 'TEXT'),
        ('focus_keyword', 'VARCHAR(200)'),
        ('meta_keywords', 'TEXT'),
        ('product_tags', 'TEXT'),
    ]:
        try:
            db.session.execute(db.text(f'ALTER TABLE product ADD COLUMN {col} {col_type}'))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Migration for Category recursive hierarchy and gender attributes
    for col, col_type in [
        ('parent_id', 'INTEGER'),
        ('gender', 'VARCHAR(20)'),
    ]:
        try:
            db.session.execute(db.text(f'ALTER TABLE category ADD COLUMN {col} {col_type}'))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Migrate SubCategory entries to Category entries
    try:
        from models import SubCategory, Product
        subcategories = SubCategory.query.all()
        if subcategories:
            print(f"Migrating {len(subcategories)} SubCategory records to Category...")
            sub_to_cat_map = {}
            for sub in subcategories:
                gender = 'Both'
                name = sub.name
                if sub.name.lower().startswith('men - '):
                    gender = 'Men'
                    name = sub.name[6:]
                elif sub.name.lower().startswith('women - '):
                    gender = 'Women'
                    name = sub.name[8:]
                elif sub.name.lower() == 'men':
                    gender = 'Men'
                elif sub.name.lower() == 'women':
                    gender = 'Women'

                existing_cat = Category.query.filter_by(name=name, parent_id=sub.category_id, gender=gender).first()
                if not existing_cat:
                    existing_cat = Category(
                        name=name,
                        parent_id=sub.category_id,
                        gender=gender,
                        img=sub.category.img if sub.category else None
                    )
                    db.session.add(existing_cat)
                    db.session.flush()
                sub_to_cat_map[sub.id] = existing_cat.id

            products = Product.query.filter(Product.sub_category_id.isnot(None)).all()
            for prod in products:
                if prod.sub_category_id in sub_to_cat_map:
                    prod.category_id = sub_to_cat_map[prod.sub_category_id]
                    p_cat = Category.query.get(prod.category_id)
                    prod.cat_name = p_cat.name if p_cat else 'Uncategorized'
            db.session.commit()

            db.session.query(SubCategory).delete()
            db.session.commit()
            print("SubCategory migration completed.")
    except Exception as e:
        db.session.rollback()
        print(f"Error during category migration: {e}")



    # Ensure upload directories exist
    upload_dirs = [
        app.config['UPLOAD_FOLDER'],
        os.path.join(app.config['UPLOAD_FOLDER'], 'products'),
        os.path.join(app.config['UPLOAD_FOLDER'], 'categories'),
    ]
    for d in upload_dirs:
        try:
            if not os.path.exists(d):
                os.makedirs(d)
        except OSError:
            pass

    # Seed Admin
    admin_email = os.getenv('ADMIN_EMAIL')
    if not User.query.filter_by(email=admin_email).first():
        admin = User(email=admin_email, is_admin=True)
        admin.set_password(os.getenv('ADMIN_PASSWORD'))
        db.session.add(admin)

    # Seed default configs
    default_configs = {
        'shipping_charges': '₹99',
        'free_shipping_above': '₹1499',
        'payment_methods': 'COD, Razorpay, UPI',
        'contact_email': 'dadsonjewelry@gmail.com'
    }
    for key, value in default_configs.items():
        if not AppConfig.query.filter_by(key=key).first():
            config = AppConfig(key=key, value=value)
            db.session.add(config)

    db.session.commit()

    # Gender attribute — disable from Product Details (Men/Women/Unisex are now categories)
    try:
        from models import Attribute, AttributeValue
        Attribute.query.filter(Attribute.name.in_(['Men', 'Women'])).delete()
        db.session.commit()
        gender_attr = Attribute.query.filter_by(slug='gender').first()
        if gender_attr:
            gender_attr.is_featured = False
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error updating Gender attribute: {e}")

    # Ensure Watch is top-level with Men/Women/Unisex underneath it.
    # Jewelry categories (Kada, Earrings, Chain Pendant Set, Chain, Rings) are top-level.
    try:
        watch_cat = Category.query.filter_by(name='Watch').first()
        if watch_cat and watch_cat.parent_id is not None:
            watch_cat.parent_id = None
            db.session.commit()

        if watch_cat:
            for gender_name in ['Men', 'Women', 'Unisex']:
                g = Category.query.filter_by(name=gender_name).first()
                if not g:
                    db.session.add(Category(name=gender_name, parent_id=watch_cat.id))
                elif g.parent_id != watch_cat.id:
                    g.parent_id = watch_cat.id
            db.session.commit()

        for jewelry_name in ['Kada', 'Earrings', 'Chain Pendant Set', 'Chain', 'Rings']:
            j = Category.query.filter_by(name=jewelry_name).first()
            if j and j.parent_id is not None:
                j.parent_id = None
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error ensuring category hierarchy: {e}")

# ---------------------------------------------------------------------------
# Simple in-process caches — avoid DB round-trips on every page load
# ---------------------------------------------------------------------------
_category_cache = {'data': None}
_config_cache = {}
_admin_notif_cache = {'data': None, 'ts': 0}
_ADMIN_NOTIF_TTL = 30  # seconds

def get_cached_categories():
    if _category_cache['data'] is None:
        from sqlalchemy.orm import joinedload
        _category_cache['data'] = Category.query.options(
            joinedload(Category.subcategories)
        ).all()
    return _category_cache['data']

def get_cached_config(key):
    if key not in _config_cache:
        cfg = AppConfig.query.filter_by(key=key).first()
        _config_cache[key] = cfg.value if cfg and cfg.value else None
    return _config_cache[key]

def get_cached_admin_notifications():
    now = time.time()
    if _admin_notif_cache['data'] is not None and now - _admin_notif_cache['ts'] < _ADMIN_NOTIF_TTL:
        return _admin_notif_cache['data']
    from models import Order, Product
    notifications = []
    recent_orders = Order.query.order_by(Order.id.desc()).limit(3).all()
    for o in recent_orders:
        notifications.append({"text": f"New order #{o.order_number} received", "time": "Recently", "type": "order"})
    low_stock = Product.query.filter(Product.stock_status == 'outofstock').limit(2).all()
    for p in low_stock:
        notifications.append({"text": f"Product '{p.name}' is out of stock", "time": "Alert", "type": "stock"})
    _admin_notif_cache['data'] = notifications
    _admin_notif_cache['ts'] = now
    return notifications

def invalidate_category_cache():
    _category_cache['data'] = None

def invalidate_config_cache(key=None):
    if key:
        _config_cache.pop(key, None)
    else:
        _config_cache.clear()

# Expose so admin routes can call these
app.invalidate_category_cache = invalidate_category_cache
app.invalidate_config_cache = invalidate_config_cache


# Context processor — runs on every request; keep it lean
@app.context_processor
def inject_globals():
    cart = session.get('cart', {})
    count = sum(cart.values())
    wishlist = session.get('wishlist', [])
    wishlist_count = len(wishlist)

    # Cached — no DB hit unless cache was invalidated
    categories = get_cached_categories()

    user = None
    admin_notifications = []

    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.is_admin:
            admin_notifications = get_cached_admin_notifications()

    ga_measurement_id = get_cached_config('ga_measurement_id')
    facebook_pixel_id = get_cached_config('facebook_pixel_id')

    return dict(
        cart_count=count,
        all_categories=categories,
        current_user=user,
        wishlist_count=wishlist_count,
        admin_notifications=admin_notifications,
        ga_measurement_id=ga_measurement_id,
        facebook_pixel_id=facebook_pixel_id,
    )


# Error Handlers
@app.errorhandler(404)
def page_not_found(e):
    from flask import render_template
    return render_template('404.html'), 404

@app.errorhandler(Exception)
def handle_exception(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    from flask import render_template
    app.logger.error(f"Unhandled Server Error: {e}")
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
