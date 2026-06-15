"""NSDCP Admin — SA2 compatible, full logging"""
from datetime import datetime
from functools import wraps
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, User, Post, Poll, Report, Group, Notification, AdminLog, ScholarshipApplication
from main import push_notification

admin_bp = Blueprint('admin', __name__)
ROLES        = ['student','representative','vice_president','president','group_admin','admin']
TRUST_LEVELS = ['new','verified','trusted','flagged']
GROUP_TRUST  = ['new','verified','trusted','flagged']


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


def log_action(action, target='', details=''):
    db.session.add(AdminLog(actor_id=current_user.id,
                            action=action, target=target, details=details))


@admin_bp.route('/')
@login_required
@admin_required
def dashboard():
    stats = {
        'users':     db.session.query(User).count(),
        'verified':  db.session.query(User).filter_by(verification_level=2).count(),
        'posts':     db.session.query(Post).filter_by(status='approved').count(),
        'pending':   db.session.query(Post).filter_by(status='pending').count(),
        'polls':     db.session.query(Poll).count(),
        'reports':   db.session.query(Report).filter_by(status='pending').count(),
        'groups':    db.session.query(Group).count(),
        'suspended': db.session.query(User).filter_by(is_suspended=True).count(),
        'scholarship': db.session.query(ScholarshipApplication).count(),
    }
    recent_users    = db.session.query(User).order_by(User.created_at.desc()).limit(8).all()
    pending_posts   = db.session.query(Post).filter_by(status='pending').order_by(Post.created_at.desc()).limit(6).all()
    pending_reports = db.session.query(Report).filter_by(status='pending').order_by(Report.created_at.desc()).limit(6).all()
    recent_logs     = db.session.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
        stats=stats, recent_users=recent_users,
        pending_posts=pending_posts, pending_reports=pending_reports,
        recent_logs=recent_logs)


@admin_bp.route('/posts/review')
@login_required
@admin_required
def review_posts():
    filter_status = request.args.get('status', 'pending')
    posts = db.session.query(Post).filter_by(status=filter_status).order_by(Post.created_at.desc()).all()
    return render_template('admin/posts.html', posts=posts, filter_status=filter_status)


@admin_bp.route('/posts/<int:post_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_post(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    post.status      = 'approved'
    post.approved_by = current_user.id
    post.approved_at = datetime.utcnow()
    log_action('approve_post', f'Post #{post_id}', post.title or post.content[:60])
    push_notification(post.user_id, 'post_approved',
        f'✅ Your post "{(post.title or post.content[:50])}" has been approved.',
        url_for('posts.view', post_id=post_id))
    db.session.commit()
    flash('Post approved.', 'success')
    return redirect(url_for('admin.review_posts'))


@admin_bp.route('/posts/<int:post_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_post(post_id):
    post   = db.session.get(Post, post_id) or abort(404)
    reason = request.form.get('reason', 'Does not meet community guidelines.')
    post.status        = 'rejected'
    post.reject_reason = reason
    log_action('reject_post', f'Post #{post_id}', reason)
    push_notification(post.user_id, 'post_rejected',
        f'❌ Your post was rejected. Reason: {reason}',
        url_for('main.dashboard'))
    db.session.commit()
    flash('Post rejected.', 'info')
    return redirect(url_for('admin.review_posts'))


@admin_bp.route('/posts/<int:post_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    log_action('delete_post', f'Post #{post_id}')
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'info')
    return redirect(url_for('admin.review_posts'))


@admin_bp.route('/posts/<int:post_id>/toggle-comments', methods=['POST'])
@login_required
@admin_required
def toggle_comments(post_id):
    post = db.session.get(Post, post_id) or abort(404)
    post.comments_enabled = not post.comments_enabled
    db.session.commit()
    return redirect(request.referrer or url_for('posts.view', post_id=post_id))


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    q = request.args.get('q', '')
    school = request.args.get('school', '')
    role   = request.args.get('role', '')
    trust  = request.args.get('trust', '')
    q_obj  = db.session.query(User)
    if q:      q_obj = q_obj.filter(db.or_(User.full_name.ilike(f'%{q}%'), User.email.ilike(f'%{q}%')))
    if school: q_obj = q_obj.filter(User.school_name.ilike(f'%{school}%'))
    if role:   q_obj = q_obj.filter_by(role=role)
    if trust:  q_obj = q_obj.filter_by(trust_level=trust)
    users = q_obj.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, roles=ROLES,
        trust_levels=TRUST_LEVELS, q=q, school=school, sel_role=role, sel_trust=trust)


@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    user     = db.session.get(User, user_id) or abort(404)
    reports  = db.session.query(Report).filter_by(reported_user_id=user_id).order_by(Report.created_at.desc()).limit(10).all()
    posts    = db.session.query(Post).filter_by(user_id=user_id).order_by(Post.created_at.desc()).limit(10).all()
    scholar  = db.session.query(ScholarshipApplication).filter_by(user_id=user_id).first()
    return render_template('admin/user_detail.html', user=user, roles=ROLES,
        trust_levels=TRUST_LEVELS, reports=reports, posts=posts, scholar=scholar)


@admin_bp.route('/users/<int:user_id>/set-role', methods=['POST'])
@login_required
@admin_required
def set_role(user_id):
    user  = db.session.get(User, user_id) or abort(404)
    role  = request.form.get('role')
    title = request.form.get('role_title', '').strip()
    if role not in ROLES:
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    old_role    = user.role
    user.role   = role
    user.role_title = title or None
    log_action('set_role', user.email, f'{old_role} → {role}')
    push_notification(user_id, 'verification',
        f'🎖️ Your role: {title or role.replace("_"," ").title()}',
        url_for('auth.profile', user_id=user_id))
    db.session.commit()
    flash('Role updated.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/set-trust', methods=['POST'])
@login_required
@admin_required
def set_trust(user_id):
    user  = db.session.get(User, user_id) or abort(404)
    trust = request.form.get('trust_level')
    if trust not in TRUST_LEVELS:
        flash('Invalid.', 'danger')
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
    user  = db.session.get(User, user_id) or abort(404)
    level = request.form.get('level', type=int, default=2)
    user.verification_level = level
    if level == 2:
        user.trust_level = 'verified'
    log_action('verify_user', user.email, f'Level {level}')
    push_notification(user_id, 'verification',
        f'✅ Account verified (Level {level}: {user.verification_label}).',
        url_for('auth.profile', user_id=user_id))
    db.session.commit()
    flash(f'User verified at level {level}.', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    if user.role == 'admin':
        flash('Cannot suspend an admin.', 'danger')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    user.is_suspended = not user.is_suspended
    log_action('suspend' if user.is_suspended else 'unsuspend', user.email)
    db.session.commit()
    flash(f'User {"suspended" if user.is_suspended else "unsuspended"}.', 'info')
    return redirect(url_for('admin.user_detail', user_id=user_id))


@admin_bp.route('/groups')
@login_required
@admin_required
def groups():
    ft = request.args.get('trust', '')
    q  = db.session.query(Group)
    if ft: q = q.filter_by(trust_level=ft)
    groups = q.order_by(Group.created_at.desc()).all()
    return render_template('admin/groups.html', groups=groups, group_trust=GROUP_TRUST, sel_trust=ft)


@admin_bp.route('/groups/<int:gid>/set-trust', methods=['POST'])
@login_required
@admin_required
def set_group_trust(gid):
    group = db.session.get(Group, gid) or abort(404)
    trust = request.form.get('trust_level')
    if trust not in GROUP_TRUST:
        flash('Invalid.', 'danger')
        return redirect(url_for('admin.groups'))
    group.trust_level = trust
    log_action('set_group_trust', group.name, trust)
    db.session.commit()
    flash('Group trust updated.', 'success')
    return redirect(url_for('admin.groups'))


@admin_bp.route('/groups/<int:gid>/freeze', methods=['POST'])
@login_required
@admin_required
def freeze_group(gid):
    group = db.session.get(Group, gid) or abort(404)
    group.is_frozen = not group.is_frozen
    log_action('freeze_group' if group.is_frozen else 'unfreeze_group', group.name)
    db.session.commit()
    flash(f'Group {"frozen" if group.is_frozen else "unfrozen"}.', 'info')
    return redirect(url_for('admin.groups'))


@admin_bp.route('/groups/<int:gid>/delete', methods=['POST'])
@login_required
@admin_required
def delete_group(gid):
    group = db.session.get(Group, gid) or abort(404)
    log_action('delete_group', group.name)
    db.session.delete(group)
    db.session.commit()
    flash('Group deleted.', 'info')
    return redirect(url_for('admin.groups'))


@admin_bp.route('/reports')
@login_required
@admin_required
def reports():
    status = request.args.get('status', 'pending')
    rtype  = request.args.get('type', '')
    q = db.session.query(Report)
    if status: q = q.filter_by(status=status)
    if rtype:  q = q.filter_by(type=rtype)
    reports = q.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', reports=reports, sel_status=status, sel_type=rtype)


@admin_bp.route('/reports/<int:rid>/resolve', methods=['POST'])
@login_required
@admin_required
def resolve_report(rid):
    r = db.session.get(Report, rid) or abort(404)
    r.status = 'resolved'
    log_action('resolve_report', f'Report #{rid}')
    db.session.commit()
    flash('Report resolved.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/reports/<int:rid>/review', methods=['POST'])
@login_required
@admin_required
def review_report(rid):
    r = db.session.get(Report, rid) or abort(404)
    r.status = 'reviewed'
    db.session.commit()
    return redirect(url_for('admin.reports'))


@admin_bp.route('/scholarship')
@login_required
@admin_required
def scholarship():
    apps = db.session.query(ScholarshipApplication).order_by(
        ScholarshipApplication.submitted_at.desc()
    ).all()
    return render_template('admin/scholarship.html', apps=apps)


@admin_bp.route('/scholarship/<int:sid>/notify', methods=['POST'])
@login_required
@admin_required
def notify_scholar(sid):
    app = db.session.get(ScholarshipApplication, sid) or abort(404)
    app.status       = 'approved'
    app.notified_at  = datetime.utcnow()
    push_notification(app.user_id, 'announcement',
        '🎓 Congratulations! You have been selected for a scholarship. Please check your registered bank account.',
        url_for('auth.edit_profile'))
    log_action('notify_scholarship', f'User #{app.user_id}')
    db.session.commit()
    flash('Student notified of scholarship.', 'success')
    return redirect(url_for('admin.scholarship'))


@admin_bp.route('/broadcast', methods=['GET', 'POST'])
@login_required
@admin_required
def broadcast():
    if request.method == 'POST':
        message = request.form.get('message', '').strip()
        link    = request.form.get('link', '').strip() or url_for('main.dashboard')
        if not message:
            flash('Message required.', 'danger')
            return redirect(url_for('admin.broadcast'))
        for u in db.session.query(User).filter_by(is_suspended=False).all():
            if u.id != current_user.id:
                push_notification(u.id, 'announcement', f'📢 {message}', link)
        log_action('broadcast', 'all users', message[:100])
        db.session.commit()
        flash('Broadcast sent!', 'success')
        return redirect(url_for('admin.dashboard'))
    return render_template('admin/broadcast.html')


@admin_bp.route('/logs')
@login_required
@admin_required
def logs():
    logs = db.session.query(AdminLog).order_by(AdminLog.created_at.desc()).limit(200).all()
    return render_template('admin/logs.html', logs=logs)
