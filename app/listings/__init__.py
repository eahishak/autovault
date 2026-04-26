from flask import Blueprint

listings = Blueprint('listings', __name__)

from app.listings import routes  # noqa