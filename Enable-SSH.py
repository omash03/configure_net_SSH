from netmiko import ConnectHandler
from getpass import getpass
import time
import yaml

default_gateway = "10.175.136.1"

# Load the configuration from the YAML file
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

# Filter the dictionary to include only the required fields for connections
def connect_filter(dev_name):
    required_fields = ["device_type", "host", "port"]
    return {key: dev_name[key] for key in required_fields if key in dev_name}

def exec_cisco():
    for command in commands:
        if command == "reload":
            # Send the reload command and confirm
            output = net_connect.send_command_timing(command)
            if "Proceed with reload" in output:
                output += net_connect.send_command_timing("y")
            print(output)
            
            # Wait for the device to reload
            time.sleep(120)  # Adjust the sleep time as needed
            
            # Reconnect to the device after reload
            net_connect = ConnectHandler(**filtered_device)
            
            # Handle the initial configuration dialog
            output = net_connect.send_command_timing("\n")
            if "Would you like to enter the initial configuration dialog" in output:
                output += net_connect.send_command_timing("no")
            print(output)
        else:
            output = net_connect.send_command(command, expect_string=r"#")
            print(output)

# Iterate over each device in the configuration
for device_name, device_config in config.items():
    filtered_device = connect_filter(device_config)
    
    # Print the filtered device configuration for debugging
    print(f"Connecting to {device_name} with the following configuration:")
    for key, value in filtered_device.items():
        print(f"{key}: {value}")

    print()
    # Establish the connection
    net_connect = ConnectHandler(**filtered_device)
    
    # Define the commands with variables from the configuration
    # TODO - How TF to configure L3 Devices for SSH?
    if filtered_device["device_type"] == "cisco_ios" and filtered_device['Layer'] == "L2Switch":
        commands = [
            "write erase",
            "reload",
            "enable",
            "configure terminal",
            f"hostname {device_config['hostname']}",
            f"ip domain-name {device_config['domain_name']}",
            f"username {device_config['username']} privilege 15 secret {device_config['secret']}",
            f"enable secret {device_config['secret']}",
            "crypto key generate rsa modulus 2048",
            "aaa new-model",
            "int e0/0",
            "no shutdown",
            "vlan 1",
            "no shutdown",
            "name Management",
            "no spanning-tree vlan 1",
            "exit",
            "ip ssh version 2",
            "line vty 0 4",
            "login local",
            "transport input ssh",
            "end",
            "write memory"
        ]
        print(net_connect.find_prompt())

        exec_cisco()

    if filtered_device["device_type"] == "cisco_ios" and filtered_device['Layer'] == "L3Switch":
        commands = [
            "write erase",
            "reload",
            "enable",
            "configure terminal",
            f"ip default-gateway {default_gateway}",
            f"ip route 0.0.0.0 0.0.0.0 {default_gateway}",
            f"hostname {device_config['hostname']}",
            f"ip domain-name {device_config['domain_name']}",
            f"username {device_config['username']} privilege 15 secret {device_config['secret']}",
            f"enable secret {device_config['secret']}",
            "crypto key generate rsa general-keys modulus 2048",
            "aaa new-model",
            "int e0/0",
            "no shutdown",
            f"ip {device_config['mgt_ip']} {device_config['mgt_mask']}",
            "exit",
            "ip ssh version 2",
            "line vty 0 4",
            "transport input ssh",
            "end",
            "write memory"
        ]
        print(net_connect.find_prompt())

        exec_cisco()
    
    
    # Disconnect from the device
    net_connect.disconnect()