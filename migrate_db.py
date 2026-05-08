import sqlite3
import os
from app import app
from models import db, User, Category, Product, SubCategory, ProductVariation, Order, OrderItem, AppConfig, Attribute, AttributeValue, ProductAttribute, VariationOption, ProductImage, Brand, Review, Coupon, Subscriber
import cloudinary
import cloudinary.uploader
import shutil

def upload_to_cloudinary(local_path, folder):
    if not local_path:
        return None
    if local_path.startswith('http') or local_path.startswith('cloudinary://'):
        return local_path
        
    # Full path to the file
    full_path = os.path.join(app.root_path, local_path.lstrip('/'))
    if not os.path.exists(full_path):
        # Try finding it in static/
        full_path = os.path.join(app.root_path, 'static', local_path.replace('static/', '', 1).lstrip('/'))
        if not os.path.exists(full_path):
            print(f"File not found: {local_path} -> {full_path}")
            return local_path # Return original if not found
            
    print(f"Uploading {full_path} to Cloudinary folder {folder}...")
    try:
        result = cloudinary.uploader.upload(full_path, folder=f"dadson/{folder}")
        return result.get('secure_url')
    except Exception as e:
        print(f"Upload failed: {e}")
        return local_path

def migrate():
    # Setup cloudinary config
    cloudinary.config(
        cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key = os.getenv('CLOUDINARY_API_KEY'),
        api_secret = os.getenv('CLOUDINARY_API_SECRET'),
        secure = True
    )

    with app.app_context():
        # Recreate all tables in postgres
        print("Creating tables in Postgres...")
        db.create_all()
        
        print("Connecting to SQLite...")
        sqlite_db = os.path.join(app.instance_path, 'dadson.db')
        if not os.path.exists(sqlite_db):
            print(f"SQLite DB not found at {sqlite_db}")
            return
            
        conn = sqlite3.connect(sqlite_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Helper to clear table and insert
        def migrate_table(table_name, model_class, image_fields=None):
            print(f"Migrating {table_name}...")
            cur.execute(f'SELECT * FROM "{table_name}"')
            rows = cur.fetchall()
            for row in rows:
                data = dict(row)
                
                # Check if record exists
                pk = 'id'
                if model_class == User:
                    existing = model_class.query.filter_by(email=data.get('email')).first()
                elif model_class == AppConfig:
                    existing = model_class.query.filter_by(key=data.get('key')).first()
                elif model_class == Order:
                    existing = model_class.query.filter_by(order_number=data.get('order_number')).first()
                else:
                    existing = model_class.query.get(data.get(pk))
                    
                if existing:
                    continue
                
                # Upload images if needed
                if image_fields:
                    for field, folder in image_fields.items():
                        if data.get(field):
                            new_url = upload_to_cloudinary(data[field], folder)
                            data[field] = new_url
                            
                # For sqlite datetimes
                if 'join_date' in data and data['join_date']:
                    from datetime import datetime
                    try:
                        data['join_date'] = datetime.strptime(data['join_date'], '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        pass
                if 'date' in data and data['date']:
                    from datetime import datetime
                    try:
                        data['date'] = datetime.strptime(data['date'], '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        pass
                if 'expiry_date' in data and data['expiry_date']:
                    from datetime import datetime
                    try:
                        data['expiry_date'] = datetime.strptime(data['expiry_date'], '%Y-%m-%d %H:%M:%S.%f')
                    except:
                        pass
                        
                obj = model_class(**data)
                db.session.add(obj)
            db.session.commit()
            print(f"Migrated {len(rows)} records for {table_name}.")

        migrate_table('user', User)
        migrate_table('app_config', AppConfig)
        migrate_table('brand', Brand, {'logo': 'brands'})
        migrate_table('category', Category, {'img': 'categories'})
        migrate_table('sub_category', SubCategory)
        migrate_table('attribute', Attribute, {'image_url': 'attributes'})
        migrate_table('attribute_value', AttributeValue, {'image_url': 'attributes'})
        migrate_table('product', Product, {'img': 'products', 'size_chart': 'products'})
        migrate_table('product_variation', ProductVariation, {'img_url': 'products'})
        migrate_table('product_image', ProductImage, {'img_url': 'products'})
        migrate_table('product_attribute', ProductAttribute)
        migrate_table('variation_option', VariationOption)
        migrate_table('coupon', Coupon)
        migrate_table('subscriber', Subscriber)
        migrate_table('order', Order)
        migrate_table('order_item', OrderItem)
        migrate_table('review', Review)
        
        print("Migration complete!")

if __name__ == '__main__':
    migrate()
