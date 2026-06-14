from flask import Blueprint, redirect, url_for, flash, abort, render_template, request
from flask_login import login_required, current_user
from models import db, User, FriendRequest, Block, Notification, friendship
from main import push_notification

friends_bp = Blueprint('friends', __name__)


@friends_bp.route('/request/<int:user_id>', methods=['POST'])
@login_required
def send_request(user_id):
    if user_id == current_user.id:
        flash('Cannot send request to yourself.', 'warning')
        return redirect(url_for('auth.profile', user_id=user_id))
    if not current_user.has_full_access:
        flash('Complete your profile verification to add friends.', 'warning')
        return redirect(url_for('auth.profile', user_id=user_id))

    user = User.query.get_or_404(user_id)
    if FriendRequest.query.filter_by(sender_id=current_user.id, receiver_id=user_id).first():
        flash('Request already sent.', 'info')
        return redirect(url_for('auth.profile', user_id=user_id))

    req = FriendRequest(sender_id=current_user.id, receiver_id=user_id)
    db.session.add(req)
    push_notification(user_id, 'friend_request',
        f'👋 {current_user.display_name} sent you a connection request.',
        url_for('auth.profile', user_id=current_user.id))
    db.session.commit()
    flash(f'Connection request sent to {user.full_name.split()[0]}!', 'success')
    return redirect(url_for('auth.profile', user_id=user_id))


@friends_bp.route('/accept/<int:req_id>', methods=['POST'])
@login_required
def accept(req_id):
    req = FriendRequest.query.filter_by(id=req_id, receiver_id=current_user.id).first_or_404()
    req.status = 'accepted'
    sender = User.query.get(req.sender_id)
    current_user.friends.append(sender)
    sender.friends.append(current_user)
    push_notification(req.sender_id, 'friend_request',
        f'✅ {current_user.display_name} accepted your connection request.',
        url_for('auth.profile', user_id=current_user.id))
    db.session.commit()
    flash(f'You are now connected with {sender.full_name.split()[0]}!', 'success')
    return redirect(url_for('main.dashboard'))


@friends_bp.route('/reject/<int:req_id>', methods=['POST'])
@login_required
def reject(req_id):
    req = FriendRequest.query.filter_by(id=req_id, receiver_id=current_user.id).first_or_404()
    req.status = 'rejected'
    db.session.commit()
    flash('Request declined.', 'info')
    return redirect(url_for('main.dashboard'))


@friends_bp.route('/remove/<int:user_id>', methods=['POST'])
@login_required
def remove(user_id):
    user = User.query.get_or_404(user_id)
    if current_user.is_friends_with(user):
        current_user.friends.remove(user)
        user.friends.remove(current_user)
        FriendRequest.query.filter(
            ((FriendRequest.sender_id == current_user.id) & (FriendRequest.receiver_id == user_id)) |
            ((FriendRequest.sender_id == user_id) & (FriendRequest.receiver_id == current_user.id))
        ).delete()
        db.session.commit()
        flash('Connection removed.', 'info')
    return redirect(url_for('auth.profile', user_id=user_id))


@friends_bp.route('/block/<int:user_id>', methods=['POST'])
@login_required
def block(user_id):
    if user_id == current_user.id:
        abort(400)
    if not Block.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first():
        db.session.add(Block(blocker_id=current_user.id, blocked_id=user_id))
        # Remove friendship if exists
        user = User.query.get(user_id)
        if user and current_user.is_friends_with(user):
            current_user.friends.remove(user)
            user.friends.remove(current_user)
        db.session.commit()
        flash('User blocked.', 'info')
    return redirect(url_for('main.dashboard'))


@friends_bp.route('/unblock/<int:user_id>', methods=['POST'])
@login_required
def unblock(user_id):
    b = Block.query.filter_by(blocker_id=current_user.id, blocked_id=user_id).first()
    if b:
        db.session.delete(b)
        db.session.commit()
        flash('User unblocked.', 'success')
    return redirect(url_for('main.dashboard'))


@friends_bp.route('/list')
@login_required
def list_friends():
    friends = current_user.friends.filter_by(is_suspended=False).all()
    return render_template('friends.html', friends=friends)
