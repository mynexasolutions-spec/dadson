import os
from app import app
from models import db, Category, SubCategory

def update_categories():
    with app.app_context():
        # Ensure Watch category exists
        watch_cat = Category.query.filter_by(name="Watch").first()
        if not watch_cat:
            watch_cat = Category(name="Watch", img="https://images.unsplash.com/photo-1522312346375-d1a52e2b99b3?auto=format&fit=crop&w=700&q=80")
            db.session.add(watch_cat)
            db.session.commit()
            print("Created Watch category.")
        
        # Remove any existing subcategories for Watch category to avoid duplicates
        SubCategory.query.filter_by(category_id=watch_cat.id).delete()
        
        # Add new subcategories as requested:
        # Men: Gym watch, Office watch, Luxury watch
        # Women: Gym watch, Luxury Watch, Fashion watches
        watch_subcats = [
            "Men - Gym watch",
            "Men - Office watch",
            "Men - Luxury watch",
            "Women - Gym watch",
            "Women - Luxury Watch",
            "Women - Fashion watches"
        ]
        
        for name in watch_subcats:
            sub = SubCategory(name=name, category_id=watch_cat.id)
            db.session.add(sub)
            
        db.session.commit()
        app.invalidate_category_cache()
        print("Successfully updated Watch subcategories in database.")

if __name__ == '__main__':
    update_categories()
