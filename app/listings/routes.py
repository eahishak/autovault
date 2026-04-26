import json
from flask import render_template, redirect, url_for, flash, abort, request
from flask_login import login_required, current_user
from app.listings import listings
from app.listings.forms import CarListingForm
from app.models import Car, CarImage
from app.extensions import db
from app.utils import generate_car_slug, utcnow


def _seller_required():
    if not current_user.is_seller:
        abort(403)


@listings.route('/listings/new', methods=['GET', 'POST'])
@login_required
def new_listing():
    _seller_required()
    form = CarListingForm()
    if form.validate_on_submit():
        price_cents = int(float(form.price.data) * 100)
        car = Car(
            seller_id=current_user.id,
            make=form.make.data,
            model=form.model.data.strip(),
            year=form.year.data,
            trim=form.trim.data.strip() if form.trim.data else None,
            vin=form.vin.data or None,
            condition=form.condition.data,
            price=price_cents,
            mileage=form.mileage.data,
            body_type=form.body_type.data,
            fuel_type=form.fuel_type.data,
            transmission=form.transmission.data,
            drivetrain=form.drivetrain.data or None,
            engine=form.engine.data.strip() if form.engine.data else None,
            horsepower=form.horsepower.data,
            exterior_color=form.exterior_color.data.strip() if form.exterior_color.data else None,
            interior_color=form.interior_color.data.strip() if form.interior_color.data else None,
            doors=form.doors.data,
            seats=form.seats.data,
            city=form.city.data.strip(),
            state=form.state.data,
            zip_code=form.zip_code.data.strip() if form.zip_code.data else None,
            description=form.description.data.strip() if form.description.data else None,
            primary_image_url=form.primary_image_url.data.strip() if form.primary_image_url.data else None,
            status='active',
        )

        # parse features textarea
        if form.features.data:
            lines = [l.strip() for l in form.features.data.splitlines() if l.strip()]
            car.features = json.dumps(lines)

        db.session.add(car)
        db.session.flush()
        car.slug = generate_car_slug(car.year, car.make, car.model, car.id)

        # extra images
        if form.extra_images.data:
            for order, url in enumerate(
                [u.strip() for u in form.extra_images.data.splitlines() if u.strip()]
            ):
                db.session.add(CarImage(car_id=car.id, url=url, display_order=order))

        db.session.commit()
        flash('Listing posted successfully!', 'success')
        return redirect(url_for('main.car_detail', slug=car.slug))

    return render_template('listings/new_listing.html', form=form, mode='new')


@listings.route('/listings/<int:car_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_listing(car_id):
    car = Car.query.get_or_404(car_id)
    if car.seller_id != current_user.id and not current_user.is_admin:
        abort(403)

    form = CarListingForm(obj=car)
    # pre-populate price
    if request.method == 'GET':
        form.price.data = round(car.price / 100, 2)
        if car.features:
            try:
                form.features.data = '\n'.join(json.loads(car.features))
            except (json.JSONDecodeError, TypeError):
                pass
        urls = [img.url for img in car.images.order_by('display_order').all()]
        form.extra_images.data = '\n'.join(urls)

    if form.validate_on_submit():
        new_price = int(float(form.price.data) * 100)
        if new_price < car.price:
            car.original_price = car.price  # triggers price-drop badge

        car.make = form.make.data
        car.model = form.model.data.strip()
        car.year = form.year.data
        car.trim = form.trim.data.strip() if form.trim.data else None
        car.vin = form.vin.data or None
        car.condition = form.condition.data
        car.price = new_price
        car.mileage = form.mileage.data
        car.body_type = form.body_type.data
        car.fuel_type = form.fuel_type.data
        car.transmission = form.transmission.data
        car.drivetrain = form.drivetrain.data or None
        car.engine = form.engine.data.strip() if form.engine.data else None
        car.horsepower = form.horsepower.data
        car.exterior_color = form.exterior_color.data.strip() if form.exterior_color.data else None
        car.interior_color = form.interior_color.data.strip() if form.interior_color.data else None
        car.doors = form.doors.data
        car.seats = form.seats.data
        car.city = form.city.data.strip()
        car.state = form.state.data
        car.zip_code = form.zip_code.data.strip() if form.zip_code.data else None
        car.description = form.description.data.strip() if form.description.data else None
        car.primary_image_url = form.primary_image_url.data.strip() if form.primary_image_url.data else None

        if form.features.data:
            lines = [l.strip() for l in form.features.data.splitlines() if l.strip()]
            car.features = json.dumps(lines)

        car.slug = generate_car_slug(car.year, car.make, car.model, car.id)

        # replace extra images
        car.images.delete()
        if form.extra_images.data:
            for order, url in enumerate(
                [u.strip() for u in form.extra_images.data.splitlines() if u.strip()]
            ):
                db.session.add(CarImage(car_id=car.id, url=url, display_order=order))

        db.session.commit()
        flash('Listing updated.', 'success')
        return redirect(url_for('main.car_detail', slug=car.slug))

    return render_template('listings/new_listing.html', form=form, car=car, mode='edit')


@listings.route('/listings/<int:car_id>/delete', methods=['POST'])
@login_required
def delete_listing(car_id):
    car = Car.query.get_or_404(car_id)
    if car.seller_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(car)
    db.session.commit()
    flash('Listing deleted.', 'info')
    return redirect(url_for('dashboard.seller'))


@listings.route('/listings/<int:car_id>/mark-sold', methods=['POST'])
@login_required
def mark_sold(car_id):
    car = Car.query.get_or_404(car_id)
    if car.seller_id != current_user.id and not current_user.is_admin:
        abort(403)
    car.status = 'sold'
    car.sold_at = utcnow()
    db.session.commit()
    flash('Listing marked as sold.', 'success')
    return redirect(url_for('dashboard.seller'))


@listings.route('/listings/<int:car_id>/repost', methods=['POST'])
@login_required
def repost_listing(car_id):
    car = Car.query.get_or_404(car_id)
    if car.seller_id != current_user.id and not current_user.is_admin:
        abort(403)
    if car.status not in ('archived', 'sold'):
        flash('Only archived or sold listings can be reposted.', 'warning')
        return redirect(url_for('dashboard.seller'))
    car.status = 'active'
    car.created_at = utcnow()
    car.archived_at = None
    car.sold_at = None
    db.session.commit()
    flash('Listing is live again!', 'success')
    return redirect(url_for('main.car_detail', slug=car.slug))