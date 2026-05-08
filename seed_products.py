import os
from app import app
from models import db, Category, Product
import cloudinary
import cloudinary.uploader

categories_data = [
    {"name": "Rings", "img": "https://images.unsplash.com/photo-1611591437281-460bfbe1220a?auto=format&fit=crop&w=700&q=80"},
    {"name": "Earrings", "img": "https://images.unsplash.com/photo-1635767798638-3e25273a8236?auto=format&fit=crop&w=700&q=80"},
    {"name": "Necklaces", "img": "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=700&q=80"},
    {"name": "Bracelets", "img": "https://images.unsplash.com/photo-1611085583191-a3b181a88401?auto=format&fit=crop&w=700&q=80"},
    {"name": "Mangalsutra", "img": "https://images.unsplash.com/photo-1588444650700-6ad8eac5dcaf?auto=format&fit=crop&w=700&q=80"},
]

products_data = [
    # Rings
    {"name": "Diamond Solitaire Ring", "cat_name": "Rings", "img": "https://images.unsplash.com/photo-1611591437282-7ac8b30f3ee9?auto=format&fit=crop&w=500&q=80", "desc": "Lab-Grown Diamond", "price": "Rs. 5,799", "orig": "Rs. 7,999"},
    {"name": "Stackable Ring Set", "cat_name": "Rings", "img": "https://images.unsplash.com/photo-1617038260897-41a1f14a8ca0?auto=format&fit=crop&w=500&q=80", "desc": "Silver & Gold Mix", "price": "Rs. 3,299", "orig": None},
    {"name": "Twist Band Ring", "cat_name": "Rings", "img": "https://images.unsplash.com/photo-1605100804763-247f67b3557e?auto=format&fit=crop&w=500&q=80", "desc": "18K Gold Plated", "price": "Rs. 2,699", "orig": None},
    {"name": "Minimal Dome Ring", "cat_name": "Rings", "img": "https://images.unsplash.com/photo-1629224316810-9d8805b95e76?auto=format&fit=crop&w=500&q=80", "desc": "Vermeil Finish", "price": "Rs. 2,999", "orig": None},
    
    # Necklaces
    {"name": "Minimalist Chain", "cat_name": "Necklaces", "img": "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?auto=format&fit=crop&w=500&q=80", "desc": "Sterling Silver", "price": "Rs. 2,299", "orig": "Rs. 3,299"},
    {"name": "Pearl Elegance Necklace", "cat_name": "Necklaces", "img": "https://images.unsplash.com/photo-1599643478512-f39baa8a1a85?auto=format&fit=crop&w=500&q=80", "desc": "Freshwater Pearl", "price": "Rs. 3,899", "orig": None},
    {"name": "Layered Pendant Set", "cat_name": "Necklaces", "img": "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?auto=format&fit=crop&w=500&q=80", "desc": "Gold Plated", "price": "Rs. 2,899", "orig": "Rs. 3,999"},
    {"name": "Bar Pendant Necklace", "cat_name": "Necklaces", "img": "https://images.unsplash.com/photo-1611652022419-a9419f74343d?auto=format&fit=crop&w=500&q=80", "desc": "Gold Vermeil", "price": "Rs. 3,199", "orig": None},

    # Earrings
    {"name": "Stellar Glow Earrings", "cat_name": "Earrings", "img": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?auto=format&fit=crop&w=500&q=80", "desc": "18K Gold Vermeil", "price": "Rs. 3,499", "orig": "Rs. 4,999"},
    {"name": "Rose Gold Studs", "cat_name": "Earrings", "img": "https://images.unsplash.com/photo-1599643478517-8b9d3c8c0bf9?auto=format&fit=crop&w=500&q=80", "desc": "Rose Gold Vermeil", "price": "Rs. 2,599", "orig": None},
    {"name": "Classic Hoop Earrings", "cat_name": "Earrings", "img": "https://images.unsplash.com/photo-1635767798638-3e25273a8236?auto=format&fit=crop&w=500&q=80", "desc": "Gold Plated", "price": "Rs. 2,899", "orig": None},
    {"name": "DADSON Leaf Earrings", "cat_name": "Earrings", "img": "static/images/dadson box img.jpeg", "desc": "Statement Gold Finish", "price": "Rs. 3,999", "orig": None},

    # Bracelets
    {"name": "Golden Hour Bracelet", "cat_name": "Bracelets", "img": "https://images.unsplash.com/photo-1611085583191-a3b181a88401?auto=format&fit=crop&w=500&q=80", "desc": "18K Gold Plated", "price": "Rs. 4,199", "orig": None},
]

def upload_image(image_path, folder):
    if image_path.startswith('static/'):
        image_path = os.path.join(app.root_path, image_path)
    print(f"Uploading {image_path} to {folder}...")
    try:
        res = cloudinary.uploader.upload(image_path, folder=f"dadson/{folder}")
        return res.get('secure_url')
    except Exception as e:
        print(f"Failed to upload {image_path}: {e}")
        return image_path

def seed():
    with app.app_context():
        # Categories
        cat_map = {}
        for cdata in categories_data:
            cat = Category.query.filter_by(name=cdata['name']).first()
            if not cat:
                cimg_url = upload_image(cdata['img'], 'categories')
                cat = Category(name=cdata['name'], img=cimg_url)
                db.session.add(cat)
                db.session.commit()
                print(f"Added category {cat.name}")
            cat_map[cat.name] = cat.id
            
        # Products
        for pdata in products_data:
            pid = pdata['name'].lower().replace(' ', '-')
            prod = Product.query.get(pid)
            if not prod:
                pimg_url = upload_image(pdata['img'], 'products')
                
                prod = Product(
                    id=pid,
                    name=pdata['name'],
                    cat_name=pdata['cat_name'],
                    category_id=cat_map.get(pdata['cat_name']),
                    desc=pdata['desc'],
                    price=pdata['price'],
                    orig=pdata['orig'],
                    img=pimg_url,
                    stock_status='instock',
                    is_featured=True, # Make them featured so they show up easily
                    product_type='simple'
                )
                db.session.add(prod)
                print(f"Added product {prod.name}")
        
        db.session.commit()
        print("Seeding complete!")

if __name__ == '__main__':
    seed()
