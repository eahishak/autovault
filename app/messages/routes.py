from flask import render_template, request, redirect, url_for, abort, flash
from flask_login import login_required, current_user
from sqlalchemy import or_, and_
from app.messages import messages
from app.models import Message, Car, User, Notification
from app.extensions import db
from app.utils import utcnow


def _conversation_parties(car_id, other_user_id):
    """Return (my_msgs, their_msgs) querys for a conversation thread."""
    return Message.query.filter(
        Message.car_id == car_id,
        or_(
            and_(Message.sender_id == current_user.id,
                 Message.receiver_id == other_user_id),
            and_(Message.sender_id == other_user_id,
                 Message.receiver_id == current_user.id),
        )
    ).order_by(Message.created_at.asc())


@messages.route('/messages')
@login_required
def inbox():
    # Get unique conversations: (car_id, other_user_id) pairs
    raw = db.session.query(
        Message.car_id,
        db.case(
            (Message.sender_id == current_user.id, Message.receiver_id),
            else_=Message.sender_id
        ).label('other_id'),
        db.func.max(Message.created_at).label('last_msg'),
        db.func.sum(
            db.case((
                and_(Message.receiver_id == current_user.id,
                     Message.is_read == False),  # noqa
                1), else_=0)
        ).label('unread'),
    ).filter(
        or_(Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id)
    ).group_by(
        Message.car_id,
        db.case(
            (Message.sender_id == current_user.id, Message.receiver_id),
            else_=Message.sender_id
        )
    ).order_by(db.text('last_msg DESC')).all()

    conversations = []
    for row in raw:
        car = db.session.get(Car, row.car_id)
        other = db.session.get(User, row.other_id)
        if car and other:
            last_msg = Message.query.filter(
                Message.car_id == row.car_id,
                or_(
                    and_(Message.sender_id == current_user.id,
                         Message.receiver_id == row.other_id),
                    and_(Message.sender_id == row.other_id,
                         Message.receiver_id == current_user.id),
                )
            ).order_by(Message.created_at.desc()).first()
            conversations.append({
                'car': car,
                'other': other,
                'last_msg': last_msg,
                'unread': int(row.unread),
            })

    return render_template('messages/inbox.html', conversations=conversations)


@messages.route('/messages/<int:car_id>/<int:other_user_id>')
@login_required
def conversation(car_id, other_user_id):
    car = Car.query.get_or_404(car_id)
    other = User.query.get_or_404(other_user_id)

    if other.id == current_user.id:
        abort(400)

    thread = _conversation_parties(car_id, other_user_id).all()

    # mark incoming messages as read
    for msg in thread:
        if msg.receiver_id == current_user.id and not msg.is_read:
            msg.is_read = True
    db.session.commit()

    return render_template('messages/conversation.html',
                           car=car, other=other, thread=thread)


@messages.route('/messages/send', methods=['POST'])
@login_required
def send_message():
    car_id = request.form.get('car_id', type=int)
    receiver_id = request.form.get('receiver_id', type=int)
    content = (request.form.get('content') or '').strip()

    if not car_id or not receiver_id or not content:
        flash('Message cannot be empty.', 'warning')
        return redirect(request.referrer or url_for('messages.inbox'))

    if receiver_id == current_user.id:
        flash('You cannot message yourself.', 'warning')
        return redirect(request.referrer or url_for('messages.inbox'))

    car = Car.query.get_or_404(car_id)
    receiver = User.query.get_or_404(receiver_id)

    msg = Message(
        sender_id=current_user.id,
        receiver_id=receiver_id,
        car_id=car_id,
        content=content[:2000],
    )
    db.session.add(msg)

    notif = Notification(
        user_id=receiver_id,
        type='new_message',
        title=f'New message from {current_user.name}',
        body=content[:120],
        link=url_for('messages.conversation', car_id=car_id,
                     other_user_id=current_user.id),
    )
    db.session.add(notif)
    db.session.commit()

    flash('Message sent.', 'success')
    return redirect(url_for('messages.conversation',
                             car_id=car_id, other_user_id=receiver_id))


@messages.route('/messages/<int:car_id>/<int:other_user_id>/delete', methods=['POST'])
@login_required
def delete_conversation(car_id, other_user_id):
    thread = _conversation_parties(car_id, other_user_id).all()
    for msg in thread:
        db.session.delete(msg)
    db.session.commit()
    flash('Conversation deleted.', 'info')
    return redirect(url_for('messages.inbox'))