"""
NSDCP — Auth Blueprint
Registration with Nigerian states + universities
SA2 compatible
"""
import os, secrets
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User, Block, FriendRequest, Post
from werkzeug.utils import secure_filename

auth_bp = Blueprint('auth', __name__)

ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

# ── Nigerian States ───────────────────────────────────────────────────────────
NIGERIAN_STATES = [
    'Abia','Adamawa','Akwa Ibom','Anambra','Bauchi','Bayelsa','Benue','Borno',
    'Cross River','Delta','Ebonyi','Edo','Ekiti','Enugu','FCT','Gombe','Imo',
    'Jigawa','Kaduna','Kano','Katsina','Kebbi','Kogi','Kwara','Lagos','Nasarawa',
    'Niger','Ogun','Ondo','Osun','Oyo','Plateau','Rivers','Sokoto','Taraba',
    'Yobe','Zamfara'
]

# ── Nigerian Universities, Polytechnics & Colleges (by state) ─────────────────
NIGERIAN_SCHOOLS = {
    'Abia': [
        'Abia State University (ABSU), Uturu',
        'Abia State Polytechnic, Aba',
        'Michael Okpara University of Agriculture, Umudike',
        'Gregory University, Uturu',
        'Evangel University, Akaeze',
    ],
    'Adamawa': [
        'Modibbo Adama University (MAU), Yola',
        'Adamawa State University, Mubi',
        'American University of Nigeria, Yola',
        'Adamawa State Polytechnic, Yola',
    ],
    'Akwa Ibom': [
        'University of Uyo (UNIUYO)',
        'Akwa Ibom State University (AKSU)',
        'Akwa Ibom State Polytechnic, Ikot Osura',
        'Heritage Polytechnic, Eket',
        'Air Force Institute of Technology (AFIT), Kaduna',
    ],
    'Anambra': [
        'Nnamdi Azikiwe University (NAU/UNIZIK), Awka',
        'Chukwuemeka Odumegwu Ojukwu University (COOU)',
        'Anambra State University (ANSU)',
        'Madonna University, Okija',
        'Tansian University, Umunya',
        'Anambra State Polytechnic, Mgbakwu',
    ],
    'Bauchi': [
        'Abubakar Tafawa Balewa University (ATBU), Bauchi',
        'Bauchi State University, Gadau',
        'Bauchi State College of Agriculture, Bauchi',
        'Bauchi State Polytechnic, Bauchi',
    ],
    'Bayelsa': [
        'Niger Delta University (NDU), Wilberforce Island',
        'Federal University, Otuoke',
        'Bayelsa Medical University',
        'Isaac Jasper Boro College of Education, Sagbama',
    ],
    'Benue': [
        'University of Agriculture, Makurdi (UAM)',
        'Benue State University (BSU), Makurdi',
        'Joseph Sarwuan Tarkaa University, Makurdi',
        'Federal University of Health Sciences, Otukpo',
        'Benue State Polytechnic, Ugbokolo',
    ],
    'Borno': [
        'University of Maiduguri (UNIMAID)',
        'Ramat Polytechnic, Maiduguri',
        'Borno State University',
        'Federal Polytechnic, Damaturu',
    ],
    'Cross River': [
        'University of Calabar (UNICAL)',
        'Cross River University of Technology (CRUTECH)',
        'Arthur Jarvis University, Akpabuyo',
        'Federal College of Education, Obudu',
    ],
    'Delta': [
        'Delta State University (DELSU), Abraka',
        'Federal University of Petroleum Resources, Effurun',
        'Western Delta University, Oghara',
        'Delta State Polytechnic, Ogwashi-Uku',
        'Delta State Polytechnic, Otefe-Oghara',
        'Delta State College of Education, Mosogar',
    ],
    'Ebonyi': [
        'Ebonyi State University (EBSU), Abakaliki',
        'Federal University, Ndufu-Alike (FUNAI)',
        'Caritas University, Amorji-Nike',
        'David Umahi University of Medical Sciences',
    ],
    'Edo': [
        'University of Benin (UNIBEN)',
        'Ambrose Alli University (AAU), Ekpoma',
        'Benson Idahosa University (BIU), Benin City',
        'Igbinedion University, Okada',
        'Auchi Polytechnic, Auchi',
        'College of Education, Ekiadolor',
    ],
    'Ekiti': [
        'Ekiti State University (EKSU), Ado-Ekiti',
        'Federal University, Oye-Ekiti (FUOYE)',
        'Afe Babalola University, Ado-Ekiti (ABUAD)',
        'Bamidele Olumilua University of Education, Ikere-Ekiti',
    ],
    'Enugu': [
        'University of Nigeria, Nsukka (UNN)',
        'Enugu State University of Science & Technology (ESUT)',
        'Institute of Management and Technology (IMT), Enugu',
        'Godfrey Okoye University, Enugu',
        'Renaissance University, Enugu',
    ],
    'FCT': [
        'University of Abuja (UNIABUJA)',
        'Baze University, Abuja',
        'Veritas University, Abuja',
        'Nile University of Nigeria, Abuja',
        'National Open University of Nigeria (NOUN), Abuja',
        'Federal Polytechnic, Bida',
        'Nigerian Defence Academy (NDA)',
        'Nigerian Law School, Abuja',
    ],
    'Gombe': [
        'Gombe State University (GSU)',
        'Federal University, Kashere',
        'Gombe State Polytechnic',
        'Federal College of Education (Technical), Gombe',
    ],
    'Imo': [
        'Federal University of Technology, Owerri (FUTO)',
        'Imo State University (IMSU), Owerri',
        'Imo State Polytechnic, Umuagwo',
        'Federal Polytechnic, Nekede',
        'Rhema University, Aba',
        'Gregory University, Uturu',
    ],
    'Jigawa': [
        'Federal University, Dutse',
        'Sule Lamido University, Kafin Hausa',
        'Hussaini Adamu Federal Polytechnic, Kazaure',
        'Jigawa State Polytechnic, Dutse',
    ],
    'Kaduna': [
        'Ahmadu Bello University (ABU), Zaria',
        'Kaduna State University (KASU)',
        'Kaduna Polytechnic',
        'Air Force Institute of Technology (AFIT), Kaduna',
        'Nigerian Defence Academy (NDA), Kaduna',
        'Federal College of Education, Zaria',
        'Nuhu Bamalli Polytechnic, Zaria',
    ],
    'Kano': [
        'Bayero University, Kano (BUK)',
        'Kano University of Science and Technology, Wudil',
        'Yusuf Maitama Sule University, Kano',
        'Kano State Polytechnic',
        'Federal College of Education, Kano',
        'Aminu Kano College of Islamic Studies',
    ],
    'Katsina': [
        'Umaru Musa Yaradua University (UMYU), Katsina',
        'Federal University, Dutsin-Ma',
        'Hassan Usman Katsina Polytechnic',
        'Isa Kaita College of Education, Dutsin-Ma',
    ],
    'Kebbi': [
        'Federal University, Birnin Kebbi',
        'Kebbi State University of Science and Technology, Aliero',
        'Kebbi State Polytechnic, Dakingari',
        'Federal College of Education (Technical), Gusau',
    ],
    'Kogi': [
        'Kogi State University (KSU), Anyigba',
        'Federal University, Lokoja',
        'Crown Polytechnic, Ado-Ekiti',
        'Kogi State Polytechnic, Lokoja',
        'Federal College of Education, Okene',
    ],
    'Kwara': [
        'University of Ilorin (UNILORIN)',
        'Kwara State University, Malete',
        'Landmark University, Omu-Aran',
        'Al-Hikmah University, Ilorin',
        'Kwara State Polytechnic, Ilorin',
        'Kwara State College of Education, Ilorin',
    ],
    'Lagos': [
        'University of Lagos (UNILAG)',
        'Lagos State University (LASU)',
        'Lagos State University of Science and Technology (LASUSTECH)',
        'Pan-Atlantic University, Lagos',
        'Yaba College of Technology (YABATECH)',
        'Lagos State Polytechnic, Ikorodu',
        'Federal College of Education (Technical), Akoka',
        'Nigerian Institute of Journalism (NIJ)',
        'Lagos Business School',
    ],
    'Nasarawa': [
        'Nasarawa State University (NSUK), Keffi',
        'Federal University of Lafia',
        'Nasarawa State Polytechnic, Lafia',
        'College of Agriculture, Lafia',
    ],
    'Niger': [
        'Federal University of Technology, Minna (FUTMINNA)',
        'Ibrahim Badamasi Babangida University, Lapai',
        'Niger State University, Minna',
        'Federal Polytechnic, Bida',
        'Niger State Polytechnic, Zungeru',
    ],
    'Ogun': [
        'Olabisi Onabanjo University (OOU), Ago-Iwoye',
        'Federal University of Agriculture, Abeokuta (FUNAAB)',
        'Babcock University, Ilishan-Remo',
        'Covenant University, Ota',
        'Crawford University, Faith City',
        'Moshood Abiola Polytechnic, Abeokuta',
        'Gateway Polytechnic, Saapade',
    ],
    'Ondo': [
        'Federal University of Technology, Akure (FUTA)',
        'Adekunle Ajasin University (AAUA), Akungba-Akoko',
        'Ondo State University of Science and Technology',
        'Elizade University, Ilara-Mokin',
        'Rufus Giwa Polytechnic, Owo',
    ],
    'Osun': [
        'Obafemi Awolowo University (OAU/UNIFE), Ile-Ife',
        'Osun State University (UNIOSUN)',
        'Redeemers University, Ede',
        'LAUTECH, Ogbomoso',
        'Osun State College of Technology, Esa-Oke',
    ],
    'Oyo': [
        'University of Ibadan (UI)',
        'Lead City University, Ibadan',
        'The Polytechnic, Ibadan',
        'Ladoke Akintola University of Technology (LAUTECH), Ogbomoso',
        'Oyo State College of Agriculture, Igboora',
        'Nigerian College of Aviation Technology (NCAT), Zaria',
    ],
    'Plateau': [
        'University of Jos (UNIJOS)',
        'Plateau State University, Bokkos',
        'Federal College of Education, Pankshin',
        'Plateau State Polytechnic, Barkin Ladi',
    ],
    'Rivers': [
        'University of Port Harcourt (UNIPORT)',
        'Rivers State University (RSU)',
        'Ken Saro-Wiwa Polytechnic, Bori',
        'Ignatius Ajuru University of Education, Port Harcourt',
        'Captain Elechi Amadi Polytechnic, Port Harcourt',
    ],
    'Sokoto': [
        'Usmanu Danfodiyo University, Sokoto (UDUS)',
        'Sokoto State University',
        'Federal Polytechnic, Kaura Namoda',
        'Sokoto State Polytechnic',
    ],
    'Taraba': [
        'Taraba State University, Jalingo',
        'Federal University, Wukari',
        'College of Agriculture, Science and Technology, Jalingo',
    ],
    'Yobe': [
        'Federal University, Gashua',
        'Yobe State University (YSU), Damaturu',
        'Federal Polytechnic, Damaturu',
        'College of Agriculture, Gujba',
    ],
    'Zamfara': [
        'Federal University, Gusau',
        'Zamfara State University',
        'Zamfara State Polytechnic',
        'Federal College of Education (Technical), Gusau',
    ],
}

# Nigerian Banks
NIGERIAN_BANKS = [
    'Access Bank', 'Citibank Nigeria', 'Ecobank Nigeria',
    'Fidelity Bank', 'First Bank of Nigeria', 'First City Monument Bank (FCMB)',
    'Globus Bank', 'Guaranty Trust Bank (GTBank)', 'Heritage Bank',
    'Jaiz Bank', 'Keystone Bank', 'Lotus Bank',
    'Optimus Bank', 'Parallex Bank', 'Polaris Bank',
    'Premium Trust Bank', 'Providus Bank', 'Signature Bank',
    'Stanbic IBTC Bank', 'Standard Chartered Bank', 'Sterling Bank',
    'SunTrust Bank', 'Titan Trust Bank', 'Union Bank of Nigeria',
    'United Bank for Africa (UBA)', 'Unity Bank', 'Wema Bank',
    'Zenith Bank',
]


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
        phone     = f.get('phone_number', '').strip()

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
            return render_template('register.html',
                states=NIGERIAN_STATES,
                schools=NIGERIAN_SCHOOLS,
                banks=NIGERIAN_BANKS,
                form=f)

        user = User(
            full_name=full_name, email=email,
            phone_number=phone or None,
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

        user.institution_tag = school
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html',
        states=NIGERIAN_STATES,
        schools=NIGERIAN_SCHOOLS,
        banks=NIGERIAN_BANKS,
        form={})


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
    user = db.session.get(User, user_id) or db.session.query(User).filter_by(id=user_id).first_or_404()
    blocked_by_me = Block.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    blocked_me    = Block.query.filter_by(blocker_id=user_id, blocked_id=current_user.id).first()
    is_friend     = current_user.is_friends_with(user) if user.id != current_user.id else False
    req_sent      = current_user.friend_request_sent_to(user) if user.id != current_user.id else None
    req_recv      = FriendRequest.query.filter_by(
        sender_id=user_id, receiver_id=current_user.id, status='pending'
    ).first()

    posts = db.session.query(Post).filter_by(
        user_id=user_id, status='approved'
    ).order_by(Post.created_at.desc()).limit(15).all()

    return render_template('profile.html',
        profile_user=user,
        is_blocked=blocked_by_me, blocked_me=blocked_me,
        is_friend=is_friend, req_sent=req_sent, req_recv=req_recv,
        posts=posts)


@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    from models import ScholarshipApplication
    if request.method == 'POST':
        current_user.bio = request.form.get('bio', '').strip() or None
        current_user.town_lga = request.form.get('town_lga', '').strip() or None
        current_user.faculty = request.form.get('faculty', '').strip() or None
        current_user.department = request.form.get('department', '').strip() or None
        current_user.residential_address = request.form.get('residential_address', '').strip() or None
        current_user.phone_number = request.form.get('phone_number', '').strip() or None

        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and file.filename and allowed_file(file.filename):
                ext  = file.filename.rsplit('.', 1)[1].lower()
                fname = secure_filename(f'u{current_user.id}_{secrets.token_hex(4)}.{ext}')
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
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

    scholarship = db.session.query(ScholarshipApplication).filter_by(
        user_id=current_user.id
    ).first()
    return render_template('edit_profile.html',
        states=NIGERIAN_STATES,
        schools=NIGERIAN_SCHOOLS,
        banks=NIGERIAN_BANKS,
        scholarship=scholarship)


@auth_bp.route('/scholarship', methods=['POST'])
@login_required
def submit_scholarship():
    from models import ScholarshipApplication
    bank_name      = request.form.get('bank_name', '').strip()
    account_number = request.form.get('account_number', '').strip()
    account_name   = request.form.get('account_name', '').strip()

    if not all([bank_name, account_number, account_name]):
        flash('Please fill in all banking fields.', 'danger')
        return redirect(url_for('auth.edit_profile'))

    existing = db.session.query(ScholarshipApplication).filter_by(
        user_id=current_user.id
    ).first()
    if existing:
        existing.bank_name      = bank_name
        existing.account_number = account_number
        existing.account_name   = account_name
    else:
        app_obj = ScholarshipApplication(
            user_id=current_user.id,
            bank_name=bank_name,
            account_number=account_number,
            account_name=account_name
        )
        db.session.add(app_obj)
    db.session.commit()
    flash('Scholarship registration saved! We will notify you when a scholarship is available.', 'success')
    return redirect(url_for('auth.edit_profile'))


@auth_bp.route('/settings/theme', methods=['POST'])
@login_required
def toggle_theme():
    current_user.dark_mode = not current_user.dark_mode
    db.session.commit()
    return redirect(request.referrer or url_for('main.dashboard'))
