from concurrent.futures import ThreadPoolExecutor
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

    match dev_name["device_type"]:
        case "cisco":
            device_type = "cisco_ios_telnet"
        case "juniper":
            device_type = "juniper_junos_telnet"
        case "cumulus":
            device_type = "linux"
        case _:
            raise ValueError(f"Unsupported device type: {dev_name['device_type']}")

    return {
        "device_type": device_type,
        "host": dev_name["host"],
        "port": dev_name["port"]
    }

def allkey_filter(dev_name):
    return {key: dev_name[key] for key in dev_name}

def exec_cisco(net_connect, commands):
    # Execute with proper timing handling to stop hanging

    timing_keywords = [
        "enable",
        "configure terminal",
        "crypto key generate rsa modulus 2048",
        "int vlan 1",
        "line vty 0 4",
        "end",
        "hostname",
        "exit"
    ]

    for command in commands:
        # Check if any timing keyword is in the command
        needs_timing = any(keyword in command for keyword in timing_keywords)
        
        match command:
            case "reload":
                output = net_connect.send_command_timing(command)
                if "Proceed with reload" in output:
                    output += net_connect.send_command_timing("y")
                print(output)
                time.sleep(120)
                
                output = net_connect.send_command_timing("\n")
                if "Would you like to enter the initial configuration dialog" in output:
                    output += net_connect.send_command_timing("no")
                    
            case _ if needs_timing:
                output = net_connect.send_command_timing(command, strip_prompt=False, strip_command=False)
                
            case _:
                output = net_connect.send_command(command, strip_prompt=False, strip_command=False)
                
        print(output)
    
    net_connect.disconnect()

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

def configure_device(device_name, device_config, username, password, domain_name, mgt_gateway, mgt_mask):
    # include commands for all devices
    try:
        filtered_device = connect_filter(device_config)
        all_keys = allkey_filter(device_config)
        
        print(f"Attempting to connect to {device_name} ({filtered_device['host']}:{filtered_device['port']})")
        dev_connection = ConnectHandler(**filtered_device)
        print(f"Successfully connected to {device_name}")
        
        if filtered_device["device_type"] == "cisco_ios_telnet" and all_keys['layer'] == "L2Switch":
            print(f"Connecting to L2 Cisco Switch: {device_name}")
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
                "int e0/0",
                "int e0/0",
                "no shutdown",
                "exit",
                "ip routing",
                "aaa new-model",
                "ip ssh version 2",
                "line vty 0 4",
                "transport input ssh",
                "end",
                "write memory"
            ]
            exec_cisco(dev_connection, commands)
            
        elif filtered_device["device_type"] == "cisco_ios_telnet" and all_keys['layer'] == "L3Switch":
            print(f"Connecting to L3 Cisco Switch: {device_name}")
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
            exec_cisco(dev_connection, commands)
            
        elif filtered_device["device_type"] == "juniper_junos_telnet":
            print(f"Connecting to Juniper Switch: {device_name}")
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
            exec_juniper(dev_connection, commands, filtered_device)
            
    except Exception as e:
        print(f"Failed to configure {device_name}. Error: {e}")

def main():

    username = config["Globals"]["username"]
    password = get_password()
    
    # If the user wants to use the same domain name for all devices
    if universal_domain == "yes" or universal_domain == "y":
        domain_name = config["Globals"]["domain_name"]

    if mgt_net == "yes" or mgt_net == "y":
        mgt_gateway = config["Globals"]["mgt_gateway"]
        mgt_mask = config["Globals"]["mgt_mask"]
    else:
        mgt_gateway = input("Enter the default gateway for the management network: ")
        mgt_mask = input("Enter the subnet mask for the management network: ")

    # Create a thread pool
    max_threads = 10  # Adjust based on your needs
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []
        
        # Submit device configurations to thread pool
        for device_name, device_config in config.items():
            if device_name == "Globals":
                continue
                
            future = executor.submit(
                configure_device,
                device_name,
                device_config,
                username,
                password,
                domain_name,
                mgt_gateway,
                mgt_mask
            )
            futures.append(future)
        
        # Wait for all configurations to complete
        for future in futures:
            future.result()

if __name__ == "__main__":
    main()  