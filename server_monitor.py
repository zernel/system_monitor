#!/usr/bin/env python3

import os
import sys
import json
import time
import logging
import psutil
import requests
import subprocess
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Configuration
CONFIG = {
    'feishu_webhook_url': os.environ.get('FEISHU_WEBHOOK_URL', ''),  # Feishu webhook
    'slack_webhook_url': os.environ.get('SLACK_WEBHOOK_URL', ''),    # Slack webhook
    'mattermost_webhook_url': os.environ.get('MATTERMOST_WEBHOOK_URL', ''),  # Mattermost webhook
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
    'test_mode': False,
    'recovery_commands': os.environ.get('RECOVERY_COMMANDS', '').strip(),
    'recovery_wait_time': int(os.environ.get('RECOVERY_WAIT_TIME', '10'))
}

# Setup logging - MODIFIED to prevent duplicate logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# Clear any existing handlers
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# Add only the appropriate handlers based on execution context
if os.environ.get('RUNNING_FROM_CRON') == 'true':
    # When running from cron, only use file handler as stdout is redirected to the file anyway
    logger.addHandler(logging.FileHandler(CONFIG['log_file']))
else:
    # Interactive mode - add both handlers
    logger.addHandler(logging.FileHandler(CONFIG['log_file']))
    logger.addHandler(logging.StreamHandler())

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

def execute_recovery_commands():
    """Execute recovery commands and return results"""
    if not CONFIG['recovery_commands']:
        logger.info("No recovery commands configured")
        return "No recovery commands configured", False
    
    logger.info(f"Executing recovery commands: {CONFIG['recovery_commands']}")
    
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would execute recovery commands")
        return CONFIG['recovery_commands'], True
    
    results = []
    success = True
    
    # Split and execute multiple commands
    commands = CONFIG['recovery_commands'].split(';')
    for cmd in commands:
        cmd = cmd.strip()
        if not cmd:
            continue
            
        try:
            logger.info(f"Executing command: {cmd}")
            result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
            results.append(f"✅ {cmd}")
            logger.info(f"Command executed successfully: {cmd}")
        except subprocess.CalledProcessError as e:
            results.append(f"❌ {cmd} (Error: {str(e)})")
            logger.error(f"Failed to execute command: {cmd}, error: {str(e)}")
            success = False
    
    return "\n".join(results), success

def send_feishu_notification(alerts, stats, is_recovery_check=False, recovery_results=None):
    """Send alert to Feishu webhook"""
    # Skip if webhook not configured
    if not CONFIG['feishu_webhook_url']:
        logger.info("Feishu webhook URL not configured, skipping notification")
        return False

    # Set different title and content based on notification type
    if is_recovery_check:
        if not alerts:
            title = f"✅ Services Recovered - {CONFIG['hostname']}"
            header_template = "green"
            content_prefix = "System resources have returned to normal levels!"
        else:
            title = f"⚠️ Services Still Affected - {CONFIG['hostname']}"
            header_template = "orange"
            content_prefix = "System resources are still exceeding thresholds after recovery attempts:"
            
        alert_details = "\n".join([
            f"• {a['resource'].replace('_', ' ').title()}: {a['value']:.1f}% (threshold: {a['threshold']}%)"
            for a in alerts
        ]) if alerts else ""
        
        recovery_info = f"\n\n**Recovery Commands Executed:**\n{recovery_results}" if recovery_results else ""
        
    else:
        title = f"❗ Resource Alert - {CONFIG['hostname']}"
        header_template = "red"
        content_prefix = f"The following resources have exceeded thresholds for {CONFIG['check_count']} consecutive checks:"
        
        alert_details = "\n".join([
            f"• {a['resource'].replace('_', ' ').title()}: {a['value']:.1f}% (threshold: {a['threshold']}%)"
            for a in alerts
        ])
        
        recovery_info = f"\n\n**Recovery Commands to Execute:**\n{CONFIG['recovery_commands']}" if CONFIG['recovery_commands'] else ""
    
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
                    "content": title
                },
                "template": header_template
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{content_prefix}\n{alert_details}{recovery_info}{top_processes}"
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
        return True
    
    try:
        response = requests.post(
            CONFIG['feishu_webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Alert sent to Feishu successfully")
            return True
        else:
            logger.error(f"Failed to send alert to Feishu: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending alert to Feishu: {str(e)}")
        return False

def send_slack_notification(alerts, stats, is_recovery_check=False, recovery_results=None):
    """Send alert to Slack webhook"""
    # Skip if webhook not configured
    if not CONFIG['slack_webhook_url']:
        logger.info("Slack webhook URL not configured, skipping notification")
        return False
    
    # Set message header based on notification type
    if is_recovery_check:
        if not alerts:
            header = f"✅ *Services Recovered - {CONFIG['hostname']}*"
            content_prefix = "System resources have returned to normal levels!"
        else:
            header = f"⚠️ *Services Still Affected - {CONFIG['hostname']}*"
            content_prefix = "System resources are still exceeding thresholds after recovery attempts:"
    else:
        header = f"❗ *Resource Alert - {CONFIG['hostname']}*"
        content_prefix = f"The following resources have exceeded thresholds for {CONFIG['check_count']} consecutive checks:"

    # Format alert details
    alert_details = ""
    if alerts:
        alert_details = "\n".join([
            f"• {a['resource'].replace('_', ' ').title()}: {a['value']:.1f}% (threshold: {a['threshold']}%)"
            for a in alerts
        ])
    
    # Add recovery information if applicable
    recovery_info = ""
    if is_recovery_check and recovery_results:
        recovery_info = f"\n\n*Recovery Commands Executed:*\n{recovery_results}"
    elif not is_recovery_check and CONFIG['recovery_commands']:
        recovery_info = f"\n\n*Recovery Commands to Execute:*\n{CONFIG['recovery_commands']}"
    
    # Add process information for high memory usage
    top_processes = ""
    if any(a['resource'] == 'memory_percent' for a in alerts):
        processes = sorted(
            [p for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent'])],
            key=lambda p: p.info['memory_percent'],
            reverse=True
        )[:5]
        
        top_processes = "\n\n*Top Memory Processes:*\n" + "\n".join([
            f"• {p.info['name']} (PID {p.info['pid']}): Memory {p.info['memory_percent']:.1f}%, CPU {p.info['cpu_percent']:.1f}%"
            for p in processes
        ])
    
    # Build system stats section
    system_stats = (
        f"*Current System Stats:*\n"
        f"• Memory: {stats['memory_percent']:.1f}%\n"
        f"• CPU: {stats['cpu_percent']:.1f}%\n"
        f"• Swap: {stats['swap_percent']:.1f}%\n"
        f"• Disk: {stats['disk_percent']:.1f}%\n\n"
        f"_Alert Time: {stats['timestamp']}_"
    )
    
    # Create Slack message payload
    message = {
        "text": f"Server Monitor Alert - {CONFIG['hostname']}",
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": header
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{content_prefix}\n{alert_details}{recovery_info}{top_processes}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": system_stats
                }
            }
        ]
    }
    
    # Send to Slack
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would send this alert to Slack:")
        logger.info(json.dumps(message, indent=2))
        return True
    
    try:
        response = requests.post(
            CONFIG['slack_webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Alert sent to Slack successfully")
            return True
        else:
            logger.error(f"Failed to send alert to Slack: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending alert to Slack: {str(e)}")
        return False

def send_mattermost_notification(alerts, stats, is_recovery_check=False, recovery_results=None):
    """Send alert to Mattermost webhook"""
    # Skip if webhook not configured
    if not CONFIG['mattermost_webhook_url']:
        logger.info("Mattermost webhook URL not configured, skipping notification")
        return False
    
    # Set message header based on notification type
    if is_recovery_check:
        if not alerts:
            header = f"#### :white_check_mark: Services Recovered - {CONFIG['hostname']}"
            content_prefix = "System resources have returned to normal levels!"
        else:
            header = f"#### :warning: Services Still Affected - {CONFIG['hostname']}"
            content_prefix = "System resources are still exceeding thresholds after recovery attempts:"
    else:
        header = f"#### :rotating_light: Resource Alert - {CONFIG['hostname']}"
        content_prefix = f"The following resources have exceeded thresholds for {CONFIG['check_count']} consecutive checks:"

    # Format alert details
    alert_details = ""
    if alerts:
        alert_details = "\n" + "\n".join([
            f"* {a['resource'].replace('_', ' ').title()}: {a['value']:.1f}% (threshold: {a['threshold']}%)"
            for a in alerts
        ])
    
    # Add recovery information if applicable
    recovery_info = ""
    if is_recovery_check and recovery_results:
        recovery_info = f"\n\n**Recovery Commands Executed:**\n```\n{recovery_results}\n```"
    elif not is_recovery_check and CONFIG['recovery_commands']:
        recovery_info = f"\n\n**Recovery Commands to Execute:**\n```\n{CONFIG['recovery_commands']}\n```"
    
    # Add process information for high memory usage
    top_processes = ""
    if any(a['resource'] == 'memory_percent' for a in alerts):
        processes = sorted(
            [p for p in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent'])],
            key=lambda p: p.info['memory_percent'],
            reverse=True
        )[:5]
        
        process_list = "\n" + "\n".join([
            f"* {p.info['name']} (PID {p.info['pid']}): Memory {p.info['memory_percent']:.1f}%, CPU {p.info['cpu_percent']:.1f}%"
            for p in processes
        ])
        top_processes = f"\n\n**Top Memory Processes:**{process_list}"
    
    # Build system stats section
    system_stats = (
        f"**Current System Stats:**\n"
        f"* Memory: {stats['memory_percent']:.1f}%\n"
        f"* CPU: {stats['cpu_percent']:.1f}%\n"
        f"* Swap: {stats['swap_percent']:.1f}%\n"
        f"* Disk: {stats['disk_percent']:.1f}%\n\n"
        f"*Alert Time: {stats['timestamp']}*"
    )
    
    # Create Mattermost message text
    text = (
        f"{header}\n\n"
        f"{content_prefix}{alert_details}{recovery_info}{top_processes}\n\n"
        f"---\n\n"
        f"{system_stats}"
    )
    
    # Create message payload
    message = {
        "text": text
    }
    
    # Send to Mattermost
    if CONFIG['test_mode']:
        logger.info("TEST MODE: Would send this alert to Mattermost:")
        logger.info(json.dumps(message, indent=2))
        return True
    
    try:
        response = requests.post(
            CONFIG['mattermost_webhook_url'],
            headers={"Content-Type": "application/json"},
            data=json.dumps(message)
        )
        if response.status_code == 200:
            logger.info("Alert sent to Mattermost successfully")
            return True
        else:
            logger.error(f"Failed to send alert to Mattermost: {response.status_code} {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending alert to Mattermost: {str(e)}")
        return False

def send_alert(alerts, stats, is_recovery_check=False, recovery_results=None):
    """Send alerts to all configured notification channels"""
    if not alerts and not is_recovery_check:
        return False
    
    # Check if any notification channel is configured
    if not (CONFIG['feishu_webhook_url'] or CONFIG['slack_webhook_url'] or CONFIG['mattermost_webhook_url']):
        logger.error("No notification webhook URLs configured. Set at least one webhook URL in the environment variables.")
        return False
    
    success = False
    
    # Send to all configured platforms
    if CONFIG['feishu_webhook_url']:
        if send_feishu_notification(alerts, stats, is_recovery_check, recovery_results):
            success = True
    
    if CONFIG['slack_webhook_url']:
        if send_slack_notification(alerts, stats, is_recovery_check, recovery_results):
            success = True
    
    if CONFIG['mattermost_webhook_url']:
        if send_mattermost_notification(alerts, stats, is_recovery_check, recovery_results):
            success = True
    
    return success

def main():
    """Main function to check resources and send alerts if needed"""
    logger.info("Starting server resource check")
    
    try:
        # Check if test mode is enabled
        if len(sys.argv) > 1 and sys.argv[1] == "--test":
            CONFIG['test_mode'] = True
            logger.info("Running in TEST MODE")
        
        # Validate configuration
        if not (CONFIG['feishu_webhook_url'] or CONFIG['slack_webhook_url'] or CONFIG['mattermost_webhook_url']) and not CONFIG['test_mode']:
            logger.warning("No notification webhook URLs configured. Set at least one webhook URL in the environment variables.")
        
        alerts, stats = check_resource_issues()
        if alerts:
            logger.warning(f"Resource alerts triggered: {alerts}")
            send_alert(alerts, stats)
            
            # Execute recovery commands if configured
            if CONFIG['recovery_commands']:
                recovery_results, success = execute_recovery_commands()
                
                # Wait for specified time
                logger.info(f"Waiting {CONFIG['recovery_wait_time']} seconds for recovery...")
                time.sleep(CONFIG['recovery_wait_time'])
                
                # Recheck resource status
                recovery_alerts, recovery_stats = check_resource_issues()
                
                # Send recovery status notification
                send_alert(recovery_alerts, recovery_stats, is_recovery_check=True, recovery_results=recovery_results)
        else:
            logger.info("No resource issues detected")
            
    except Exception as e:
        logger.error(f"Error in monitoring script: {str(e)}", exc_info=True)

if __name__ == "__main__":
    main()
