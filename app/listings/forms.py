from flask_wtf import FlaskForm
from wtforms import (StringField, IntegerField, SelectField, TextAreaField,
                     DecimalField, FieldList, BooleanField)
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError, URL


MAKES = [
    'Acura','Audi','BMW','Buick','Cadillac','Chevrolet','Chrysler',
    'Dodge','Ferrari','Ford','GMC','Honda','Hyundai','Infiniti',
    'Jeep','Kia','Lamborghini','Land Rover','Lexus','Lincoln',
    'Maserati','Mazda','Mercedes-Benz','Mitsubishi','Nissan',
    'Porsche','Ram','Rolls-Royce','Subaru','Tesla','Toyota',
    'Volkswagen','Volvo','Other',
]

BODY_TYPES = [
    'Sedan','SUV','Coupe','Convertible','Pickup Truck',
    'Hatchback','Minivan','Wagon','Van','Sports Car','Electric',
]

FUEL_TYPES = [
    'Gasoline','Diesel','Hybrid','Plug-in Hybrid',
    'Electric','Hydrogen','Flex Fuel',
]

CONDITIONS    = ['New','Used','Certified Pre-Owned']
TRANSMISSIONS = ['Automatic','Manual','CVT','Semi-Automatic']
DRIVETRAINS   = ['FWD','RWD','AWD','4WD']
US_STATES     = [
    'AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID',
    'IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS',
    'MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK',
    'OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV',
    'WI','WY','DC',
]


def _choice(lst):
    return [('', '— select —')] + [(v, v) for v in lst]


class CarListingForm(FlaskForm):
    # core
    make         = SelectField('Make', choices=_choice(MAKES), validators=[DataRequired()])
    model        = StringField('Model', validators=[DataRequired(), Length(1, 60)])
    year         = IntegerField('Year', validators=[DataRequired(), NumberRange(1900, 2100)])
    trim         = StringField('Trim / Edition', validators=[Optional(), Length(max=60)])
    vin          = StringField('VIN', validators=[Optional(), Length(min=11, max=17)])
    condition    = SelectField('Condition', choices=_choice(CONDITIONS), validators=[DataRequired()])

    # pricing
    price        = DecimalField('Price ($)', places=2, validators=[DataRequired(), NumberRange(min=0)])

    # specs
    mileage      = IntegerField('Mileage', validators=[DataRequired(), NumberRange(min=0)])
    body_type    = SelectField('Body type', choices=_choice(BODY_TYPES), validators=[DataRequired()])
    fuel_type    = SelectField('Fuel type', choices=_choice(FUEL_TYPES), validators=[DataRequired()])
    transmission = SelectField('Transmission', choices=_choice(TRANSMISSIONS), validators=[DataRequired()])
    drivetrain   = SelectField('Drivetrain', choices=_choice(DRIVETRAINS), validators=[Optional()])
    engine       = StringField('Engine', validators=[Optional(), Length(max=60)])
    horsepower   = IntegerField('Horsepower', validators=[Optional(), NumberRange(min=0, max=3000)])
    exterior_color = StringField('Exterior color', validators=[Optional(), Length(max=40)])
    interior_color = StringField('Interior color', validators=[Optional(), Length(max=40)])
    doors        = IntegerField('Doors', validators=[Optional(), NumberRange(min=1, max=10)])
    seats        = IntegerField('Seats', validators=[Optional(), NumberRange(min=1, max=20)])

    # location
    city         = StringField('City', validators=[DataRequired(), Length(max=80)])
    state        = SelectField('State', choices=_choice(US_STATES), validators=[DataRequired()])
    zip_code     = StringField('ZIP code', validators=[Optional(), Length(max=10)])

    # content
    description  = TextAreaField('Description', validators=[Optional(), Length(max=5000)])
    features     = TextAreaField('Features (one per line)', validators=[Optional()])
    primary_image_url = StringField('Main photo URL', validators=[Optional(), Length(max=500)])
    extra_images = TextAreaField('Additional photo URLs (one per line)', validators=[Optional()])

    def validate_primary_image_url(self, field):
        if field.data and not field.data.startswith(('http://', 'https://')):
            raise ValidationError('Must be a valid URL.')

    def validate_vin(self, field):
        if field.data:
            vin = field.data.upper().replace('-', '').replace(' ', '')
            if len(vin) not in (11, 17):
                raise ValidationError('VIN must be 11 or 17 characters.')
            field.data = vin