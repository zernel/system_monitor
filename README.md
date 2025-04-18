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

## Features

- **Resource Monitoring**: Tracks CPU, memory, swap, and disk usage
- **Network Monitoring**: Checks connectivity to external services (e.g., Google)
- **Multiple Notification Channels**: Supports Feishu, Slack, and Mattermost
- **Automatic Recovery**: Can execute custom commands when issues are detected
- **Fallback Mechanisms**: Handles permission issues gracefully

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
    - Note: If the system cannot write to this location, it will automatically fall back to `~/server_monitor.log`

- **Recovery Options**
  - `RECOVERY_COMMANDS`: Commands to execute when thresholds are exceeded (optional, separate multiple commands with semicolons)
  - `RECOVERY_WAIT_TIME`: Time to wait after executing recovery commands before rechecking resources (default: 10 seconds)

- **Network Monitoring Settings**
  - `NETWORK_CHECK_TARGET`: URL to check for network connectivity (default: https://www.google.com)

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

## Network Monitoring

In addition to resource monitoring, the system can monitor network connectivity:

1. **How it works**:
   - The system makes an HTTP request to a target URL (default: https://www.google.com)
   - If the request fails after multiple retries, an alert is sent
   - The check runs every 10 minutes by default

2. **Simple configuration**:
   - Set `NETWORK_CHECK_TARGET` in your `.env` file to specify a different URL to check
   - Example: `NETWORK_CHECK_TARGET=https://example.com`

3. **Testing network monitoring**:
   ```bash
   cd /path/to/system_monitor/
   python3 network_monitor.py --test
   ```

## Troubleshooting

### Permission Issues

If you encounter permission errors when running the monitoring system:

1. **Log file access denied**: The system will automatically fall back to using a log file in the user's home directory (`~/server_monitor.log`) if it cannot write to the configured system log file.

2. **Setup with limited privileges**: If running the setup script without sudo access to system directories, the script will automatically configure an alternative log file location in your home directory.

3. **Manual permission fix**: If you want to use the system log directory but get permission errors:
   ```bash
   # Make the log file writable by all users (less secure, but simple)
   sudo touch /var/log/server_monitor.log
   sudo chmod 666 /var/log/server_monitor.log
   
   # OR, more secure option: add your user to the appropriate group
   sudo touch /var/log/server_monitor.log
   sudo chown root:adm /var/log/server_monitor.log
   sudo chmod 664 /var/log/server_monitor.log
   sudo usermod -a -G adm your-username
   # Then log out and back in for group changes to take effect
   ```

## Maintenance

- **Review logs regularly** to identify patterns in resource usage
- **Update thresholds** if you find they're too sensitive or not sensitive enough by editing the `.env` file
- **Test the alert system monthly** to ensure it's functioning properly
- **Back up your `.env` file** when making configuration changes

## Updating the System

When updating the monitoring system using rsync, file permissions may be reset, causing scripts to lose their executable status. To fix this:

1. After updating with rsync, run the update script to restore permissions:
   ```bash
   cd /path/to/system_monitor/
   chmod +x update_monitor.sh  # First make the update script itself executable
   ./update_monitor.sh
   ```

2. Alternatively, you can run the setup script with the update flag:
   ```bash
   cd /path/to/system_monitor/
   chmod +x setup_monitor.sh  # First make the setup script executable
   ./setup_monitor.sh --update
   ```

This will ensure all scripts have the correct executable permissions after an update.

## Log Management

Ubuntu system log files (such as /var/log/syslog) can accumulate over time and potentially consume a large amount of disk space. Here are effective methods for managing system logs:

### Understanding logrotate

Ubuntu uses the logrotate tool by default to automatically manage and rotate log files:

1. **Check current configuration**:
   ```bash
   cat /etc/logrotate.d/rsyslog
   ```
   This displays the rotation configuration for syslog and other system logs.

2. **Default behavior**:
   - Logs are typically rotated weekly
   - Logs are kept for 4 weeks
   - Rotated logs are compressed

### Customizing Log Rotation

If the default configuration doesn't meet your needs, you can customize the logrotate configuration:

1. **Modify existing configuration**:
   ```bash
   sudo vim /etc/logrotate.d/rsyslog
   ```

2. **Configuration example** - Rotate large log files more frequently:
   ```
   /var/log/syslog
   {
       su root syslog
       rotate 7
       daily
       maxsize 100M
       missingok
       notifempty
       delaycompress
       compress
       postrotate
           /usr/lib/rsyslog/rsyslog-rotate
       endscript
   }
   ```
   
   - `su root syslog`: Specifies to use root user and syslog group for log rotation (resolves permission issues)
   - `rotate 7`: Keeps 7 rotated files
   - `daily`: Rotates logs daily
   - `maxsize 100M`: Rotates when file exceeds 100MB, even if not yet rotation time

3. **Apply new configuration**:
   ```bash
   sudo logrotate -f /etc/logrotate.d/rsyslog
   ```

   If you encounter a permission error like this:
   ```
   error: skipping "/var/log/syslog" because parent directory has insecure permissions (It's world writable or writable by group which is not "root") Set "su" directive in config file to tell logrotate which user/group should be used for rotation.
   ```
   
   Make sure you've added the `su root syslog` directive to your configuration file as shown in the example above. This tells logrotate to use the root user and syslog group when performing log rotation.

### Manually Handling Large Log Files

If log files are already large:

1. **Safely empty log files**:
   ```bash
   sudo truncate -s 0 /var/log/syslog
   ```
   This empties the file content while preserving the file itself.

2. **Compress old logs**:
   ```bash
   sudo gzip /var/log/syslog.1
   ```

3. **Check log directory usage**:
   ```bash
   sudo du -sh /var/log/*
   ```


