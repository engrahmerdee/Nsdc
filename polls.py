"""NSDCP Polls — SA2 compatible"""
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from models import db, Poll, PollOption, Vote, User
from main import push_notification

polls_bp = Blueprint('polls', __name__)
MAX_CHANGES = 3


@polls_bp.route('/')
@login_required
def index():
    polls = db.session.query(Poll).order_by(Poll.created_at.desc()).all()
    user_votes = {v.poll_id: v for v in db.session.query(Vote).filter_by(
        user_id=current_user.id).all()}
    return render_template('polls.html', polls=polls, user_votes=user_votes, now=datetime.utcnow())


@polls_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if current_user.role != 'admin':
        abort(403)
    if request.method == 'POST':
        question    = request.form.get('question', '').strip()
        description = request.form.get('description', '').strip()
        ends_at_str = request.form.get('ends_at', '')
        show_live   = 'show_live' in request.form
        options     = [o.strip() for o in request.form.getlist('options') if o.strip()]

        if not question or len(options) < 2:
            flash('Question and at least 2 options required.', 'danger')
            return redirect(url_for('polls.create'))
        try:
            ends_at = datetime.fromisoformat(ends_at_str)
        except Exception:
            flash('Invalid end date.', 'danger')
            return redirect(url_for('polls.create'))

        poll = Poll(question=question, description=description,
                    created_by=current_user.id, ends_at=ends_at, show_live=show_live)
        db.session.add(poll)
        db.session.flush()
        for opt in options:
            db.session.add(PollOption(poll_id=poll.id, text=opt))

        for u in db.session.query(User).filter_by(is_suspended=False).all():
            if u.id != current_user.id:
                push_notification(u.id, 'poll',
                    f'🗳️ New poll: {question[:80]}',
                    url_for('polls.view', poll_id=poll.id))
        db.session.commit()
        flash('Poll created!', 'success')
        return redirect(url_for('polls.view', poll_id=poll.id))

    return render_template('create_poll.html')


@polls_bp.route('/<int:poll_id>')
@login_required
def view(poll_id):
    poll = db.session.get(Poll, poll_id) or abort(404)
    user_vote = Vote.query.filter_by(user_id=current_user.id, poll_id=poll_id).first()
    options   = db.session.query(PollOption).filter_by(poll_id=poll_id).all()
    total     = poll.total_votes()
    return render_template('poll_detail.html',
        poll=poll, user_vote=user_vote, options=options,
        total=total, now=datetime.utcnow(), MAX_CHANGES=MAX_CHANGES)


@polls_bp.route('/<int:poll_id>/vote', methods=['POST'])
@login_required
def vote(poll_id):
    if not current_user.has_full_access:
        flash('Complete your profile to vote.', 'warning')
        return redirect(url_for('polls.view', poll_id=poll_id))
    poll = db.session.get(Poll, poll_id) or abort(404)
    if not poll.is_open:
        flash('This poll is closed.', 'warning')
        return redirect(url_for('polls.view', poll_id=poll_id))
    option_id = request.form.get('option_id', type=int)
    option = PollOption.query.filter_by(id=option_id, poll_id=poll_id).first()
    if not option:
        flash('Invalid option.', 'danger')
        return redirect(url_for('polls.view', poll_id=poll_id))

    existing = Vote.query.filter_by(user_id=current_user.id, poll_id=poll_id).first()
    if existing:
        if existing.is_locked:
            flash('Your vote is permanently locked.', 'warning')
            return redirect(url_for('polls.view', poll_id=poll_id))
        existing.option_id = option_id
        existing.change_count += 1
        existing.updated_at = datetime.utcnow()
        if existing.change_count >= MAX_CHANGES:
            existing.is_locked = True
            flash(f'Vote updated and locked (used all {MAX_CHANGES} changes).', 'warning')
        else:
            flash(f'Vote changed. {MAX_CHANGES - existing.change_count} change(s) remaining.', 'info')
    else:
        db.session.add(Vote(user_id=current_user.id, poll_id=poll_id, option_id=option_id))
        flash('Vote cast!', 'success')

    db.session.commit()
    return redirect(url_for('polls.view', poll_id=poll_id))


@polls_bp.route('/<int:poll_id>/close', methods=['POST'])
@login_required
def close(poll_id):
    if current_user.role != 'admin':
        abort(403)
    poll = db.session.get(Poll, poll_id) or abort(404)
    poll.is_active = False
    db.session.commit()
    flash('Poll closed.', 'info')
    return redirect(url_for('polls.view', poll_id=poll_id))


@polls_bp.route('/<int:poll_id>/delete', methods=['POST'])
@login_required
def delete(poll_id):
    if current_user.role != 'admin':
        abort(403)
    poll = db.session.get(Poll, poll_id) or abort(404)
    db.session.delete(poll)
    db.session.commit()
    flash('Poll deleted.', 'info')
    return redirect(url_for('polls.index'))
