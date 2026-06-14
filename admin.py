from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, User, Post, Poll, Report, Group, Notification, AdminLog, GroupMessage, PrivateMessage
from main import push_notification

admin_bp = Blueprint('admin', __name__)

ROLES = ['student', 'representative', 'vice_president', 'president', 'group_admin', 'admin']
TRUST_LEVELS = ['new', 'verified', 'trusted', 'flagged']
GROUP_TRUST = ['new', 'verified', 'trusted', 'flagged']


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def log_action(action, target='', details=''):
    entry = AdminLog(actor_id=current_user.id, action=action, target=target, details=details)
    db.session.add(entry)


# ── Dashboard ─────────────────────────────────────────────────────────────────
@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'users':       User.query.count(),
        'verified':    User.query.filter_by(verification_level=2).count(),
        'posts':       Post.query.filter_by(status='approved').count(),
        'pending':     Post.query.filter_by(status='pending').count(),
        'polls':       Poll.query.count(),
        'reports':     Report.query.filter_by(status='pending').count(),
        'groups':      Group.query.count(),
        'suspended':   User.query.filter_by(is_suspended=True).count(),
    }
    recent_users   = User.query.order_by(User.created_at.desc()).limit(8).all()
    pending_posts  = Post.query.filter_by(status='pending').order_by(Post.created_at.desc()).limit(6).all()
    pending_reports = Report.query.filter_by(status='pending').order_by(Report.created_at.desc()).limit(6).all()
    recent_logs    = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
        stats=stats, recent_users=recent_users,
        pending_posts=pending_posts, pending_reports=pending_reports,
        recent_logs=recent_logs)


# ── Post Moderation ───────────────────────────────────────────────────────────
@admin_bp.route('/posts/review')
@login_required
@admin_required
def review_posts():
    filter_status = request.args.get('status', 'pending')
    posts = Post.query.filter_by(status=filter_status).order_by(Post.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts, filter_status=filter_status)


@admin_bp.route('/posts/<int:post_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_post(post_id):
    post = Post.query.get_or_404(post_id)
    post.status = 'approved'
    post.approved_by = current_user.id
    post.approved_at = datetime.utcnow()
    log_action('approve_post', f'Post #{post_id}', post.title or post.content[:60])
    push_notification(post.user_id, 'post_approved',
        f'✅ Your post "{post.title or post.content[:50]}" has been approved.',
        url_for('posts.view', post_id=post_id))
    db.session.commit()
    flash('Post approved and published.', 'success')
    return redirect(url_for('admin.review_posts'))


@admin_bp.route('/posts/<int:post_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_post(post_id):
    post = Post.query.get_or_404(post_id)
    reason = request.form.get('reason', 'Does not meet community guidelines.')
    post.status = 'rejected'
    post.reject_reason = reason
    log_action('reject_post', f'Post #{post_id}', reason)
    push_notification(post.user_id, 'post_rejected',
        f'❌ Your post was not approved. Reason: {reason}',
        url_for('main.dashboard'))
    db.session.commit()
    flash('Post rejected.', 'info')
    return redirect(url_for('admin.review_posts'))


@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    log_action('delete_post', f'Post #{post_id}')
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'info')
    return redirect(url_for('admin.review_posts'))


@admin_bp.route('/posts/<int:post_id>/toggle-comments', methods=['POST'])
@login_required
@admin_required
def toggle_comments(post_id):
    post = Post.query.get_or_404(post_id)
    post.comments_enabled = not post.comments_enabled
    db.session.commit()
    return redirect(request.referrer or url_for('posts.view', post_id=post_id))


# ── User Management ───────────────────────────────────────────────────────────
@admin_bp.route('/users')
@login_required
@admin_required
def users():
    q      = request.args.get('q', '')
    school = request.args.get('school', '')
    role   = request.args.get('role', '')
    trust  = request.args.get('trust', '')
    q_obj  = User.query
    if q:      q_obj = q_obj.filter((User.full_name.ilike(f'%{q}%')) | (User.email.ilike(f'%{q}%')))
    if school: q_obj = q_obj.filter(User.school_name.ilike(f'%{school}%'))
    if role:   q_obj = q_obj.filter_by(role=role)
    if trust:  q_obj = q_obj.filter_by(trust_level=trust)
    users = q_obj.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users,
        roles=ROLES, trust_levels=TRUST_LEVELS, q=q, school=school, sel_role=role, sel_trust=trust)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    user = User.query.get_or_404(user_id)
    reports = Report.query.filter_by(reported_user_id=user_id).order_by(Report.created_at.desc()).limit(10).all()
    posts = Post.query.filter_by(user_id=user_id).order_by(Post.created_at.desc()).limit(10).all()
    return render_template('admin/user_detail.html', user=user, roles=ROLES,
        trust_levels=TRUST_LEVELS, reports=reports, posts=posts)


@admin_bp.route('/users/<int:user_id>/set-role', methods=['POST'])
@login_required
@admin_required
def set_role(user_id):
    user = User.query.get_or_404(user_id)
    role  = request.form.get('role')
    title = request.form.get('role_title', '').strip()
    if role not in ROLES:
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    old_role = user.role
    user.role = role
    user.role_title = title or None
    log_action('set_role', user.email, f'{old_role} → {role} | {title}')
    push_notification(user_id, 'verification',
        f'🎖️ Your role has been updated to: {title or role.replace("_"," ").title()}',
        url_for('auth.profile', user_id=user_id))
    db.session.commit()
    flash(f'Role updated for {user.full_name.split()[0]}.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/set-trust', methods=['POST'])
@login_required
@admin_required
def set_trust(user_id):
    user = User.query.get_or_404(user_id)
    trust = request.form.get('trust_level')
    if trust not in TRUST_LEVELS:
        flash('Invalid trust level.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    user.trust_level = trust
    log_action('set_trust', user.email, trust)
    db.session.commit()
    flash('Trust level updated.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/verify', methods=['POST'])
@login_required
@admin_required
def verify_user(user_id):
    user  = User.query.get_or_404(user_id)
    level = request.form.get('level', type=int, default=2)
    user.verification_level = level
    if level == 2:
        user.trust_level = 'verified'
    log_action('verify_user', user.email, f'Level {level}')
    push_notification(user_id, 'verification',
        f'✅ Your account has been verified (Level {level}: {user.verification_label}).',
        url_for('auth.profile', user_id=user_id))
    db.session.commit()
    flash(f'User verified at level {level}.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == 'admin':
        flash('Cannot suspend an admin.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    user.is_suspended = not user.is_suspended
    action = 'suspend' if user.is_suspended else 'unsuspend'
    log_action(action, user.email)
    db.session.commit()
    flash(f'User {"suspended" if user.is_suspended else "unsuspended"}.', 'info')
    return redirect(url_for('admin.user_detail', user_id=user_id))


# ── Groups ────────────────────────────────────────────────────────────────────
@admin_bp.route('/groups')
@login_required
@admin_required
def groups():
    filter_trust = request.args.get('trust', '')
    q_obj = Group.query
    if filter_trust:
        q_obj = q_obj.filter_by(trust_level=filter_trust)
    groups = q_obj.order_by(Group.created_at.desc()).all()
    return render_template('admin/groups.html', groups=groups, group_trust=GROUP_TRUST, sel_trust=filter_trust)


@admin_bp.route('/groups/<int:group_id>/set-trust', methods=['POST'])
@login_required
@admin_required
def set_group_trust(group_id):
    group = Group.query.get_or_404(group_id)
    trust = request.form.get('trust_level')
    if trust not in GROUP_TRUST:
        flash('Invalid trust level.', 'danger')
        return redirect(url_for('admin.groups'))
    group.trust_level = trust
    log_action('set_group_trust', group.name, trust)
    db.session.commit()
    flash(f'Group trust level set to {trust}.', 'success')
    return redirect(url_for('admin.groups'))


@admin_bp.route('/groups/<int:group_id>/freeze', methods=['POST'])
@login_required
@admin_required
def freeze_group(group_id):
    group = Group.query.get_or_404(group_id)
    group.is_frozen = not group.is_frozen
    action = 'freeze' if group.is_frozen else 'unfreeze'
    log_action(action + '_group', group.name)
    db.session.commit()
    flash(f'Group {"frozen" if group.is_frozen else "unfrozen"}.', 'info')
    return redirect(url_for('admin.groups'))


@admin_bp.route('/groups/<int:group_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_group(group_id):
    group = Group.query.get_or_404(group_id)
    log_action('delete_group', group.name)
    db.session.delete(group)
    db.session.commit()
    flash('Group deleted.', 'info')
    return redirect(url_for('admin.groups'))


# ── Reports ───────────────────────────────────────────────────────────────────
@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    status = request.args.get('status', 'pending')
    rtype  = request.args.get('type', '')
    q_obj  = Report.query
    if status: q_obj = q_obj.filter_by(status=status)
    if rtype:  q_obj = q_obj.filter_by(type=rtype)
    reports = q_obj.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports, sel_status=status, sel_type=rtype)


@admin_bp.route('/reports/<int:rid>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_report(rid):
    r = Report.query.get_or_404(rid)
    r.status = 'resolved'
    log_action('resolve_report', f'Report #{rid}')
    db.session.commit()
    flash('Report resolved.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/reports/<int:rid>/review', methods=['POST'])
@login_required
@admin_required
def review_report(rid):
    r = Report.query.get_or_404(rid)
    r.status = 'reviewed'
    db.session.commit()
    return redirect(url_for('admin.reports'))


# ── Broadcast ─────────────────────────────────────────────────────────────────
@admin_bp.route('/broadcast', methods=['GET', 'POST'])
@login_required
@admin_required
def broadcast():
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        link    = request.form.get('link', '').strip() or url_for('main.dashboard')
        if not message:
            flash('Message is required.', 'danger')
            return redirect(url_for('admin.broadcast'))
        for u in User.query.filter_by(is_suspended=False).all():
            if u.id != current_user.id:
                push_notification(u.id, 'announcement', f'📢 {message}', link)
        log_action('broadcast', 'all users', message[:100])
        db.session.commit()
        flash(f'Broadcast sent to all users.', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/broadcast.html')


# ── Activity Log ──────────────────────────────────────────────────────────────
@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    logs = AdminLog.query.order_by(AdminLog.created_at.desc()).limit(200).all()
    return render_template('admin/logs.html', logs=logs)
