import os
from flask import Flask, session
from models import db, Category, User, AppConfig
from dotenv import load_dotenv
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

# ---------------------------------------------------------------------------
# Simple in-process category cache — avoids a DB round-trip on every page load
# ---------------------------------------------------------------------------
_category_cache = {'data': None}

def get_cached_categories():
    if _category_cache['data'] is None:
        _category_cache['data'] = Category.query.all()
    return _category_cache['data']

def invalidate_category_cache():
    """Call this whenever categories are created/edited/deleted."""
    _category_cache['data'] = None

# Expose so admin routes can call app.invalidate_category_cache()
app.invalidate_category_cache = invalidate_category_cache


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
            from models import Order, Product
            recent_orders = Order.query.order_by(Order.id.desc()).limit(3).all()
            for o in recent_orders:
                admin_notifications.append({
                    "text": f"New order #{o.order_number} received",
                    "time": "Recently",
                    "type": "order"
                })
            low_stock = Product.query.filter(Product.stock_status == 'outofstock').limit(2).all()
            for p in low_stock:
                admin_notifications.append({
                    "text": f"Product '{p.name}' is out of stock",
                    "time": "Alert",
                    "type": "stock"
                })

    return dict(
        cart_count=count,
        all_categories=categories,
        current_user=user,
        wishlist_count=wishlist_count,
        admin_notifications=admin_notifications
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
