"""NSDCP Groups — SA2 compatible"""
import os, secrets
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, current_app
from flask_login import login_required, current_user
from models import db, Group, GroupMessage, GroupInvite, User, Notification, Block, Report, group_members
from main import push_notification
from werkzeug.utils import secure_filename

groups_bp = Blueprint('groups', __name__)
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXT


def _is_member(group_id, user_id):
    return db.session.execute(
        group_members.select().where(
            (group_members.c.group_id == group_id) &
            (group_members.c.user_id == user_id)
        )
    ).first() is not None


def _get_role(group_id, user_id):
    row = db.session.execute(
        group_members.select().where(
            (group_members.c.group_id == group_id) &
            (group_members.c.user_id == user_id)
        )
    ).first()
    return row.role if row else None


def _can_manage(group, user):
    if user.role == 'admin':
        return True
    return _get_role(group.id, user.id) in ('owner', 'admin')


@groups_bp.context_processor
def inject_helpers():
    return dict(can_manage=_can_manage)


@groups_bp.route('/')
@login_required
def index():
    my_rows = db.session.execute(
        group_members.select().where(group_members.c.user_id == current_user.id)
    ).fetchall()
    my_ids = [r.group_id for r in my_rows]
    my_groups = db.session.query(Group).filter(
        Group.id.in_(my_ids), Group.is_frozen == False
    ).all() if my_ids else []

    discover = db.session.query(Group).filter(
        Group.is_frozen == False,
        Group.trust_level.in_(['verified', 'trusted']),
        ~Group.id.in_(my_ids) if my_ids else db.true()
    ).order_by(Group.created_at.desc()).limit(10).all()

    return render_template('group/index.html', groups=my_groups, discover=discover)


@groups_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if not current_user.has_full_access:
        flash('Complete verification to create groups.', 'warning')
        return redirect(url_for('groups.index'))

    if request.method == 'POST':
        name       = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        school_tag = request.form.get('school_tag', '').strip() or current_user.school_name

        if not name:
            flash('Group name is required.', 'danger')
            return redirect(url_for('groups.create'))

        group = Group(name=name, description=description,
                      school_tag=school_tag, creator_id=current_user.id)

        if 'avatar' in request.files:
            f = request.files['avatar']
            if f and f.filename and allowed_file(f.filename):
                ext  = f.filename.rsplit('.', 1)[1].lower()
                fname = secure_filename(f'grp_{secrets.token_hex(6)}.{ext}')
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                group.avatar = fname

        db.session.add(group)
        db.session.flush()

        db.session.execute(group_members.insert().values(
            user_id=current_user.id, group_id=group.id, role='owner'
        ))
        for admin in User.query.filter_by(role='admin').all():
            push_notification(admin.id, 'group_created',
                f'New group "{name}" needs trust verification.',
                url_for('admin.groups'))
        db.session.commit()
        flash('Group created! Admin will verify it shortly.', 'success')
        return redirect(url_for('groups.view', group_id=group.id))

    return render_template('group/create.html')


@groups_bp.route('/<int:group_id>')
@login_required
def view(group_id):
    group = db.session.get(Group, group_id)
    if not group:
        abort(404)
    member_role = _get_role(group_id, current_user.id)
    if not member_role and current_user.role != 'admin':
        flash('You are not a member of this group.', 'warning')
        return redirect(url_for('groups.index'))
    if group.is_frozen and current_user.role != 'admin':
        flash('This group has been frozen by admin.', 'danger')
        return redirect(url_for('groups.index'))

    messages = db.session.query(GroupMessage).filter_by(
        group_id=group_id
    ).order_by(GroupMessage.created_at).limit(100).all()

    members_raw = db.session.execute(
        group_members.select().where(group_members.c.group_id == group_id)
    ).fetchall()
    member_data = [(db.session.get(User, r.user_id), r.role) for r in members_raw if db.session.get(User, r.user_id)]

    return render_template('group/chat.html',
        group=group, member_role=member_role,
        messages=messages, member_data=member_data,
        room=f'group_{group_id}')


@groups_bp.route('/<int:group_id>/invite', methods=['POST'])
@login_required
def invite(group_id):
    group = db.session.get(Group, group_id) or abort(404)
    if not (_is_member(group_id, current_user.id) or current_user.role == 'admin'):
        abort(403)
    email = request.form.get('email', '').strip().lower()
    user  = User.query.filter_by(email=email).first()
    if not user:
        flash('User not found.', 'danger')
        return redirect(url_for('groups.view', group_id=group_id))
    if _is_member(group_id, user.id):
        flash('User is already a member.', 'info')
        return redirect(url_for('groups.view', group_id=group_id))
    if GroupInvite.query.filter_by(group_id=group_id, invited_user_id=user.id, status='pending').first():
        flash('Invite already sent.', 'info')
        return redirect(url_for('groups.view', group_id=group_id))
    inv = GroupInvite(group_id=group_id, invited_user_id=user.id, invited_by=current_user.id)
    db.session.add(inv)
    push_notification(user.id, 'group_invite',
        f'You were invited to join "{group.name}".',
        url_for('groups.index'))
    db.session.commit()
    flash('Invitation sent.', 'success')
    return redirect(url_for('groups.view', group_id=group_id))


@groups_bp.route('/invite/<int:invite_id>/accept', methods=['POST'])
@login_required
def accept_invite(invite_id):
    inv = GroupInvite.query.filter_by(id=invite_id, invited_user_id=current_user.id).first_or_404()
    inv.status = 'accepted'
    db.session.execute(group_members.insert().values(
        user_id=current_user.id, group_id=inv.group_id, role='member'
    ))
    db.session.commit()
    flash(f'You joined "{inv.group.name}"!', 'success')
    return redirect(url_for('groups.view', group_id=inv.group_id))


@groups_bp.route('/invite/<int:invite_id>/reject', methods=['POST'])
@login_required
def reject_invite(invite_id):
    inv = GroupInvite.query.filter_by(id=invite_id, invited_user_id=current_user.id).first_or_404()
    inv.status = 'rejected'
    db.session.commit()
    flash('Invitation declined.', 'info')
    return redirect(url_for('main.dashboard'))


@groups_bp.route('/<int:group_id>/leave', methods=['POST'])
@login_required
def leave(group_id):
    if not _is_member(group_id, current_user.id):
        abort(400)
    db.session.execute(
        group_members.delete().where(
            (group_members.c.group_id == group_id) &
            (group_members.c.user_id == current_user.id)
        )
    )
    db.session.commit()
    flash('You left the group.', 'info')
    return redirect(url_for('groups.index'))


@groups_bp.route('/<int:group_id>/message/report/<int:msg_id>', methods=['POST'])
@login_required
def report_message(group_id, msg_id):
    msg    = db.session.get(GroupMessage, msg_id)
    reason = request.form.get('reason', 'abuse')
    r = Report(reporter_id=current_user.id, reported_user_id=msg.sender_id,
               type='group_message', reason=reason, ref_id=msg_id)
    if msg:
        msg.is_reported = True
    db.session.add(r)
    db.session.commit()
    flash('Message reported.', 'info')
    return redirect(url_for('groups.view', group_id=group_id))
