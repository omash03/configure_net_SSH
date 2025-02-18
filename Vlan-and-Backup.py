from netmiko import ConnectHandler
from getpass import getpass
import yaml
import datetime

def get_password(prompt="Enter your password: "):
    while True:
        password = getpass(prompt)
        confirm_password = getpass("Confirm your password: ")
        if password == confirm_password:
            return password
        else:
            print("Passwords do not match. Please try again.")

def connect_filter(dev_name):
    required_fields = ["device_type", "mgt_ip", "port"]
    return {key: dev_name[key] for key in required_fields if key in dev_name}

def allkey_filter(dev_name):
    return {key: dev_name[key] for key in dev_name}

def create_device_params(device_config):
    # Convert YAML config to Netmiko device parameters
    return {
        #TODO: don't hardcode device_type
        'device_type': device_config['device_type'],
        'host': device_config['mgt_ip'],
        'username': device_config['username'],
        'password': get_password(),
        'port': 22,
        'secret': get_password("Enter your enable secret: "),
    }

def get_password(prompt="Enter your password: "):
    while True:
        password = getpass(prompt)
        confirm_password = getpass("Confirm your password: ")
        if password == confirm_password:
            return password
        else:
            print("Passwords do not match. Please try again.")

def create_vlans(net_connect, vlan_start=10, vlan_end=50, step=10):
    """Create VLANs and assign names in steps of 10"""
    print("Creating VLANs...")
    
    config_commands = []
    for vlan_id in range(vlan_start, vlan_end + 1, step):
        commands = [
            f"vlan {vlan_id}",
            f"name vlan {vlan_id}",
            "exit"
        ]
        config_commands.extend(commands)
    
    print(config_commands)
    output = net_connect.send_config_set(config_commands)
    print(output)
    
def backup_config_tftp(net_connect, hostname, tftp_server):
    """Backup the startup configuration using TFTP"""
    print("Backing up configuration using TFTP...")
    
    # Create filename with timestamp
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{hostname}_startup_{timestamp}.cfg"
    
    # Copy startup-config to TFTP server
    command = f"copy startup-config tftp://{tftp_server}/{filename}"
    
    # Handle TFTP transfer prompts
    output = net_connect.send_command_timing(command)
    if "Address or name of remote host" in output:
        output += net_connect.send_command_timing(tftp_server)
    if "Destination filename" in output:
        output += net_connect.send_command_timing(filename)
    
    print(output)
    return filename

def main():
    # Add TFTP server IP (your PC's IP address)
    tftp_server = "10.175.136.3"  # Replace with your PC's IP

    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    # Device connection parameters
    for device_name, device_config in config.items():
        print(device_name)

        if device_name == "Globals":
            continue

        if device_config["device_type"] == "cisco_ios":
            try:
                # Connect to the device
                net_connect = ConnectHandler(**create_device_params(device_config))
                net_connect.enable()
                print("Entered enable mode")
                
                # Create VLANs
                net_connect.config_mode()
                print("Entered global configuration mode")

                create_vlans(net_connect, 10, 50, 10)
                
                # Backup the configuration using TFTP
                backup_config_tftp(net_connect, device_config['hostname'], tftp_server)
                
                # Disconnect
                net_connect.disconnect()
                
            except Exception as e:
                print(f"Failed to connect to {device_name}.")
                print(e)

        else :
            print(f"Unsupported device type: {device_config['device_type']}")

if __name__ == "__main__":
    main()