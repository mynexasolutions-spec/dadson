from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for
from models import Product, Coupon, Order
from datetime import datetime

cart_bp = Blueprint('cart', __name__)

import re

def safe_price(price_str):
    """Safely parse price string by removing all non-numeric characters."""
    if not price_str:
        return 0
    digits = re.sub(r'[^\d]', '', str(price_str))
    try:
        return int(digits) if digits else 0
    except ValueError:
        return 0

@cart_bp.route('/cart')
def view_cart():
    from models import ProductVariation
    cart = session.get('cart', {})
    cart_items = []
    subtotal = 0
    for product_id, quantity in list(cart.items()):
        product = None
        variation = None
        display_price = 0
        variant_labels = [] # To store list of {name: '', value: ''}

        if product_id.startswith('var:'):
            try:
                var_id = int(product_id.split(':')[1])
                variation = ProductVariation.query.get(var_id)
                if variation:
                    product = variation.product
                    display_price = safe_price(variation.price)
            except (ValueError, IndexError):
                pass
            
            if variation:
                for opt in variation.options:
                    variant_labels.append({
                        'name': opt.attribute_value.attribute.name,
                        'value': opt.attribute_value.value
                    })
        else:
            try:
                base_id = product_id.split('_')[0]
                product = Product.query.get(base_id)
                if product:
                    if product.product_type == 'variable' and product.variations:
                        display_price = safe_price(product.variations[0].price)
                    else:
                        display_price = safe_price(product.price)
                    if '_' in product_id:
                        parts = product_id.split('_')
                        if len(parts) >= 2 and parts[1] != 'NA': variant_labels.append({'name': 'Size', 'value': parts[1]})
                        if len(parts) >= 3 and parts[2] != 'NA': variant_labels.append({'name': 'Color', 'value': parts[2]})
            except (IndexError, ValueError):
                pass

        if product:
            item_total = display_price * quantity
            subtotal += item_total
            var_img = None
            if variation:
                # Use variation specific image if it exists
                var_img = variation.img_url
                # Fallback to color matched gallery image if variation image is empty
                if not var_img:
                    color_opt = next((opt for opt in variation.options if 'color' in opt.attribute_value.attribute.name.lower()), None)
                    if color_opt:
                        for p_img in product.images:
                            if p_img.attribute_value_id == color_opt.attribute_value_id:
                                var_img = p_img.img_url
                                break
            if not var_img:
                var_img = product.img

            orig_price = safe_price(variation.orig_price) if variation and variation.orig_price else safe_price(product.orig)
            
            cart_items.append({
                'id': product_id,
                'product': product,
                'variation': variation,
                'quantity': quantity,
                'item_total': f"₹{item_total:,}",
                'display_price': f"₹{display_price:,}",
                'orig_price': f"₹{orig_price:,}" if orig_price else None,
                'var_img': var_img,
                'variant_labels': variant_labels
            })
        else:
            # Cleanup: Remove "ghost" items that don't exist in DB
            cart.pop(product_id, None)
            session['cart'] = cart
            session.modified = True

    from routes.checkout import get_shipping_config
    shipping_charge, free_above = get_shipping_config()
    actual_shipping = 0 if (free_above and subtotal >= free_above) else shipping_charge

    # Coupon Validation & Calculation
    discount_amount = 0
    coupon_code = session.get('coupon_code')
    coupon = None
    if coupon_code:
        coupon = Coupon.query.filter_by(code=coupon_code).first()
        if coupon and coupon.is_active:
            # Check expiry
            if not (coupon.expiry_date and datetime.utcnow() > coupon.expiry_date):
                # Check threshold
                if subtotal >= coupon.threshold:
                    # Check usage limit
                    user_id = session.get('user_id')
                    eligible = True
                    if user_id:
                        usage_count = Order.query.filter_by(user_id=user_id, coupon_code=coupon.code).count()
                        if usage_count >= coupon.usage_limit:
                            eligible = False
                    
                    if eligible:
                        if coupon.type == 'percentage':
                            discount_amount = (subtotal * coupon.discount) / 100.0
                        else:
                            discount_amount = coupon.discount
                        discount_amount = min(discount_amount, subtotal)
        
        # If no longer eligible, remove from session
        if discount_amount == 0:
            session.pop('coupon_code', None)
            session.modified = True
            coupon_code = None

    total = subtotal - discount_amount + actual_shipping

    return render_template('cart.html', 
                           cart_items=cart_items, 
                           subtotal=f"₹{subtotal:,}",
                           shipping_charge_str="FREE" if actual_shipping == 0 else f"₹{actual_shipping:,}",
                           discount_amount_str=f"-₹{discount_amount:,}" if discount_amount > 0 else None,
                           coupon_code=coupon_code,
                           total_str=f"₹{total:,}")

@cart_bp.route('/apply-coupon', methods=['POST'])
def apply_coupon():
    code = request.form.get('code', '').upper().strip()
    if not code:
        return jsonify({'success': False, 'message': 'Please enter a coupon code.'})
        
    coupon = Coupon.query.filter_by(code=code).first()
    if not coupon:
        return jsonify({'success': False, 'message': 'Invalid coupon code.'})
        
    if not coupon.is_active:
        return jsonify({'success': False, 'message': 'This coupon is no longer active.'})
        
    if coupon.expiry_date and datetime.utcnow() > coupon.expiry_date:
        return jsonify({'success': False, 'message': 'This coupon has expired.'})
        
    cart = session.get('cart', {})
    subtotal = 0
    from models import ProductVariation
    for product_id, quantity in cart.items():
        price = 0
        if product_id.startswith('var:'):
            var_id = int(product_id.split(':')[1])
            var = ProductVariation.query.get(var_id)
            if var:
                price = safe_price(var.price)
        else:
            base_id = product_id.split('_')[0]
            p = Product.query.get(base_id)
            if p:
                price = safe_price(p.price)
        subtotal += price * quantity
        
    if subtotal == 0:
        return jsonify({'success': False, 'message': 'Your bag is empty.'})
        
    if subtotal < coupon.threshold:
        return jsonify({'success': False, 'message': f'Minimum order value of ₹{coupon.threshold:.0f} is required for this coupon.'})
        
    user_id = session.get('user_id')
    if user_id:
        usage_count = Order.query.filter_by(user_id=user_id, coupon_code=coupon.code).count()
        if usage_count >= coupon.usage_limit:
            return jsonify({'success': False, 'message': f'You have reached the maximum usage limit ({coupon.usage_limit}) for this coupon.'})
            
    session['coupon_code'] = coupon.code
    session.modified = True
    
    if coupon.type == 'percentage':
        discount_amount = (subtotal * coupon.discount) / 100.0
    else:
        discount_amount = coupon.discount
        
    discount_amount = min(discount_amount, subtotal)
    
    return jsonify({
        'success': True,
        'message': f'Coupon "{coupon.code}" applied!',
        'discount_amount': discount_amount,
        'discount_str': f"-₹{discount_amount:,.2f}"
    })

@cart_bp.route('/remove-coupon', methods=['POST'])
def remove_coupon():
    session.pop('coupon_code', None)
    session.modified = True
    return jsonify({'success': True, 'message': 'Coupon removed successfully.'})

@cart_bp.route('/add-to-cart/<id>', methods=['POST'])
def add_to_cart(id):
    if id.startswith('var:'):
        cart_key = id
    else:
        variation_id = request.form.get('variation_id')
        if variation_id:
            cart_key = f"var:{variation_id}"
        else:
            # Check if base product is variable and needs selection
            product = Product.query.get(id)
            if product and product.product_type == 'variable':
                from flask import url_for
                target_url = url_for('public.product_detail', id=id)
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return jsonify({
                        'success': False,
                        'redirect': target_url,
                        'message': 'Please select your variation.'
                    })
                return redirect(target_url)
                
            size = request.form.get('size')
            color = request.form.get('color')
            cart_key = id
            if size or color:
                cart_key = f"{id}_{size or 'NA'}_{color or 'NA'}"
        
    cart = session.get('cart', {})
    cart[cart_key] = cart.get(cart_key, 0) + 1
    session['cart'] = cart
    session.modified = True
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'cart_count': sum(cart.values())})
    return redirect(request.referrer or url_for('public.home'))

@cart_bp.route('/update-cart/<id>', methods=['POST'])
def update_cart(id):
    if request.is_json:
        data = request.get_json()
        quantity = int(data.get('quantity', 1))
    else:
        quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', {})
    if quantity > 0:
        cart[id] = quantity
    else:
        cart.pop(id, None)
    session['cart'] = cart
    session.modified = True
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        from models import ProductVariation
        display_price = 0
        if id.startswith('var:'):
            try:
                var_id = int(id.split(':')[1])
                var = ProductVariation.query.get(var_id)
                if var: display_price = safe_price(var.price)
            except (ValueError, IndexError):
                pass
        else:
            base_id = id.split('_')[0]
            product = Product.query.get(base_id)
            if product: display_price = safe_price(product.price)

        item_total = display_price * quantity
        total = 0
        for pid, qty in cart.items():
            if pid.startswith('var:'):
                try:
                    v_id = int(pid.split(':')[1])
                    v = ProductVariation.query.get(v_id)
                    if v: total += safe_price(v.price) * qty
                except (ValueError, IndexError):
                    pass
            else:
                base_pid = pid.split('_')[0]
                p = Product.query.get(base_pid)
                if p: total += safe_price(p.price) * qty

        return jsonify({
            'success': True, 
            'cart_count': sum(cart.values()),
            'item_total': f"Rs. {item_total:,}",
            'subtotal': f"Rs. {total:,}"
        })
    return redirect(url_for('cart.view_cart'))

@cart_bp.route('/remove-from-cart/<id>')
def remove_from_cart(id):
    cart = session.get('cart', {})
    cart.pop(id, None)
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('cart.view_cart'))
