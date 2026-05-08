from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash, jsonify
from functools import wraps
from models import db, User, Product, Category, SubCategory, ProductVariation, Order, AppConfig, Attribute, AttributeValue, ProductAttribute, VariationOption, Brand, Review, Coupon, ProductImage
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from flask import current_app
import cloudinary.uploader
import re

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

def save_image(file, folder):
    if not file:
        return None
    # Upload to Cloudinary
    upload_result = cloudinary.uploader.upload(file, folder=f"dadson/{folder}")
    return upload_result.get('secure_url')

def delete_image(image_url):
    if not image_url or 'cloudinary' not in image_url:
        return
    try:
        parts = image_url.split('/')
        upload_idx = -1
        for i, part in enumerate(parts):
            if part == 'upload':
                upload_idx = i
                break
        
        if upload_idx != -1:
            id_parts = parts[upload_idx + 2:]
            public_id_with_ext = "/".join(id_parts)
            public_id = public_id_with_ext.rsplit('.', 1)[0]
            cloudinary.uploader.destroy(public_id)
    except Exception as e:
        print(f"Error deleting from Cloudinary: {e}")

@admin_bp.route('/admin/dashboard')
@admin_required
def dashboard():
    products_count = Product.query.count()
    categories_count = Category.query.count()
    users_count = User.query.filter_by(is_admin=False).count()
    orders_count = Order.query.count()
    
    recent_orders = Order.query.order_by(Order.id.desc()).limit(5).all()
    
    low_stock_products = Product.query.filter(Product.stock_status == 'outofstock').limit(3).all()
    if not low_stock_products:
        low_stock_products = Product.query.limit(2).all()
        
    return render_template('admin/dashboard.html', 
                           products_count=products_count,
                           categories_count=categories_count,
                           users_count=users_count,
                           orders_count=orders_count,
                           recent_orders=recent_orders,
                           low_stock_products=low_stock_products)

@admin_bp.route('/admin/profile', methods=['GET', 'POST'])
@admin_required
def profile():
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        db.session.commit()
        flash('Admin profile updated!', 'success')
        return redirect(url_for('admin.profile'))
    return render_template('admin/profile.html', user=user)

# --- PRODUCT ROUTES ---

@admin_bp.route('/admin/products')
@admin_required
def products():
    all_products = Product.query.all()
    return render_template('admin/products.html', products=all_products)

@admin_bp.route('/admin/product/new', methods=['GET', 'POST'])
@admin_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price_raw = request.form.get('price', '').replace('Rs.', '').replace(',', '').strip()
        price = price_raw if price_raw else '0'
        badge = request.form.get('badge')
        sizes = request.form.get('sizes')
        colors = request.form.get('colors')
        desc = request.form.get('desc')
        product_type = request.form.get('product_type', 'simple')
        stock_status = request.form.get('stock_status', 'instock')
        category_id = request.form.get('category_id') or None
        sub_category_id = request.form.get('sub_category_id') or None
        brand_id = request.form.get('brand_id') or None
        is_featured = True if request.form.get('is_featured') == 'on' else False
        
        category = Category.query.get(category_id)
        cat_name = category.name if category else 'Uncategorized'
        
        img_file = request.files.get('img')
        img = save_image(img_file, 'products') if img_file else None
        
        new_id = name.lower().replace(' ', '-')
        if Product.query.get(new_id):
            new_id = f"{new_id}-{int(datetime.now().timestamp())}"
            
        product = Product(
            id=new_id, 
            name=name, 
            price=f"Rs. {price}", 
            cat_name=cat_name, 
            category_id=category_id,
            sub_category_id=sub_category_id,
            brand_id=brand_id,
            badge=badge, 
            img=img,
            sizes=sizes,
            colors=colors,
            desc=desc,
            product_type=product_type,
            stock_status=stock_status,
            is_featured=is_featured
        )
        db.session.add(product)
        db.session.commit()
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin.products'))
    
    categories = Category.query.all()
    subcategories = SubCategory.query.all()
    attributes = Attribute.query.all()
    brands = Brand.query.all()
    return render_template('admin/product_form.html', categories=categories, subcategories=subcategories, attributes=attributes, brands=brands)

@admin_bp.route('/admin/product/edit/<id>', methods=['GET', 'POST'])
@admin_required
def edit_product(id):
    product = Product.query.get(id)
    if not product:
        abort(404)
        
    if request.method == 'POST':
        product.name = request.form.get('name')
        price = request.form.get('price').replace('Rs.', '').strip()
        product.price = f"Rs. {price}"
        category_id = request.form.get('category_id') or None
        product.category_id = category_id
        product.sub_category_id = request.form.get('sub_category_id') or None
        product.brand_id = request.form.get('brand_id') or None
        product.badge = request.form.get('badge')
        product.sizes = request.form.get('sizes')
        product.colors = request.form.get('colors')
        product.desc = request.form.get('desc')
        product.product_type = request.form.get('product_type', 'simple')
        product.stock_status = request.form.get('stock_status', 'instock')
        product.is_featured = True if request.form.get('is_featured') == 'on' else False
        
        category = Category.query.get(category_id)
        if category:
            product.cat_name = category.name
        
        img_file = request.files.get('img')
        if img_file and img_file.filename:
            product.img = save_image(img_file, 'products')
        
        db.session.commit()
        flash('Product updated successfully!', 'success')
        return redirect(url_for('admin.products'))
        
    categories = Category.query.all()
    subcategories = SubCategory.query.all()
    attributes = Attribute.query.all()
    brands = Brand.query.all()
    return render_template('admin/product_form.html', categories=categories, subcategories=subcategories, attributes=attributes, brands=brands, product=product)

@admin_bp.route('/admin/product/delete/<id>', methods=['POST'])
@admin_required
def delete_product(id):
    product = Product.query.get(id)
    if product:
        # Delete main image
        delete_image(product.img)
        
        # Delete gallery images
        for img_obj in product.images:
            delete_image(img_obj.img_url)
            
        # Delete variation images
        for var in product.variations:
            if var.img_url:
                delete_image(var.img_url)
                
        db.session.delete(product)
        db.session.commit()
        flash('Product deleted!', 'success')
    return redirect(url_for('admin.products'))

# --- CATEGORY ROUTES ---

@admin_bp.route('/admin/categories')
@admin_required
def categories():
    all_categories = Category.query.all()
    return render_template('admin/categories.html', categories=all_categories)

@admin_bp.route('/admin/category/new', methods=['GET', 'POST'])
@admin_required
def new_category():
    if request.method == 'POST':
        name = request.form.get('name')
        img_file = request.files.get('img')
        img = save_image(img_file, 'categories') if img_file else None
        
        category = Category(name=name, img=img)
        db.session.add(category)
        db.session.commit()
        flash('Category added successfully!', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html')

@admin_bp.route('/admin/category/delete/<int:id>', methods=['POST'])
@admin_required
def delete_category(id):
    category = Category.query.get(id)
    if category:
        delete_image(category.img)
        db.session.delete(category)
        db.session.commit()
        flash('Category deleted!', 'success')
    return redirect(url_for('admin.categories'))

@admin_bp.route('/admin/subcategory/new', methods=['GET', 'POST'])
@admin_required
def new_subcategory():
    if request.method == 'POST':
        name = request.form.get('name')
        category_id = request.form.get('category_id')
        subcategory = SubCategory(name=name, category_id=category_id)
        db.session.add(subcategory)
        db.session.commit()
        flash('SubCategory added successfully!', 'success')
        return redirect(url_for('admin.categories'))
    categories = Category.query.all()
    return render_template('admin/subcategory_form.html', categories=categories)

# --- CUSTOMER ROUTES ---

@admin_bp.route('/admin/customers')
@admin_required
def customers():
    all_users = User.query.filter_by(is_admin=False).all()
    return render_template('admin/customers.html', users=all_users)

# --- ORDER ROUTES ---

@admin_bp.route('/admin/orders')
@admin_required
def orders():
    all_orders = Order.query.all()
    return render_template('admin/orders.html', orders=all_orders)

# --- ATTRIBUTE ROUTES ---

@admin_bp.route('/admin/attributes')
@admin_required
def admin_attributes():
    all_attributes = Attribute.query.all()
    return render_template('admin/attributes.html', attributes=all_attributes)

@admin_bp.route('/admin/attribute/new', methods=['GET', 'POST'])
@admin_required
def admin_attribute_new():
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug') or name.lower().replace(' ', '-')
        attribute = Attribute(name=name, slug=slug)
        db.session.add(attribute)
        db.session.commit()
        flash('Attribute added successfully!', 'success')
        return redirect(url_for('admin.admin_attributes'))
    return render_template('admin/attribute_form.html')

@admin_bp.route('/admin/attribute/<int:attr_id>/values', methods=['GET', 'POST'])
@admin_required
def admin_attribute_values(attr_id):
    attribute = Attribute.query.get(attr_id)
    if request.method == 'POST':
        value_content = request.form.get('value')
        new_val = AttributeValue(attribute_id=attr_id, value=value_content)
        db.session.add(new_val)
        db.session.commit()
        flash('Value added!', 'success')
    values = AttributeValue.query.filter_by(attribute_id=attr_id).all()
    return render_template('admin/attribute_values.html', attribute=attribute, values=values)

# --- BRAND ROUTES ---

@admin_bp.route('/admin/brands')
@admin_required
def brands():
    all_brands = Brand.query.all()
    return render_template('admin/brands.html', brands=all_brands)

@admin_bp.route('/admin/brand/new', methods=['GET', 'POST'])
@admin_required
def new_brand():
    if request.method == 'POST':
        name = request.form.get('name')
        logo_file = request.files.get('logo')
        logo = save_image(logo_file, 'brands') if logo_file else None
        brand = Brand(name=name, logo=logo)
        db.session.add(brand)
        db.session.commit()
        flash('Brand added successfully!', 'success')
        return redirect(url_for('admin.brands'))
    return render_template('admin/brand_form.html')

@admin_bp.route('/admin/brand/delete/<int:id>', methods=['POST'])
@admin_required
def delete_brand(id):
    brand = Brand.query.get(id)
    if brand:
        delete_image(brand.logo)
        db.session.delete(brand)
        db.session.commit()
        flash('Brand deleted!', 'success')
    return redirect(url_for('admin.brands'))

# --- REVIEW ROUTES ---
@admin_bp.route('/admin/reviews')
@admin_required
def reviews():
    all_reviews = Review.query.order_by(Review.date.desc()).all()
    return render_template('admin/reviews.html', reviews=all_reviews)

@admin_bp.route('/admin/review/new', methods=['POST'])
@admin_required
def new_review():
    customer_name = request.form.get('customer_name')
    customer_location = request.form.get('customer_location')
    rating = int(request.form.get('rating', 5))
    comment = request.form.get('comment')
    is_featured = True if request.form.get('is_featured') == 'on' else False
    
    review = Review(
        customer_name=customer_name,
        customer_location=customer_location,
        rating=rating,
        comment=comment,
        is_featured=is_featured,
        status='Approved'
    )
    db.session.add(review)
    db.session.commit()
    flash('Review added successfully!', 'success')
    return redirect(url_for('admin.reviews'))

@admin_bp.route('/admin/review/edit/<int:id>', methods=['POST'])
@admin_required
def edit_review(id):
    review = Review.query.get(id)
    if review:
        review.customer_name = request.form.get('customer_name')
        review.customer_location = request.form.get('customer_location')
        review.rating = int(request.form.get('rating', 5))
        review.comment = request.form.get('comment')
        review.is_featured = True if request.form.get('is_featured') == 'on' else False
        db.session.commit()
        flash('Review updated successfully!', 'success')
    return redirect(url_for('admin.reviews'))

@admin_bp.route('/admin/review/delete/<int:id>', methods=['POST'])
@admin_required
def delete_review(id):
    review = Review.query.get(id)
    if review:
        db.session.delete(review)
        db.session.commit()
        flash('Review deleted!', 'success')
    return redirect(url_for('admin.reviews'))

@admin_bp.route('/admin/review/status/<int:id>', methods=['POST'])
@admin_required
def review_status(id):
    review = Review.query.get(id)
    if review:
        status = request.form.get('status')
        review.status = status
        db.session.commit()
        flash(f'Review {status.lower()} successfully!', 'success')
    return redirect(url_for('admin.reviews'))

# --- COUPON ROUTES ---
@admin_bp.route('/admin/coupons')
@admin_required
def coupons():
    all_coupons = Coupon.query.all()
    return render_template('admin/coupons.html', coupons=all_coupons)

@admin_bp.route('/admin/coupon/new', methods=['GET', 'POST'])
@admin_required
def new_coupon():
    if request.method == 'POST':
        code = request.form.get('code').upper()
        type = request.form.get('type')
        discount = float(request.form.get('discount', 0))
        coupon = Coupon(code=code, type=type, discount=discount)
        db.session.add(coupon)
        db.session.commit()
        flash('Coupon created successfully!', 'success')
        return redirect(url_for('admin.coupons'))
    return render_template('admin/coupon_form.html')

# --- SETTINGS ---

@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        for key, value in request.form.items():
            config = AppConfig.query.filter_by(key=key).first()
            if config: config.value = value
            else: db.session.add(AppConfig(key=key, value=value))
        db.session.commit()
        flash('Settings updated!', 'success')
        return redirect(url_for('admin.settings'))
    configs = {c.key: c.value for c in AppConfig.query.all()}
    return render_template('admin/settings.html', configs=configs)
