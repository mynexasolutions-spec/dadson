import os
import hmac
import hashlib
import random
import string
import requests
from datetime import datetime
from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for
from models import db, User, Order, OrderItem, Product, ProductVariation, AppConfig, Coupon

checkout_bp = Blueprint('checkout', __name__)

def get_razorpay_keys():
    key_id_cfg = AppConfig.query.filter_by(key='razorpay_key_id').first()
    key_secret_cfg = AppConfig.query.filter_by(key='razorpay_key_secret').first()
    
    key_id = key_id_cfg.value.strip() if (key_id_cfg and key_id_cfg.value) else os.getenv('RAZORPAY_KEY_ID', 'rzp_test_zHk1B8i6N7m4qF')
    key_secret = key_secret_cfg.value.strip() if (key_secret_cfg and key_secret_cfg.value) else os.getenv('RAZORPAY_KEY_SECRET', 'k1B8i6N7m4qFzHk1B8i6N7m4')
    
    return key_id, key_secret

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

def get_shipping_config():
    shipping_charges = 0
    free_shipping_above = 0
    try:
        cfg_charges = AppConfig.query.filter_by(key='shipping_charges').first()
        if cfg_charges and cfg_charges.value:
            shipping_charges = int(cfg_charges.value.replace('Rs.', '').replace('₹', '').replace(',', '').strip())
    except Exception:
        pass
        
    try:
        cfg_free = AppConfig.query.filter_by(key='free_shipping_above').first()
        if cfg_free and cfg_free.value:
            free_shipping_above = int(cfg_free.value.replace('Rs.', '').replace('₹', '').replace(',', '').strip())
    except Exception:
        pass
        
    return shipping_charges, free_shipping_above

@checkout_bp.route('/checkout')
def checkout():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('auth.login', next='/checkout'))
        
    user = User.query.get(user_id)
    cart = session.get('cart', {})
    if not cart:
        return redirect(url_for('cart.view_cart'))
        
    cart_items = []
    subtotal = 0
    
    for product_id, quantity in list(cart.items()):
        product = None
        variation = None
        display_price = 0
        variant_labels = []

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
                var_img = variation.img_url
                if not var_img:
                    color_opt = next((opt for opt in variation.options if 'color' in opt.attribute_value.attribute.name.lower()), None)
                    if color_opt:
                        for p_img in product.images:
                            if p_img.attribute_value_id == color_opt.attribute_value_id:
                                var_img = p_img.img_url
                                break
            
            cart_items.append({
                'id': product_id,
                'product': product,
                'variation': variation,
                'quantity': quantity,
                'item_total': f"₹{item_total:,}",
                'display_price': f"₹{display_price:,}",
                'var_img': var_img or product.img,
                'variant_labels': variant_labels
            })
            
    if not cart_items:
        return redirect(url_for('cart.view_cart'))
        
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
    razorpay_key_id, _ = get_razorpay_keys()
    
    cod_cfg = AppConfig.query.filter_by(key='payment_method_cod').first()
    razorpay_cfg = AppConfig.query.filter_by(key='payment_method_razorpay').first()
    is_cod_enabled = (cod_cfg.value == 'on') if cod_cfg else True
    is_razorpay_enabled = (razorpay_cfg.value == 'on') if razorpay_cfg else True
        
    return render_template('checkout.html', 
                           cart_items=cart_items, 
                           subtotal=subtotal, 
                           subtotal_str=f"₹{subtotal:,}", 
                           shipping_charge=actual_shipping,
                           shipping_charge_str="FREE" if actual_shipping == 0 else f"₹{actual_shipping:,}",
                           discount_amount=discount_amount,
                           discount_amount_str=f"-₹{discount_amount:,}" if discount_amount > 0 else None,
                           coupon_code=coupon_code,
                           total=total,
                           total_str=f"₹{total:,}",
                           user=user,
                           razorpay_key_id=razorpay_key_id,
                           is_cod_enabled=is_cod_enabled,
                           is_razorpay_enabled=is_razorpay_enabled)

@checkout_bp.route('/checkout/create-order', methods=['POST'])
def create_order():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False, 'message': 'Please login first.'}), 401
        
    user = User.query.get(user_id)
    cart = session.get('cart', {})
    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty.'}), 400
        
    data = request.get_json() or request.form
    name = data.get('name')
    phone = data.get('phone')
    address = data.get('address')
    city = data.get('city')
    state = data.get('state')
    zipcode = data.get('zipcode')
    payment_method = data.get('payment_method', 'online')
    
    if not all([name, phone, address, city, state, zipcode]):
        return jsonify({'success': False, 'message': 'All fields are required.'}), 400
        
    # Update user details - Combine City and State into user.city
    user.username = name
    user.phone = phone
    user.address = address
    user.city = f"{city}, {state}" if state else city
    user.zipcode = zipcode
    db.session.commit()
    
    # Calculate subtotal
    subtotal = 0
    order_items_data = []
    
    for product_id, quantity in cart.items():
        price = 0
        if product_id.startswith('var:'):
            var_id = int(product_id.split(':')[1])
            var = ProductVariation.query.get(var_id)
            if var:
                price = safe_price(var.price)
                label_parts = [f"{opt.attribute_value.attribute.name}: {opt.attribute_value.value}" for opt in var.options]
                order_items_data.append((product_id, quantity, var.price, var_id, ', '.join(label_parts)))
        else:
            base_id = product_id.split('_')[0]
            p = Product.query.get(base_id)
            if p:
                price = safe_price(p.price)
                order_items_data.append((product_id, quantity, p.price, None, None))

        subtotal += price * quantity
        
    if subtotal == 0:
        return jsonify({'success': False, 'message': 'Invalid cart items.'}), 400
        
    shipping_charge, free_above = get_shipping_config()
    actual_shipping = 0 if (free_above and subtotal >= free_above) else shipping_charge

    # Coupon Validation & Calculation during order creation
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
                    usage_count = Order.query.filter_by(user_id=user.id, coupon_code=coupon.code).count()
                    if usage_count < coupon.usage_limit:
                        if coupon.type == 'percentage':
                            discount_amount = (subtotal * coupon.discount) / 100.0
                        else:
                            discount_amount = coupon.discount
                        discount_amount = min(discount_amount, subtotal)
        
        # If no longer eligible, remove
        if discount_amount == 0:
            coupon_code = None

    total = subtotal - discount_amount + actual_shipping
        
    # Generate unique order number (strictly under 20 characters for database VARCHAR(20) limit)
    timestamp = datetime.utcnow().strftime('%y%m%d%H%M%S') # 12 characters
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4)) # 4 characters
    order_num = f"D{timestamp}{random_str}" # 17 characters total!
    
    # Create database Order
    initial_status = 'Processing (COD)' if payment_method == 'cod' else 'Pending'
    order = Order(
        order_number=order_num,
        user_id=user.id,
        total_amount=f"₹{total:,}",
        status=initial_status,
        coupon_code=coupon_code,
        discount_amount=discount_amount
    )
    db.session.add(order)
    db.session.flush() # Populate order ID
    
    # Create OrderItems
    for pid, qty, price_str, var_id, var_label in order_items_data:
        base_pid = pid.split('_')[0]
        if pid.startswith('var:'):
            var = ProductVariation.query.get(var_id)
            if var:
                base_pid = var.product_id

        item = OrderItem(
            order_id=order.id,
            product_id=base_pid,
            quantity=qty,
            price_at_time=price_str,
            variation_id=var_id,
            variation_label=var_label,
        )
        db.session.add(item)
        
    db.session.commit()
    
    # If payment method is Cash on Delivery (COD)
    if payment_method == 'cod':
        # Clear cart and coupon immediately
        session.pop('cart', None)
        session.pop('coupon_code', None)
        session.modified = True
        return jsonify({
            'success': True,
            'cod': True,
            'order_number': order_num
        })
        
    # Create Razorpay Order for Online Payment method
    amount_paise = int(total * 100)
    razorpay_order_id = ""
    key_id, key_secret = get_razorpay_keys()
    
    try:
        res = requests.post(
            'https://api.razorpay.com/v1/orders',
            auth=(key_id, key_secret),
            json={
                'amount': amount_paise,
                'currency': 'INR',
                'receipt': order_num,
                'payment_capture': 1  # Enable dynamic auto capture
            },
            timeout=10
        )
        if res.status_code == 200:
            res_data = res.json()
            razorpay_order_id = res_data.get('id', '')
    except Exception as e:
        print("Razorpay API Error:", e)
        
    # Fallback to local mockup order id if Razorpay is offline or invalid keys
    if not razorpay_order_id:
        razorpay_order_id = f"order_mock_{random_str.lower()}"
        
    return jsonify({
        'success': True,
        'cod': False,
        'order_number': order_num,
        'razorpay_order_id': razorpay_order_id,
        'amount': amount_paise,
        'currency': 'INR',
        'key_id': key_id,
        'customer_name': name,
        'customer_email': user.email,
        'customer_phone': phone
    })

@checkout_bp.route('/checkout/verify-payment', methods=['POST'])
def verify_payment():
    data = request.get_json() or request.form
    order_num = data.get('order_number')
    payment_id = data.get('razorpay_payment_id')
    razorpay_order_id = data.get('razorpay_order_id')
    signature = data.get('razorpay_signature')
    
    order = Order.query.filter_by(order_number=order_num).first()
    if not order:
        return jsonify({'success': False, 'message': 'Order not found.'}), 404
        
    # Signature verification
    verified = False
    _, key_secret = get_razorpay_keys()
    if razorpay_order_id and payment_id and signature:
        if razorpay_order_id.startswith('order_mock_'):
            # In mock test mode, allow it automatically
            verified = True
        else:
            try:
                msg = f"{razorpay_order_id}|{payment_id}"
                generated_sig = hmac.new(
                    key=key_secret.encode('utf-8'),
                    msg=msg.encode('utf-8'),
                    digestmod=hashlib.sha256
                ).hexdigest()
                if hmac.compare_digest(generated_sig, signature):
                    verified = True
            except Exception as e:
                print("Signature Verification Error:", e)
                
    if verified:
        order.status = 'Paid'
        db.session.commit()
        # Clear cart and coupon
        session.pop('cart', None)
        session.pop('coupon_code', None)
        session.modified = True
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Payment verification failed.'}), 400

@checkout_bp.route('/order-success/<order_number>')
def order_success(order_number):
    order = Order.query.filter_by(order_number=order_number).first()
    if not order:
        return redirect(url_for('public.home'))
    return render_template('order_success.html', order=order)
