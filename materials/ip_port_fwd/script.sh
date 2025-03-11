#!/bin/bash

IP_FWD_CODE="${IP_FWD_CODE}"
ETH_IF="${ETH_IF}"
FE_PORT=${FE_PORT}
DEST_HOST="${DEST_HOST}"
DEST_PORT=${DEST_PORT}

nslookup_output=$(nslookup $DEST_HOST)
# Extract the Canonical Name (CNAME) if it exists
DEST_HOST=$(echo "$nslookup_output" | grep "Name" | awk '{print $NF}')


#1. Make sure you're root
echo -e "\e[32mChecking whether we're root...\e[0m"
if [ -z $${UID} ]; then
	UID=$(id -u)
fi
if [ "$${UID}" != "0" ]; then
	echo -e "\e[31mERROR: user must be root\e[0m"
	exit 1
fi


# Define the service name and path
SERVICE_NAME=ip_fwd
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
SCRIPT_PATH="/usr/bin/$SERVICE_NAME.sh"

# Copy the base64 content to script file
echo "$IP_FWD_CODE" | base64 --decode > $SCRIPT_PATH

# Make the script executable
chmod +x $SCRIPT_PATH

# Create the systemd service file
cat << EOF > $SERVICE_FILE
[Unit]
Description=$SERVICE_NAME
After=network.target

[Service]
ExecStartPre=/usr/sbin/iptables -t nat -F PREROUTING
ExecStart=$SCRIPT_PATH -i $ETH_IF -f $FE_PORT -a $DEST_HOST -b $DEST_PORT
Restart=on-failure
RestartSec=10s
User=root

[Install]
WantedBy=multi-user.target
EOF


# Clear table routes
#iptables -t nat -F PREROUTING

# Reload systemd to pick up the new service
systemctl daemon-reload

# Enable the service to start at boot
systemctl enable $SERVICE_NAME

# Start the service immediately
systemctl start $SERVICE_NAME

echo "Daemon $SERVICE_NAME is now running and set to start on boot."
