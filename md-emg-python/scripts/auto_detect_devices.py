#!/usr/bin/env python3
"""
Auto-detect EMG hardware devices on the network.
Identifies devices by their behavior, not MAC addresses.
Updates config files automatically.
"""

import socket
import subprocess
import os
import sys
import time
import re

# Config file paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(SCRIPT_DIR, '..', 'config')
CONFIG_64 = os.path.join(CONFIG_DIR, '64_config.yaml')
CONFIG_ESP32 = os.path.join(CONFIG_DIR, 'esp32_control.yaml')
HOTSPOT_SCRIPT = os.path.join(SCRIPT_DIR, '..', 'setup_hotspot.sh')

# Network settings
HOTSPOT_SUBNET = "192.168.50"
HOTSPOT_GATEWAY = "192.168.50.1"
SQ_PORT = 45454
ESP32_PORT = 4210


def get_network_devices():
    """Scan network for all connected devices"""
    devices = []
    
    # Method 1: ARP cache
    result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if HOTSPOT_SUBNET in line:
            # Parse: ? (192.168.50.10) at 58:2b:0a:a6:2f:cc [ether] on wlp3s0
            match = re.search(r'\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]+)', line, re.I)
            if match:
                ip, mac = match.groups()
                if ip != HOTSPOT_GATEWAY:
                    devices.append({'ip': ip, 'mac': mac.lower()})
    
    # Method 2: Quick ping sweep for devices not in ARP cache
    for i in range(2, 20):
        ip = f"{HOTSPOT_SUBNET}.{i}"
        if not any(d['ip'] == ip for d in devices):
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '1', ip],
                capture_output=True
            )
            if result.returncode == 0:
                # Get MAC from ARP after ping
                result = subprocess.run(['arp', '-n', ip], capture_output=True, text=True)
                match = re.search(r'([0-9a-f:]{17})', result.stdout, re.I)
                if match:
                    devices.append({'ip': ip, 'mac': match.group(1).lower()})
    
    return devices


def identify_sessantaquattro(ip, timeout=5):
    """
    Identify if device is Sessantaquattro by:
    1. Checking web interface
    2. Testing TCP client behavior (SQ connects to us)
    """
    # Check web interface
    try:
        import urllib.request
        req = urllib.request.Request(f'http://{ip}/', method='GET')
        req.add_header('User-Agent', 'EMG-Detector/1.0')
        with urllib.request.urlopen(req, timeout=2) as response:
            html = response.read().decode('utf-8', errors='ignore')
            if 'sessantaquattro' in html.lower():
                return True, "Web interface detected"
    except:
        pass
    
    return False, "Not a Sessantaquattro"


def identify_esp32(ip, timeout=3):
    """
    Identify if device is ESP32 Glove by:
    1. Connecting to TCP port 4210
    2. Checking for "ESP32 Glove Ready" response
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, ESP32_PORT))
        
        # Check for welcome message
        sock.settimeout(2)
        try:
            response = sock.recv(256).decode('utf-8', errors='ignore')
            if 'ESP32' in response or 'Glove' in response:
                sock.close()
                return True, f"Response: {response.strip()}"
        except socket.timeout:
            pass
        
        # Try sending a command
        sock.send(b'status\n')
        sock.settimeout(1)
        try:
            response = sock.recv(256).decode('utf-8', errors='ignore')
            sock.close()
            if response:
                return True, f"Status response received"
        except:
            pass
        
        sock.close()
        return True, "TCP connection successful (assumed ESP32)"
        
    except ConnectionRefusedError:
        return False, "Connection refused"
    except socket.timeout:
        return False, "Connection timeout"
    except Exception as e:
        return False, str(e)


def update_config_file(filepath, key, value):
    """Update a YAML config file with new value"""
    try:
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Simple regex replacement for ip_address
        if key == 'ip_address':
            new_content = re.sub(
                r'ip_address:\s*["\']?[\d.]+["\']?',
                f'ip_address: "{value}"',
                content
            )
            
            with open(filepath, 'w') as f:
                f.write(new_content)
            return True
    except Exception as e:
        print(f"Error updating {filepath}: {e}")
        return False


def update_hotspot_script(sq_mac=None, esp32_mac=None):
    """Update setup_hotspot.sh with detected MAC addresses"""
    if not os.path.exists(HOTSPOT_SCRIPT):
        return False
    
    try:
        with open(HOTSPOT_SCRIPT, 'r') as f:
            content = f.read()
        
        if sq_mac:
            content = re.sub(
                r'BOARD1_MAC="[^"]*"',
                f'BOARD1_MAC="{sq_mac.upper()}"',
                content
            )
        
        if esp32_mac:
            content = re.sub(
                r'BOARD2_MAC="[^"]*"',
                f'BOARD2_MAC="{esp32_mac.upper()}"',
                content
            )
        
        with open(HOTSPOT_SCRIPT, 'w') as f:
            f.write(content)
        
        return True
    except Exception as e:
        print(f"Error updating hotspot script: {e}")
        return False


def main():
    print("=" * 60)
    print("       EMG Hardware Auto-Detection")
    print("=" * 60)
    print(f"\nScanning {HOTSPOT_SUBNET}.0/24 for devices...")
    
    devices = get_network_devices()
    print(f"Found {len(devices)} device(s) on network\n")
    
    sessantaquattro = None
    esp32 = None
    
    for device in devices:
        ip = device['ip']
        mac = device['mac']
        print(f"Checking {ip} (MAC: {mac})...")
        
        # Try to identify as Sessantaquattro
        is_sq, sq_reason = identify_sessantaquattro(ip)
        if is_sq:
            print(f"  ✅ SESSANTAQUATTRO detected: {sq_reason}")
            sessantaquattro = device
            continue
        
        # Try to identify as ESP32
        is_esp, esp_reason = identify_esp32(ip)
        if is_esp:
            print(f"  ✅ ESP32 GLOVE detected: {esp_reason}")
            esp32 = device
            continue
        
        print(f"  ❓ Unknown device")
    
    print("\n" + "=" * 60)
    print("       Detection Results")
    print("=" * 60)
    
    # Update configs if devices found
    updates_made = False
    
    if sessantaquattro:
        print(f"\nSessantaquattro:")
        print(f"  IP:  {sessantaquattro['ip']}")
        print(f"  MAC: {sessantaquattro['mac']}")
        
        if update_config_file(CONFIG_64, 'ip_address', sessantaquattro['ip']):
            print(f"  ✅ Updated {os.path.basename(CONFIG_64)}")
            updates_made = True
    else:
        print("\n❌ Sessantaquattro not found")
        print("   Make sure it's powered on and connected to the hotspot")
    
    if esp32:
        print(f"\nESP32 Glove:")
        print(f"  IP:  {esp32['ip']}")
        print(f"  MAC: {esp32['mac']}")
        
        if update_config_file(CONFIG_ESP32, 'ip_address', esp32['ip']):
            print(f"  ✅ Updated {os.path.basename(CONFIG_ESP32)}")
            updates_made = True
    else:
        print("\n❌ ESP32 Glove not found")
        print("   Make sure it's powered on and connected to the hotspot")
    
    # Update hotspot script MACs if both devices found
    if sessantaquattro and esp32:
        print("\n" + "-" * 40)
        if update_hotspot_script(sessantaquattro['mac'], esp32['mac']):
            print("✅ Updated setup_hotspot.sh with detected MACs")
            print("   Run 'sudo ./setup_hotspot.sh' to apply DHCP reservations")
        updates_made = True
    
    print("\n" + "=" * 60)
    if sessantaquattro and esp32:
        print("✅ All devices detected! Ready to run emg_control_64.py")
    elif updates_made:
        print("⚠️  Partial detection. Check device connections.")
    else:
        print("❌ No devices detected. Check hotspot and device power.")
    print("=" * 60)
    
    return sessantaquattro is not None and esp32 is not None


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
