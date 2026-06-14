from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from flask_socketio import emit, join_room, leave_room
from app import socketio
from models import db, User, PrivateMessage, Block, Notification, Report, GroupMessage, group_members
from main import push_notification

chat_bp = Blueprint('chat', __name__)


def get_pm_room(a, b):
    return f"pm_{min(a,b)}_{max(a,b)}"


# ── Private Chat ──────────────────────────────────────────────────────────────
@chat_bp.route('/')
@login_required
def inbox():
    friend_ids = [f.id for f in current_user.friends]
    convos = []
    for fid in friend_ids:
        friend = User.query.get(fid)
        last = PrivateMessage.query.filter(
            ((PrivateMessage.sender_id == current_user.id) & (PrivateMessage.receiver_id == fid)) |
            ((PrivateMessage.sender_id == fid) & (PrivateMessage.receiver_id == current_user.id))
        ).order_by(PrivateMessage.created_at.desc()).first()
        unread = PrivateMessage.query.filter_by(
            sender_id=fid, receiver_id=current_user.id, is_read=False
        ).count()
        convos.append({'friend': friend, 'last': last, 'unread': unread})

    convos.sort(key=lambda x: x['last'].created_at if x['last'] else datetime.min, reverse=True)
    return render_template('chat/inbox.html', convos=convos)


@chat_bp.route('/with/<int:user_id>')
@login_required
def conversation(user_id):
    other = User.query.get_or_404(user_id)

    if Block.query.filter(
        ((Block.blocker_id == current_user.id) & (Block.blocked_id == user_id)) |
        ((Block.blocker_id == user_id) & (Block.blocked_id == current_user.id))
    ).first():
        flash('You cannot message this user.', 'danger')
        return redirect(url_for('chat.inbox'))

    if not current_user.is_friends_with(other):
        flash('You can only message accepted friends.', 'warning')
        return redirect(url_for('auth.profile', user_id=user_id))

    # Mark messages as read
    PrivateMessage.query.filter_by(
        sender_id=user_id, receiver_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()

    messages = PrivateMessage.query.filter(
        ((PrivateMessage.sender_id == current_user.id) & (PrivateMessage.receiver_id == user_id)) |
        ((PrivateMessage.sender_id == user_id) & (PrivateMessage.receiver_id == current_user.id))
    ).order_by(PrivateMessage.created_at).all()

    room = get_pm_room(current_user.id, user_id)
    friends = current_user.friends.filter_by(is_suspended=False).all()
    return render_template('chat/conversation.html',
        other=other, messages=messages, room=room, friends=friends)


@chat_bp.route('/report/<int:msg_id>', methods=['POST'])
@login_required
def report_message(msg_id):
    msg = PrivateMessage.query.get_or_404(msg_id)
    if msg.receiver_id != current_user.id:
        abort(403)
    reason = request.form.get('reason', 'abuse')
    details = request.form.get('details', '')
    r = Report(reporter_id=current_user.id, reported_user_id=msg.sender_id,
               type='private_message', reason=reason, details=details, ref_id=msg_id)
    msg.is_reported = True
    db.session.add(r)
    db.session.commit()
    flash('Message reported. Admin will review it.', 'info')
    return redirect(url_for('chat.conversation', user_id=msg.sender_id))


# ── SocketIO — Private Messages ───────────────────────────────────────────────
@socketio.on('pm_join')
def on_pm_join(data):
    join_room(data.get('room'))


@socketio.on('pm_send')
def on_pm_send(data):
    from flask_login import current_user as cu
    room        = data.get('room')
    content     = (data.get('content') or '').strip()
    receiver_id = data.get('receiver_id')
    if not content or not receiver_id:
        return

    msg = PrivateMessage(sender_id=cu.id, receiver_id=receiver_id, content=content)
    db.session.add(msg)
    push_notification(receiver_id, 'message',
        f'💬 New message from {cu.display_name}',
        url_for('chat.conversation', user_id=cu.id))
    db.session.commit()

    emit('pm_receive', {
        'id': msg.id,
        'content': content,
        'sender_id': cu.id,
        'sender_name': cu.display_name,
        'sender_pic': cu.profile_pic,
        'timestamp': msg.created_at.strftime('%H:%M'),
    }, room=room)


# ── SocketIO — Group Chat ─────────────────────────────────────────────────────
@socketio.on('group_join')
def on_group_join(data):
    join_room(data.get('room'))


@socketio.on('group_send')
def on_group_send(data):
    from flask_login import current_user as cu
    from models import Group
    room     = data.get('room')
    content  = (data.get('content') or '').strip()
    group_id = data.get('group_id')
    if not content or not group_id:
        return

    # Verify membership
    row = db.session.execute(
        group_members.select().where(
            (group_members.c.group_id == group_id) &
            (group_members.c.user_id == cu.id)
        )
    ).first()
    if not row:
        return

    msg = GroupMessage(group_id=group_id, sender_id=cu.id, content=content)
    db.session.add(msg)
    db.session.commit()

    emit('group_receive', {
        'id': msg.id,
        'content': content,
        'sender_id': cu.id,
        'sender_name': cu.display_name,
        'sender_pic': cu.profile_pic,
        'timestamp': msg.created_at.strftime('%H:%M'),
        'group_id': group_id,
    }, room=room)
