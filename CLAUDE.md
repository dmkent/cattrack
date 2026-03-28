# CatTrack - Claude Code Guide

## Project Overview

Personal spending tracker Django REST API. Imports bank transactions (OFX/Quicken), auto-categorizes them with scikit-learn, and provides a REST API for tracking spending by category.

**Stack:** Python 3.12, Django 5.2, Django REST Framework, scikit-learn, SQLite (dev) / PostgreSQL (prod)

## Development Environment

- **Python environment:** conda environment `cats25_py312` (Python 3.12)
- **Conda path:** `/Users/dkent/anaconda/bin/conda`
- **Python path:** `/Users/dkent/anaconda/envs/cats25_py312/bin/python`
- Dependencies managed via `requirements.txt`
- Run all Python/Django commands via: `/Users/dkent/anaconda/bin/conda run -n cats25_py312 <command>`

## Common Commands

All Python commands must be run through the conda environment.

```bash
# Shorthand used below
CONDA_RUN="/Users/dkent/anaconda/bin/conda run -n cats25_py312"

# Run all tests
$CONDA_RUN python manage.py test

# Run a specific test file
$CONDA_RUN python manage.py test ctrack.test_categories

# Run dev server
$CONDA_RUN python manage.py runserver

# Apply migrations
$CONDA_RUN python manage.py migrate

# Create new migration after model changes
$CONDA_RUN python manage.py makemigrations

# Load fixture data
$CONDA_RUN python manage.py loaddata ctrack/fixtures/*.yaml
```

## Project Structure

- `cattrack/` - Django project settings (`settings.py`, `settings_prod.py`, `urls.py`)
- `ctrack/` - Main app (models, views, API, tests, migrations)
  - `ctrack/api/` - REST API views and serializers
  - `ctrack/fixtures/` - YAML fixture data
  - `ctrack/migrations/` - Database migrations
- `docker/` - Docker entrypoint scripts
- `Dockerfile` / `Dockerfile.prod` - Dev and prod Docker images

## Testing

- Uses Django's built-in test framework (`django.test.TestCase`)
- Test files are in `ctrack/`: `test_categories.py`, `test_category_groups.py`, `test_transaction_api.py`, `tests_transaction_import.py`, `tests.py`
- CI runs `python manage.py test` on push/PR to `master`

## Key Patterns

- API views are in `ctrack/api/` with serializers in `ctrack/api/serializers/`
- Models are defined in `ctrack/models.py`
- JWT authentication via `djangorestframework-simplejwt`
- CORS configured via `django-cors-headers`
