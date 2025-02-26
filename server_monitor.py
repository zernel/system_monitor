#!/usr/bin/env python3

import os
import sys
import json
import time
import logging
import psutil
import requests
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Configuration
CONFIG = {
    'webhook_url': os.environ.get('FEISHU_WEBHOOK_URL', ''),  # Get webhook URL from environment variable
    'thresholds': {
        'memory_percent': float(os.environ.get('THRESHOLD_MEMORY', '85.0')),
        'cpu_percent': float(os.environ.get('THRESHOLD_CPU', '90.0')),
        'disk_percent': float(os.environ.get('THRESHOLD_DISK', '90.0')),
        'swap_percent': float(os.environ.get('THRESHOLD_SWAP', '80.0'))
    },
    'check_interval': int(os.environ.get('CHECK_INTERVAL', '60')),
    'check_count': int(os.environ.get('CHECK_COUNT', '3')),
    'hostname': os.environ.get('CUSTOM_HOSTNAME', os.uname()[1]),
    'log_file': os.environ.get('LOG_FILE', '/var/log/server_monitor.log'),
    'test_mode': False
}

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(CONFIG['log_file']),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

def get_system_stats():
    """Get current system resource usage stats"""
    stats = {
        'memory_percent': psutil.virtual_memory().percent,
        'cpu_percent': psutil.cpu_percent(interval=1),
        'swap_percent': psutil.swap_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    return stats

def check_resource_issues():
    """Check if any resource exceeds the threshold multiple times"""
    alerts = []
    consecutive_alerts = {k: 0 for k in CONFIG['thresholds'].keys()}
    
    for _ in range(CONFIG['check_count']):
        stats = get_system_stats()
        logger.info(f"Current stats: {stats}")
        
        # Check each resource
        for resource, threshold in CONFIG['thresholds'].items():
            if stats[resource] > threshold:
                consecutive_alerts[resource] += 1
                logger.warning(f"{resource} is high: {stats[resource]}% (threshold: {threshold}%)")
            else:
                consecutive_alerts[resource] = 0
                
        # Wait before next check
        time.sleep(CONFIG['check_interval'])
    
    # Only alert if a resource exceeded threshold for all checks
    for resource, count in consecutive_alerts.items():
        if count >= CONFIG['check_count']:
            stats = get_system_stats()
            alerts.append({
                'resource': resource,
                'value': stats[resource],
                'threshold': CONFIG['thresholds'][resource]
            })
    
    return alerts, get_system_stats()

def send_feishu_alert(alerts, stats):
    """Send alert to Feishu webhook"""
    if not alerts:
        return
    
    # Check if webhook URL is configured
    if not CONFIG['webhook_url']:
        logger.error("Feishu webhook URL not configured. Set the FEISHU_WEBHOOK_URL environment variable.")
        return
    
    # Format alert message for Feishu
    alert_details = "\n".join([
        f"• {a['resource'].replace('_', ' ').title()}: {a['value']:.1f}% (threshold: {a['threshold']}%)"
        for a in alerts
    ])
    
    # Get process information for high memory usage case
    top_processes = ""
    if any(a['resource'] == 'memory_percent' for a in alerts):
        processes = sorted(
            [p for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent'])],
            key=lambda p: p.info['memory_percent'],
            reverse=True
        )[:5]
        
        top_processes = "\n\n**Top Memory Processes:**\n" + "\n".join([
            f"• {p.info['name']} (PID {p.info['pid']}): Memory {p.info['memory_percent']:.1f}%, CPU {p.info['cpu_percent']:.1f}%"
            for p in processes
        ])
    
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
                    "content": f"❗ Server Resource Alert - {CONFIG['hostname']}"
                },
                "template": "red"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"The following resources have exceeded thresholds for {CONFIG['check_count']} consecutive checks:\n\n{alert_details}{top_processes}"
                    }
                },
                {
                    "tag": "hr"
                },
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**Current System Stats:**\n• Memory: {stats['memory_percent']:.1f}%\n• CPU: {stats['cpu_percent']:.1f}%\n• Swap: {stats['swap_percent']:.1f}%\n• Disk: {stats['disk_percent']:.1f}%"
                    }
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"Alert Time: {stats['timestamp']}"
                        }
                    ]
                }
            ]
        }
    }
    
    # Send to Feishu
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would send this alert to Feishu:")
        logger.info(json.dumps(message, indent=2))
        return
    
    try:
        response = requests.post(
            CONFIG['webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Alert sent to Feishu successfully")
        else:
            logger.error(f"Failed to send alert to Feishu: {response.status_code} {response.text}")
    except Exception as e:
        logger.error(f"Error sending alert to Feishu: {str(e)}")

def main():
    """Main function to check resources and send alerts if needed"""
    logger.info("Starting server resource check")
    
    try:
        # Check if test mode is enabled
        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            CONFIG['test_mode'] = True
            logger.info("Running in TEST MODE")
        
        # Validate configuration
        if not CONFIG['webhook_url'] and not CONFIG['test_mode']:
            logger.warning("No Feishu webhook URL configured. Set the FEISHU_WEBHOOK_URL environment variable.")
        
        alerts, stats = check_resource_issues()
        if alerts:
            logger.warning(f"Resource alerts triggered: {alerts}")
            send_feishu_alert(alerts, stats)
        else:
            logger.info("No resource issues detected")
            
    except Exception as e:
        logger.error(f"Error in monitoring script: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
