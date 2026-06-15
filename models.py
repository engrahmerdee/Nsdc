"""
NSDCP — Nigerian Student Digital Community Platform
Database Models — SQLAlchemy 2.x Compatible
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
import os, hashlib

db = SQLAlchemy()
bcrypt = Bcrypt()

# ── Simple XOR-based encryption (no cryptography package needed) ──────────────
def _get_key():
    key = os.environ.get('ENCRYPT_KEY', 'nsdcp-default-key-change-in-prod')
    return hashlib.sha256(key.encode()).digest()

def encrypt_field(val):
    if not val:
        return None
    try:
        import base64
        key = _get_key()
        data = val.encode('utf-8')
        encrypted = bytes([data[i] ^ key[i % len(key)] for i in range(len(data))])
        return base64.urlsafe_b64encode(encrypted).decode('utf-8')
    except Exception:
        return None

def decrypt_field(val):
    if not val:
        return None
    try:
        import base64
        key = _get_key()
        encrypted = base64.urlsafe_b64decode(val.encode('utf-8'))
        decrypted = bytes([encrypted[i] ^ key[i % len(key)] for i in range(len(encrypted))])
        return decrypted.decode('utf-8')
    except Exception:
        return None


# ── Association Tables ────────────────────────────────────────────────────────
friendship = db.Table('friendships',
    db.Column('user_id',   db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
)

group_members = db.Table('group_members',
    db.Column('user_id',   db.Integer, db.ForeignKey('user.id'),  primary_key=True),
    db.Column('group_id',  db.Integer, db.ForeignKey('group.id'), primary_key=True),
    db.Column('role',      db.String(20), default='member'),
    db.Column('joined_at', db.DateTime,   default=datetime.utcnow),
)


# ── User ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    full_name           = db.Column(db.String(120), nullable=False)
    email               = db.Column(db.String(120), unique=True, nullable=False)
    password_hash       = db.Column(db.String(256), nullable=False)
    phone_number        = db.Column(db.String(20))
    date_of_birth       = db.Column(db.Date)
    state_of_origin     = db.Column(db.String(60))
    town_lga            = db.Column(db.String(100))
    school_name         = db.Column(db.String(200))
    faculty             = db.Column(db.String(100))
    department          = db.Column(db.String(100))
    residential_address = db.Column(db.Text)
    profile_pic         = db.Column(db.String(200), default='default.png')
    bio                 = db.Column(db.Text)

    # Encrypted sensitive fields
    _nin                = db.Column('nin', db.Text)
    _school_reg         = db.Column('school_reg', db.Text)

    # Scholarship banking fields (admin-only visible)
    _bank_name          = db.Column('bank_name', db.Text)
    _account_number     = db.Column('account_number', db.Text)
    _account_name       = db.Column('account_name', db.Text)
    scholarship_applied = db.Column(db.Boolean, default=False)
    scholarship_notified = db.Column(db.Boolean, default=False)

    # Role & Rank
    role                = db.Column(db.String(50), default='student')
    role_title          = db.Column(db.String(200))
    institution_tag     = db.Column(db.String(150))

    # Verification & Trust
    verification_level  = db.Column(db.Integer, default=0)
    trust_level         = db.Column(db.String(20), default='new')
    is_suspended        = db.Column(db.Boolean, default=False)
    email_verified      = db.Column(db.Boolean, default=False)
    email_token         = db.Column(db.String(100))
    dark_mode           = db.Column(db.Boolean, default=False)

    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen           = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships — use select (SA 2.x compatible, not lazy='dynamic')
    posts               = db.relationship('Post', backref='author', lazy='select',
                              foreign_keys='Post.user_id')
    comments            = db.relationship('Comment', backref='author', lazy='select')
    votes               = db.relationship('Vote', backref='voter', lazy='select')
    sent_requests       = db.relationship('FriendRequest', foreign_keys='FriendRequest.sender_id',
                              backref='sender', lazy='select')
    received_requests   = db.relationship('FriendRequest', foreign_keys='FriendRequest.receiver_id',
                              backref='receiver', lazy='select')
    sent_messages       = db.relationship('PrivateMessage', foreign_keys='PrivateMessage.sender_id',
                              backref='sender', lazy='select')
    notifications       = db.relationship('Notification', foreign_keys='Notification.user_id',
                              backref='user', lazy='select',
                              order_by='Notification.created_at.desc()')
    reports_made        = db.relationship('Report', foreign_keys='Report.reporter_id',
                              backref='reporter', lazy='select')
    activity_logs       = db.relationship('AdminLog', foreign_keys='AdminLog.actor_id',
                              backref='actor', lazy='select')
    group_invites_sent  = db.relationship('GroupInvite', foreign_keys='GroupInvite.invited_by',
                              backref='inviter', lazy='select')

    friends = db.relationship('User', secondary=friendship,
        primaryjoin=(friendship.c.user_id == id),
        secondaryjoin=(friendship.c.friend_id == id),
        lazy='select')

    # Encrypted properties
    @property
    def nin(self):
        return decrypt_field(self._nin)
    @nin.setter
    def nin(self, val):
        self._nin = encrypt_field(val)

    @property
    def school_reg(self):
        return decrypt_field(self._school_reg)
    @school_reg.setter
    def school_reg(self, val):
        self._school_reg = encrypt_field(val)

    @property
    def bank_name(self):
        return decrypt_field(self._bank_name)
    @bank_name.setter
    def bank_name(self, val):
        self._bank_name = encrypt_field(val)

    @property
    def account_number(self):
        return decrypt_field(self._account_number)
    @account_number.setter
    def account_number(self, val):
        self._account_number = encrypt_field(val)

    @property
    def account_name(self):
        return decrypt_field(self._account_name)
    @account_name.setter
    def account_name(self, val):
        self._account_name = encrypt_field(val)

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    def is_friends_with(self, user):
        return any(f.id == user.id for f in self.friends)

    def friend_request_sent_to(self, user):
        return FriendRequest.query.filter_by(
            sender_id=self.id, receiver_id=user.id, status='pending'
        ).first()

    def unread_notifications_count(self):
        return db.session.query(Notification).filter_by(
            user_id=self.id, is_read=False
        ).count()

    def unread_messages_count(self):
        return db.session.query(PrivateMessage).filter_by(
            receiver_id=self.id, is_read=False
        ).count()

    @property
    def display_name(self):
        first = self.full_name.split()[0] if self.full_name else 'User'
        school = self.school_name or 'Unknown School'
        return f"{first} from {school}"

    @property
    def display_with_role(self):
        first = self.full_name.split()[0] if self.full_name else 'User'
        if self.role_title:
            return f"{first} ({self.role_title})"
        role_label = self.role.replace('_', ' ').title()
        school = self.school_name or ''
        return f"{first} ({role_label}{' – ' + school if school else ''})"

    @property
    def verification_label(self):
        return {0: 'Unverified', 1: 'Partially Verified', 2: 'Fully Verified'}.get(
            self.verification_level, 'Unknown')

    @property
    def can_post(self):
        return self.role in ('admin', 'president', 'vice_president', 'representative') \
               and not self.is_suspended

    @property
    def has_full_access(self):
        return self.verification_level >= 1 or self.role == 'admin'

    def get_recent_notifications(self, limit=10):
        return db.session.query(Notification).filter_by(
            user_id=self.id
        ).order_by(Notification.created_at.desc()).limit(limit).all()

    def __repr__(self):
        return f'<User {self.email}>'


# ── Post ──────────────────────────────────────────────────────────────────────
class Post(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(200))
    content          = db.Column(db.Text, nullable=False)
    image            = db.Column(db.String(200))
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status           = db.Column(db.String(20), default='pending')
    approved_by      = db.Column(db.Integer, db.ForeignKey('user.id'))
    approved_at      = db.Column(db.DateTime)
    reject_reason    = db.Column(db.Text)
    comments_enabled = db.Column(db.Boolean, default=True)
    is_announcement  = db.Column(db.Boolean, default=False)
    pinned           = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approver = db.relationship('User', foreign_keys=[approved_by])
    comments = db.relationship('Comment', backref='post', lazy='select',
                   cascade='all, delete-orphan')
    likes    = db.relationship('Like', backref='post', lazy='select',
                   cascade='all, delete-orphan')

    def likes_count(self):
        return db.session.query(Like).filter_by(post_id=self.id).count()

    def comments_count(self):
        return db.session.query(Comment).filter_by(post_id=self.id, is_deleted=False).count()


class Comment(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text, nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Like(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)


# ── Group ─────────────────────────────────────────────────────────────────────
class Group(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    avatar      = db.Column(db.String(200), default='group_default.png')
    school_tag  = db.Column(db.String(150))
    creator_id  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trust_level = db.Column(db.String(20), default='new')
    is_frozen   = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    creator  = db.relationship('User', backref='created_groups')
    members  = db.relationship('User', secondary=group_members, lazy='select',
                   primaryjoin=(group_members.c.group_id == id))
    messages = db.relationship('GroupMessage', backref='group', lazy='select',
                   cascade='all, delete-orphan')
    invites  = db.relationship('GroupInvite', backref='group', lazy='select',
                   cascade='all, delete-orphan')

    def member_count(self):
        return db.session.query(group_members).filter(
            group_members.c.group_id == self.id
        ).count()

    def get_member_role(self, user_id):
        row = db.session.execute(
            group_members.select().where(
                (group_members.c.group_id == self.id) &
                (group_members.c.user_id == user_id)
            )
        ).first()
        return row.role if row else None


class GroupInvite(db.Model):
    id              = db.Column(db.Integer, primary_key=True)
    group_id        = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    invited_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invited_by      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status          = db.Column(db.String(20), default='pending')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    invited_user = db.relationship('User', foreign_keys=[invited_user_id],
                       backref='group_invites_received')


class GroupMessage(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content     = db.Column(db.Text, nullable=False)
    is_reported = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', backref='group_messages_sent')


# ── Private Messaging ─────────────────────────────────────────────────────────
class PrivateMessage(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content     = db.Column(db.Text, nullable=False)
    is_read     = db.Column(db.Boolean, default=False)
    is_reported = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    receiver = db.relationship('User', foreign_keys=[receiver_id],
                   backref='received_messages')


# ── Poll ──────────────────────────────────────────────────────────────────────
class Poll(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    question    = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    starts_at   = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at     = db.Column(db.DateTime, nullable=False)
    show_live   = db.Column(db.Boolean, default=True)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='polls')
    options = db.relationship('PollOption', backref='poll', lazy='select',
                  cascade='all, delete-orphan')
    votes   = db.relationship('Vote', backref='poll', lazy='select',
                  cascade='all, delete-orphan')

    @property
    def is_open(self):
        return self.is_active and datetime.utcnow() < self.ends_at

    def total_votes(self):
        return db.session.query(Vote).filter_by(poll_id=self.id).count()


class PollOption(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    text    = db.Column(db.String(200), nullable=False)
    votes   = db.relationship('Vote', backref='option', lazy='select')

    def vote_count(self):
        return db.session.query(Vote).filter_by(option_id=self.id).count()

    def percentage(self, total):
        if total == 0:
            return 0
        return round((self.vote_count() / total) * 100, 1)


class Vote(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    poll_id      = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    option_id    = db.Column(db.Integer, db.ForeignKey('poll_option.id'), nullable=False)
    change_count = db.Column(db.Integer, default=0)
    is_locked    = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'poll_id'),)


# ── Social ────────────────────────────────────────────────────────────────────
class FriendRequest(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status      = db.Column(db.String(20), default='pending')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('sender_id', 'receiver_id'),)


class Block(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    blocker_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    blocked_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('blocker_id', 'blocked_id'),)


class Notification(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type       = db.Column(db.String(50))
    message    = db.Column(db.String(300))
    link       = db.Column(db.String(200))
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    reporter_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type             = db.Column(db.String(30))
    reason           = db.Column(db.String(100))
    details          = db.Column(db.Text)
    ref_id           = db.Column(db.Integer)
    status           = db.Column(db.String(20), default='pending')
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    reported_user = db.relationship('User', foreign_keys=[reported_user_id],
                        backref='reports_against')


class AdminLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    actor_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action     = db.Column(db.String(100))
    target     = db.Column(db.String(200))
    details    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ── Scholarship Application ───────────────────────────────────────────────────
class ScholarshipApplication(db.Model):
    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    bank_name      = db.Column(db.String(100))
    account_number = db.Column(db.String(20))
    account_name   = db.Column(db.String(120))
    status         = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    submitted_at   = db.Column(db.DateTime, default=datetime.utcnow)
    notified_at    = db.Column(db.DateTime)
    admin_notes    = db.Column(db.Text)

    user = db.relationship('User', backref=db.backref('scholarship_app', uselist=False))
