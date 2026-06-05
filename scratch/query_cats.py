from app import app
from models import Category

with app.app_context():
    cats = Category.query.all()
    for c in cats:
        print(f"ID: {c.id}, Name: {c.name}, Parent ID: {c.parent_id}, Gender: {c.gender}")
