#!/usr/bin/env python3

import os
import sys
import json
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Configuration
CONFIG = {
    'feishu_webhook_url': os.environ.get('FEISHU_WEBHOOK_URL', ''),  # Feishu webhook
    'slack_webhook_url': os.environ.get('SLACK_WEBHOOK_URL', ''),    # Slack webhook
    'mattermost_webhook_url': os.environ.get('MATTERMOST_WEBHOOK_URL', ''),  # Mattermost webhook
    'hostname': os.environ.get('CUSTOM_HOSTNAME', os.uname()[1]),
    'log_file': os.environ.get('LOG_FILE', '/var/log/server_monitor.log'),
    'test_mode': False,
    
    # Network check configurations
    'network_check_target': os.environ.get('NETWORK_CHECK_TARGET', 'https://www.google.com'),
    'network_timeout': os.environ.get('NETWORK_TIMEOUT', 5),  # Timeout in seconds
    'max_retry': os.environ.get('MAX_RETRY', 5),  # Number of retries
    'retry_interval': os.environ.get('RETRY_INTERVAL', 10),  # Retry interval in seconds
}

# Setup logging with fallback mechanism
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Clear any existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Try to use configured log file, fall back to user directory if permission denied
log_file = CONFIG['log_file']
fallback_log_file = os.path.expanduser('~/server_monitor.log')

def setup_logging():
    """Set up logging with fallback to user home directory if system log is not writable"""
    global log_file
    
    try:
        # Try to use the configured log file
        file_handler = logging.FileHandler(log_file)
        logger.addHandler(file_handler)
        
        # Add console handler if not running from cron
        if os.environ.get('RUNNING_FROM_CRON') != 'true':
            logger.addHandler(logging.StreamHandler())
            
        logger.info(f"Logging to {log_file}")
        return True
    except PermissionError:
        # If permission denied, try to use a file in user's home directory
        try:
            log_file = fallback_log_file
            file_handler = logging.FileHandler(log_file)
            logger.addHandler(file_handler)
            
            # Add console handler if not running from cron
            if os.environ.get('RUNNING_FROM_CRON') != 'true':
                logger.addHandler(logging.StreamHandler())
                
            logger.warning(f"Permission denied for configured log file. Falling back to {log_file}")
            return True
        except Exception as e:
            # If that also fails, use only stderr
            logger.addHandler(logging.StreamHandler())
            logger.error(f"Could not create any log file, using stderr only: {str(e)}")
            return False

# Initialize logging
setup_logging()

def check_network():
    """Check if network is working by making an HTTP request to the target URL"""
    target = CONFIG['network_check_target']
    timeout = CONFIG['network_timeout']
    
    logger.info(f"Checking network connectivity to {target}")
    
    try:
        response = requests.head(target, timeout=timeout, allow_redirects=True)
        status_code = response.status_code
        
        if 200 <= status_code < 400:  # Consider any 2xx or 3xx response as success
            logger.info(f"Network check successful: {target} responded with status code {status_code}")
            return True, f"HTTP request to {target} successful (Status code: {status_code})"
        else:
            logger.warning(f"Network check failed: {target} responded with status code {status_code}")
            return False, f"HTTP request to {target} failed (Status code: {status_code})"
            
    except requests.exceptions.Timeout:
        logger.warning(f"Network check failed: connection to {target} timed out")
        return False, f"HTTP request to {target} timed out after {timeout}s"
        
    except requests.exceptions.ConnectionError:
        logger.warning(f"Network check failed: could not connect to {target}")
        return False, f"HTTP request to {target} failed: Connection error"
        
    except Exception as e:
        logger.warning(f"Network check failed with error: {str(e)}")
        return False, f"HTTP request to {target} failed: {str(e)}"

def send_feishu_notification(is_network_up, check_result):
    """Send network status alert to Feishu webhook"""
    # Skip if webhook not configured
    if not CONFIG['feishu_webhook_url']:
        logger.info("Feishu webhook URL not configured, skipping notification")
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Set title and content based on network status
    if is_network_up:
        # Don't send notification for successful checks
        return False
    else:
        title = f"❌ Network Down - {CONFIG['hostname']}"
        header_template = "red"
        content_prefix = "Network connectivity issue detected:"
    
    # Create message
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {
                "wide_screen_mode": True
            },
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": header_template
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{content_prefix}\n• {check_result}"
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"Check Time: {timestamp}"
                        }
                    ]
                }
            ]
        }
    }
    
    # Send to Feishu
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would send this network alert to Feishu:")
        logger.info(json.dumps(message, indent=2))
        return True
    
    try:
        response = requests.post(
            CONFIG['feishu_webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Network alert sent to Feishu successfully")
            return True
        else:
            logger.error(f"Failed to send network alert to Feishu: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending network alert to Feishu: {str(e)}")
        return False

def send_slack_notification(is_network_up, check_result):
    """Send network status alert to Slack webhook"""
    # Skip if webhook not configured or if network is up
    if not CONFIG['slack_webhook_url'] or is_network_up:
        return False
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create Slack message payload
    message = {
        "text": f"Network Down - {CONFIG['hostname']}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *Network Down - {CONFIG['hostname']}*"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Network connectivity issue detected:\n• {check_result}"
                }
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Check Time: {timestamp}_"
                    }
                ]
            }
        ]
    }
    
    # Send to Slack
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would send this network alert to Slack")
        return True
    
    try:
        response = requests.post(
            CONFIG['slack_webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Network alert sent to Slack successfully")
            return True
        else:
            logger.error(f"Failed to send network alert to Slack: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending network alert to Slack: {str(e)}")
        return False

def send_mattermost_notification(is_network_up, check_result):
    """Send network status alert to Mattermost webhook"""
    # Skip if webhook not configured or if network is up
    if not CONFIG['mattermost_webhook_url'] or is_network_up:
        return False
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create Mattermost message text
    text = (
        f"#### :x: Network Down - {CONFIG['hostname']}\n\n"
        f"Network connectivity issue detected:\n* {check_result}\n\n"
        f"*Check Time: {timestamp}*"
    )
    
    # Create message payload
    message = {
        "text": text
    }
    
    # Send to Mattermost
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would send this network alert to Mattermost")
        return True
    
    try:
        response = requests.post(
            CONFIG['mattermost_webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Network alert sent to Mattermost successfully")
            return True
        else:
            logger.error(f"Failed to send network alert to Mattermost: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending network alert to Mattermost: {str(e)}")
        return False

def send_alert(is_network_up, check_result):
    """Send network status alerts to all configured notification channels"""
    # Only send alerts when network is down
    if is_network_up and not CONFIG['test_mode']:
        return False
    
    # Check if any notification channel is configured
    if not (CONFIG['feishu_webhook_url'] or CONFIG['slack_webhook_url'] or CONFIG['mattermost_webhook_url']):
        logger.error("No notification webhook URLs configured. Set at least one webhook URL in the environment variables.")
        return False
    
    success = False
    
    # Send to all configured platforms
    if CONFIG['feishu_webhook_url']:
        if send_feishu_notification(is_network_up, check_result):
            success = True
    
    if CONFIG['slack_webhook_url']:
        if send_slack_notification(is_network_up, check_result):
            success = True
    
    if CONFIG['mattermost_webhook_url']:
        if send_mattermost_notification(is_network_up, check_result):
            success = True
    
    return success

def main():
    """Main function to check network connectivity and send alerts if needed"""
    logger.info("Starting network connectivity check")
    
    try:
        # Check if test mode is enabled
        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            CONFIG['test_mode'] = True
            logger.info("Running in TEST MODE")
        
        # Validate configuration
        if not (CONFIG['feishu_webhook_url'] or CONFIG['slack_webhook_url'] or CONFIG['mattermost_webhook_url']) and not CONFIG['test_mode']:
            logger.warning("No notification webhook URLs configured. Set at least one webhook URL in the environment variables.")
        
        # Try to check network connectivity with retries
        max_retry = CONFIG['max_retry']
        retry_interval = CONFIG['retry_interval']
        is_network_up = False
        check_result = ""
        
        for attempt in range(max_retry):
            is_network_up, check_result = check_network()
            if is_network_up:
                break
                
            if attempt < max_retry - 1:
                logger.info(f"Network check failed. Retrying in {retry_interval} seconds... (Attempt {attempt+1}/{max_retry})")
                time.sleep(retry_interval)
        
        # Send alert if network is down
        if not is_network_up:
            logger.warning("Network connectivity is down, sending alert")
            send_alert(is_network_up, check_result)
        else:
            logger.info("Network connectivity is up")
            
    except Exception as e:
        logger.error(f"Error in network monitoring script: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
