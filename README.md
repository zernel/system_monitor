# Server Resource Monitoring System

This system monitors server resources and sends alerts to multiple notification platforms (Feishu, Slack, and Mattermost) when thresholds are exceeded.

## Setup

1. Clone this repository to your server, or use rsync to copy the files:
   ```bash
    rsync -avz --exclude='.git' --exclude='.DS_Store' ./ ubuntu@your_server:/home/ubuntu/system_monitor/
   ```
2. Run the setup script:
   ```bash
   chmod +x setup_monitor.sh
   sudo ./setup_monitor.sh
   ```
3. When prompted, edit the `.env` file to configure your webhook URLs:
   ```bash
   cp .env.example .env
   vim .env
   ```
4. The system will automatically start monitoring and send test alerts if configured properly

## Configuration

All configuration is managed through environment variables in the `.env` file:

- **Notification Webhooks**
  - `FEISHU_WEBHOOK_URL`: Your Feishu webhook URL (optional)
  - `SLACK_WEBHOOK_URL`: Your Slack webhook URL (optional)
  - `MATTERMOST_WEBHOOK_URL`: Your Mattermost webhook URL (optional)
  - Note: At least one webhook URL is required for notifications

- **Monitoring Thresholds**
  - `THRESHOLD_MEMORY`: Memory usage percentage threshold (default: 85.0)
  - `THRESHOLD_CPU`: CPU usage percentage threshold (default: 90.0)
  - `THRESHOLD_DISK`: Disk usage percentage threshold (default: 90.0)
  - `THRESHOLD_SWAP`: Swap usage percentage threshold (default: 80.0)

- **Check Parameters**
  - `CHECK_INTERVAL`: Seconds between consecutive checks (default: 60)
  - `CHECK_COUNT`: Number of consecutive threshold violations before alerting (default: 3)
  - `CUSTOM_HOSTNAME`: Custom server name for alerts (default: system hostname)
  - `LOG_FILE`: Log file location (default: /var/log/server_monitor.log)

- **Recovery Options**
  - `RECOVERY_COMMANDS`: Commands to execute when thresholds are exceeded (optional, separate multiple commands with semicolons)
  - `RECOVERY_WAIT_TIME`: Time to wait after executing recovery commands before rechecking resources (default: 10 seconds)

You can edit the `.env` file anytime to change these settings:

```bash
vim /path/to/system_monitor/.env
```

## Notification Channels

The monitoring system supports three notification channels:

1. **Feishu**: Enterprise collaboration platform by ByteDance
   - Set `FEISHU_WEBHOOK_URL` to enable
   - Format: Interactive card with color-coded headers

2. **Slack**: Team communication platform
   - Set `SLACK_WEBHOOK_URL` to enable
   - Format: Rich message blocks with formatted text

3. **Mattermost**: Open-source team collaboration platform
   - Set `MATTERMOST_WEBHOOK_URL` to enable
   - Format: Markdown-formatted messages

You can configure any combination of these channels simultaneously. The system will send alerts to all configured channels when thresholds are exceeded.

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

## Automatic Recovery Feature

The system now supports automatic recovery actions when resources exceed thresholds:

1. **Configure recovery commands** in your `.env` file:
   ```
   # Example: Restart services when resources are low
   RECOVERY_COMMANDS=sudo systemctl restart sing-box-legacy;sudo systemctl restart dae
   RECOVERY_WAIT_TIME=10
   ```

2. **How it works**:
   - When resources exceed thresholds, the system sends an initial alert
   - It then executes the configured recovery commands
   - After waiting for the specified time (default: 10 seconds), it checks resources again
   - A second notification is sent showing if resources have recovered or still exceed thresholds

3. **Execution flow**:
   - Alert 1: Resources exceeded thresholds, executing recovery commands
   - System executes the configured commands
   - System waits for the specified time
   - Alert 2: Either "Services recovered successfully" or "Services still experiencing issues"

4. **Security considerations**:
   - Ensure the user running the script has appropriate permissions for the recovery commands
   - Use full paths in commands to avoid path-related issues
   - Consider using sudo with NOPASSWD for specific commands if needed

## Maintenance

- **Review logs regularly** to identify patterns in resource usage
- **Update thresholds** if you find they're too sensitive or not sensitive enough by editing the `.env` file
- **Test the alert system monthly** to ensure it's functioning properly
- **Back up your `.env` file** when making configuration changes