"""
app/admin/routes.py

Admin-only portal: user management, listing oversight,
manual archive, platform statistics.
All routes require role=admin via @admin_required.
"""

from functools import wraps
from flask import render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from sqlalchemy import func
from app.admin import admin
from app.models import User, Car, Message, Notification
from app.extensions import db
from app.utils import utcnow


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin.route('/')
@admin_required
def dashboard():
    stats = {
        'total_users':    User.query.count(),
        'total_active':   Car.query.filter_by(status='active').count(),
        'total_archived': Car.query.filter_by(status='archived').count(),
        'total_sold':     Car.query.filter_by(status='sold').count(),
        'total_messages': Message.query.count(),
        'new_users_week': User.query.filter(
            User.created_at >= db.func.datetime('now', '-7 days')
        ).count(),
    }

    # top makes
    top_makes = db.session.query(
        Car.make,
        func.count(Car.id).label('cnt')
    ).filter_by(status='active').group_by(Car.make).order_by(func.count(Car.id).desc()).limit(8).all()

    recent_users = User.query.order_by(User.created_at.desc()).limit(8).all()
    recent_cars  = Car.query.order_by(Car.created_at.desc()).limit(8).all()

    return render_template('admin/dashboard.html',
                           stats=stats,
                           top_makes=top_makes,
                           recent_users=recent_users,
                           recent_cars=recent_cars)


@admin.route('/users')
@admin_required
def users():
    page  = request.args.get('page', 1, type=int)
    role  = request.args.get('role', '')
    q_str = (request.args.get('q') or '').strip()

    query = User.query
    if role:
        query = query.filter_by(role=role)
    if q_str:
        like = f'%{q_str}%'
        query = query.filter(
            db.or_(User.name.ilike(like), User.email.ilike(like))
        )

    pagination = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    return render_template('admin/users.html',
                           users=pagination.items,
                           pagination=pagination,
                           role=role, q=q_str)


@admin.route('/users/<int:user_id>/toggle-verified', methods=['POST'])
@admin_required
def toggle_verified(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    flash(f'{"Verified" if user.is_verified else "Unverified"} {user.name}.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin.users'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash(f'User {user.email} deleted.', 'info')
    return redirect(url_for('admin.users'))


@admin.route('/listings')
@admin_required
def listings():
    page   = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'active')
    q_str  = (request.args.get('q') or '').strip()

    query = Car.query
    if status in ('active', 'archived', 'sold', 'draft'):
        query = query.filter_by(status=status)
    if q_str:
        like = f'%{q_str}%'
        query = query.filter(
            db.or_(Car.make.ilike(like), Car.model.ilike(like))
        )

    pagination = query.order_by(Car.created_at.desc()).paginate(
        page=page, per_page=30, error_out=False
    )
    return render_template('admin/listings.html',
                           cars=pagination.items,
                           pagination=pagination,
                           status=status, q=q_str)


@admin.route('/listings/<int:car_id>/archive', methods=['POST'])
@admin_required
def archive_listing(car_id):
    car = Car.query.get_or_404(car_id)
    car.status      = 'archived'
    car.archived_at = utcnow()
    db.session.commit()
    flash(f'{car.year} {car.make} {car.model} archived.', 'info')
    return redirect(url_for('admin.listings'))


@admin.route('/listings/<int:car_id>/feature', methods=['POST'])
@admin_required
def toggle_featured(car_id):
    car = Car.query.get_or_404(car_id)
    car.is_featured = not car.is_featured
    db.session.commit()
    flash(f'{"Featured" if car.is_featured else "Unfeatured"}: {car.year} {car.make} {car.model}.', 'success')
    return redirect(url_for('admin.listings'))


@admin.route('/listings/<int:car_id>/delete', methods=['POST'])
@admin_required
def delete_listing(car_id):
    car = Car.query.get_or_404(car_id)
    db.session.delete(car)
    db.session.commit()
    flash('Listing permanently deleted.', 'info')
    return redirect(url_for('admin.listings'))


@admin.route('/stats')
@admin_required
def stats():
    # listings by body type
    by_body = db.session.query(
        Car.body_type, func.count(Car.id)
    ).filter_by(status='active').group_by(Car.body_type).all()

    # listings by fuel type
    by_fuel = db.session.query(
        Car.fuel_type, func.count(Car.id)
    ).filter_by(status='active').group_by(Car.fuel_type).all()

    # price distribution buckets
    price_buckets = [
        ('Under $10k',    Car.query.filter(Car.status=='active', Car.price < 1_000_000).count()),
        ('$10k-$25k',     Car.query.filter(Car.status=='active', Car.price.between(1_000_000, 2_500_000)).count()),
        ('$25k-$50k',     Car.query.filter(Car.status=='active', Car.price.between(2_500_000, 5_000_000)).count()),
        ('$50k-$100k',    Car.query.filter(Car.status=='active', Car.price.between(5_000_000, 10_000_000)).count()),
        ('Over $100k',    Car.query.filter(Car.status=='active', Car.price > 10_000_000).count()),
    ]

    return render_template('admin/stats.html',
                           by_body=by_body,
                           by_fuel=by_fuel,
                           price_buckets=price_buckets)