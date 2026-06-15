"""NSDCP Posts — SA2 compatible"""
import os, secrets
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, abort, current_app
from flask_login import login_required, current_user
from models import db, Post, Comment, Like, User, Report
from main import push_notification
from werkzeug.utils import secure_filename

posts_bp = Blueprint('posts', __name__)
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(f):
    return '.' in f and f.rsplit('.', 1)[1].lower() in ALLOWED_EXT


@posts_bp.route('/submit', methods=['GET', 'POST'])
@login_required
def submit():
    if not current_user.can_post:
        flash('Only verified leaders can submit posts.', 'warning')
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        title   = request.form.get('title', '').strip()
        content = request.form.get('content', '').strip()
        if not content:
            flash('Post content is required.', 'danger')
            return redirect(url_for('posts.submit'))

        is_announcement = 'is_announcement' in request.form and current_user.role == 'admin'
        status = 'approved' if current_user.role == 'admin' else 'pending'

        post = Post(
            title=title, content=content,
            user_id=current_user.id,
            comments_enabled='comments_enabled' in request.form,
            is_announcement=is_announcement,
            pinned='pinned' in request.form and current_user.role == 'admin',
            status=status,
            approved_by=current_user.id if status == 'approved' else None,
            approved_at=datetime.utcnow() if status == 'approved' else None,
        )

        if 'image' in request.files:
            f = request.files['image']
            if f and f.filename and allowed_file(f.filename):
                ext  = f.filename.rsplit('.', 1)[1].lower()
                fname = secure_filename(f'post_{secrets.token_hex(8)}.{ext}')
                f.save(os.path.join(current_app.config['UPLOAD_FOLDER'], fname))
                post.image = fname

        db.session.add(post)
        db.session.commit()

        if status == 'approved' and is_announcement:
            for u in db.session.query(User).filter(
                User.is_suspended == False, User.id != current_user.id
            ).all():
                push_notification(u.id, 'announcement',
                    f'📢 {title or content[:60]}',
                    url_for('posts.view', post_id=post.id))
            db.session.commit()

        if status == 'pending':
            for admin in User.query.filter_by(role='admin').all():
                push_notification(admin.id, 'post_pending',
                    f'New post awaiting review from {current_user.display_with_role}',
                    url_for('admin.review_posts'))
            db.session.commit()
            flash('Post submitted for review.', 'info')
        else:
            flash('Post published!', 'success')

        return redirect(url_for('main.dashboard'))

    return render_template('create_post.html')


@posts_bp.route('/<int:post_id>')
@login_required
def view(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    if post.status != 'approved' and current_user.role != 'admin' and post.user_id != current_user.id:
        abort(403)
    comments = db.session.query(Comment).filter_by(
        post_id=post_id, is_deleted=False
    ).order_by(Comment.created_at).all()
    liked = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    return render_template('post.html', post=post, comments=comments, liked=liked)


@posts_bp.route('/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    if not current_user.has_full_access:
        flash('Complete your profile to comment.', 'warning')
        return redirect(url_for('posts.view', post_id=post_id))
    post = db.session.get(Post, post_id)
    if not post or post.status != 'approved' or not post.comments_enabled:
        abort(403)
    content = request.form.get('content', '').strip()
    if not content:
        flash('Comment cannot be empty.', 'danger')
        return redirect(url_for('posts.view', post_id=post_id))
    c = Comment(content=content, user_id=current_user.id, post_id=post_id)
    db.session.add(c)
    if post.author.id != current_user.id:
        push_notification(post.author.id, 'comment',
            f'{current_user.display_name} commented on your post.',
            url_for('posts.view', post_id=post_id))
    db.session.commit()
    return redirect(url_for('posts.view', post_id=post_id))


@posts_bp.route('/<int:post_id>/like', methods=['POST'])
@login_required
def toggle_like(post_id):
    post = db.session.get(Post, post_id)
    if not post or post.status != 'approved':
        return jsonify({'error': 'Not available'}), 403
    existing = Like.query.filter_by(user_id=current_user.id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({'liked': False, 'count': post.likes_count()})
    db.session.add(Like(user_id=current_user.id, post_id=post_id))
    db.session.commit()
    return jsonify({'liked': True, 'count': post.likes_count()})


@posts_bp.route('/<int:post_id>/delete', methods=['POST'])
@login_required
def delete(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    if current_user.role != 'admin' and post.user_id != current_user.id:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted.', 'info')
    return redirect(url_for('main.dashboard'))


@posts_bp.route('/comment/<int:cid>/delete', methods=['POST'])
@login_required
def delete_comment(cid):
    c = db.session.get(Comment, cid)
    if not c:
        abort(404)
    if current_user.role != 'admin' and c.user_id != current_user.id:
        abort(403)
    c.is_deleted = True
    db.session.commit()
    return redirect(url_for('posts.view', post_id=c.post_id))


@posts_bp.route('/<int:post_id>/report', methods=['POST'])
@login_required
def report_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        abort(404)
    reason  = request.form.get('reason', 'inappropriate')
    details = request.form.get('details', '')
    r = Report(reporter_id=current_user.id, reported_user_id=post.user_id,
               type='post', reason=reason, details=details, ref_id=post_id)
    db.session.add(r)
    db.session.commit()
    flash('Post reported.', 'info')
    return redirect(url_for('posts.view', post_id=post_id))
