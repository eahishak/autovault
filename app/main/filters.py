from app.models import Car


SORT_OPTIONS = {
    'newest':    Car.created_at.desc(),
    'oldest':    Car.created_at.asc(),
    'price_asc': Car.price.asc(),
    'price_desc':Car.price.desc(),
    'mileage':   Car.mileage.asc(),
    'year_desc': Car.year.desc(),
    'year_asc':  Car.year.asc(),
}


def build_car_query(args):
    """
    Build a SQLAlchemy query from request args dict.
    All filters are optional; only applied when present and non-empty.
    """
    q = Car.query.filter(Car.status == 'active')

    # text search across make + model
    search = (args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        q = q.filter(
            db.or_(
                Car.make.ilike(like),
                Car.model.ilike(like),
                Car.trim.ilike(like),
                db.func.concat(Car.make, ' ', Car.model).ilike(like),
            )
        )

    # discrete filters
    _str_filters = {
        'make':         Car.make,
        'body_type':    Car.body_type,
        'fuel_type':    Car.fuel_type,
        'transmission': Car.transmission,
        'condition':    Car.condition,
        'drivetrain':   Car.drivetrain,
        'state':        Car.state,
        'city':         Car.city,
        'exterior_color': Car.exterior_color,
    }
    for key, col in _str_filters.items():
        val = (args.get(key) or '').strip()
        if val:
            q = q.filter(col.ilike(f'%{val}%'))

    # range filters
    try:
        if args.get('price_min'):
            q = q.filter(Car.price >= int(float(args['price_min']) * 100))
        if args.get('price_max'):
            q = q.filter(Car.price <= int(float(args['price_max']) * 100))
        if args.get('mileage_max'):
            q = q.filter(Car.mileage <= int(args['mileage_max']))
        if args.get('year_min'):
            q = q.filter(Car.year >= int(args['year_min']))
        if args.get('year_max'):
            q = q.filter(Car.year <= int(args['year_max']))
    except (ValueError, TypeError):
        pass

    sort = args.get('sort', 'newest')
    q = q.order_by(SORT_OPTIONS.get(sort, Car.created_at.desc()))

    return q


# avoid circular — import db here so this module is usable stand-alone
from app.extensions import db  # noqa