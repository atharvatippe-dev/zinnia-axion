"""
WSGI entry point for Gunicorn.
Usage: gunicorn wsgi:application
"""
from backend.app import create_app
from backend.config import Config

config = Config()
application = create_app(config)

# For debugging
if __name__ == "__main__":
    application.run()
