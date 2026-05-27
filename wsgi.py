"""
WSGI entry point for Render.com deployment
This file explicitly imports and exposes the Flask app from app.py
to ensure Render's buildpack correctly identifies the application entry point.
"""

from app import app

if __name__ == "__main__":
      app.run()
