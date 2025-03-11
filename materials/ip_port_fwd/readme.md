# **Automating `iptables` Configuration for ADF-to-PostgreSQL Connectivity Using Azure VM Custom Script Extension**

## **Introduction**
Connecting Azure Data Factory (ADF) to a **VNet-integrated PostgreSQL server** can be tricky. One of Microsoft blogs provides a manual approach to achieve this setup, which you can find [here](https://techcommunity.microsoft.com/blog/adforpostgresql/how-to-access-azure-postgresql-flex-server-from-adf-managed-vnet-using-a-private/3707742). Here one step is setting up port forwarding. Traditionally, setting up **port forwarding with `iptables`** requires logging into the **Self-Hosted Integration Runtime (SHIR) Linux VM** and manually configuring rules. But let’s be honest—manual setup is prone to errors, inconsistent configurations, and unnecessary operational overhead.


### **The Solution? Automation!** 🚀
By leveraging **Azure VM Custom Script Extension and Terraform**, we can automate the entire process. This ensures:

✔ Consistent and error-free configurations across deployments.  
✔ Persistence of `iptables` rules after VM reboots.  
✔ Seamless connectivity between ADF and PostgreSQL.  
✔ Infrastructure as Code (IaC) for better maintainability.  

Let’s dive into how you can set this up effortlessly!

---

## **How It Works**
To automate `iptables` configuration, we will:
1. **Create a Bash script** (`ip_fwd.sh`) to enable IP forwarding and configure `iptables` rules.
2. **Create a deployment script** (`script.sh`) to run `ip_fwd.sh` as a daemon service.
3. **Deploy the script via Terraform** using **Azure VM Custom Script Extension**.

Here’s the step-by-step implementation. 👇

---

## **1. Create the `iptables` Configuration Script**
The `ip_fwd.sh` script:
- Enables **IP forwarding**.
- Sets up **port forwarding rules**.
- Ensures packets reach the PostgreSQL server.

### **ip_fwd.sh**
```bash
#!/bin/bash

#-------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. 
#--------------------------------------------------------------------------

usage() {
	echo -e "\e[33m"
	echo "usage: ${0} [-i <eth_interface>] [-f <frontend_port>] [-a <dest_ip_addr>] [-b <dest_port>]" 1>&2
	echo "where:" 1>&2
	echo "<eth_interface>: Interface on which packet will arrive and be forwarded" 1>&2
	echo "<frontend_port>: Frontend port on which packet arrives" 1>&2
	echo "<dest_port>    : Destination port to which packet is forwarded" 1>&2
	echo "<dest_ip_addr> : Destination IP which packet is forwarded" 1>&2
	echo -e "\e[0m"
}

if [[ $# -eq 0 ]]; then
	echo -e "\e[31mERROR: no options given\e[0m"
	usage
	exit 1
fi
while getopts 'i:f:a:b:' OPTS; do
	case "${OPTS}" in
		i)
			echo -e "\e[32mUsing ethernet interface ${OPTARG}\e[0m"
			ETH_IF=${OPTARG}
			;;
		f)
			echo -e "\e[32mFrontend port is ${OPTARG}\e[0m"
			FE_PORT=${OPTARG}
			;;
		a)
			echo -e "\e[32mDestination IP Address is ${OPTARG}\e[0m"
			DEST_HOST=${OPTARG}
			;;
		b)
			echo -e "\e[32mDestination Port is ${OPTARG}\e[0m"
			DEST_PORT=${OPTARG}
			;;
		*)
			usage
			exit 1
			;;
	esac
done

if [ -z ${ETH_IF} ]; then
	echo -e "\e[31mERROR: ethernet interface not specified!!!\e[0m"
	usage
	exit 1
fi
if [ -z ${FE_PORT} ]; then
	echo -e "\e[31mERROR: frontend port not specified!!!\e[0m"
	usage
	exit 1
fi
if [ -z ${DEST_HOST} ]; then
	echo -e "\e[31mERROR: destination IP not specified!!!\e[0m"
	usage
	exit 1
fi
if [ -z ${DEST_PORT} ]; then
	echo -e "\e[31mERROR: destination port not specified!!!\e[0m"
	usage
	exit 1
fi

# Enable IP forwarding
echo "1" > /proc/sys/net/ipv4/ip_forward

# Resolve Destination IP
if [[ ${DEST_HOST} =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
	DEST_IP=${DEST_HOST}
else
	DEST_IP=$(host ${DEST_HOST} | grep "has address" | awk '{print $NF}')
fi

# Get local IP
LOCAL_IP=$(ip addr ls ${ETH_IF} | grep -w inet | awk '{print $2}' | awk -F/ '{print $1}')

# Apply iptables rules
iptables -t nat -A PREROUTING -p tcp -i ${ETH_IF} --dport ${FE_PORT} -j DNAT --to ${DEST_IP}:${DEST_PORT}
iptables -t nat -A POSTROUTING -o ${ETH_IF} -j MASQUERADE
```

> 🎯 This script takes the network interface, frontend port, destination IP, and destination port as inputs.

---

## **2. Create the Deployment Script**
The `script.sh` script:
- **Resolves the PostgreSQL private link hostname** (since it gets a dynamic IP).
- **Creates a daemon service** to execute `ip_fwd.sh` on every reboot.
- **Automatically starts the service** after deployment.

### **script.sh**
```bash
#!/bin/bash

# Resolve destination hostname to IP
nslookup_output=$(nslookup $DEST_HOST)
DEST_HOST=$(echo "$nslookup_output" | grep "Name" | awk '{print $NF}')

# Define the service name and paths
SERVICE_NAME=ip_fwd
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"
SCRIPT_PATH="/usr/bin/$SERVICE_NAME.sh"

# Save the iptables script
echo "$IP_FWD_CODE" | base64 --decode > $SCRIPT_PATH
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

# Reload systemd and start the service
systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo "Daemon $SERVICE_NAME is now running and set to start on boot."
```

> ✅ This script ensures `iptables` rules are **automatically applied on boot**, eliminating manual intervention.

---

## **3. Deploy the Scripts Using Terraform**
Finally, we use Terraform to upload and execute these scripts via **Azure VM Custom Script Extension**.

### **Terraform Code**
```hcl
locals {
  script_info = {
    file_path = "script.sh"
    file_variables = {
      IP_FWD_CODE = base64encode(file("ip_fwd.sh"))
      ETH_IF="eth0"
      FE_PORT="6432"
      DEST_HOST="<postgres_server_name>"
      DEST_PORT="6432"
    }
  }  
}

resource "azurerm_virtual_machine_extension" "vm" {
  name                       = "custom_script"
  virtual_machine_id         = <vm_id>
  publisher                  = "Microsoft.Azure.Extensions"
  type                       = "CustomScript"
  type_handler_version       = "2.0"

  protected_settings = <<PROT
  {
    "script": "${base64encode(templatefile(local.script_info.file_path, local.script_info.file_variables))}"
  }
  PROT
}
```

> 🔹 This Terraform configuration ensures the script runs **automatically** when the VM is provisioned.

---

## **Final Thoughts**
With this setup, you no longer have to manually configure `iptables` for **ADF-to-PostgreSQL connectivity** or similar setup. Everything is automated, ensuring a **reliable, repeatable, and scalable** solution.


