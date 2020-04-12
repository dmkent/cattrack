#!/bin/sh

# Bail on error
set -e

# Ensure that we've generated a secret key
if [ ! -f secretkey.txt ] ;
then
  python -c "import secrets; print(secrets.token_urlsafe(50))" > secretkey.txt
  chmod 0600 secretkey.txt
fi

# Collect static files
python manage.py collectstatic --no-input --settings cattrack.settings_prod

# Fire off the server
gunicorn --env DJANGO_SETTINGS_MODULE=cattrack.settings_prod --workers 3 -b 0.0.0.0:8000 cattrack.wsgi:application