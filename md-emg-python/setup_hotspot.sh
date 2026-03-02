#!/bin/bash
set -e

# ==========================================
# CONFIGURATION (EDIT THESE)
# ==========================================
IFACE="wlp3s0"                 # Your Wi-Fi interface (check with 'ip link')
CON_NAME="lab-hotspot"         # Name for the connection in NM
SSID="Arlen"              # Wi-Fi Name
PASS="12345678"       # Wi-Fi Password (min 8 chars)
GATEWAY_IP="192.168.50.1/24"   # The laptop's IP in the hotspot

# Sessantaquattro EMG Amplifier Configuration
BOARD1_MAC="0C:B2:B7:07:98:11" # Sessantaquattro (Texas Instruments)
BOARD1_IP="192.168.50.10"

# ESP32 Glove Controller Configuration  
BOARD2_MAC="68:FE:71:80:2F:BC" # ESP32 (Espressif)
BOARD2_IP="192.168.50.11"
# ==========================================

# Check for root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root (sudo)"
  exit 1
fi

echo ">>> Removing old connection '$CON_NAME' if exists..."
nmcli connection delete "$CON_NAME" 2>/dev/null || true

echo ">>> Creating Hotspot Connection..."
# Create the connection profile
nmcli connection add type wifi ifname "$IFACE" con-name "$CON_NAME" \
    autoconnect yes ssid "$SSID"

# Configure Security (WPA2), Mode (AP), and IP (Shared/NAT)
nmcli connection modify "$CON_NAME" \
    802-11-wireless.mode ap \
    802-11-wireless.band bg \
    ipv4.method shared \
    ipv4.addresses "$GATEWAY_IP" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "$PASS"

echo ">>> Configuring Static IPs for Boards..."
# Create the NetworkManager dnsmasq shared config directory if missing
mkdir -p /etc/NetworkManager/dnsmasq-shared.d

# Write the static lease configuration
cat <<EOF > /etc/NetworkManager/dnsmasq-shared.d/lab-static-leases.conf
# Static IPs for Embedded Boards
dhcp-host=$BOARD1_MAC,$BOARD1_IP
dhcp-host=$BOARD2_MAC,$BOARD2_IP
EOF

echo ">>> Applying Changes..."
# Restart NetworkManager to pick up the new dnsmasq config
systemctl restart NetworkManager

echo ">>> Starting Hotspot..."
nmcli connection up "$CON_NAME"

echo "================================================="
echo "Hotspot '$SSID' is active on $IFACE."
echo "Gateway (Laptop): ${GATEWAY_IP%/*}"
echo "Board 1 assigned: $BOARD1_IP"
echo "Board 2 assigned: $BOARD2_IP"
echo "================================================="
