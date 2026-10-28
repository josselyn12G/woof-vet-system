#!/usr/bin/env bash
# Lo ejecuta Render en cada despliegue (Build Command: ./build.sh)
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
