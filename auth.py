import os, secrets
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, AdminLog
from werkzeug.utils import secure_filename

auth_bp = Blueprint('auth', __name__)

NIGERIAN_STATES = [
    'Abia','Adamawa','Akwa Ibom','Anambra','Bauchi','Bayelsa','Benue','Borno',
    'Cross River','Delta','Ebonyi','Edo','Ekiti','Enugu','FCT','Gombe','Imo',
    'Jigawa','Kaduna','Kano','Katsina','Kebbi','Kogi','Kwara','Lagos','Nasarawa',
    'Niger','Ogun','Ondo','Osun','Oyo','Plateau','Rivers','Sokoto','Taraba',
    'Yobe','Zamfara'
]

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        f = request.form
        full_name = f.get('full_name', '').strip()
        email     = f.get('email', '').strip().lower()
        password  = f.get('password', '')
        confirm   = f.get('confirm_password', '')
        state     = f.get('state_of_origin', '')
        town      = f.get('town_lga', '').strip()
        school    = f.get('school_name', '').strip()

        errors = []
        if not all([full_name, email, password, confirm, state, town, school]):
            errors.append('Please fill in all required fields.')
        if password != confirm:
            errors.append('Passwords do not match.')
        if len(password) < 8:
            errors.append('Password must be at least 8 characters.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        dob = None
        dob_str = f.get('date_of_birth', '')
        if dob_str:
            try:
                dob = date.fromisoformat(dob_str)
            except ValueError:
                errors.append('Invalid date of birth.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('register.html', states=NIGERIAN_STATES, form=f)

        user = User(
            full_name=full_name, email=email,
            date_of_birth=dob, state_of_origin=state,
            town_lga=town, school_name=school,
            email_token=secrets.token_urlsafe(32)
        )
        user.set_password(password)
        user.faculty    = f.get('faculty', '').strip() or None
        user.department = f.get('department', '').strip() or None
        user.residential_address = f.get('residential_address', '').strip() or None

        nin = f.get('nin', '').strip()
        srn = f.get('school_reg', '').strip()
        if nin: user.nin = nin
        if srn: user.school_reg = srn
        if nin or srn:
            user.verification_level = 1

        # Institution tag (privacy-safe)
        user.institution_tag = school

        db.session.add(user)
        db.session.commit()
        flash('Account created! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', states=NIGERIAN_STATES, form={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = 'remember' in request.form

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if user.is_suspended:
                flash('Your account has been suspended. Contact admin.', 'danger')
                return redirect(url_for('auth.login'))
            login_user(user, remember=remember)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            nxt = request.args.get('next')
            return redirect(nxt or url_for('main.dashboard'))
        flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile/<int:user_id>')
@login_required
def profile(user_id):
    from models import Block, FriendRequest
    user = User.query.get_or_404(user_id)
    blocked_by_me = Block.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    blocked_me    = Block.query.filter_by(blocker_id=user_id, blocked_id=current_user.id).first()
    is_friend     = current_user.is_friends_with(user) if user.id != current_user.id else False
    req_sent      = current_user.friend_request_sent_to(user) if user.id != current_user.id else None
    req_recv      = FriendRequest.query.filter_by(sender_id=user_id, receiver_id=current_user.id, status='pending').first()

    from models import Post
    posts = Post.query.filter_by(user_id=user_id, status='approved').order_by(Post.created_at.desc()).limit(15).all()

    return render_template('profile.html',
        profile_user=user,
        is_blocked=blocked_by_me,
        blocked_me=blocked_me,
        is_friend=is_friend,
        req_sent=req_sent,
        req_recv=req_recv,
        posts=posts
    )


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '').strip() or None
        current_user.town_lga = request.form.get('town_lga', '').strip() or None
        current_user.faculty = request.form.get('faculty', '').strip() or None
        current_user.department = request.form.get('department', '').strip() or None
        current_user.residential_address = request.form.get('residential_address', '').strip() or None

        if 'profile_pic' in request.files:
            f = request.files['profile_pic']
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit('.', 1)[1].lower()
                fname = secure_filename(f'u{current_user.id}_{secrets.token_hex(4)}.{ext}')
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                current_user.profile_pic = fname

        nin = request.form.get('nin', '').strip()
        srn = request.form.get('school_reg', '').strip()
        if nin: current_user.nin = nin
        if srn: current_user.school_reg = srn
        if (nin or srn) and current_user.verification_level == 0:
            current_user.verification_level = 1

        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('auth.profile', user_id=current_user.id))

    return render_template('edit_profile.html', states=NIGERIAN_STATES)


@auth_bp.route('/settings/theme', methods=['POST'])
@login_required
def toggle_theme():
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return redirect(request.referrer or url_for('main.dashboard'))
