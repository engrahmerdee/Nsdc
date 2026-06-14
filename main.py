from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, request
from flask_login import login_required, current_user
from models import db, User, Post, Poll, Notification, FriendRequest, Block, GroupInvite

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('index.html')


@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Feed: approved posts only (announcements + friends' posts)
    friend_ids = [f.id for f in current_user.friends] + [current_user.id]

    posts = Post.query.filter(
        Post.status == 'approved',
        (Post.is_announcement == True) | (Post.user_id.in_(friend_ids))
    ).order_by(Post.pinned.desc(), Post.created_at.desc()).limit(30).all()

    # Active polls
    polls = Poll.query.filter(
        Poll.is_active == True, Poll.ends_at > datetime.utcnow()
    ).order_by(Poll.created_at.desc()).limit(5).all()

    # Pending friend requests
    friend_reqs = FriendRequest.query.filter_by(
        receiver_id=current_user.id, status='pending'
    ).order_by(FriendRequest.created_at.desc()).all()

    # Pending group invites
    group_invites = GroupInvite.query.filter_by(
        invited_user_id=current_user.id, status='pending'
    ).all()

    # Notifications — use Query directly (not dynamic relationship)
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(12).all()

    # Posts pending review (only admin)
    pending_posts_count = 0
    if current_user.role == 'admin':
        pending_posts_count = Post.query.filter_by(status='pending').count()

    # People you may know (same school)
    blocked_ids = [b.blocked_id for b in Block.query.filter_by(blocker_id=current_user.id).all()]
    blocked_ids += [b.blocker_id for b in Block.query.filter_by(blocked_id=current_user.id).all()]
    suggestions = User.query.filter(
        User.id != current_user.id,
        User.school_name == current_user.school_name,
        ~User.id.in_(friend_ids),
        ~User.id.in_(blocked_ids),
        User.is_suspended == False
    ).limit(5).all()

    return render_template('dashboard.html',
        posts=posts,
        polls=polls,
        friend_reqs=friend_reqs,
        group_invites=group_invites,
        notifications=notifications,
        pending_posts_count=pending_posts_count,
        suggestions=suggestions,
        now=datetime.utcnow()
    )


@main_bp.route('/search')
@login_required
def search():
    q = request.args.get('q', '').strip()
    results = []
    if q:
        results = User.query.filter(
            (User.full_name.ilike(f'%{q}%')) | (User.school_name.ilike(f'%{q}%')),
            User.is_suspended == False
        ).limit(20).all()
    return render_template('search.html', results=results, query=q)


@main_bp.route('/notifications/read/<int:nid>')
@login_required
def read_notification(nid):
    n = Notification.query.filter_by(id=nid, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return redirect(n.link or url_for('main.dashboard'))


@main_bp.route('/notifications/read-all')
@login_required
def read_all_notifications():
    # SQLAlchemy 2.x: use Query.update() with synchronize_session=False
    # (Cannot use dynamic relationship .update() — it's removed in 2.x)
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True}, synchronize_session=False)
    db.session.commit()
    return redirect(url_for('main.dashboard'))


# ── Helpers ───────────────────────────────────────────────────────────────────
def push_notification(user_id, notif_type, message, link=''):
    from models import Notification
    n = Notification(user_id=user_id, type=notif_type, message=message, link=link)
    db.session.add(n)
