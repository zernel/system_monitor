# Server Resource Monitoring System

This system monitors server resources and sends alerts to Feishu when thresholds are exceeded.

## Setup

1. Clone this repository to your server
2. Run the setup script:
   ```bash
   chmod +x setup_monitor.sh
   sudo ./setup_monitor.sh
   ```
3. When prompted, edit the `.env` file to configure your Feishu webhook URL:
   ```bash
   nano .env
   ```
4. The system will automatically start monitoring and send test alerts if configured properly

## Configuration

All configuration is managed through environment variables in the `.env` file:

- `FEISHU_WEBHOOK_URL`: Your Feishu webhook URL for sending alerts (required)
- `THRESHOLD_MEMORY`: Memory usage percentage threshold (default: 85.0)
- `THRESHOLD_CPU`: CPU usage percentage threshold (default: 90.0)
- `THRESHOLD_DISK`: Disk usage percentage threshold (default: 90.0)
- `THRESHOLD_SWAP`: Swap usage percentage threshold (default: 80.0)
- `CHECK_INTERVAL`: Seconds between consecutive checks (default: 60)
- `CHECK_COUNT`: Number of consecutive threshold violations before alerting (default: 3)
- `CUSTOM_HOSTNAME`: Custom server name for alerts (default: system hostname)
- `LOG_FILE`: Log file location (default: /var/log/server_monitor.log)

You can edit the `.env` file anytime to change these settings:

```bash
nano /path/to/system_monitor/.env
```

## Safe Debugging

To safely debug and test the monitoring system:

1. **Test mode**: Run the script with the `--test` flag:
   ```bash
   cd /path/to/system_monitor/
   sudo python3 server_monitor.py --test
   ```
   This will simulate the alert process without actually sending messages.

2. **Check logs**: Monitor the log file for detailed information:
   ```bash
   tail -f /var/log/server_monitor.log
   ```

3. **Adjust thresholds temporarily**: For testing, you can lower the thresholds in the `.env` file to trigger alerts more easily.

4. **Manual validation**: Verify system resource usage with standard tools:
   ```bash
   free -m
   top
   df -h
   ```

5. **Verify environment variables**: Check if environment variables are loaded correctly:
   ```bash
   cd /path/to/system_monitor/
   python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print('FEISHU_WEBHOOK_URL:', os.environ.get('FEISHU_WEBHOOK_URL'))"
   ```

## Adding Automatic Restart Functionality

To add automatic restart capabilities:

1. Create a new function in `server_monitor.py`:

```python
def restart_service(service_name):
    """Restart a system service"""
    logger.warning(f"Attempting to restart {service_name}")
    
    try:
        # Execute restart command
        result = subprocess.run(
            ["sudo", "systemctl", "restart", service_name],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Log success
        logger.info(f"Successfully restarted {service_name}")
        
        # Send notification about restart
        notify_restart_action(service_name, success=True)
        
        return True
        
    except subprocess.CalledProcessError as e:
        # Log failure
        logger.error(f"Failed to restart {service_name}: {e.stderr}")
        
        # Send notification about failed restart
        notify_restart_action(service_name, success=False, error=e.stderr)
        
        return False
```

2. Create service-specific handling in the main monitoring logic:

```python
def handle_resource_alerts(alerts, stats):
    """Handle resource alerts with appropriate actions"""
    
    # Send alert notification
    send_feishu_alert(alerts, stats)
    
    # Check for specific conditions that require service restarts
    if any(a['resource'] == 'memory_percent' and a['value'] > 95 for a in alerts):
        # Critical memory situation - identify problem services
        high_mem_processes = get_high_memory_processes()
        
        # Example: If nginx is using excessive memory
        if any(p.name() == "nginx" for p in high_mem_processes[:3]):
            restart_service("nginx")
            
        # Example: Restart dae if it's problematic
        if any(p.name() == "dae" for p in high_mem_processes[:3]):
            restart_service("dae")
```

3. Add a function to identify resource-heavy processes:

```python
def get_high_memory_processes(limit=10):
    """Get processes using the most memory"""
    return sorted(
        psutil.process_iter(['pid', 'name', 'memory_percent']),
        key=lambda p: p.info['memory_percent'],
        reverse=True
    )[:limit]
```

4. Create a notification function for restart actions:

```python
def notify_restart_action(service_name, success, error=None):
    """Send notification about service restart action"""
    
    status = "successfully restarted" if success else "failed to restart"
    color = "green" if success else "red"
    
    message = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"🔄 Service {status} - {CONFIG['hostname']}"},
                "template": color
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"Service **{service_name}** was {status} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            ]
        }
    }
    
    # Add error details if restart failed
    if error:
        message["card"]["elements"].append({
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": f"**Error details:**\n```\n{error}\n```"
            }
        })
    
    # Send to Feishu
    if not CONFIG['test_mode']:
        try:
            requests.post(
                CONFIG['webhook_url'],
                headers={"Content-Type": "application/json"},
                data=json.dumps(message)
            )
        except Exception as e:
            logger.error(f"Failed to send restart notification: {str(e)}")
```

5. Implement checks before restarting to avoid continuous restart loops:

```python
def should_restart_service(service_name):
    """Determine if a service should be restarted (avoid loops)"""
    
    # Check restart history in last 30 minutes
    restart_count = get_recent_restart_count(service_name, minutes=30)
    
    # Don't restart if already restarted 3+ times recently
    if restart_count >= 3:
        logger.warning(f"Skipping restart of {service_name} - already restarted {restart_count} times in last 30 minutes")
        return False
        
    return True
```

6. If needed, add additional environment variables in the `.env` file to control automated restart behavior:

```
# Restart settings
ENABLE_AUTO_RESTART=true
MAX_RESTART_COUNT=3
RESTART_WINDOW_MINUTES=30
```

## Maintenance

- **Review logs regularly** to identify patterns in resource usage
- **Update thresholds** if you find they're too sensitive or not sensitive enough by editing the `.env` file
- **Test the alert system monthly** to ensure it's functioning properly
- **Back up your `.env` file** when making configuration changes