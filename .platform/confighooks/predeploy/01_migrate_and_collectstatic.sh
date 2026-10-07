#!/bin/bash
# Same as .platform/hooks/predeploy. EB runs only confighooks when environment properties change, and rebuilds
# the app folder without the collected static files, so without this the admin breaks after any config change.
set -e

source /var/app/venv/*/bin/activate

cd /var/app/staging

python manage.py migrate --noinput
python manage.py collectstatic --noinput
