"""
Nutrition Agent Webhook Server
Automated nutrition analysis with Claude AI, Airtable integration, and email approval workflow
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify
from functools import wraps
import requests

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Environment variables
AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLE_ID = os.getenv('AIRTABLE_TABLE_ID')
AIRTABLE_TABLE_NAME = os.getenv('AIRTABLE_TABLE_NAME', 'Nutrition Requests')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
EMAIL_FROM = os.getenv('EMAIL_FROM')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
NOTIFICATION_EMAIL = os.getenv('NOTIFICATION_EMAIL')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 5000))

# Store pending approvals in memory (in production, use a database)
PENDING_APPROVALS = {}

def require_auth(f):
      """Decorator to require API key authentication"""
      @wraps(f)
      def decorated_function(*args, **kwargs):
                api_key = request.headers.get('X-API-Key')
                if not api_key or api_key != os.getenv('API_KEY'):
                              return jsonify({'error': 'Unauthorized'}), 401
                          return f(*args, **kwargs)
            return decorated_function


@app.route('/health', methods=['GET'])
def health():
      """Health check endpoint"""
    return jsonify({
              'status': 'healthy',
              'timestamp': datetime.utcnow().isoformat(),
              'environment': ENVIRONMENT
    }), 200


@app.route('/nutrition-agent', methods=['POST'])
def nutrition_agent():
      """
          Main webhook endpoint for nutrition analysis requests

              CRITICAL SECURITY: This endpoint NEVER sends emails automatically.
                  It returns 202 (Accepted) with PENDING_SEND_APPROVAL status.
                      Emails are only sent after explicit approval via /approve-and-send endpoint.

                          Spanish: NUNCA se envía email sin tu aprobación explícita
                              """
    try:
              data = request.get_json()

        if not data:
                      return jsonify({'error': 'No data provided'}), 400

        # Extract request data
        request_id = data.get('id', f"req_{datetime.utcnow().timestamp()}")
        user_email = data.get('email')
        user_name = data.get('name')
        food_items = data.get('food_items', [])
        message = data.get('message')

        logger.info(f"Received nutrition request {request_id} from {user_email}")

        # Prepare the nutrition analysis request
        analysis_request = {
                      'id': request_id,
                      'email': user_email,
                      'name': user_name,
                      'food_items': food_items,
                      'message': message,
                      'timestamp': datetime.utcnow().isoformat(),
                      'status': 'pending_approval',
                      'created_at': datetime.utcnow().isoformat()
        }

        # Store for later approval
        PENDING_APPROVALS[request_id] = analysis_request

        # Log to Airtable if configured
        if AIRTABLE_TOKEN and AIRTABLE_BASE_ID and AIRTABLE_TABLE_ID:
                      try:
                                        airtable_record = {
                                                              'fields': {
                                                                                        'Request ID': request_id,
                                                                                        'Email': user_email,
                                                                                        'Name': user_name,
                                                                                        'Food Items': json.dumps(food_items),
                                                                                        'Message': message,
                                                                                        'Status': 'Pending Approval',
                                                                                        'Created At': datetime.utcnow().isoformat()
                                                              }
                                        }

                          response = requests.post(
                                                f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_ID}",
                                                headers={
                                                                          'Authorization': f'Bearer {AIRTABLE_TOKEN}',
                        'Content-Type': 'application/json'
                                                },
                                                json=airtable_record
                          )

                if response.status_code == 200:
                                      logger.info(f"Logged request {request_id} to Airtable")
else:
                    logger.warning(f"Failed to log to Airtable: {response.status_code}")
except Exception as e:
                logger.error(f"Airtable logging error: {str(e)}")

        # Return 202 Accepted with PENDING_SEND_APPROVAL status
        # Email will NOT be sent until explicit approval
        return jsonify({
                      'status': 'PENDING_SEND_APPROVAL',
                      'message': 'Nutrition analysis request received. Awaiting approval to send response.',
            'request_id': request_id,
                      'next_step': f'/approve-and-send?request_id={request_id}',
                      'note': 'Email will NOT be sent automatically. Explicit approval required.'
        }), 202

except Exception as e:
        logger.error(f"Error processing nutrition request: {str(e)}")
                  return jsonify({'error': 'Internal server error', 'details': str(e)}), 500
