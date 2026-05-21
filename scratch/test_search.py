import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from models import db, Product, Category, SubCategory
from sqlalchemy import or_

def run_test_query(search_query):
    print(f"\n==================================================")
    print(f"Testing Search Query: '{search_query}'")
    print(f"==================================================")
    
    query = Product.query
    
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
    
    print(f"Collection flags: New Arrivals={match_new_arrivals}, Best Sellers={match_best_sellers}, Featured={match_featured}, All Collections={match_all_collections}")
    print(f"Clean Query: '{clean_query}'")
    
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
        
    # Check strict query count
    if strict_query.count() > 0:
        print("Using Strict Query (AND)")
        products = strict_query.all()
    else:
        print("Strict Query returned 0 results. Falling back to broader OR search...")
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
            
        products = query.filter(or_(*fallback_filters)).all()

    print(f"Results Count: {len(products)}")
    for p in products:
        flags = []
        if p.is_new_arrival or p.badge == 'New': flags.append("New Arrival")
        if p.is_best_seller: flags.append("Best Seller")
        if p.is_featured: flags.append("Featured")
        flags_str = f" [{', '.join(flags)}]" if flags else ""
        print(f" - {p.name} (Category: {p.cat_name}){flags_str}")

if __name__ == '__main__':
    with app.app_context():
        # List total products count first
        print(f"Total products in DB: {Product.query.count()}")
        
        # Test runs
        run_test_query("best seller rings")
        run_test_query("new arrivals")
        run_test_query("rings collection")
        run_test_query("collection")
        run_test_query("best")
        run_test_query("featured necklace")
        run_test_query("nonexistent query")
