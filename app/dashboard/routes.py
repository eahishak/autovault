from flask import render_template, redirect, url_for, session
from flask_login import login_required, current_user
from app.dashboard import dashboard
from app.models import Car, Favorite, Notification
from app.extensions import db


@dashboard.route('/dashboard')
@login_required
def index():
    if current_user.is_admin:
        return redirect(url_for('admin.dashboard'))
    if current_user.is_seller:
        return redirect(url_for('dashboard.seller'))
    return redirect(url_for('dashboard.buyer'))


@dashboard.route('/dashboard/buyer')
@login_required
def buyer():
    saved = current_user.favorites\
                        .join(Car)\
                        .filter(Car.status == 'active')\
                        .order_by(Favorite.created_at.desc())\
                        .all()

    # recently viewed from session
    viewed_ids = session.get('recently_viewed', [])
    viewed_cars = []
    if viewed_ids:
        car_map = {c.id: c for c in Car.query.filter(Car.id.in_(viewed_ids)).all()}
        viewed_cars = [car_map[i] for i in viewed_ids if i in car_map]

    notifications = current_user.notifications\
                                .order_by(Notification.created_at.desc())\
                                .limit(20).all()

    # mark notifications as read
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('dashboard/buyer.html',
                           saved=saved,
                           viewed_cars=viewed_cars,
                           notifications=notifications)


@dashboard.route('/dashboard/seller')
@login_required
def seller():
    if not current_user.is_seller:
        return redirect(url_for('dashboard.buyer'))

    active = current_user.listings.filter_by(status='active')\
                                  .order_by(Car.created_at.desc()).all()
    archived = current_user.listings.filter_by(status='archived')\
                                    .order_by(Car.archived_at.desc()).all()
    sold = current_user.listings.filter_by(status='sold')\
                                .order_by(Car.sold_at.desc()).all()

    total_views = sum(c.view_count or 0 for c in active + archived + sold)
    total_favorites = sum(c.favorite_count for c in active)
    unread = current_user.unread_message_count

    notifications = current_user.notifications\
                                .order_by(Notification.created_at.desc())\
                                .limit(20).all()
    current_user.notifications.filter_by(is_read=False).update({'is_read': True})
    db.session.commit()

    return render_template('dashboard/seller.html',
                           active=active,
                           archived=archived,
                           sold=sold,
                           total_views=total_views,
                           total_favorites=total_favorites,
                           unread=unread,
                           notifications=notifications)