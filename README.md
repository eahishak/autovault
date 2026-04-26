# AutoVault

Vehicle marketplace. Buyers browse and filter listings, save favorites, compare cars side by side, and message sellers directly. Sellers manage inventory from a dashboard. Listings auto-archive after 40 days.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![Flask](https://img.shields.io/badge/Flask-3.0-lightgrey) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red) ![Tests](https://img.shields.io/badge/tests-173%20passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-green)

## Stack

- **Backend:** Python 3.12, Flask 3.0, SQLAlchemy 2.0
- **Auth:** Flask-Login, Flask-Bcrypt, Flask-WTF
- **Frontend:** Vanilla JS (ES6+), HTML5, CSS3 — no framework
- **AI:** Anthropic Claude API
- **Tests:** pytest, pytest-cov

## Quickstart

```bash
git clone https://github.com/eahishak/autovault.git
cd autovault

python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

Opens at `http://127.0.0.1:5000`. Database initializes on first boot, seeds 25 listings from `seed_data.json`, and provisions two accounts:

```
admin@autovault.com  /  Admin1234!
demo@autovault.com   /  Demo1234!
```

## Configuration

`.env.example` works as-is for local development. Optional overrides:

```bash
ANTHROPIC_API_KEY=     # AI assistant on listing pages
MAIL_USERNAME=         # Gmail address for password reset emails
MAIL_PASSWORD=         # App password, not account password
ARCHIVE_AFTER_DAYS=40  # Listing lifetime before auto-archive
```

## Project Layout

```
app/
├── __init__.py        # application factory
├── models.py          # 7 ORM models
├── utils.py           # archiving, slugs, seed loader, formatters
├── auth/              # register · login · logout · password reset · profile
├── main/              # index · browse · car detail · compare · archive
├── listings/          # create · edit · delete · mark sold · repost
├── dashboard/         # buyer and seller views
├── messages/          # inbox · conversation threads
├── admin/             # user management · listing management · stats
├── api/               # JSON endpoints for all client-side features
├── static/
│   ├── css/           # main · components · dashboard · admin
│   └── js/
│       ├── search.js         # debounced autocomplete
│       ├── filters.js        # live filter → /api/cars?format=html
│       ├── favorites.js      # optimistic heart toggle
│       ├── messages.js       # optimistic send + 5s poll
│       ├── compare.js        # weighted scoring engine
│       ├── calculator.js     # amortization + canvas chart
│       ├── image_gallery.js  # lightbox
│       └── ai_assistant.js   # chat widget
└── templates/
```

## Data Model

Seven tables, cascade deletes throughout.

| Table | Notes |
|---|---|
| `users` | Roles: `buyer` / `seller` / `admin`. `avatar_url` takes a URL or base64 data URI. Signed reset token with 2h expiry. |
| `cars` | Price in cents. `slug` from `{year}-{make}-{model}-{id}`. `original_price` set on reduction → triggers Price Drop badge. `features` as JSON string. |
| `car_images` | Extra photos per listing ordered by `display_order`. |
| `messages` | Scoped to `(sender, receiver, car)`. `is_read` flips on thread open. |
| `favorites` | Unique on `(user_id, car_id)`. |
| `reviews` | 1–5 stars, one per `(reviewer, reviewee)`. Seller `avg_rating` is a computed property. |
| `notifications` | Auto-created on messages, price drops, archival. Polled on demand. |

## API

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/api/search?q=` | — | Typeahead |
| GET | `/api/cars` | — | Filtered grid. `format=html` returns renderable markup. |
| POST | `/api/favorites` | ✓ | Toggle. Body: `{ car_id }` |
| GET | `/api/notifications` | ✓ | Unread list |
| POST | `/api/messages/send` | ✓ | Body: `{ car_id, receiver_id, content }` |
| GET | `/api/messages/poll` | ✓ | Messages after `since_id` |
| GET | `/api/compare?ids=` | — | Spec data for up to 3 cars |
| POST | `/api/ai-assistant` | ✓ | Claude Q&A |

## Tests

```bash
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
```

173 tests, 0 failures. Per-test transaction isolation via SQLAlchemy savepoints — no schema teardown between runs.

## Deployment

```bash
FLASK_CONFIG=production
SECRET_KEY=<generated>
DATABASE_URL=postgresql://user:pass@host/autovault

gunicorn "app:create_app()" -w 4 -b 0.0.0.0:8000
```

`ProductionConfig` enables `SESSION_COOKIE_SECURE` and a rotating file log handler. Swap SQLite for Postgres or MySQL via `DATABASE_URL` — no code changes required.

## License

MIT