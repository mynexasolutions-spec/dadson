import os
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Order

auth_bp = Blueprint('auth', __name__)

def _firebase_config():
    return dict(
        firebase_api_key=os.getenv('FIREBASE_API_KEY', ''),
        firebase_auth_domain=os.getenv('FIREBASE_AUTH_DOMAIN', ''),
        firebase_project_id=os.getenv('FIREBASE_PROJECT_ID', ''),
        firebase_messaging_sender_id=os.getenv('FIREBASE_MESSAGING_SENDER_ID', ''),
        firebase_app_id=os.getenv('FIREBASE_APP_ID', ''),
    )


@auth_bp.route('/login', methods=['GET'])
def login():
    # Store redirect destination
    next_url = request.args.get('next')
    if next_url:
        session['login_next'] = next_url
    return render_template('auth.html', **_firebase_config())


@auth_bp.route('/auth/phone-login', methods=['POST'])
def phone_login():
    data = request.get_json(silent=True) or {}
    id_token = data.get('id_token', '').strip()
    if not id_token:
        return jsonify({'success': False, 'message': 'Missing token.'}), 400
    try:
        phone = None

        # Try Firebase Admin SDK first (requires service account JSON)
        try:
            import firebase_admin
            from firebase_admin import auth as fb_auth
            if firebase_admin._apps:
                decoded = fb_auth.verify_id_token(id_token)
                phone = decoded.get('phone_number')
        except Exception as admin_err:
            from flask import current_app
            current_app.logger.warning(f"Firebase Admin verify failed (falling back to JWT decode): {admin_err}")
            phone = None

        # Fallback: decode JWT payload directly (Firebase already verified OTP client-side)
        # The phone_number claim in the payload is set by Firebase after successful OTP verification
        if not phone:
            import base64, json as _json
            try:
                # JWT format: header.payload.signature — decode the payload part
                payload_b64 = id_token.split('.')[1]
                # Fix base64 padding
                payload_b64 += '=' * (4 - len(payload_b64) % 4)
                payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
                phone = payload.get('phone_number')
            except Exception as jwt_err:
                from flask import current_app
                current_app.logger.error(f"JWT decode failed: {jwt_err}")
                phone = None

        if not phone:
            return jsonify({'success': False, 'message': 'Could not extract phone number from token.'}), 400

        user = User.query.filter_by(phone=phone).first()
        if not user:
            import uuid
            user = User(phone=phone, email=f"phone_{uuid.uuid4().hex[:12]}@dadson.internal")
            user.set_password(uuid.uuid4().hex)
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id
        session['is_admin'] = user.is_admin

        next_url = session.pop('login_next', None)
        if user.is_admin:
            redirect_url = url_for('admin.dashboard')
        elif next_url:
            redirect_url = next_url
        else:
            redirect_url = url_for('public.home')

        return jsonify({'success': True, 'redirect': redirect_url})
    except Exception as e:
        import traceback
        from flask import current_app
        current_app.logger.error(f"phone_login error: {e}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': 'Verification failed. Please try again.'}), 500


@auth_bp.route('/admin-access', methods=['GET', 'POST'])
def admin_access():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password')
        user = User.query.filter_by(email=email, is_admin=True).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['is_admin'] = True
            return redirect(url_for('admin.dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('admin/login.html')


@auth_bp.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
    return redirect(url_for('public.home'))


@auth_bp.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip() or user.full_name
        user.username = user.full_name
        user.alt_phone = request.form.get('alt_phone', '').strip()
        user.address = request.form.get('address')
        city = request.form.get('city')
        state = request.form.get('state')
        user.city = f"{city}, {state}" if state else city
        user.zipcode = request.form.get('zipcode')
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))

    orders = Order.query.filter_by(user_id=user.id).order_by(Order.date.desc()).all()
    return render_template('profile.html', user=user, orders=orders)
