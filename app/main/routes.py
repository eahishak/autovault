import json
from flask import render_template, request, abort, redirect, url_for, jsonify, session
from flask_login import current_user
from sqlalchemy import func
from app.main import main
from app.main.filters import build_car_query
from app.models import Car, User, Favorite
from app.extensions import db
from app.utils import archive_old_listings


@main.before_app_request
def run_archive_check():
    """Run auto-archive at most once per hour without a scheduler dependency."""
    import time
    from flask import g
    now = time.time()
    last = g.get('_last_archive', 0)
    if now - last > 3600:
        try:
            archive_old_listings()
        except Exception:
            pass
        g._last_archive = now


@main.route('/')
def index():
    featured = Car.query.filter_by(status='active', is_featured=True)\
                        .order_by(Car.created_at.desc()).limit(6).all()
    recent   = Car.query.filter_by(status='active')\
                        .order_by(Car.created_at.desc()).limit(12).all()

    # quick stats for the hero banner
    stats = {
        'total_active': Car.query.filter_by(status='active').count(),
        'total_sellers': User.query.filter_by(role='seller').count(),
        'makes': db.session.query(func.count(func.distinct(Car.make)))\
                           .filter_by(status='active').scalar() or 0,
    }

    makes = [r[0] for r in db.session.query(Car.make)
             .filter_by(status='active')
             .group_by(Car.make)
             .order_by(func.count(Car.id).desc())
             .limit(12).all()]

    return render_template('index.html',
                           featured=featured,
                           recent=recent,
                           stats=stats,
                           makes=makes)


@main.route('/browse')
def browse():
    page = request.args.get('page', 1, type=int)
    per_page = 18

    q = build_car_query(request.args)
    pagination = q.paginate(page=page, per_page=per_page, error_out=False)

    # sidebar filter options (only show values that have active listings)
    def distinct_vals(col):
        return [r[0] for r in db.session.query(col)
                .filter(Car.status == 'active')
                .filter(col.isnot(None))
                .group_by(col)
                .order_by(col).all()]

    filter_opts = {
        'makes':         distinct_vals(Car.make),
        'body_types':    distinct_vals(Car.body_type),
        'fuel_types':    distinct_vals(Car.fuel_type),
        'transmissions': distinct_vals(Car.transmission),
        'conditions':    distinct_vals(Car.condition),
        'drivetrains':   distinct_vals(Car.drivetrain),
        'colors':        distinct_vals(Car.exterior_color),
        'states':        distinct_vals(Car.state),
    }

    price_range = db.session.query(
        func.min(Car.price), func.max(Car.price)
    ).filter_by(status='active').first()
    year_range = db.session.query(
        func.min(Car.year), func.max(Car.year)
    ).filter_by(status='active').first()

    favorited_ids = set()
    if current_user.is_authenticated:
        favorited_ids = {
            f.car_id for f in current_user.favorites
            .filter(Favorite.car_id.in_([c.id for c in pagination.items])).all()
        }

    # page_args strips 'page' so pagination links don't duplicate it
    page_args = {k: v for k, v in request.args.items() if k != 'page'}

    return render_template('browse.html',
                           cars=pagination.items,
                           pagination=pagination,
                           filter_opts=filter_opts,
                           price_range=price_range,
                           year_range=year_range,
                           favorited_ids=favorited_ids,
                           args=request.args,
                           page_args=page_args)


@main.route('/car/<slug>')
def car_detail(slug):
    car = Car.query.filter_by(slug=slug).first_or_404()

    # track view
    try:
        car.view_count = (car.view_count or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()

    # track recently viewed (stored in session as list of IDs)
    viewed = session.get('recently_viewed', [])
    if car.id not in viewed:
        viewed.insert(0, car.id)
    session['recently_viewed'] = viewed[:10]

    images = car.images.order_by('display_order').all()
    seller = car.seller

    similar = Car.query.filter(
        Car.status == 'active',
        Car.id != car.id,
        Car.make == car.make,
    ).order_by(Car.created_at.desc()).limit(6).all()

    is_favorited = False
    if current_user.is_authenticated:
        is_favorited = current_user.favorites.filter_by(car_id=car.id).first() is not None

    features = []
    if car.features:
        try:
            features = json.loads(car.features)
        except (json.JSONDecodeError, TypeError):
            pass

    return render_template('car_detail.html',
                           car=car,
                           images=images,
                           seller=seller,
                           similar=similar,
                           is_favorited=is_favorited,
                           features=features)


@main.route('/car/<int:car_id>')
def car_by_id(car_id):
    car = Car.query.get_or_404(car_id)
    if car.slug:
        return redirect(url_for('main.car_detail', slug=car.slug))
    return redirect(url_for('main.browse'))


@main.route('/compare')
def compare():
    ids_raw = request.args.getlist('ids')
    try:
        ids = [int(i) for i in ids_raw if i.isdigit()][:3]
    except (ValueError, AttributeError):
        ids = []

    cars = Car.query.filter(Car.id.in_(ids), Car.status == 'active').all() if ids else []
    # maintain order matching requested ids
    car_map = {c.id: c for c in cars}
    cars_ordered = [car_map[i] for i in ids if i in car_map]

    return render_template('compare.html', cars=cars_ordered)


@main.route('/archive')
def archive():
    page = request.args.get('page', 1, type=int)
    pagination = Car.query.filter_by(status='archived')\
                          .order_by(Car.archived_at.desc())\
                          .paginate(page=page, per_page=18, error_out=False)
    return render_template('archive.html',
                           cars=pagination.items,
                           pagination=pagination)


@main.route('/seller/<int:user_id>')
def seller_profile(user_id):
    seller = User.query.get_or_404(user_id)
    if seller.role not in ('seller', 'admin'):
        abort(404)
    active = seller.listings.filter_by(status='active')\
                            .order_by(Car.created_at.desc()).all()
    return render_template('seller_profile.html', seller=seller, cars=active)