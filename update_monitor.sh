#!/bin/bash

set -e

# Script location
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

echo "Updating server monitoring system permissions..."

# Ensure scripts have executable permissions
chmod +x "$SCRIPT_DIR/server_monitor.py"
chmod +x "$SCRIPT_DIR/network_monitor.py"
chmod +x "$SCRIPT_DIR/setup_monitor.sh"
chmod +x "$SCRIPT_DIR/update_monitor.sh"

echo "Permissions restored successfully."
echo "System monitoring will continue to function normally."
echo ""
echo "If you made changes to configuration, you may want to run:"
echo "sudo ./setup_monitor.sh"
echo "to ensure all settings are applied correctly."
