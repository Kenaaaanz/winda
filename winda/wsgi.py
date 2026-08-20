"""
WSGI config for winda project.
"""

import os
import sys
from django.core.wsgi import get_wsgi_application

# Add the project directory to the path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set the settings module based on environment
settings_module = os.environ.get('DJANGO_SETTINGS_MODULE', 'winda.settings')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

application = get_wsgi_application()