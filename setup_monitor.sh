#!/bin/bash

set -e

# Script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
MONITOR_SCRIPT="$SCRIPT_DIR/server_monitor.py"
ENV_EXAMPLE="$SCRIPT_DIR/.env.example"
ENV_FILE="$SCRIPT_DIR/.env"
DEFAULT_LOG_FILE="/var/log/server_monitor.log"
FALLBACK_LOG_FILE="$HOME/server_monitor.log"

# Function to ensure all required files have correct permissions
ensure_permissions() {
    echo "Setting correct permissions for scripts..."
    chmod +x "$SCRIPT_DIR/server_monitor.py"
    chmod +x "$SCRIPT_DIR/setup_monitor.sh"
    
    # Add any other scripts that need executable permissions
    if [ -f "$SCRIPT_DIR/update_monitor.sh" ]; then
        chmod +x "$SCRIPT_DIR/update_monitor.sh"
    fi
    
    echo "Permissions set successfully."
}

# Function to set up the log file with appropriate permissions
setup_log_file() {
    # Get log file location from .env if available
    if [ -f "$ENV_FILE" ]; then
        LOG_FILE_ENV=$(grep -E "^LOG_FILE=" "$ENV_FILE" | cut -d= -f2)
        if [ -n "$LOG_FILE_ENV" ]; then
            DEFAULT_LOG_FILE="$LOG_FILE_ENV"
        fi
    fi
    
    # Try to create system log file, fall back to user directory if we can't
    if sudo touch "$DEFAULT_LOG_FILE" 2>/dev/null && sudo chmod 666 "$DEFAULT_LOG_FILE" 2>/dev/null; then
        echo "Successfully created log file: $DEFAULT_LOG_FILE (with global write permissions)"
        LOG_FILE="$DEFAULT_LOG_FILE"
    else
        echo "Could not create log file in system directory. Using user directory: $FALLBACK_LOG_FILE"
        touch "$FALLBACK_LOG_FILE"
        chmod 644 "$FALLBACK_LOG_FILE"
        LOG_FILE="$FALLBACK_LOG_FILE"
        
        # Update .env file with new log location if needed
        if [ -f "$ENV_FILE" ]; then
            if grep -q "^LOG_FILE=" "$ENV_FILE"; then
                sed -i "s|^LOG_FILE=.*|LOG_FILE=$FALLBACK_LOG_FILE|" "$ENV_FILE"
            else
                echo "LOG_FILE=$FALLBACK_LOG_FILE" >> "$ENV_FILE"
            fi
        fi
    fi
    
    echo "Log file configured: $LOG_FILE"
}

echo "Setting up server monitoring..."

# Always ensure permissions are correct (helpful after rsync updates)
ensure_permissions

# Install dependencies
echo "Installing required packages..."
sudo apt-get update
sudo apt-get install -y python3 python3-pip

# Install Python dependencies
echo "Installing Python requirements..."
sudo pip3 install psutil requests python-dotenv

# Create .env file if it doesn't exist
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env file from template..."
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    echo "Please edit $ENV_FILE to set at least one notification webhook URL:"
    echo "vim $ENV_FILE"
    read -p "Press Enter to continue after editing the .env file..."
else
    echo "Using existing .env file."
fi

# Set up log file with appropriate permissions
setup_log_file

# Set up cron job to run every 30 minutes with environment flag
echo "Setting up cron job..."
CRON_JOB="*/30 * * * * cd $SCRIPT_DIR && RUNNING_FROM_CRON=true python3 $MONITOR_SCRIPT >> $LOG_FILE 2>&1"
(crontab -l 2>/dev/null || echo "") | grep -v "$MONITOR_SCRIPT" | { cat; echo "$CRON_JOB"; } | crontab -

# Check if any webhook URL is configured
if ! grep -q -E "^(FEISHU|SLACK|MATTERMOST)_WEBHOOK_URL=.+" "$ENV_FILE" || grep -q "your-webhook-token-here" "$ENV_FILE"; then
    echo "WARNING: You need to configure at least one notification webhook URL in $ENV_FILE"
    echo "Please edit the file and update the webhook URL for Feishu, Slack, or Mattermost."
else
    echo "Testing the script..."
    # Run the script in test mode
    sudo python3 "$MONITOR_SCRIPT" --test
fi

echo "Setup complete! Server monitoring is now active and will check resources every 30 minutes."
echo "Log file: $LOG_FILE"
echo "Environment configuration: $ENV_FILE"
echo ""
echo "You can edit the environment settings anytime by running: vim $ENV_FILE"
echo ""
echo "NOTE: If you update this system using rsync, run './setup_monitor.sh --update' afterward to restore proper permissions."
