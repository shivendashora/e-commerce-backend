# E-commerce API (FastAPI)

An async REST API for listing and managing products. It includes JWT authentication, image uploads, Redis caching, and PostgreSQL storage.

## Features

- **Auth**: sign up, then log in with username or email to get a JWT bearer token (passwords are hashed with bcrypt)
- **Products**: create, update, soft-delete, and list products. Only the owner can modify a product.
- **Image uploads**: product thumbnails are saved to a local folder and served at `/static`
- **Search & pagination**: case-insensitive name search backed by a `pg_trgm` GIN index, with `offset`/`limit` paging
- **Caching**: the product listing is cached in Redis for 60s, and any write clears the cache

## Tech stack

FastAPI · SQLAlchemy 2 (async) · asyncpg · PostgreSQL · Redis · PyJWT · bcrypt

## Project structure

```
.
├── main.py                 # app setup, product routes
├── auth.py                 # /auth routes (signup, login, me)
├── database.py             # async engine, session dependency, table creation
├── tables.py               # SQLAlchemy models (users, products, payments)
├── model.py                # Pydantic request/response schemas
└── helpers/
    ├── auth/authHelpers.py         # password hashing, JWT, current-user dependency
    ├── files/storeFiles.py         # saving and deleting uploaded files
    └── products/productHelpers.py  # ownership checks, updates, response shaping
```

## Getting started

### Prerequisites

- Python 3.12+
- PostgreSQL running on `localhost:5432` with a database named `e-commerce`
- Redis

### Setup

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
port=8000
upload_dir=uploads
SECRET_KEY=change-me-to-a-long-random-string
ACCESS_TOKEN_EXPIRE_MINUTES=30
REDIS_URL=redis://localhost:6379/0
```

The database URL is currently hardcoded in [database.py](database.py) as `postgresql+asyncpg://postgres:postgres@localhost:5432/e-commerce`. Edit it there if your credentials are different.

### Run

```bash
python main.py
```

Tables, indexes, and the `pg_trgm` extension are created automatically on startup.

Interactive docs: http://localhost:8000/docs

## API endpoints

| Method | Path | Auth | Description |
| ------ | ---- | :--: | ----------- |
| GET | `/` | | Health check |
| POST | `/auth/signup` | | Register a user (JSON: `username`, `email`, `password`) |
| POST | `/auth/login` | | Get an access token (form: `username` (or email), `password`) |
| GET | `/auth/me` | ✔ | Current user's profile |
| POST | `/list-product` | ✔ | Create a product (form: `name`, `price`, `description`, `file`) |
| PUT | `/update-product?productId=` | ✔ | Update your own product (all form fields optional) |
| GET | `/fetchAllProducts` | | List products (`offset`, `limit`, `search`) |
| DELETE | `/delete-product/{product_id}` | ✔ | Soft-delete your own product |
| POST | `/trigger-payment` | | Placeholder payment endpoint |

Protected routes expect an `Authorization: Bearer <token>` header. In Swagger UI, click **Authorize** and log in.
