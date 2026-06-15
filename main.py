"""
NSDCP — Main Blueprint
Dashboard, feed, search, notifications
SQLAlchemy 2.x compatible
"""
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
    friend_ids = [f.id for f in current_user.friends] + [current_user.id]

    posts = db.session.query(Post).filter(
        Post.status == 'approved',
        db.or_(Post.is_announcement == True, Post.user_id.in_(friend_ids))
    ).order_by(Post.pinned.desc(), Post.created_at.desc()).limit(30).all()

    polls = db.session.query(Poll).filter(
        Poll.is_active == True,
        Poll.ends_at > datetime.utcnow()
    ).order_by(Poll.created_at.desc()).limit(5).all()

    friend_reqs = db.session.query(FriendRequest).filter_by(
        receiver_id=current_user.id, status='pending'
    ).order_by(FriendRequest.created_at.desc()).all()

    group_invites = db.session.query(GroupInvite).filter_by(
        invited_user_id=current_user.id, status='pending'
    ).all()

    # SA 2.x: use method from model instead of lazy dynamic
    notifications = current_user.get_recent_notifications(12)

    pending_posts_count = 0
    if current_user.role == 'admin':
        pending_posts_count = db.session.query(Post).filter_by(status='pending').count()

    blocked_ids = [b.blocked_id for b in
                   db.session.query(Block).filter_by(blocker_id=current_user.id).all()]
    blocked_ids += [b.blocker_id for b in
                    db.session.query(Block).filter_by(blocked_id=current_user.id).all()]

    suggestions = db.session.query(User).filter(
        User.id != current_user.id,
        User.school_name == current_user.school_name,
        ~User.id.in_(friend_ids),
        ~User.id.in_(blocked_ids) if blocked_ids else db.true(),
        User.is_suspended == False
    ).limit(5).all()

    return render_template('dashboard.html',
        posts=posts, polls=polls,
        friend_reqs=friend_reqs, group_invites=group_invites,
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
        results = db.session.query(User).filter(
            db.or_(User.full_name.ilike(f'%{q}%'), User.school_name.ilike(f'%{q}%')),
            User.is_suspended == False
        ).limit(20).all()
    return render_template('search.html', results=results, query=q)


@main_bp.route('/notifications/read/<int:nid>')
@login_required
def read_notification(nid):
    n = db.session.query(Notification).filter_by(
        id=nid, user_id=current_user.id
    ).first_or_404()
    n.is_read = True
    db.session.commit()
    return redirect(n.link or url_for('main.dashboard'))


@main_bp.route('/notifications/read-all')
@login_required
def read_all_notifications():
    # SA 2.x compatible update
    db.session.query(Notification).filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return redirect(url_for('main.dashboard'))


def push_notification(user_id, notif_type, message, link=''):
    """Helper used by all blueprints."""
    n = Notification(user_id=user_id, type=notif_type, message=message, link=link)
    db.session.add(n)
