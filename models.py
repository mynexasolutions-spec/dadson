from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(512), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    join_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Profile Details
    username = db.Column(db.String(80))
    phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    city = db.Column(db.String(100))
    zipcode = db.Column(db.String(10))
    
    orders = db.relationship('Order', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.email}>"

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    img = db.Column(db.String(255))
    bg = db.Column(db.String(20))
    count = db.Column(db.String(50))
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    gender = db.Column(db.String(20), default='Both') # 'Men', 'Women', 'Both'

    products = db.relationship('Product', backref='category', lazy=True)
    subcategories = db.relationship('Category', backref=db.backref('parent', remote_side='Category.id'), lazy=True, cascade="all, delete-orphan")
    legacy_subcategories = db.relationship('SubCategory', backref='category', lazy=True, cascade="all, delete-orphan")

    def get_full_path(self):
        path = [self.name]
        curr = self.parent
        visited = {self.id}
        while curr and curr.id not in visited:
            path.append(curr.name)
            visited.add(curr.id)
            curr = curr.parent
        return " > ".join(reversed(path))

    def get_gender(self):
        if self.gender:
            return self.gender
        if self.parent:
            return self.parent.get_gender()
        return 'Both'

    def __repr__(self):
        return f"<Category {self.name}>"

class Product(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    cat_name = db.Column(db.String(100))
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=True)
    sub_category_id = db.Column(db.Integer, db.ForeignKey('sub_category.id'), nullable=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brand.id'), nullable=True)
    price = db.Column(db.String(20), nullable=False)
    orig = db.Column(db.String(20))
    badge = db.Column(db.String(50))
    img = db.Column(db.String(512), nullable=False)
    desc = db.Column(db.Text)
    sizes = db.Column(db.String(100))
    colors = db.Column(db.String(100))
    size_chart = db.Column(db.String(512))
    product_type = db.Column(db.String(20), default='simple') # 'simple' or 'variable'
    stock_status = db.Column(db.String(20), default='instock') # 'instock' or 'outofstock'
    is_featured = db.Column(db.Boolean, default=False)
    is_best_seller = db.Column(db.Boolean, default=False)
    is_new_arrival = db.Column(db.Boolean, default=False)
    materials = db.Column(db.Text)
    care = db.Column(db.Text)
    seo_title = db.Column(db.String(200))
    seo_description = db.Column(db.Text)
    focus_keyword = db.Column(db.String(200))
    meta_keywords = db.Column(db.Text)
    product_tags = db.Column(db.Text)

    variations = db.relationship('ProductVariation', backref='product', lazy=True, cascade="all, delete-orphan")
    attributes = db.relationship('ProductAttribute', backref='product', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Product {self.name}>"

class SubCategory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    products = db.relationship('Product', backref='subcategory', lazy=True)

    def __repr__(self):
        return f"<SubCategory {self.name}>"

class ProductVariation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    price = db.Column(db.String(20))
    orig_price = db.Column(db.String(20))
    img_url = db.Column(db.String(512))
    stock_status = db.Column(db.String(20), default='instock')

    def __repr__(self):
        return f"<Variation for {self.product_id}>"


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(50), default='Pending')
    coupon_code = db.Column(db.String(50), nullable=True)
    discount_amount = db.Column(db.Float, default=0.0)
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.String(50), db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price_at_time = db.Column(db.String(20), nullable=False)
    variation_id = db.Column(db.Integer, db.ForeignKey('product_variation.id', ondelete='SET NULL'), nullable=True)
    variation_label = db.Column(db.String(500), nullable=True)
    product = db.relationship('Product')
    variation = db.relationship('ProductVariation')

class AppConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)

class Attribute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(100), unique=True)
    type = db.Column(db.String(50), default='select') # 'text', 'select', 'color'
    image_url = db.Column(db.String(512))
    is_featured = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return f"<Attribute {self.name}>"


class AttributeValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    value = db.Column(db.String(100), nullable=False)
    image_url = db.Column(db.String(512))
    attribute = db.relationship('Attribute', backref=db.backref('values', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f"<AttributeValue {self.value} for {self.attribute.name}>"

class ProductAttribute(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    attribute = db.relationship('Attribute')

class SelectedAttributeValue(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), db.ForeignKey('product.id', ondelete='CASCADE'), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    attribute_value_id = db.Column(db.Integer, db.ForeignKey('attribute_value.id'), nullable=False)
    product = db.relationship('Product', backref=db.backref('selected_values', lazy=True, cascade="all, delete-orphan"))
    attribute_value = db.relationship('AttributeValue')

class VariationOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    variation_id = db.Column(db.Integer, db.ForeignKey('product_variation.id', ondelete='CASCADE'), nullable=False)
    attribute_value_id = db.Column(db.Integer, db.ForeignKey('attribute_value.id'), nullable=False)
    variation = db.relationship('ProductVariation', backref=db.backref('options', lazy=True, cascade="all, delete-orphan"))
    attribute_value = db.relationship('AttributeValue')

class ProductImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), db.ForeignKey('product.id'), nullable=False)
    attribute_value_id = db.Column(db.Integer, db.ForeignKey('attribute_value.id'), nullable=True)
    img_url = db.Column(db.String(512), nullable=False)
    product_rel = db.relationship('Product', backref=db.backref('images', lazy=True, cascade="all, delete-orphan"))
    attribute_value = db.relationship('AttributeValue')

class Brand(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    logo = db.Column(db.String(512))
    products = db.relationship('Product', backref='brand', lazy=True)

    def __repr__(self):
        return f"<Brand {self.name}>"

class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.String(50), db.ForeignKey('product.id'), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    customer_name = db.Column(db.String(100))
    customer_location = db.Column(db.String(100))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='Approved')
    is_featured = db.Column(db.Boolean, default=False)
    product = db.relationship('Product', backref=db.backref('reviews', lazy=True))
    user_rel = db.relationship('User', backref=db.backref('reviews', lazy=True))

class Coupon(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    type = db.Column(db.String(20), nullable=False) # 'flat', 'percentage'
    discount = db.Column(db.Float, nullable=False)
    threshold = db.Column(db.Float, default=0.0)
    usage_limit = db.Column(db.Integer, default=1)
    expiry_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)

# New model for Newsletter
class Subscriber(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Subscriber {self.email}>"

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    message = db.Column(db.Text, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<ContactMessage {self.email}>"
