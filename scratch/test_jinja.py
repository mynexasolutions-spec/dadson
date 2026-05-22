import os
import sys

# Add the parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from flask import render_template

with app.app_context():
    try:
        print("Attempting to compile templates...")
        # Compile base.html
        app.jinja_env.get_template('base.html')
        print("base.html compiled successfully.")
        
        # Compile product.html
        app.jinja_env.get_template('product.html')
        print("product.html compiled successfully.")
    except Exception as e:
        import traceback
        traceback.print_exc()
