from app import app
from models import db, Product

def seed_flags():
    with app.app_context():
        products = Product.query.all()
        if not products:
            print("No products found in the database. Please run seed_products.py first.")
            return
        
        # Reset and assign flags
        for i, p in enumerate(products):
            # Reset
            p.is_best_seller = False
            p.is_new_arrival = False
            
            # Set Best Seller
            if i % 3 == 0:
                p.is_best_seller = True
                print(f"Product '{p.name}' (ID: {p.id}) flagged as Best Seller.")
                
            # Set New Arrival
            if i % 2 == 0 or i == len(products) - 1:
                p.is_new_arrival = True
                print(f"Product '{p.name}' (ID: {p.id}) flagged as New Arrival.")
                
        db.session.commit()
        print("Database flags successfully updated!")

if __name__ == '__main__':
    seed_flags()
