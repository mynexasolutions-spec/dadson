from flask import Blueprint, render_template, session, redirect, url_for, abort, request, flash, jsonify
from functools import wraps
from models import db, User, Product, Category, SubCategory, ProductVariation, Order, AppConfig, Attribute, AttributeValue, ProductAttribute, VariationOption, Brand, Review, Coupon, ProductImage, SelectedAttributeValue, OrderItem
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
    from models import Subscriber
    subscribers_count = Subscriber.query.count()
    
    return render_template('admin/dashboard.html', 
                           products_count=products_count,
                           categories_count=categories_count,
                           users_count=users_count,
                           orders_count=orders_count,
                           subscribers_count=subscribers_count,
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
    categories = Category.query.all()
    return render_template('admin/products.html', products=all_products, categories=categories)

@admin_bp.route('/admin/product/new', methods=['GET', 'POST'])
@admin_required
def new_product():
    if request.method == 'POST':
        name = request.form.get('name')
        price_raw = request.form.get('price', '').replace('Rs.', '').replace('₹', '').replace(',', '').strip()
        orig_raw = request.form.get('orig', '').replace('Rs.', '').replace('₹', '').replace(',', '').strip()
        
        price = f"₹{int(float(price_raw)):,}" if price_raw else "₹0"
        orig = f"₹{int(float(orig_raw)):,}" if orig_raw else None
        
        badge = request.form.get('badge')
        desc = request.form.get('desc')
        product_type = request.form.get('product_type', 'simple')
        stock_status = request.form.get('stock_status', 'instock')
        category_id = request.form.get('category_id') or None
        sub_category_id = request.form.get('sub_category_id') or None
        brand_id = request.form.get('brand_id') or None
        is_featured = True if request.form.get('is_featured') == 'on' else False
        is_best_seller = True if request.form.get('is_best_seller') == 'on' else False
        is_new_arrival = True if request.form.get('is_new_arrival') == 'on' else False
        
        category = Category.query.get(category_id)
        cat_name = category.name if category else 'Uncategorized'
        
        img_file = request.files.get('img')
        img = save_image(img_file, 'products') if img_file else None
        
        size_chart_file = request.files.get('size_chart')
        size_chart = save_image(size_chart_file, 'size_charts') if size_chart_file else None
        
        new_id = name.lower().replace(' ', '-')
        if Product.query.get(new_id):
            new_id = f"{new_id}-{int(datetime.now().timestamp())}"
            
        product = Product(
            id=new_id,
            name=name,
            price=price,
            orig=orig,
            cat_name=cat_name,
            category_id=category_id,
            sub_category_id=sub_category_id,
            brand_id=brand_id,
            badge=badge,
            img=img,
            size_chart=size_chart,
            desc=desc,
            product_type=product_type,
            stock_status=stock_status,
            is_featured=is_featured,
            is_best_seller=is_best_seller,
            is_new_arrival=is_new_arrival,
            materials=request.form.get('materials'),
            care=request.form.get('care'),
            seo_title=request.form.get('seo_title') or None,
            seo_description=request.form.get('seo_description') or None,
            focus_keyword=request.form.get('focus_keyword') or None,
            meta_keywords=request.form.get('meta_keywords') or None,
            product_tags=request.form.get('product_tags') or None,
        )
        db.session.add(product)
        db.session.flush() # Get product ID for related models
        
        # Handle Attributes & Values
        SelectedAttributeValue.query.filter_by(product_id=product.id).delete()
        ProductAttribute.query.filter_by(product_id=product.id).delete()
        attr_ids = request.form.getlist('product_attributes[]')
        for a_id in attr_ids:
            if a_id:
                db.session.add(ProductAttribute(product_id=product.id, attribute_id=a_id))
                # Also save selected values for this attribute
                val_ids = request.form.getlist(f'attr_val_{a_id}[]')
                for v_id in val_ids:
                    if v_id:
                        db.session.add(SelectedAttributeValue(
                            product_id=product.id,
                            attribute_id=a_id,
                            attribute_value_id=v_id
                        ))
        
        # Handle Gallery Images
        gallery_files = request.files.getlist('gallery[]')
        for g_file in gallery_files:
            if g_file and g_file.filename:
                g_url = save_image(g_file, 'products/gallery')
                if g_url:
                    db.session.add(ProductImage(product_id=product.id, img_url=g_url))
        
        # Handle Variations
        if product_type == 'variable':
            var_indices = request.form.getlist('var_idx[]')
            for idx in var_indices:
                var_price_raw = request.form.getlist('var_price[]')[var_indices.index(idx)].replace('₹', '').replace(',', '').strip()
                var_price = f"₹{int(var_price_raw):,}" if var_price_raw and var_price_raw.isdigit() else product.price
                
                var_orig_raw = request.form.getlist('var_orig[]')[var_indices.index(idx)].replace('₹', '').replace(',', '').strip()
                var_orig = f"₹{int(var_orig_raw):,}" if var_orig_raw and var_orig_raw.isdigit() else None
                
                var_stock = request.form.getlist('var_stock[]')[var_indices.index(idx)]
                
                var_img_file = request.files.get(f'var_img_{idx}')
                var_img_url = save_image(var_img_file, 'products/variations') if var_img_file else None
                
                variation = ProductVariation(
                    product_id=product.id,
                    price=var_price,
                    orig_price=var_orig,
                    stock_status=var_stock,
                    img_url=var_img_url
                )
                db.session.add(variation)
                db.session.flush()
                
                for a_id in attr_ids:
                    v_val_id = request.form.get(f'var_attr_{idx}_{a_id}')
                    if v_val_id:
                        db.session.add(VariationOption(variation_id=variation.id, attribute_value_id=v_val_id))

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
        price_raw = request.form.get('price', '').replace('Rs.', '').replace('₹', '').replace(',', '').strip()
        orig_raw = request.form.get('orig', '').replace('Rs.', '').replace('₹', '').replace(',', '').strip()
        
        product.price = f"₹{int(float(price_raw)):,}" if price_raw else "₹0"
        product.orig = f"₹{int(float(orig_raw)):,}" if orig_raw else None
        
        category_id = request.form.get('category_id') or None
        product.category_id = category_id
        product.sub_category_id = request.form.get('sub_category_id') or None
        product.brand_id = request.form.get('brand_id') or None
        product.badge = request.form.get('badge')
        product.desc = request.form.get('desc')
        product.product_type = request.form.get('product_type', 'simple')
        product.stock_status = request.form.get('stock_status', 'instock')
        product.is_featured = True if request.form.get('is_featured') == 'on' else False
        product.is_best_seller = True if request.form.get('is_best_seller') == 'on' else False
        product.is_new_arrival = True if request.form.get('is_new_arrival') == 'on' else False
        product.materials = request.form.get('materials')
        product.care = request.form.get('care')
        product.seo_title = request.form.get('seo_title') or None
        product.seo_description = request.form.get('seo_description') or None
        product.focus_keyword = request.form.get('focus_keyword') or None
        product.meta_keywords = request.form.get('meta_keywords') or None
        product.product_tags = request.form.get('product_tags') or None

        # Logging for debug
        print(f"DEBUG: Saving product {id}, Type: {product.product_type}, Stock: {product.stock_status}")
        
        category = Category.query.get(category_id)
        if category:
            product.cat_name = category.name
        
        img_file = request.files.get('img')
        if img_file and img_file.filename:
            # Delete old image if exists
            if product.img: delete_image(product.img)
            product.img = save_image(img_file, 'products')
            
        size_chart_file = request.files.get('size_chart')
        if size_chart_file and size_chart_file.filename:
            if product.size_chart: delete_image(product.size_chart)
            product.size_chart = save_image(size_chart_file, 'size_charts')
        
        # Handle Attributes & Values (Cleanup and Save)
        SelectedAttributeValue.query.filter_by(product_id=product.id).delete()
        ProductAttribute.query.filter_by(product_id=product.id).delete()
        
        attr_ids = request.form.getlist('product_attributes[]')
        for a_id in attr_ids:
            if a_id:
                db.session.add(ProductAttribute(product_id=product.id, attribute_id=a_id))
                # Save selected values for this attribute
                val_ids = request.form.getlist(f'attr_val_{a_id}[]')
                for v_id in val_ids:
                    if v_id:
                        db.session.add(SelectedAttributeValue(
                            product_id=product.id,
                            attribute_id=a_id,
                            attribute_value_id=v_id
                        ))
                
        # Handle Gallery Images
        remove_gallery_ids = request.form.getlist('remove_gallery[]')
        for r_id in remove_gallery_ids:
            img_obj = ProductImage.query.get(r_id)
            if img_obj:
                delete_image(img_obj.img_url)
                db.session.delete(img_obj)
        
        gallery_files = request.files.getlist('gallery[]')
        for g_file in gallery_files:
            if g_file and g_file.filename:
                g_url = save_image(g_file, 'products/gallery')
                if g_url:
                    db.session.add(ProductImage(product_id=product.id, img_url=g_url))
        
        # Handle Variations
        if product.product_type == 'variable':
            # Clean up old variations
            new_existing_imgs = request.form.getlist('var_existing_img[]')
            for old_var in product.variations:
                if old_var.img_url and old_var.img_url not in new_existing_imgs:
                    delete_image(old_var.img_url)
                db.session.delete(old_var)
            db.session.flush()

            var_indices = request.form.getlist('var_idx[]')
            var_prices = request.form.getlist('var_price[]')
            var_origs = request.form.getlist('var_orig[]')
            var_stocks = request.form.getlist('var_stock[]')
            var_existing_imgs = request.form.getlist('var_existing_img[]')

            for i, idx in enumerate(var_indices):
                # Robust price parsing
                raw_p = var_prices[i].replace('₹', '').replace(',', '').strip() if i < len(var_prices) else ""
                try:
                    var_price = f"₹{int(float(raw_p)):,}" if raw_p else product.price
                except (ValueError, TypeError):
                    var_price = product.price
                
                raw_o = var_origs[i].replace('₹', '').replace(',', '').strip() if i < len(var_origs) else ""
                try:
                    var_orig = f"₹{int(float(raw_o)):,}" if raw_o else None
                except (ValueError, TypeError):
                    var_orig = None
                
                var_stock = var_stocks[i] if i < len(var_stocks) else 'instock'
                existing_img = var_existing_imgs[i] if i < len(var_existing_imgs) else ""
                var_img_file = request.files.get(f'var_img_{idx}')
                var_img_url = save_image(var_img_file, 'products/variations') if var_img_file else existing_img
                
                variation = ProductVariation(
                    product_id=product.id,
                    price=var_price,
                    orig_price=var_orig,
                    stock_status=var_stock,
                    img_url=var_img_url
                )
                db.session.add(variation)
                db.session.flush()
                
                for a_id in attr_ids:
                    v_val_id = request.form.get(f'var_attr_{idx}_{a_id}')
                    if v_val_id:
                        db.session.add(VariationOption(variation_id=variation.id, attribute_value_id=v_val_id))
        else:
            # Cleanup variations if switched to simple
            for old_var in product.variations:
                if old_var.img_url: delete_image(old_var.img_url)
                db.session.delete(old_var)

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
        # Check if the product has been ordered to prevent ForeignKeyViolation
        order_items_count = OrderItem.query.filter_by(product_id=id).count()
        if order_items_count > 0:
            flash(f"Cannot delete '{product.name}' because it has been purchased in {order_items_count} past customer order(s). We recommend changing its stock status to 'Out of Stock' to hide or disable it instead.", 'error')
            return redirect(url_for('admin.products'))

        # Delete main image
        delete_image(product.img)
        
        # Delete gallery images
        for img_obj in product.images:
            delete_image(img_obj.img_url)
            
        # Delete variation images
        for var in product.variations:
            if var.img_url:
                delete_image(var.img_url)
                
        # Delete any associated reviews
        Review.query.filter_by(product_id=id).delete()
        
        try:
            db.session.delete(product)
            db.session.commit()
            flash('Product deleted successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting product {id}: {e}")
            flash('An error occurred while deleting the product. The transaction has been rolled back.', 'error')
            
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
        current_app.invalidate_category_cache()
        flash('Category added successfully!', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html')

@admin_bp.route('/admin/category/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_category(id):
    category = Category.query.get_or_404(id)
    if request.method == 'POST':
        category.name = request.form.get('name')
        img_file = request.files.get('img')
        if img_file and img_file.filename:
            delete_image(category.img)
            category.img = save_image(img_file, 'categories')
            
        db.session.commit()
        current_app.invalidate_category_cache()
        flash('Category updated successfully!', 'success')
        return redirect(url_for('admin.categories'))
    return render_template('admin/category_form.html', category=category)

@admin_bp.route('/admin/category/delete/<int:id>', methods=['POST'])
@admin_required
def delete_category(id):
    category = Category.query.get(id)
    if category:
        delete_image(category.img)
        db.session.delete(category)
        db.session.commit()
        current_app.invalidate_category_cache()
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
        current_app.invalidate_category_cache()
        flash('SubCategory added successfully!', 'success')
        return redirect(url_for('admin.categories'))
    categories = Category.query.all()
    selected_category_id = request.args.get('category_id', type=int)
    return render_template('admin/subcategory_form.html', categories=categories, selected_category_id=selected_category_id)

@admin_bp.route('/admin/subcategory/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def edit_subcategory(id):
    subcategory = SubCategory.query.get_or_404(id)
    if request.method == 'POST':
        subcategory.name = request.form.get('name')
        subcategory.category_id = request.form.get('category_id')
        db.session.commit()
        current_app.invalidate_category_cache()
        flash('SubCategory updated successfully!', 'success')
        return redirect(url_for('admin.categories'))
    categories = Category.query.all()
    return render_template('admin/subcategory_form.html', subcategory=subcategory, categories=categories)

@admin_bp.route('/admin/subcategory/delete/<int:id>', methods=['POST'])
@admin_required
def delete_subcategory(id):
    subcategory = SubCategory.query.get(id)
    if subcategory:
        db.session.delete(subcategory)
        db.session.commit()
        current_app.invalidate_category_cache()
        flash('SubCategory deleted!', 'success')
    return redirect(url_for('admin.categories'))

# --- CUSTOMER ROUTES ---

@admin_bp.route('/admin/customers')
@admin_required
def customers():
    all_users = User.query.order_by(User.id.asc()).all()
    return render_template('admin/customers.html', users=all_users)

@admin_bp.route('/admin/customers/delete/<int:id>', methods=['POST'])
@admin_required
def delete_customer(id):
    user = User.query.get_or_404(id)
    if user.is_admin:
        flash('Cannot delete an admin account.', 'error')
        return redirect(url_for('admin.customers'))
        
    # Delete associated orders & order items to prevent FK constraints
    for order in user.orders:
        OrderItem.query.filter_by(order_id=order.id).delete()
        db.session.delete(order)
        
    db.session.delete(user)
    db.session.commit()
    flash('Customer deleted successfully!', 'success')
    return redirect(url_for('admin.customers'))

# --- ORDER ROUTES ---

@admin_bp.route('/admin/orders')
@admin_required
def orders():
    all_orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin/orders.html', orders=all_orders)

@admin_bp.route('/admin/order/<int:order_id>')
@admin_required
def get_order_details(order_id):
    order = Order.query.get_or_404(order_id)
    user = order.user
    
    city_val = ''
    state_val = ''
    if user.city:
        if ',' in user.city:
            parts = user.city.split(',')
            city_val = parts[0].strip()
            state_val = parts[1].strip()
        else:
            city_val = user.city
            
    items = []
    for item in order.items:
        # Resolve the best image for this item
        img = item.product.img
        if item.variation and item.variation.img_url:
            img = item.variation.img_url
        elif item.variation:
            from models import ProductImage
            color_opt = next(
                (opt for opt in item.variation.options
                 if 'color' in opt.attribute_value.attribute.name.lower()),
                None
            )
            if color_opt:
                color_img = next(
                    (pi.img_url for pi in item.product.images
                     if pi.attribute_value_id == color_opt.attribute_value_id),
                    None
                )
                if color_img:
                    img = color_img

        # Build full attribute list from the saved label or live variation options
        attributes = []
        if item.variation_label:
            for part in item.variation_label.split(', '):
                if ':' in part:
                    k, v = part.split(':', 1)
                    attributes.append({'name': k.strip(), 'value': v.strip()})
        elif item.variation:
            for opt in item.variation.options:
                attributes.append({
                    'name': opt.attribute_value.attribute.name,
                    'value': opt.attribute_value.value
                })

        items.append({
            'name': item.product.name,
            'img': img,
            'quantity': item.quantity,
            'price_at_time': item.price_at_time,
            'attributes': attributes,
        })
        
    return jsonify({
        'success': True,
        'order_number': order.order_number,
        'date': order.date.strftime('%d %b %Y, %H:%M'),
        'total': order.total_amount,
        'status': order.status,
        'customer_name': user.username or 'N/A',
        'customer_email': user.email,
        'customer_phone': user.phone or 'N/A',
        'address': user.address or 'N/A',
        'city': city_val,
        'state': state_val,
        'zipcode': user.zipcode or 'N/A',
        'items': items
    })

@admin_bp.route('/admin/order/update-status/<int:order_id>', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    if new_status:
        order.status = new_status
        db.session.commit()
        flash(f'Order {order.order_number} status updated to {new_status}!', 'success')
    return redirect(url_for('admin.orders'))

@admin_bp.route('/admin/order/delete/<int:order_id>', methods=['POST'])
@admin_required
def delete_order(order_id):
    order = Order.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    flash(f'Order {order.order_number} deleted successfully!', 'success')
    return redirect(url_for('admin.orders'))

# --- ATTRIBUTE ROUTES ---

@admin_bp.route('/admin/attributes')
@admin_required
def admin_attributes():
    attributes = Attribute.query.all()
    attr_data = []
    for attr in attributes:
        # In Dadson, variations use stock_status instead of stock_count
        # We can count 'instock' variations or just sum up if we add stock_count
        # For now, let's count 'instock' variations that use these values
        total_instock = 0
        value_ids = [v.id for v in attr.values]
        if value_ids:
            total_instock = ProductVariation.query.join(VariationOption)\
                .filter(VariationOption.attribute_value_id.in_(value_ids)).count()
        
        attr_data.append({
            'attr': attr,
            'total_stock': total_instock,
            'values_str': ", ".join([v.value for v in attr.values]),
            'value_count': len(attr.values)
        })
    return render_template('admin/attributes.html', attributes=attr_data)

@admin_bp.route('/admin/attribute/new', methods=['GET', 'POST'])
@admin_required
def admin_attribute_new():
    if request.method == 'POST':
        name = request.form.get('name')
        slug = request.form.get('slug') or name.lower().replace(' ', '-')
        attr_type = request.form.get('type', 'select')
        
        img_file = request.files.get('img')
        image_url = save_image(img_file, 'attributes') if img_file else None
        
        is_featured = True if request.form.get('is_featured') == 'on' else False
        
        # Check if already exists
        existing = Attribute.query.filter_by(slug=slug).first()
        if existing:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Attribute already exists'}), 400
            flash('Attribute already exists!', 'error')
            return redirect(url_for('admin.admin_attributes'))

        attribute = Attribute(name=name, slug=slug, type=attr_type, image_url=image_url, is_featured=is_featured)
        db.session.add(attribute)
        db.session.flush()
        
        # Handle initial values
        values_str = request.form.get('values')
        if values_str:
            vals = [v.strip() for v in values_str.split(',') if v.strip()]
            for val in vals:
                db.session.add(AttributeValue(attribute_id=attribute.id, value=val))
        
        db.session.commit()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'id': attribute.id, 'name': attribute.name})
            
        flash('Attribute added successfully!', 'success')
        return redirect(url_for('admin.admin_attributes'))
    return render_template('admin/attribute_form.html')

@admin_bp.route('/admin/attribute/edit/<int:attr_id>', methods=['GET', 'POST'])
@admin_required
def admin_attribute_edit(attr_id):
    attribute = Attribute.query.get_or_404(attr_id)
    if request.method == 'POST':
        attribute.name = request.form.get('name')
        attribute.slug = request.form.get('slug') or attribute.name.lower().replace(' ', '-')
        attribute.type = request.form.get('type', 'select')
        
        img_file = request.files.get('img')
        if img_file:
            if attribute.image_url:
                delete_image(attribute.image_url)
            attribute.image_url = save_image(img_file, 'attributes')
            
        attribute.is_featured = True if request.form.get('is_featured') == 'on' else False
        
        # Handle values sync
        values_str = request.form.get('values')
        if values_str:
            current_vals = [v.value for v in attribute.values]
            new_vals = [v.strip() for v in values_str.split(',') if v.strip()]
            for val in new_vals:
                if val not in current_vals:
                    db.session.add(AttributeValue(attribute_id=attribute.id, value=val))
        
        db.session.commit()
        flash('Attribute updated successfully!', 'success')
        return redirect(url_for('admin.admin_attributes'))
        
    vals_str = ", ".join([v.value for v in attribute.values])
    return render_template('admin/attribute_form.html', attribute=attribute, vals_str=vals_str)

@admin_bp.route('/admin/attribute/delete/<int:attr_id>', methods=['POST'])
@admin_required
def admin_attribute_delete(attr_id):
    attribute = Attribute.query.get_or_404(attr_id)
    db.session.delete(attribute)
    db.session.commit()
    flash('Attribute and all its values deleted!', 'success')
    return redirect(url_for('admin.admin_attributes'))

@admin_bp.route('/admin/attribute/<int:attr_id>/value/quick-add', methods=['POST'])
@admin_required
def admin_attribute_value_quick_add(attr_id):
    value_content = request.form.get('value')
    if not value_content:
        return jsonify({'success': False, 'error': 'Value is required'}), 400
        
    # Check if exists
    existing = AttributeValue.query.filter_by(attribute_id=attr_id, value=value_content).first()
    if existing:
        return jsonify({'success': True, 'id': existing.id, 'existed': True, 'image_url': existing.image_url})
        
    img_file = request.files.get('img')
    image_url = save_image(img_file, 'attributes/values') if img_file else None
    
    new_val = AttributeValue(attribute_id=attr_id, value=value_content, image_url=image_url)
    db.session.add(new_val)
    db.session.commit()
    return jsonify({'success': True, 'id': new_val.id, 'existed': False, 'image_url': image_url})

@admin_bp.route('/admin/attribute-value/<int:id>/edit', methods=['POST'])
@admin_required
def admin_attribute_value_edit(id):
    val = AttributeValue.query.get(id)
    if not val:
        return jsonify({'success': False, 'error': 'Value not found'}), 404
        
    new_value = request.form.get('value')
    if new_value:
        val.value = new_value
        
    img_file = request.files.get('img')
    if img_file:
        if val.image_url:
            delete_image(val.image_url)
        val.image_url = save_image(img_file, 'attributes/values')
        
    db.session.commit()
    return jsonify({'success': True, 'image_url': val.image_url})

@admin_bp.route('/admin/attribute-value/<int:id>/delete', methods=['POST'])
@admin_required
def admin_attribute_value_delete(id):
    val = AttributeValue.query.get(id)
    if val:
        # Check if used in any variation
        used = VariationOption.query.filter_by(attribute_value_id=id).first()
        if used:
            return jsonify({'success': False, 'error': 'This value is currently used in products. Remove it from variations first.'}), 400
            
        db.session.delete(val)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Value not found'}), 400

@admin_bp.route('/admin/attribute/<int:attr_id>/values', methods=['GET', 'POST'])
@admin_required
def admin_attribute_values(attr_id):
    attribute = Attribute.query.get(attr_id)
    if request.method == 'POST':
        value_content = request.form.get('value')
        
        img_file = request.files.get('img')
        image_url = save_image(img_file, 'attributes/values') if img_file else None
        
        new_val = AttributeValue(attribute_id=attr_id, value=value_content, image_url=image_url)
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
        code = request.form.get('code').upper().strip()
        type = request.form.get('type')  # 'flat' or 'percentage'
        discount = float(request.form.get('discount', 0))
        threshold = float(request.form.get('threshold', 0))
        usage_limit = int(request.form.get('usage_limit', 1))
        
        expiry_date_str = request.form.get('expiry_date')
        expiry_date = None
        if expiry_date_str:
            try:
                expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d')
            except ValueError:
                pass
                
        # checkbox is present in form keys if checked
        is_active = 'is_active' in request.form or request.form.get('is_active') == 'on'

        coupon = Coupon(
            code=code,
            type=type,
            discount=discount,
            threshold=threshold,
            usage_limit=usage_limit,
            expiry_date=expiry_date,
            is_active=is_active
        )
        db.session.add(coupon)
        db.session.commit()
        flash('Coupon created successfully!', 'success')
        return redirect(url_for('admin.coupons'))
    return render_template('admin/coupon_form.html')

@admin_bp.route('/admin/coupon/delete/<int:id>', methods=['POST'])
@admin_required
def delete_coupon(id):
    coupon = Coupon.query.get(id)
    if coupon:
        db.session.delete(coupon)
        db.session.commit()
        flash('Coupon deleted successfully!', 'success')
    return redirect(url_for('admin.coupons'))

# --- SETTINGS ---

@admin_bp.route('/admin/settings', methods=['GET', 'POST'])
@admin_required
def settings():
    if request.method == 'POST':
        expected_keys = [
            'shipping_charges',
            'free_shipping_above',
            'contact_email',
            'payment_method_cod',
            'payment_method_razorpay',
            'razorpay_key_id',
            'razorpay_key_secret',
            'ga_measurement_id',
        ]
        for key in expected_keys:
            value = request.form.get(key, '') # Omitted checkboxes default to empty string
            config = AppConfig.query.filter_by(key=key).first()
            if config: config.value = value
            else: db.session.add(AppConfig(key=key, value=value))
            
        # Reconstruct and synchronize legacy payment_methods comma-separated string
        enabled_methods = []
        if request.form.get('payment_method_cod') == 'on':
            enabled_methods.append('COD')
        if request.form.get('payment_method_razorpay') == 'on':
            enabled_methods.append('Razorpay')
            
        legacy_pm = ", ".join(enabled_methods)
        pm_config = AppConfig.query.filter_by(key='payment_methods').first()
        if pm_config: pm_config.value = legacy_pm
        else: db.session.add(AppConfig(key='payment_methods', value=legacy_pm))
        
        db.session.commit()
        from app import invalidate_config_cache
        invalidate_config_cache()
        flash('Settings updated!', 'success')
        return redirect(url_for('admin.settings'))
    configs = {c.key: c.value for c in AppConfig.query.all()}
    return render_template('admin/settings.html', configs=configs)

@admin_bp.route('/admin/subscribers')
@admin_required
def subscribers():
    from models import Subscriber
    all_subscribers = Subscriber.query.order_by(Subscriber.date.desc()).all()
    return render_template('admin/subscribers.html', subscribers=all_subscribers)

@admin_bp.route('/admin/subscriber/delete/<int:id>', methods=['POST'])
@admin_required
def delete_subscriber(id):
    from models import Subscriber
    subscriber = Subscriber.query.get(id)
    if subscriber:
        db.session.delete(subscriber)
        db.session.commit()
        flash('Subscriber removed!', 'success')
    return redirect(url_for('admin.subscribers'))
