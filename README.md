# Product list cleaner and API

Cleans a supplier's product CSV, loads it into PostgreSQL, and serves it through a small Django REST framework API.

- **Python:** 3.12 or newer
- **Stack:** Django 5.2, Django REST framework 3.15+, PostgreSQL 17 (psycopg 3)
- **Time spent:** _TODO: fill in your actual time_

## Setup

### 1. Create the database

With PostgreSQL running locally (for example `brew install postgresql@17 && brew services start postgresql@17`):

```bash
psql postgres -c "CREATE ROLE quixta_user WITH LOGIN CREATEDB PASSWORD 'your-password';"
psql postgres -c "CREATE DATABASE quixta_products OWNER quixta_user;"
```

`CREATEDB` is needed because `manage.py test` creates and drops a temporary test database.

### 2. Configure the connection

The database is read from `POSTGRES_*` environment variables:

```bash
cp .env.example .env               # then set POSTGRES_PASSWORD in .env
set -a; source .env; set +a        # load it into the current shell
```

| Variable | Default |
|---|---|
| `POSTGRES_NAME` | none (required for PostgreSQL) |
| `POSTGRES_USER` | none |
| `POSTGRES_PASSWORD` | none |
| `POSTGRES_HOST` | `localhost` |
| `POSTGRES_PORT` | `5432` |

If `POSTGRES_NAME` is not set, the project falls back to a local SQLite file (`db.sqlite3`), so it still runs without PostgreSQL.

### 3. Install and create the tables

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate           # creates the products_product table
```

## Clean and load the CSV

```bash
python manage.py clean_products products.csv
```

This writes `rejects.csv` to the current folder (change it with `--rejects path/to/file.csv`) and prints one JSON line. For the provided `products.csv`:

```json
{"loaded": 10, "rejected": {"invalid_sku": 1, "missing_name": 1, "unknown_category": 1, "invalid_price": 2, "invalid_stock": 3, "invalid_date": 1}, "duplicatesDropped": 3}
```

Running it again on the same file gives the same output and leaves the table unchanged.

## Run the dev server

```bash
python manage.py runserver
```

| Method | URL | Notes |
|---|---|---|
| GET | `/api/products/` | 5 per page, ordered by sku. `?category=lighting`, `?page=2` |
| GET | `/api/products/<sku>/` | One product, or 404 |
| POST | `/api/products/` | Create. 201 on success, 400 with a key per failing field |

```bash
curl -X POST http://127.0.0.1:8000/api/products/ \
  -H "Content-Type: application/json" \
  -d '{"sku": "LMP-010", "name": "Reading lamp", "category": "lighting", "price_paise": 450000, "stock": 3}'
```

## Run the tests

```bash
python manage.py test
```

## How it's organised

```
products/
  cleaning.py          # all cleaning rules, plain Python, no Django imports
  models.py            # Product
  serializers.py       # API validation, reuses the functions in cleaning.py
  views.py, urls.py    # list/create and detail endpoints
  management/commands/clean_products.py   # file in, DB + rejects.csv + summary out
  tests/               # cleaning, command and API tests
```

## Decisions and assumptions

- **One set of rules.** `cleaning.py` holds every rule. The command and the serializer both call it, so the API can't drift from the import.
- **Rejects.** Columns are checked in the brief's order and the first failure gives the reason. Line numbers come from the CSV reader's position, so they stay correct if a quoted value spans lines or the file has blank lines (blank lines are skipped).
- **Duplicates.** Among valid rows for a sku, the latest `updated_at` wins. On a tie, the row lower in the file wins.
- **Safe to re-run.** The command upserts by sku inside one transaction (`update_or_create`), and `updated_at` comes from the file, not `auto_now`. A second run writes the same values. It doesn't delete products that aren't in the file, such as ones created through the API.
- **Price.** Parsed with `Decimal`, not float, so `14,999.50` becomes exactly `1499950`. More than 2 decimal places is rejected rather than rounded.
- **Dates.** The shape is checked with a regex before `date.fromisoformat`, because on Python 3.11+ `fromisoformat` also accepts forms like `20260502`.
- **API input.** The API takes `price_paise` (already in paise), so it must be a whole number above 0. `sku`, `name` and `category` are cleaned the same way as in the CSV (` lmp-010 ` becomes `LMP-010`), and the unique check runs on the cleaned sku. `stock` defaults to 0, `updated_at` to today (Asia/Kolkata).
- **Database guards.** `sku` is unique, and `stock` and `price_paise` have database-level checks. If two creates race on the same sku, the `IntegrityError` is turned into a 400 with a `sku` key.
- The detail endpoint also uppercases the sku in the URL, so `/api/products/lmp-001/` works.
- An unknown `?category=` returns an empty list rather than an error.

## AI tools

- **Tools used:** Claude (Anthropic).
- **For which parts:** _TODO: describe honestly, e.g. "Claude generated the first version of the cleaning module, command, API and tests from the brief. I then reviewed and ran everything, and changed ..."_
- **One thing I changed or threw away:** _TODO: something you actually changed after reviewing._
