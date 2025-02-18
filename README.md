Scripts to automate common network operations when simulating with gns3.

Only supports L2 Cisco switches at the moment.
Currently working on adding support for L3 Cisco routers and switches, Juniper junos, and Cumulus linux devices.

Enable-SSH.py connects to devices with telnet and enables ssh automatically based on config parameters given.
Vlan-and-Backup.py creates vlans and backs up the configuration to a tftp server.
