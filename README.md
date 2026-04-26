# AutoVault

AutoVault is a car marketplace I built for my web development class at the University of Rochester. Buyers can browse listings, save favorites, compare vehicles side-by-side, and message sellers directly. Sellers get a dashboard to manage their inventory. There's also a full admin portal and an AI assistant powered by the Anthropic API.

The stack is Flask, SQLAlchemy, and plain HTML/CSS/JavaScript — no React, no Vue, no ORM abstractions beyond SQLAlchemy itself.

---

## Getting it running

```bash
git clone <repo-url>
cd autovault

python -m venv venv
source venv/bin/activate      # Mac/Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt
python run.py
```

Open `http://127.0.0.1:5000`. The database creates itself on first boot and seeds 25 car listings from `seed_data.json`. Two accounts are also created automatically so you don't have to register.

**Admin:** `admin@autovault.com` / `Admin1234!`  
**Seller:** `demo@autovault.com` / `Demo1234!`

---

## Environment

A working `.env` file is already included. You don't need to touch anything to run it locally. The optional variables are:

| Variable | What it does |
|---|---|
| `ANTHROPIC_API_KEY` | Enables the AI assistant on listing pages |
| `MAIL_USERNAME` / `MAIL_PASSWORD` | Gmail credentials for password reset emails |
| `ARCHIVE_AFTER_DAYS` | How many days before a listing gets archived (default: 40) |

Everything else (`SECRET_KEY`, `FLASK_CONFIG`, etc.) is pre-configured in `.env`.

---

## Structure

```
autovault/
├── run.py
├── config.py                   # Dev / Testing / Production configs
├── seed_data.json              # 25 listings loaded on first boot
├── .env
│
├── app/
│   ├── __init__.py             # create_app factory
│   ├── extensions.py           # db, login_manager, mail, bcrypt, csrf
│   ├── models.py               # 7 models
│   ├── utils.py                # archiving, seeding, slug generation, formatters
│   │
│   ├── auth/                   # register, login, logout, password reset, edit profile
│   ├── main/                   # homepage, browse, car detail, compare, archive
│   ├── listings/               # create, edit, delete, mark sold, repost
│   ├── dashboard/              # buyer and seller dashboards
│   ├── messages/               # inbox and conversation threads
│   ├── admin/                  # user management, listing management, stats
│   ├── api/                    # JSON endpoints for all AJAX features
│   │
│   ├── static/
│   │   ├── css/                # main.css, components.css, dashboard.css, admin.css
│   │   └── js/
│   │       ├── search.js       # autocomplete dropdown
│   │       ├── filters.js      # live filter panel on browse page
│   │       ├── favorites.js    # heart button toggle
│   │       ├── messages.js     # AJAX send + polling for new messages
│   │       ├── compare.js      # scoring engine + highlight logic
│   │       ├── calculator.js   # loan amortization + canvas chart
│   │       ├── image_gallery.js
│   │       └── ai_assistant.js
│   │
│   └── templates/
│       ├── base.html
│       ├── index.html
│       ├── browse.html
│       ├── car_detail.html
│       ├── compare.html
│       ├── archive.html
│       ├── seller_profile.html
│       ├── auth/
│       ├── dashboard/
│       ├── listings/
│       ├── messages/
│       ├── admin/
│       ├── partials/
│       └── errors/
│
└── tests/                      # 173 tests across 9 files
```

---

## Database

Seven tables. Cascade deletes on all relationships.

**users** — `role` is `buyer`, `seller`, or `admin`. `avatar_url` takes a URL or a base64 data URI so users can upload photos directly. Password reset uses a signed token stored in `reset_token` with a 2-hour expiry in `reset_token_expires`.

**cars** — Price is stored in cents to avoid floating-point issues. `slug` is generated from year/make/model/id. `original_price` gets set when a seller drops the price — that's what triggers the Price Drop badge. `features` is a JSON array stored as a string. `status` is `active`, `archived`, `sold`, or `draft`.

**car_images** — Extra photos per listing, ordered by `display_order`.

**messages** — Tied to a sender, receiver, and specific car. `is_read` flips when the receiver opens the thread.

**favorites** — Unique on `(user_id, car_id)`. Toggled via AJAX.

**reviews** — 1–5 star ratings, one per buyer/seller pair. The seller's `avg_rating` is a computed property on the model.

**notifications** — Auto-created on new messages, price drops, and archival events. Fetched on demand from the bell icon — no WebSockets needed.

---

## Pages

| URL | What's there |
|---|---|
| `/` | Hero, featured listings, browse by make |
| `/browse` | Full marketplace with live filters |
| `/car/<slug>` | Listing detail, gallery, calculator, AI assistant |
| `/compare?ids=1&ids=2` | Side-by-side comparison, up to 3 cars |
| `/archive` | Listings older than 40 days |
| `/seller/<id>` | Public seller profile |
| `/register` | Create an account |
| `/login` | Sign in |
| `/dashboard` | Redirects to buyer or seller dashboard |
| `/listings/new` | Post a listing |
| `/messages` | Inbox |
| `/admin/` | Admin portal |

### API

| Endpoint | Auth | Description |
|---|---|---|
| `GET /api/search?q=` | No | Autocomplete |
| `GET /api/cars` | No | Filtered car grid, JSON or HTML |
| `POST /api/favorites` | Yes | Toggle saved |
| `GET /api/notifications` | Yes | Notification list |
| `POST /api/messages/send` | Yes | Send a message |
| `GET /api/messages/poll` | Yes | Check for new messages |
| `GET /api/compare?ids=` | No | Comparison data |
| `POST /api/ai-assistant` | Yes | AI chat |

---

## Tests

```bash
python -m pytest
python -m pytest --cov=app --cov-report=term-missing
```

173 tests, 0 failures. Each test runs in its own transaction that rolls back at the end, so there's no shared state between tests and no schema teardown needed between runs.

---

## Assignment Requirements

### HTML, CSS, Python/Flask, SQLAlchemy
The whole project. Seven models, each with well over three non-PK columns.

### User Authentication
Three roles with different permissions. Registration at `/register` lets users pick buyer or seller. All protected routes use `@login_required`. Seller-only routes additionally call `_seller_required()` which aborts with 403. Admin routes use the `@admin_required` decorator in `app/admin/decorators.py`. Passwords go through bcrypt. Password reset sends a tokenized link via email that expires after 2 hours.

### AJAX
Four separate AJAX systems, each talking to a different API endpoint:

- **Browse filters** (`filters.js`) hit `/api/cars?format=html` and swap the grid innerHTML without a reload. Requests are debounced so they don't fire on every keystroke.
- **Favorites** (`favorites.js`) POST to `/api/favorites` and update the heart icon state immediately.
- **Messaging** (`messages.js`) sends via `/api/messages/send` with an optimistic append so the message appears before the server confirms, then polls `/api/messages/poll` every 5 seconds for replies.
- **Search** (`search.js`) debounces GET requests to `/api/search` and renders a keyboard-navigable dropdown.

### Additional DB Interactions
Every table has real insert and delete paths. Listings are created and deleted in `app/listings/routes.py`. Messages in `app/messages/routes.py`. Favorites and notifications in `app/api/routes.py`. The admin portal in `app/admin/routes.py` can hard-delete users and listings. Cascade deletes keep everything consistent automatically.

### Front-End JS Application
`compare.js` is the most involved module. It reads numeric spec values from `data-value` attributes on the comparison table, scores each car across four weighted criteria (price and mileage worth 3 points each, year 2, horsepower 1), finds the best and worst in each row, adds highlight classes, computes an overall winner, and animates a score bar — all in vanilla JS with no libraries.

`calculator.js` implements the loan amortization formula `M = P[r(1+r)^n] / [(1+r)^n−1]`, recalculates on every input change, and draws a donut chart on a canvas element showing how much of the total payment is principal vs interest.

### Unit Tests
Nine test files, 173 tests. Transaction-isolated using SQLAlchemy savepoints — each test gets a clean state without dropping and recreating tables. Fixtures use UUID-suffixed emails to avoid conflicts with the auto-seeded admin account.

### JSON Parsing
`seed_data.json` at the root has 25 car listings. `seed_database()` in `app/utils.py` reads it with `json.load()` on first boot (called from `create_app` when the cars table is empty) and inserts each listing, including features stored as a JSON array in the `cars.features` column.