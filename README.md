# Product list cleaner and API

Cleans a supplier's product CSV, loads it into PostgreSQL, and serves it through a small Django REST framework API.

- **Python:** 3.12 or newer
- **Stack:** Django 5.2, Django REST framework 3.15+, PostgreSQL 17 (psycopg 3)
- **Time spent:** about 3.5 hours

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

Create a `.env` file in the project folder (it is git-ignored):

```bash
POSTGRES_NAME=quixta_products
POSTGRES_USER=quixta_user
POSTGRES_PASSWORD=your-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

Then load it into the current shell:

```bash
set -a; source .env; set +a
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

**Swagger UI:** open http://127.0.0.1:8000/api/swagger/ to see every endpoint and call it from the browser (choose an endpoint, then **Try it out** and **Execute**). The raw schema is at `/api/swagger/?format=openapi`.

```bash
curl -X POST http://127.0.0.1:8000/api/products/ \
  -H "Content-Type: application/json" \
  -d '{"sku": "LMP-010", "name": "Reading lamp", "category": "lighting", "price_paise": 450000, "stock": 3}'
```

## Run the tests

Tests run with pytest and pytest-django, with coverage. Load `.env` first to run them against PostgreSQL; without it they use SQLite.

```bash
set -a; source .env; set +a
pytest                       # all tests
pytest products/tests/test_api.py -k create   # one file, matching tests only
./unit-tests.sh              # coverage run -m pytest, then coverage report -m
```

`python manage.py test` still works too. Test data for the API tests comes from `ProductFactory` in `products/tests/factories.py` (factory-boy).

## How it's organised

```
products/
  cleaning.py          # all cleaning rules, plain Python, no Django imports
  models.py            # Product
  serializers.py       # API validation, reuses the functions in cleaning.py
  views.py, urls.py    # list/create and detail endpoints
  management/commands/clean_products.py   # file in, DB + rejects.csv + summary out
  tests/               # cleaning, command and API tests (pytest, factory-boy)
config/settings.py     # database from POSTGRES_* env vars
docs/LLD.md            # low-level design
```

## Decisions and assumptions

- **One set of rules.** `cleaning.py` holds every rule. The command and the serializer both call it, so the API can't drift from the import.
- **Rejects.** Columns are checked in the brief's order and the first failure gives the reason. Line numbers come from the CSV reader's position, so they stay correct if a quoted value spans lines or the file has blank lines (blank lines are skipped).
- **Duplicates.** Among valid rows for a sku, the latest `updated_at` wins. On a tie, the row lower in the file wins.
- **Safe to re-run.** The command upserts every valid row by sku in one query (`bulk_create` with `update_conflicts`, which is `INSERT ... ON CONFLICT (sku) DO UPDATE` on PostgreSQL) inside one transaction, and `updated_at` comes from the file, not `auto_now`. A second run writes the same values. It doesn't delete products that aren't in the file, such as ones created through the API.
- **Price.** Parsed with `Decimal`, not float, so `14,999.50` becomes exactly `1499950`. More than 2 decimal places is rejected rather than rounded.
- **Dates.** The shape is checked with a regex before `date.fromisoformat`, because on Python 3.11+ `fromisoformat` also accepts forms like `20260502`.
- **API input.** The API takes `price_paise` (already in paise), so it must be a whole number above 0. `sku`, `name` and `category` are cleaned the same way as in the CSV (` lmp-010 ` becomes `LMP-010`), and the unique check runs on the cleaned sku. `stock` defaults to 0, `updated_at` to today (Asia/Kolkata).
- **Database guards.** `sku` is unique, and `stock` and `price_paise` have database-level checks. If two creates race on the same sku, the `IntegrityError` is turned into a 400 with a `sku` key.
- The detail endpoint also uppercases the sku in the URL, so `/api/products/lmp-001/` works.
- An unknown `?category=` returns an empty list rather than an error.

## AI tools

- **Tools used:** Claude.
- **For which parts:** I worked in this order: first a low-level design of the modules (`docs/LLD.md`) with Claude, which I reviewed; then the code, which I checked line by line; then the tests. Claude also helped set up PostgreSQL and pytest.
- **What I changed after reviewing:**
  - **Query optimization.** The import first saved products with `update_or_create`, which runs a SELECT and then an INSERT or UPDATE for every row. I replaced it with one bulk upsert (`bulk_create(update_conflicts=True, unique_fields=["sku"])`), so the whole file is saved in a single query. A test checks there is exactly one INSERT.
