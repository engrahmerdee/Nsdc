"""
NSDCP — Nigerian Student Digital Community Platform
Database Models
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from flask_bcrypt import Bcrypt
from cryptography.fernet import Fernet
import os, base64

db = SQLAlchemy()
bcrypt = Bcrypt()

# ─── Encryption helpers ───────────────────────────────────────────────────────
def _fernet():
    key = os.environ.get('FERNET_KEY', '')
    if not key:
        key = base64.urlsafe_b64encode(os.urandom(32)).decode()
    if isinstance(key, str):
        key = key.encode()
    return Fernet(key)

def encrypt_field(val):
    if not val:
        return None
    try:
        return _fernet().encrypt(val.encode()).decode()
    except Exception:
        return None

def decrypt_field(val):
    if not val:
        return None
    try:
        return _fernet().decrypt(val.encode()).decode()
    except Exception:
        return None


# ─── Association Tables ───────────────────────────────────────────────────────
friendship = db.Table('friendships',
    db.Column('user_id',   db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('friend_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
)

group_members = db.Table('group_members',
    db.Column('user_id',  db.Integer, db.ForeignKey('user.id'),  primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('group.id'), primary_key=True),
    db.Column('role',     db.String(20), default='member'),      # owner/admin/member
    db.Column('joined_at', db.DateTime, default=datetime.utcnow),
)


# ─── User ─────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    id                  = db.Column(db.Integer, primary_key=True)
    full_name           = db.Column(db.String(120), nullable=False)
    email               = db.Column(db.String(120), unique=True, nullable=False)
    password_hash       = db.Column(db.String(256), nullable=False)
    date_of_birth       = db.Column(db.Date)
    state_of_origin     = db.Column(db.String(60))
    town_lga            = db.Column(db.String(100))
    school_name         = db.Column(db.String(150))
    faculty             = db.Column(db.String(100))
    department          = db.Column(db.String(100))
    residential_address = db.Column(db.Text)
    profile_pic         = db.Column(db.String(200), default='default.png')
    bio                 = db.Column(db.Text)

    # Encrypted sensitive fields
    _nin                = db.Column('nin', db.Text)
    _school_reg         = db.Column('school_reg', db.Text)

    # Role & Rank
    role                = db.Column(db.String(50), default='student')
    # admin / president / vice_president / representative / group_admin / student
    role_title          = db.Column(db.String(200))  # "President – FUTB"
    institution_tag     = db.Column(db.String(150))  # stored display tag

    # Verification & Trust
    verification_level  = db.Column(db.Integer, default=0)  # 0/1/2
    trust_level         = db.Column(db.String(20), default='new')  # new/verified/trusted
    is_suspended        = db.Column(db.Boolean, default=False)
    email_verified      = db.Column(db.Boolean, default=False)
    email_token         = db.Column(db.String(100))
    dark_mode           = db.Column(db.Boolean, default=False)

    # Timestamps
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen           = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Relationships ──
    posts               = db.relationship('Post', backref='author', lazy='dynamic', foreign_keys='Post.user_id')
    comments            = db.relationship('Comment', backref='author', lazy='dynamic')
    votes               = db.relationship('Vote', backref='voter', lazy='dynamic')
    sent_requests       = db.relationship('FriendRequest', foreign_keys='FriendRequest.sender_id', backref='sender', lazy='dynamic')
    received_requests   = db.relationship('FriendRequest', foreign_keys='FriendRequest.receiver_id', backref='receiver', lazy='dynamic')
    sent_messages       = db.relationship('PrivateMessage', foreign_keys='PrivateMessage.sender_id', backref='sender', lazy='dynamic')
    notifications       = db.relationship('Notification', foreign_keys='Notification.user_id', backref='user', lazy='dynamic')
    reports_made        = db.relationship('Report', foreign_keys='Report.reporter_id', backref='reporter', lazy='dynamic')
    activity_logs       = db.relationship('AdminLog', foreign_keys='AdminLog.actor_id', backref='actor', lazy='dynamic')
    group_invites_sent  = db.relationship('GroupInvite', foreign_keys='GroupInvite.invited_by', backref='inviter', lazy='dynamic')

    friends = db.relationship('User', secondary=friendship,
        primaryjoin=(friendship.c.user_id == id),
        secondaryjoin=(friendship.c.friend_id == id),
        lazy='dynamic')

    # ── Encrypted properties ──
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

    def set_password(self, pw):
        self.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')

    def check_password(self, pw):
        return bcrypt.check_password_hash(self.password_hash, pw)

    def is_friends_with(self, user):
        return self.friends.filter(friendship.c.friend_id == user.id).count() > 0

    def friend_request_sent_to(self, user):
        return FriendRequest.query.filter_by(sender_id=self.id, receiver_id=user.id, status='pending').first()

    def unread_notifications_count(self):
        return self.notifications.filter_by(is_read=False).count()

    def unread_messages_count(self):
        return PrivateMessage.query.filter_by(receiver_id=self.id, is_read=False).count()

    @property
    def display_name(self):
        """Privacy-safe display: First name + School"""
        first = self.full_name.split()[0] if self.full_name else 'User'
        school = self.school_name or 'Unknown School'
        return f"{first} from {school}"

    @property
    def display_with_role(self):
        """First Name (Role – Institution)"""
        first = self.full_name.split()[0] if self.full_name else 'User'
        if self.role_title:
            return f"{first} ({self.role_title})"
        role_label = self.role.replace('_', ' ').title()
        school = self.school_name or ''
        return f"{first} ({role_label}{' – ' + school if school else ''})"

    @property
    def verification_label(self):
        return {0: 'Unverified', 1: 'Partially Verified', 2: 'Fully Verified'}.get(self.verification_level, 'Unknown')

    @property
    def can_post(self):
        return self.role in ('admin', 'president', 'vice_president', 'representative') and not self.is_suspended

    @property
    def has_full_access(self):
        return self.verification_level >= 1 or self.role == 'admin'

    def __repr__(self):
        return f'<User {self.email}>'


# ─── Post (Moderated) ─────────────────────────────────────────────────────────
class Post(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    title            = db.Column(db.String(200))
    content          = db.Column(db.Text, nullable=False)
    image            = db.Column(db.String(200))
    user_id          = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    # Moderation
    status           = db.Column(db.String(20), default='pending')  # pending/approved/rejected
    approved_by      = db.Column(db.Integer, db.ForeignKey('user.id'))
    approved_at      = db.Column(db.DateTime)
    reject_reason    = db.Column(db.Text)
    # Settings
    comments_enabled = db.Column(db.Boolean, default=True)
    is_announcement  = db.Column(db.Boolean, default=False)
    pinned           = db.Column(db.Boolean, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    approver         = db.relationship('User', foreign_keys=[approved_by])
    comments         = db.relationship('Comment', backref='post', lazy='dynamic', cascade='all, delete-orphan')
    likes            = db.relationship('Like', backref='post', lazy='dynamic', cascade='all, delete-orphan')

    def likes_count(self):
        return self.likes.count()

    def comments_count(self):
        return self.comments.filter_by(is_deleted=False).count()


# ─── Comment (Privacy-safe display) ──────────────────────────────────────────
class Comment(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    content     = db.Column(db.Text, nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id     = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    is_deleted  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


class Like(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id    = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    __table_args__ = (db.UniqueConstraint('user_id', 'post_id'),)


# ─── Group ────────────────────────────────────────────────────────────────────
class Group(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    name         = db.Column(db.String(120), nullable=False)
    description  = db.Column(db.Text)
    avatar       = db.Column(db.String(200), default='group_default.png')
    school_tag   = db.Column(db.String(150))
    creator_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    trust_level  = db.Column(db.String(20), default='new')  # new/verified/trusted/flagged
    is_frozen    = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    creator      = db.relationship('User', backref='created_groups')
    members      = db.relationship('User', secondary=group_members, lazy='dynamic',
                      primaryjoin=(group_members.c.group_id == id))
    messages     = db.relationship('GroupMessage', backref='group', lazy='dynamic', cascade='all, delete-orphan')
    invites      = db.relationship('GroupInvite', backref='group', lazy='dynamic', cascade='all, delete-orphan')

    def member_count(self):
        return self.members.count()

    def get_member_role(self, user_id):
        row = db.session.execute(
            group_members.select().where(
                (group_members.c.group_id == self.id) &
                (group_members.c.user_id == user_id)
            )
        ).first()
        return row.role if row else None


class GroupInvite(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    invited_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invited_by  = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status      = db.Column(db.String(20), default='pending')  # pending/accepted/rejected
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    invited_user = db.relationship('User', foreign_keys=[invited_user_id], backref='group_invites_received')


class GroupMessage(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    group_id    = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content     = db.Column(db.Text, nullable=False)
    is_reported = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    sender      = db.relationship('User', backref='group_messages_sent')


# ─── Private Messaging ────────────────────────────────────────────────────────
class PrivateMessage(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content     = db.Column(db.Text, nullable=False)
    is_read     = db.Column(db.Boolean, default=False)
    is_reported = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    receiver    = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')


# ─── Poll & Voting ────────────────────────────────────────────────────────────
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

    creator     = db.relationship('User', backref='polls')
    options     = db.relationship('PollOption', backref='poll', lazy='dynamic', cascade='all, delete-orphan')
    votes       = db.relationship('Vote', backref='poll', lazy='dynamic', cascade='all, delete-orphan')

    @property
    def is_open(self):
        return self.is_active and datetime.utcnow() < self.ends_at

    def total_votes(self):
        return self.votes.count()


class PollOption(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    poll_id  = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    text     = db.Column(db.String(200), nullable=False)
    votes    = db.relationship('Vote', backref='option', lazy='dynamic')

    def vote_count(self):
        return self.votes.count()

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


# ─── Social ───────────────────────────────────────────────────────────────────
class FriendRequest(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status      = db.Column(db.String(20), default='pending')  # pending/accepted/rejected
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
    # friend_request/message/group_invite/post_approved/post_rejected/poll/announcement/verification
    message    = db.Column(db.String(300))
    link       = db.Column(db.String(200))
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Report(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    reporter_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type             = db.Column(db.String(30))  # user/post/group_message/private_message
    reason           = db.Column(db.String(100))  # abuse/spam/fake/inappropriate
    details          = db.Column(db.Text)
    ref_id           = db.Column(db.Integer)     # post_id / message_id etc
    status           = db.Column(db.String(20), default='pending')  # pending/reviewed/resolved
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    reported_user    = db.relationship('User', foreign_keys=[reported_user_id], backref='reports_against')


# ─── Admin Activity Log ───────────────────────────────────────────────────────
class AdminLog(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    actor_id   = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action     = db.Column(db.String(100))
    target     = db.Column(db.String(200))
    details    = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
