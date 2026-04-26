"""
app/api/routes.py

All JSON endpoints consumed by the front-end JS modules.
Every route returns application/json.
"""

import json
import os
from flask import request, jsonify, render_template
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from app.api import api
from app.models import Car, Favorite, Notification, Message, User
from app.extensions import db
from app.main.filters import build_car_query


@api.route('/search')
def search():
    q     = (request.args.get('q') or '').strip()
    limit = min(int(request.args.get('limit', 8)), 20)

    if len(q) < 2:
        return jsonify(results=[])

    like = f'%{q}%'
    cars = Car.query.filter(
        Car.status == 'active',
        or_(
            Car.make.ilike(like),
            Car.model.ilike(like),
            func.concat(Car.make, ' ', Car.model).ilike(like),
            func.concat(Car.year.cast(db.String), ' ', Car.make, ' ', Car.model).ilike(like),
        )
    ).order_by(Car.created_at.desc()).limit(limit).all()

    results = []
    seen = set()
    for car in cars:
        label = f'{car.year} {car.make} {car.model}'
        if car.trim:
            label += f' {car.trim}'
        if label in seen:
            continue
        seen.add(label)
        results.append({
            'label':    label,
            'sublabel': f'{car.city}, {car.state} · {_fmt_price(car.price)}',
            'url':      f'/car/{car.slug}' if car.slug else f'/car/{car.id}',
            'icon':     'fa-car',
        })

    return jsonify(results=results)


@api.route('/cars')
def cars():
    page     = request.args.get('page', 1, type=int)
    per_page = 18
    fmt      = request.args.get('format', 'json')

    q          = build_car_query(request.args)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    if fmt == 'html':
        favorited_ids = set()
        if current_user.is_authenticated:
            favorited_ids = {
                f.car_id for f in current_user.favorites
                .filter(Favorite.car_id.in_([c.id for c in pagination.items])).all()
            }
        html = render_template(
            'partials/car_grid_items.html',
            cars=pagination.items,
            favorited_ids=favorited_ids,
        )
        return jsonify(html=html, total=pagination.total, pages=pagination.pages)

    return jsonify(
        cars=[_car_to_dict(c) for c in pagination.items],
        total=pagination.total,
        page=pagination.page,
        pages=pagination.pages,
    )


@api.route('/favorites', methods=['POST'])
@login_required
def toggle_favorite():
    data   = request.get_json(silent=True) or {}
    car_id = data.get('car_id')

    if not car_id:
        return jsonify(error='car_id required'), 400

    car = db.session.get(Car, int(car_id))
    if not car:
        return jsonify(error='Listing not found'), 404

    existing = current_user.favorites.filter_by(car_id=car.id).first()

    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify(favorited=False, car_id=car.id)

    fav = Favorite(user_id=current_user.id, car_id=car.id)
    db.session.add(fav)
    notif = Notification(
        user_id=car.seller_id,
        type='car_favorited',
        title='Someone saved your listing',
        body=f'{current_user.name} saved your {car.year} {car.make} {car.model}.',
        link=f'/car/{car.slug}' if car.slug else f'/car/{car.id}',
    )
    db.session.add(notif)
    db.session.commit()
    return jsonify(favorited=True, car_id=car.id)


@api.route('/notifications')
@login_required
def notifications():
    notifs = current_user.notifications \
                         .order_by(Notification.created_at.desc()) \
                         .limit(15).all()
    return jsonify(notifications=[{
        'id':      n.id,
        'type':    n.type,
        'title':   n.title,
        'body':    n.body,
        'link':    n.link,
        'is_read': n.is_read,
        'time':    _time_ago(n.created_at),
    } for n in notifs])


@api.route('/notifications/mark-read', methods=['POST'])
@login_required
def mark_notifications_read():
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify(ok=True)


@api.route('/messages/send', methods=['POST'])
@login_required
def send_message_ajax():
    data        = request.get_json(silent=True) or {}
    car_id      = data.get('car_id')
    receiver_id = data.get('receiver_id')
    content     = (data.get('content') or '').strip()

    if not car_id or not receiver_id or not content:
        return jsonify(error='Missing required fields'), 400

    if int(receiver_id) == current_user.id:
        return jsonify(error='Cannot message yourself'), 400

    car      = db.session.get(Car, int(car_id))
    receiver = db.session.get(User, int(receiver_id))

    if not car or not receiver:
        return jsonify(error='Car or user not found'), 404

    msg = Message(
        sender_id=current_user.id,
        receiver_id=int(receiver_id),
        car_id=int(car_id),
        content=content[:2000],
    )
    db.session.add(msg)
    notif = Notification(
        user_id=int(receiver_id),
        type='new_message',
        title=f'New message from {current_user.name}',
        body=content[:120],
        link=f'/messages/{car_id}/{current_user.id}',
    )
    db.session.add(notif)
    db.session.commit()

    return jsonify(
        ok=True,
        message_id=msg.id,
        sender=current_user.name,
        content=msg.content,
        created_at=_time_ago(msg.created_at),
    )


@api.route('/messages/poll')
@login_required
def poll_messages():
    car_id   = request.args.get('car_id', type=int)
    other_id = request.args.get('other_id', type=int)
    since_id = request.args.get('since_id', 0, type=int)

    if not car_id or not other_id:
        return jsonify(messages=[])

    from sqlalchemy import and_
    msgs = Message.query.filter(
        Message.id > since_id,
        Message.car_id == car_id,
        or_(
            and_(Message.sender_id == current_user.id, Message.receiver_id == other_id),
            and_(Message.sender_id == other_id,        Message.receiver_id == current_user.id),
        )
    ).order_by(Message.created_at.asc()).all()

    for m in msgs:
        if m.receiver_id == current_user.id and not m.is_read:
            m.is_read = True
    if msgs:
        db.session.commit()

    return jsonify(messages=[{
        'id':        m.id,
        'sender_id': m.sender_id,
        'content':   m.content,
        'time':      _time_ago(m.created_at),
        'mine':      m.sender_id == current_user.id,
    } for m in msgs])


@api.route('/compare')
def compare_data():
    ids_raw = request.args.getlist('ids')
    try:
        ids = [int(i) for i in ids_raw if str(i).isdigit()][:3]
    except (ValueError, TypeError):
        return jsonify(cars=[])

    cars = Car.query.filter(Car.id.in_(ids), Car.status == 'active').all()
    car_map = {c.id: c for c in cars}
    ordered = [car_map[i] for i in ids if i in car_map]
    return jsonify(cars=[_car_to_dict(c) for c in ordered])


@api.route('/ai-assistant', methods=['POST'])
@login_required
def ai_assistant():
    data     = request.get_json(silent=True) or {}
    messages = data.get('messages', [])
    system   = data.get('system', '')

    from flask import current_app
    api_key = os.environ.get('ANTHROPIC_API_KEY') or \
              current_app.config.get('ANTHROPIC_API_KEY')

    if not api_key:
        return jsonify(content='AI assistant is not configured. Set ANTHROPIC_API_KEY in your .env file.')

    clean_msgs = []
    for m in messages[-20:]:
        role    = m.get('role', '')
        content = str(m.get('content', ''))[:2000]
        if role in ('user', 'assistant') and content:
            clean_msgs.append({'role': role, 'content': content})

    while clean_msgs and clean_msgs[0]['role'] == 'assistant':
        clean_msgs.pop(0)

    if not clean_msgs:
        return jsonify(content='Please ask me something.')

    try:
        import anthropic
        client   = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            system=system or 'You are a helpful AutoVault car marketplace assistant.',
            messages=clean_msgs,
        )
        reply = response.content[0].text if response.content else ''
        return jsonify(content=reply)

    except ImportError:
        import urllib.request as urllib_req
        payload = json.dumps({
            'model': 'claude-haiku-4-5-20251001',
            'max_tokens': 600,
            'system': system,
            'messages': clean_msgs,
        }).encode()
        req = urllib_req.Request(
            'https://api.anthropic.com/v1/messages',
            data=payload,
            headers={
                'Content-Type':      'application/json',
                'x-api-key':         api_key,
                'anthropic-version': '2023-06-01',
            },
            method='POST',
        )
        with urllib_req.urlopen(req, timeout=20) as resp:
            body  = json.loads(resp.read())
            reply = body['content'][0]['text'] if body.get('content') else ''
        return jsonify(content=reply)

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f'AI assistant error: {e}')
        return jsonify(content='Sorry, the AI assistant is temporarily unavailable.')


def _fmt_price(cents):
    return f'${cents / 100:,.0f}'


def _time_ago(dt):
    if not dt:
        return ''
    from app.utils import time_ago
    return time_ago(dt)


def _car_to_dict(car):
    return {
        'id':           car.id,
        'slug':         car.slug,
        'make':         car.make,
        'model':        car.model,
        'year':         car.year,
        'trim':         car.trim,
        'price':        car.price,
        'price_fmt':    _fmt_price(car.price),
        'mileage':      car.mileage,
        'condition':    car.condition,
        'body_type':    car.body_type,
        'fuel_type':    car.fuel_type,
        'transmission': car.transmission,
        'city':         car.city,
        'state':        car.state,
        'image_url':    car.primary_image_url,
        'url':          f'/car/{car.slug}' if car.slug else f'/car/{car.id}',
        'days_listed':  car.days_listed,
        'is_new_arrival':  car.is_new_arrival,
        'has_price_drop':  car.has_price_drop,
        'is_low_mileage':  car.is_low_mileage,
    }