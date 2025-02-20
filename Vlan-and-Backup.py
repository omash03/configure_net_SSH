from concurrent.futures import ThreadPoolExecutor
from netmiko import ConnectHandler
from getpass import getpass
import yaml
import datetime
import time

universal_cred = None
dev_username = None
dev_secret = None

def get_password(prompt="Enter your password: "):
    while True:
        password = getpass(prompt)
        confirm_password = getpass("Enter again: ")
        if password == confirm_password:
            return password
        else:
            print("Confirmation does not match. Please try again.")

def create_device_params(device_config, universal_cred, dev_username, dev_secret):
    # Convert YAML config to Netmiko device parameters
    match device_config["device_type"].lower():
        case "cisco":
            device_type = "cisco_ios"
        case "juniper":
            device_type = "juniper_junos"
        case "cumulus":
            device_type = "linux"
        case _:
            raise ValueError(f"Unsupported device type: {device_config['device_type']}")

    if universal_cred == True:
        return {
        #TODO: don't hardcode device_type
        'device_type': device_type,
        'host': device_config['mgt_ip'],
        'username': dev_username,
        'password': dev_secret,
        'port': 22,
        'secret': dev_secret,
        }
    elif universal_cred == False:
        return {
            #TODO: don't hardcode device_type
            'device_type': device_type,
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

def configure_device(device_name, device_config, universal_cred, dev_username, dev_secret, tftp_server):
    """Configure a single device with VLANs and backup"""
    try:
        # Connect to the device
        net_connect = ConnectHandler(**create_device_params(device_config, universal_cred, dev_username, dev_secret))
        net_connect.enable()
        print(f"Connected to {device_name} and entered enable mode")
        
        # Create VLANs
        net_connect.config_mode()
        create_vlans(net_connect, 10, 50, 10)
        
        # Wait a moment before backup
        time.sleep(2)
        
        # Backup the configuration
        backup_config_tftp(net_connect, device_config['hostname'], tftp_server)
        
        net_connect.disconnect()
        
    except Exception as e:
        print(f"Failed to configure {device_name}: {str(e)}")

def main():
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)

    if input("Will you be using universal credentials?: ") == "yes".lower() or "y".lower():
        universal_cred = True
        dev_username = input("Enter your username: ")
        dev_secret = get_password("Enter your secret: ")

    else:
        universal_cred = False

# Create thread pool
    max_threads = 10  # Limit concurrent TFTP transfers
    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        futures = []
        
        for device_name, device_config in config.items():
            if device_name == "Globals":
                tftp_server = device_config["tftp_server"]
                continue
                
            future = executor.submit(
                configure_device,
                device_name,
                device_config,
                universal_cred,
                dev_username,
                dev_secret,
                tftp_server
            )
            futures.append(future)
        
        # Wait for all configurations to complete
        for future in futures:
            future.result()

if __name__ == "__main__":
    main()