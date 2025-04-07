from pymongo import MongoClient
from django.conf import settings
import os

# Get MongoDB connection details from settings or environment variables
MONGODB_HOST = getattr(settings, 'MONGODB_HOST', os.environ.get('MONGODB_HOST', 'localhost'))
MONGODB_PORT = int(getattr(settings, 'MONGODB_PORT', os.environ.get('MONGODB_PORT', 27017)))
MONGODB_USERNAME = getattr(settings, 'MONGODB_USERNAME', os.environ.get('MONGODB_USERNAME', ''))
MONGODB_PASSWORD = getattr(settings, 'MONGODB_PASSWORD', os.environ.get('MONGODB_PASSWORD', ''))
MONGODB_DATABASE = getattr(settings, 'MONGODB_DATABASE', os.environ.get('MONGODB_DATABASE', 'banking_ops'))

# Establish MongoDB connection
client = MongoClient(
    host=MONGODB_HOST,
    port=MONGODB_PORT,
    username=MONGODB_USERNAME or None,
    password=MONGODB_PASSWORD or None,
    authSource='admin' if MONGODB_USERNAME else None
)

# Get database
db = client[MONGODB_DATABASE]

# Define collections
resources = db.resources
services = db.services
dependencies = db.dependencies
pricing = db.pricing
alerts = db.alerts
usage_history = db.usage_history