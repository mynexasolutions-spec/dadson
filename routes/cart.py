from flask import Blueprint, render_template, session, request, jsonify, redirect, url_for
from models import Product

cart_bp = Blueprint('cart', __name__)

def safe_price(price_str):
    """Safely parse price string like 'Rs. 1,299' → 1299. Returns 0 on failure."""
    try:
        return int(str(price_str).replace('Rs.', '').replace(',', '').strip())
    except (ValueError, AttributeError):
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
    return render_template('cart.html', cart_items=cart_items, subtotal=f"₹{subtotal:,}")

@cart_bp.route('/add-to-cart/<id>', methods=['POST'])
def add_to_cart(id):
    if id.startswith('var:'):
        cart_key = id
    else:
        variation_id = request.form.get('variation_id')
        if variation_id:
            cart_key = f"var:{variation_id}"
        else:
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
