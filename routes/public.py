from flask import Blueprint, render_template, request, abort, session, jsonify
from models import db, Category, Product, SubCategory, Review, Subscriber

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def home():
    categories = Category.query.all()

    # Load only the products we actually need using targeted queries
    # — avoids pulling every product and filtering in Python
    all_products = Product.query.options(
        db.joinedload(Product.variations)
    ).all()

    # Expand products for display (showing each color variation)
    expanded_products = []
    for p in all_products:
        if p.product_type == 'variable' and p.variations:
            # Group by color — pick one variation per colour
            color_variations = {}
            for v in p.variations:
                color_opt = next(
                    (opt for opt in v.options
                     if 'color' in opt.attribute_value.attribute.name.lower()),
                    None
                )
                color_id = color_opt.attribute_value_id if color_opt else 'none'
                if color_id not in color_variations:
                    color_variations[color_id] = v
            for var in color_variations.values():
                expanded_products.append({'product': p, 'variation': var})
        else:
            expanded_products.append({'product': p, 'variation': None})

    new_arrivals = [p for p in expanded_products if p['product'].badge == 'New'][:8]
    if not new_arrivals:
        new_arrivals = expanded_products[:8]
    featured_products = [p for p in expanded_products if p['product'].is_featured][:8]

    # Build category sections from already-loaded products (no extra DB hits)
    cat_map = {}
    for item in expanded_products:
        cat_name = item['product'].cat_name
        if cat_name not in cat_map:
            cat_map[cat_name] = []
        if len(cat_map[cat_name]) < 8:
            cat_map[cat_name].append(item)

    category_sections = []
    for cat in categories:
        prods = cat_map.get(cat.name, [])
        if prods:
            category_sections.append({
                'name': cat.name,
                'products': prods,
                'id': cat.name.lower().replace(' ', '-')
            })

    featured_reviews = Review.query.filter_by(is_featured=True, status='Approved').all()

    return render_template('index.html',
                           new_arrivals=new_arrivals,
                           category_sections=category_sections,
                           categories=categories,
                           featured_products=featured_products,
                           featured_reviews=featured_reviews)

@public_bp.route('/api/subscribe', methods=['POST'])
def subscribe():
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400
        
    if Subscriber.query.filter_by(email=email).first():
        return jsonify({'success': True, 'message': 'Already subscribed!'})
        
    try:
        new_subscriber = Subscriber(email=email)
        db.session.add(new_subscriber)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Successfully subscribed!'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@public_bp.route('/shop')
def shop():
    selected_categories = request.args.getlist('category')
    selected_subcategories = request.args.getlist('subcategory')
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = Product.query
    if selected_categories:
        query = query.filter(Product.cat_name.in_(selected_categories))
    
    if selected_subcategories:
        query = query.join(SubCategory, Product.sub_category_id == SubCategory.id).filter(SubCategory.name.in_(selected_subcategories))
        
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items
    categories = Category.query.all()
    
    return render_template('shop.html', products=products, pagination=pagination, active_categories=selected_categories, all_categories=categories, active_subcategories=selected_subcategories)

@public_bp.route('/product/<id>')
def product_detail(id):
    product = Product.query.get(id)
    if not product:
        abort(404)
    
    variation_id = request.args.get('v')
    selected_variation = None
    if variation_id:
        from models import ProductVariation
        selected_variation = ProductVariation.query.get(variation_id)
        
    related = Product.query.filter(Product.cat_name == product.cat_name, Product.id != product.id).limit(5).all()
    return render_template('product.html', product=product, related=related, selected_variation=selected_variation)

@public_bp.route('/blogs')
def blogs():
    return render_template('blog.html')

@public_bp.route('/about')
def about():
    return render_template('about.html')

@public_bp.route('/wishlist')
def wishlist():
    wishlist_ids = session.get('wishlist', [])
    wishlist_items = []
    
    for item_id in wishlist_ids:
        product = None
        variation = None
        if item_id.startswith('var:'):
            from models import ProductVariation
            var_id = item_id.split(':')[1]
            variation = ProductVariation.query.get(var_id)
            if variation:
                product = variation.product
        else:
            product = Product.query.get(item_id)
            
        if product:
            wishlist_items.append({
                'id': item_id,
                'product': product,
                'variation': variation,
                'display_price': variation.price if variation else product.price,
                'display_img': variation.img_url if (variation and variation.img_url) else product.img,
                'variant_labels': [{
                    'name': opt.attribute_value.attribute.name,
                    'value': opt.attribute_value.value
                } for opt in variation.options] if variation else []
            })
            
    return render_template('wishlist.html', items=wishlist_items)

@public_bp.route('/privacy-policy')
def privacy():
    return render_template('privacy.html')

@public_bp.route('/terms-conditions')
def terms():
    return render_template('terms.html')

@public_bp.route('/shipping-policy')
def shipping():
    return render_template('shipping.html')

@public_bp.route('/cancellation-refund')
def refund():
    return render_template('refund.html')

@public_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        message = request.form.get('message')
        
        if not name or not email or not message:
            return jsonify({'success': False, 'message': 'All required fields must be filled.'}), 400
            
        from models import db, ContactMessage
        msg = ContactMessage(name=name, email=email, phone=phone, message=message)
        db.session.add(msg)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Thank you! Your message has been sent successfully.'})
        
    return render_template('contact.html')

@public_bp.route('/toggle-wishlist/<id>', methods=['POST'])
def toggle_wishlist(id):
    wishlist = session.get('wishlist', [])
    if id in wishlist:
        wishlist.remove(id)
        action = 'removed'
    else:
        wishlist.append(id)
        action = 'added'
    session['wishlist'] = wishlist
    session.modified = True
    return jsonify({'success': True, 'action': action, 'wishlist_count': len(wishlist)})
