import json
from flask import Blueprint, render_template, request, abort, session, jsonify
from models import db, Category, Product, SubCategory, Review, Subscriber
from sqlalchemy.orm import joinedload

public_bp = Blueprint('public', __name__)

@public_bp.route('/')
def home():
    categories = Category.query.all()

    # Deep eager load — one query with all joins, eliminates N+1 for
    # variation options, attribute values, and gallery images
    from models import ProductVariation, VariationOption, AttributeValue, Attribute, ProductImage
    _var_opts = joinedload(Product.variations).joinedload(
        ProductVariation.options).joinedload(
        VariationOption.attribute_value).joinedload(
        AttributeValue.attribute)
    all_products = Product.query.options(
        _var_opts,
        joinedload(Product.images),
        joinedload(Product.category),
        joinedload(Product.subcategory),
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

    new_arrivals = [p for p in expanded_products if p['product'].is_new_arrival][:8]
    if not new_arrivals:
        new_arrivals = [p for p in expanded_products if p['product'].badge == 'New'][:8]
        if not new_arrivals:
            new_arrivals = expanded_products[:8]
            
    best_sellers = [p for p in expanded_products if p['product'].is_best_seller][:8]
    if not best_sellers:
        best_sellers = [p for p in expanded_products if p['product'].is_featured][:8]
        if not best_sellers:
            best_sellers = expanded_products[:8]

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
                           best_sellers=best_sellers,
                           featured_products=best_sellers,  # fallback/backward compatibility
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
    selected_filters = request.args.getlist('filter')
    selected_categories = [c for c in request.args.getlist('category') if c]
    selected_subcategories = [s for s in request.args.getlist('subcategory') if s]
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 12

    query = Product.query
    if selected_subcategories or selected_categories:
        # Build parent_id → [child_ids] map in one flat query (no lazy-loading)
        _all_rows = db.session.query(Category.id, Category.parent_id).all()
        _children_map = {}
        for _cid, _pid in _all_rows:
            _children_map.setdefault(_pid, []).append(_cid)

        def _all_descendants(cat_id):
            """Return the set of ALL descendant IDs (iterative BFS, no recursion limit)."""
            result, stack = set(), list(_children_map.get(cat_id, []))
            while stack:
                cid = stack.pop()
                result.add(cid)
                stack.extend(_children_map.get(cid, []))
            return result

        # Merge category + subcategory params — both resolve to Category rows.
        # Keeping them separate caused parents to override more-specific children.
        _all_names = list(set(selected_subcategories + selected_categories))
        _sel_cats  = Category.query.filter(Category.name.in_(_all_names)).all()
        _sel_ids   = {c.id for c in _sel_cats}

        # Intersection rule: skip any selected category that has a selected descendant
        # (the descendant is more specific and takes precedence).  Only "leaf"
        # selections — those with no selected descendant — drive the final filter.
        #
        #   [Watch]            → leaf=[Watch]      → Watch + all Watch children
        #   [Watch, Gym watch] → leaf=[Gym watch]  → Gym watch only
        #   [Men, Watch]       → leaf=[Watch]      → Watch + its children (Men is an ancestor)
        #   [Office w, Gym w]  → leaf=[both]       → Office watch ∪ Gym watch
        target_cat_ids = set()
        for cat in _sel_cats:
            desc = _all_descendants(cat.id)
            if not (desc & _sel_ids):        # no selected descendant → this is the leaf
                target_cat_ids.add(cat.id)
                target_cat_ids |= desc       # include the leaf's own subtree

        if target_cat_ids:
            query = query.filter(Product.category_id.in_(list(target_cat_ids)))

    if selected_filters:
        if 'best_sellers' in selected_filters:
            query = query.filter(Product.is_best_seller == True)
        if 'new_arrivals' in selected_filters:
            query = query.filter(Product.is_new_arrival == True)

    if search_query:
        from sqlalchemy import or_
        sq_lower = search_query.lower()
        words = sq_lower.split()
        
        # 1. Detect collection matches
        match_new_arrivals = False
        match_best_sellers = False
        match_featured = False
        match_all_collections = False
        
        if "new arrival" in sq_lower or "new arrivals" in sq_lower or "new" in words:
            match_new_arrivals = True
        if "best seller" in sq_lower or "best sellers" in sq_lower or "best" in words:
            match_best_sellers = True
        if "featured" in sq_lower:
            match_featured = True
        if sq_lower in ["collection", "collections", "all collections", "our collections"]:
            match_all_collections = True
            
        # 2. Get clean query for keyword matching by removing collection and generic keywords
        clean_query = sq_lower
        for phrase in ["new arrivals collection", "new arrival collection", "new arrivals", "new arrival",
                       "best sellers collection", "best seller collection", "best sellers", "best seller",
                       "featured collection", "all collections", "our collections"]:
            clean_query = clean_query.replace(phrase, "")
            
        # Split and remove single stop-words
        stop_words = {"new", "best", "featured", "collection", "collections", "jewelry", "jewelleries", "jewellery", "jewels", "jewel", "jewelers", "jeweler"}
        query_words = clean_query.split()
        filtered_words = []
        for w in query_words:
            if w not in stop_words:
                filtered_words.append(w)
        clean_query = " ".join(filtered_words)
        
        # 3. Try to perform strict filter (Collection AND Keyword)
        strict_query = query
        if match_new_arrivals:
            strict_query = strict_query.filter(or_(Product.is_new_arrival == True, Product.badge.ilike('%New%')))
        if match_best_sellers:
            strict_query = strict_query.filter(Product.is_best_seller == True)
        if match_featured:
            strict_query = strict_query.filter(Product.is_featured == True)
        if match_all_collections:
            strict_query = strict_query.filter(or_(
                Product.is_new_arrival == True,
                Product.is_best_seller == True,
                Product.is_featured == True,
                Product.badge.ilike('%New%')
            ))
            
        if clean_query:
            matched_cat_ids = []
            for c in Category.query.all():
                c_name_lower = c.name.lower()
                if c_name_lower in clean_query or clean_query in c_name_lower:
                    matched_cat_ids.append(c.id)
                    
            matched_subcat_ids = []
            for s in SubCategory.query.all():
                s_name_lower = s.name.lower()
                if s_name_lower in clean_query or clean_query in s_name_lower:
                    matched_subcat_ids.append(s.id)
                    
            keyword_filters = [
                Product.name.ilike(f'%{clean_query}%'),
                Product.desc.ilike(f'%{clean_query}%'),
                Product.cat_name.ilike(f'%{clean_query}%')
            ]
            if matched_cat_ids:
                keyword_filters.append(Product.category_id.in_(matched_cat_ids))
            if matched_subcat_ids:
                keyword_filters.append(Product.sub_category_id.in_(matched_subcat_ids))
                
            strict_query = strict_query.filter(or_(*keyword_filters))
            
        # If strict query yields matches, use it. Otherwise fall back to a broader search
        if strict_query.first() is not None:
            query = strict_query
        else:
            # Fallback to broader OR search across the full raw search query
            matched_cat_ids = [c.id for c in Category.query.filter(Category.name.ilike(f'%{search_query}%')).all()]
            matched_subcat_ids = [s.id for s in SubCategory.query.filter(SubCategory.name.ilike(f'%{search_query}%')).all()]
            
            fallback_filters = [
                Product.name.ilike(f'%{search_query}%'),
                Product.desc.ilike(f'%{search_query}%'),
                Product.cat_name.ilike(f'%{search_query}%')
            ]
            if matched_cat_ids:
                fallback_filters.append(Product.category_id.in_(matched_cat_ids))
            if matched_subcat_ids:
                fallback_filters.append(Product.sub_category_id.in_(matched_subcat_ids))
                
            if match_new_arrivals:
                fallback_filters.append(Product.is_new_arrival == True)
                fallback_filters.append(Product.badge.ilike('%New%'))
            if match_best_sellers:
                fallback_filters.append(Product.is_best_seller == True)
            if match_featured:
                fallback_filters.append(Product.is_featured == True)
                
            query = query.filter(or_(*fallback_filters))

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    products = pagination.items
    categories = Category.query.all()

    # Build tree from flat list — avoids lazy-loading .subcategories on potentially
    # stale cached objects, keeping sidebar and drilldown bar in sync.
    _cat_map = {c.id: {'id': c.id, 'name': c.name, 'children': []} for c in categories}
    _tree_roots = []
    for c in categories:
        if c.parent_id is None:
            _tree_roots.append(_cat_map[c.id])
        elif c.parent_id in _cat_map:
            _cat_map[c.parent_id]['children'].append(_cat_map[c.id])
    category_tree_json = json.dumps(_tree_roots)

    return render_template('shop.html',
        products=products,
        pagination=pagination,
        active_genders=[],
        search_query=search_query,
        active_filters=selected_filters,
        all_categories=categories,
        active_categories=selected_categories,
        active_subcategories=selected_subcategories,
        category_tree_json=category_tree_json,
    )

@public_bp.route('/product/<id>')
def product_detail(id):
    from models import ProductVariation, VariationOption, AttributeValue, Attribute, ProductImage, SelectedAttributeValue
    _var_opts = joinedload(Product.variations).joinedload(
        ProductVariation.options).joinedload(
        VariationOption.attribute_value).joinedload(
        AttributeValue.attribute)
    product = Product.query.options(
        _var_opts,
        joinedload(Product.images),
        joinedload(Product.category),
        joinedload(Product.subcategory),
        joinedload(Product.selected_values).joinedload(
            SelectedAttributeValue.attribute_value).joinedload(
            AttributeValue.attribute),
    ).filter_by(id=id).first()
    if not product:
        abort(404)

    variation_id = request.args.get('v')
    selected_variation = None
    if variation_id:
        selected_variation = ProductVariation.query.options(
            joinedload(ProductVariation.options).joinedload(
                VariationOption.attribute_value).joinedload(
                AttributeValue.attribute)
        ).get(variation_id)

    related = Product.query.options(
        joinedload(Product.variations),
        joinedload(Product.images),
    ).filter(Product.cat_name == product.cat_name, Product.id != product.id).limit(5).all()
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

@public_bp.route('/faq')
def faq():
    return render_template('faq.html')

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
