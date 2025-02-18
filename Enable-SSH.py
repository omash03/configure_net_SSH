from netmiko import ConnectHandler
from getpass import getpass
import time
import yaml

# Load the configuration from the YAML file
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

global_password = None
username = None
password = None

universal_creds = input("Use the same credentials for all devices? (y/n): ")
universal_domain = input("Use the same domain name for all devices? (y/n): ")
mgt_net = input("Use the same management network for all devices? (y/n): ")

def get_password(prompt="Enter your password: "):
    while True:
        password = getpass(prompt)
        confirm_password = getpass("Confirm your password: ")
        if password == confirm_password:
            return password
        else:
            print("Passwords do not match. Please try again.")

def perdev_check(username, password):
    if password is None:
        username = config["Globals"]["username"]
        password = get_password()
        return username, password
    else:
        password = password
        username = username
        return username, password

# Filter the dictionary to include only the required fields for connections
def connect_filter(dev_name):
    required_fields = ["device_type", "host", "port"]
    return {key: dev_name[key] for key in required_fields if key in dev_name}

def allkey_filter(dev_name):
    return {key: dev_name[key] for key in dev_name}

def exec_cisco(net_connect, commands):

    for command in commands:
        if command == "reload":
            # Send the reload command and confirm
            output = net_connect.send_command_timing(command)
            if "Proceed with reload" in output:
                output += net_connect.send_command_timing("y")
            print(output)
            
            # Wait for the device to reload
            time.sleep(120)  # Adjust the sleep time as needed
            
            # Handle the initial configuration dialog
            output = net_connect.send_command_timing("\n")
            if "Would you like to enter the initial configuration dialog" in output:
                output += net_connect.send_command_timing("no")
            print(output)
        else:
            output = net_connect.send_command_timing(command)
            print(output)
    
    net_connect.disconnect()


# Function to handle Juniper device authentication and enter CLI mode
# TODO: Less hardcoding of commands, make more like cisco function make juniper function work
def exec_juniper(net_connect, commands, filtered_device):
    print(net_connect.get_prompt())
    output = net_connect.send_command("root")

    if "root@".lower() in output:
        output += net_connect.send_command_timing(filtered_device["default_pass"])
        time.sleep(3)
    net_connect.send_command_timing("cli")

    for command in commands:
        output = net_connect.send_command(command)

        if "new password" in output.lower():
            output += net_connect.send_command_timing()
            output += net_connect.send_command_timing()

        print(output)

    net_connect.send_command("commit and-quit", expect_string=r">")
    net_connect.disconnect()


def main():

    # If the user wants to use the same domain name for all devices
    if universal_domain == "yes" or universal_domain == "y":
        domain_name = config["Globals"]["domain_name"]

    if mgt_net == "yes" or mgt_net == "y":
        mgt_gateway = config["Globals"]["mgt_gateway"]
        mgt_mask = config["Globals"]["mgt_mask"]
    else:
        mgt_gateway = input("Enter the default gateway for the management network: ")
        mgt_mask = input("Enter the subnet mask for the management network: ")

    if universal_creds == "yes" or universal_creds == "y":
        username = config["Globals"]["username"]
        password = get_password()
    else:
        username = None
        password = None

    # Set up the key value pair iteration for each device from yaml file
    for device_name, device_config in config.items():

        # Skip the globals section of the configuration
        if device_name == "Globals":
            continue

        filtered_device = connect_filter(device_config)
        all_keys = allkey_filter(device_config)
        dev_connection = ConnectHandler(**filtered_device)

        # Print the filtered device configuration for debugging
        print(f"Connecting to {device_name} with the following configuration:")
        for key, value in filtered_device.items():
            print(f"{key}: {value}")

        print(device_config)
        print(all_keys['layer'])

        # Define the commands with variables from the configuration
        if filtered_device["device_type"] == "cisco_ios_telnet" and all_keys['layer'] == "L2Switch":
            print("Connecting to L2 Cisco Switch")

            perdev_check(username, password)
            if password is None:
                password = get_password()
            if username is None:
                username = all_keys['username']

            commands = [
                "enable",
                "configure terminal",
                "no spanning-tree vlan 1",
                f"ip default-gateway {mgt_gateway}",
                f"ip route 0.0.0.0 0.0.0.0 {mgt_gateway}",
                f"hostname {all_keys['hostname']}",
                f"ip domain-name {domain_name}",
                f"username {username} privilege 15 secret {password}",
                f"enable secret {password}",
                "crypto key generate rsa modulus 2048",
                "int vlan 1",
                "no shutdown",
                f"ip address {all_keys['mgt_ip']} {all_keys['mgt_mask']}",
                "aaa new-model",
                "int e0/0",
                "ip routing",
                "int e0/0",
                "no shutdown",
                "exit",
                "ip ssh version 2",
                "line vty 0 4",
                "transport input ssh",
                "end",
                "write memory"
            ]

            exec_cisco(dev_connection, commands)

        #TODO - Correct creation of management VLAN subinterface for L3 Devices
        if filtered_device["device_type"] == "cisco_ios_telnet" and all_keys['layer'] == "L3Switch":
            print("Connecting to L3 Cisco Switch")

            perdev_check()

            commands = [
                "enable",
                "configure terminal",
                f"ip default-gateway {mgt_gateway}",
                f"ip route 0.0.0.0 0.0.0.0 {mgt_gateway}",
                f"hostname {all_keys['hostname']}",
                f"ip domain-name {all_keys['domain_name']}",
                f"username {all_keys['username']} privilege 15 secret {password}",
                f"enable secret {password}",
                "crypto key generate rsa general-keys modulus 2048",
                "aaa new-model",
                "int e0/0",
                "no shutdown",
                f"ip {all_keys['mgt_ip']} {all_keys['mgt_mask']}",
                "exit",
                "ip ssh version 2",
                "line vty 0 4",
                "transport input ssh",
                "end",
                "write memory"
            ]

            exec_cisco(ConnectHandler(**filtered_device), commands)
        
        #TODO - Finish Juniper Configuration for ssh
        if filtered_device["device_type"] == "juniper_junos_telnet" and all_keys['layer'] == "L2Switch":
            print("Connecting to Juniper Switch")

            perdev_check()

            commands = [
                "cli",
                "configure",
                "load factory-default",
                f"set system root-authentication plain-text-password {get_password()}",
                "commit",
                f"set system host-name {all_keys['hostname']}",
                f"set system domain-name {all_keys['domain_name']}",
                f"set system login user {all_keys['username']} authentication plain-text-password",
                "set interfaces vlan unit 0 vlan-id 1",
                f"set interfaces vlan unit 0 family inet address {all_keys['mgt_ip']}/{all_keys['mgt_mask']}",
                "set system services ssh",
                "set system root-authentication plain-text-password {get_password()}",
                "commit and-quit"
            ]

            exec_juniper(ConnectHandler(**filtered_device), commands)

if __name__ == "__main__":
    main()