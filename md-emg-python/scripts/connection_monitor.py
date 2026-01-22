#!/usr/bin/env python3
"""
Hardware Connection Monitor
Monitors and tests connections to Sessantaquattro and ESP32
"""

import socket
import subprocess
import time
import sys

def scan_network():
    """Scan for devices on the hotspot network"""
    print("\n🔍 Scanning network 192.168.50.0/24...")
    result = subprocess.run(
        ["arp", "-a"], 
        capture_output=True, 
        text=True
    )
    
    devices = []
    for line in result.stdout.splitlines():
        if "192.168.50" in line:
            parts = line.split()
            if len(parts) >= 2:
                ip = parts[1].strip("()")
                devices.append(ip)
    
    return devices

def test_sessantaquattro(ip="192.168.50.21", port=45454, timeout=10):
    """Test Sessantaquattro connection by acting as TCP server"""
    print(f"\n📡 Testing Sessantaquattro at {ip}:{port}...")
    
    try:
        # Python acts as TCP server, Sessantaquattro connects as client
        sq_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sq_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sq_socket.setsockopt(socket.SOL_TCP, socket.TCP_NODELAY, 1)
        sq_socket.bind(("192.168.50.1", port))
        sq_socket.listen(1)
        sq_socket.settimeout(timeout)
        
        print(f"   Server listening on 192.168.50.1:{port}")
        print(f"   Waiting for Sessantaquattro to connect (timeout: {timeout}s)...")
        
        conn, addr = sq_socket.accept()
        print(f"   ✅ Sessantaquattro connected from {addr}")
        
        conn.close()
        sq_socket.close()
        return True
        
    except socket.timeout:
        print(f"   ❌ Timeout - Sessantaquattro did not connect")
        print("      Possible issues:")
        print("      1. Check TCP Server IP is set to 192.168.50.1 in web interface")
        print("      2. Sessantaquattro may need restart after config change")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def test_esp32(ip, port=4210, timeout=5):
    """Test ESP32 TCP connection"""
    print(f"\n🤖 Testing ESP32 at {ip}:{port}...")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        
        # Send a simple status query
        sock.send(b"status\n")
        
        # Try to receive response
        sock.settimeout(2)
        try:
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            print(f"   ✅ ESP32 connected! Response: {response[:100]}...")
        except socket.timeout:
            print(f"   ✅ ESP32 connected (no response to status query)")
        
        sock.close()
        return True
        
    except socket.timeout:
        print(f"   ❌ Connection timeout")
        return False
    except ConnectionRefusedError:
        print(f"   ❌ Connection refused - ESP32 TCP server not running")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False

def find_esp32():
    """Try to find ESP32 on the network"""
    # Known IPs to check
    possible_ips = [
        "192.168.50.2",
        "192.168.50.3", 
        "192.168.50.4",
        "192.168.50.5",
        "192.168.50.22",
        "192.168.50.23",
    ]
    
    # Also check ARP cache
    devices = scan_network()
    for ip in devices:
        if ip != "192.168.50.1" and ip != "192.168.50.21":
            possible_ips.insert(0, ip)
    
    possible_ips = list(dict.fromkeys(possible_ips))  # Remove duplicates
    
    for ip in possible_ips:
        # Quick ping test first
        result = subprocess.run(
            ["ping", "-c", "1", "-W", "1", ip],
            capture_output=True
        )
        if result.returncode == 0:
            print(f"\n   Found device at {ip}, testing TCP...")
            if test_esp32(ip):
                return ip
    
    return None

def monitor_connections():
    """Continuously monitor for hardware connections"""
    print("=" * 60)
    print("       EMG Exoskeleton Connection Monitor")
    print("=" * 60)
    print("\nThis script monitors connections to:")
    print("  • Sessantaquattro EMG amplifier (TCP client)")
    print("  • ESP32 Glove controller (TCP server)")
    print("\nHotspot should be: 'Arlen' (192.168.50.1)")
    print("Press Ctrl+C to exit\n")
    
    sq_ok = False
    esp32_ok = False
    esp32_ip = None
    
    while not (sq_ok and esp32_ok):
        print("\n" + "=" * 40)
        print(f"[{time.strftime('%H:%M:%S')}] Checking connections...")
        print("=" * 40)
        
        # Scan network first
        devices = scan_network()
        print(f"   Found {len(devices)} devices: {devices}")
        
        # Test Sessantaquattro if not already confirmed
        if not sq_ok:
            if "192.168.50.21" in devices:
                sq_ok = test_sessantaquattro()
            else:
                print("\n📡 Sessantaquattro not found on network")
                print("   Make sure it's powered on and connected to 'Arlen'")
        else:
            print("\n📡 Sessantaquattro: ✅ Already confirmed working")
        
        # Test ESP32
        if not esp32_ok:
            # Look for new devices (not laptop or sessantaquattro)
            for ip in devices:
                if ip not in ["192.168.50.1", "192.168.50.21"]:
                    print(f"\n🤖 Found new device at {ip}, testing as ESP32...")
                    if test_esp32(ip):
                        esp32_ok = True
                        esp32_ip = ip
                        break
            
            if not esp32_ok:
                print("\n🤖 ESP32 not found on network")
                print("   To connect ESP32:")
                print("   1. Connect phone to 'ESP32_Glove' WiFi (pwd: 12345678)")
                print("   2. Go to http://192.168.4.1")
                print("   3. Click 'Connect to STA' button")
        else:
            print(f"\n🤖 ESP32: ✅ Connected at {esp32_ip}")
        
        if sq_ok and esp32_ok:
            print("\n" + "=" * 60)
            print("         ✅ ALL HARDWARE CONNECTED!")
            print("=" * 60)
            print(f"\nSessantaquattro: 192.168.50.21:45454")
            print(f"ESP32 Glove:     {esp32_ip}:4210")
            print("\nReady to run emg_control_64.py!")
            break
        
        print("\nWaiting 5 seconds before next check...")
        time.sleep(5)
    
    return sq_ok, esp32_ok, esp32_ip

if __name__ == "__main__":
    try:
        sq_ok, esp32_ok, esp32_ip = monitor_connections()
        
        if esp32_ip:
            # Update config file with ESP32 IP
            print(f"\n📝 Update esp32_control.yaml with IP: {esp32_ip}")
            
    except KeyboardInterrupt:
        print("\n\nMonitor stopped by user")
        sys.exit(0)
