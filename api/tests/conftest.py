"""Config for testing."""

import os

import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_api.settings")
django.setup()

settings.ALLOWED_HOSTS = ["django", "localhost", "testserver"]
