#!/usr/bin/env bash
set -euo pipefail

# Run on the VM after obtaining its actual UDP mapping with `brev ports ls`.
if [[ $# != 3 || $(id -u) != 0 ]]; then
  echo "Usage (as root): $0 <public-gateway-host> <public-udp-port> <destination-udp-port>" >&2
  exit 1
fi
gateway=$1
public_port=$2
destination_port=$3
for port in "$public_port" "$destination_port"; do
  [[ "$port" =~ ^[1-9][0-9]{3,4}$ ]] && (( port >= 1024 && port <= 65535 )) || {
    echo "Ports must be integers between 1024 and 65535" >&2; exit 1;
  }
done
[[ "$gateway" =~ ^[a-zA-Z0-9][a-zA-Z0-9.-]*$ ]] || { echo 'Invalid gateway hostname' >&2; exit 1; }
command -v iptables >/dev/null
test -f /etc/brev-selkies-desktop/native.env
test -x /opt/selkies/AppRun
/opt/selkies/AppRun --help 2>/dev/null | grep -- '--webrtc-udp-mux-port' >/dev/null
public_ip=$(getent ahostsv4 "$gateway" | awk 'NR == 1 { ip=$1 } END { print ip }')
[[ -n "$public_ip" ]] || { echo "Cannot resolve gateway: $gateway" >&2; exit 1; }

config=/etc/brev-selkies-desktop
cat > "$config/mapped-webrtc.env" <<EOF
SELKIES_WEBRTC_PUBLIC_IP=$public_ip
SELKIES_WEBRTC_UDP_MUX_PORT=$public_port
SELKIES_WEBRTC_ICE_LITE=true
SELKIES_RTC_CONFIG_JSON=$config/direct-ice.json
BREV_WEBRTC_DESTINATION_PORT=$destination_port
EOF
chmod 644 "$config/mapped-webrtc.env"
printf '%s\n' '{"iceServers":[]}' > "$config/direct-ice.json"
chmod 644 "$config/direct-ice.json"
sed -i 's/^SELKIES_MODE=.*/SELKIES_MODE=webrtc/' "$config/native.env"

cat > /usr/local/bin/brev-selkies-webrtc-network <<'NETWORK'
#!/usr/bin/env bash
set -euo pipefail
. /etc/brev-selkies-desktop/mapped-webrtc.env
chain=BREV_SELKIES_WEBRTC
# Only this installer's own chain is refreshed; other firewall rules stay intact.
iptables -t nat -S "$chain" >/dev/null 2>&1 || iptables -t nat -N "$chain"
iptables -t nat -F "$chain"
if [[ "$BREV_WEBRTC_DESTINATION_PORT" != "$SELKIES_WEBRTC_UDP_MUX_PORT" ]]; then
  iptables -t nat -A "$chain" -p udp --dport "$BREV_WEBRTC_DESTINATION_PORT" \
    -m addrtype --dst-type LOCAL -j REDIRECT --to-ports "$SELKIES_WEBRTC_UDP_MUX_PORT"
fi
iptables -t nat -C PREROUTING -j "$chain" 2>/dev/null || iptables -t nat -A PREROUTING -j "$chain"
NETWORK
chmod 755 /usr/local/bin/brev-selkies-webrtc-network
mkdir -p /etc/systemd/system/brev-selkies-native.service.d
cat > /etc/systemd/system/brev-selkies-native.service.d/mapped-webrtc.conf <<EOF
[Service]
EnvironmentFile=$config/mapped-webrtc.env
ExecStartPre=/usr/local/bin/brev-selkies-webrtc-network
EOF
systemctl daemon-reload
systemctl restart brev-selkies-native.service
echo "WebRTC configured: $gateway:$public_port -> VM UDP $destination_port -> Selkies UDP $public_port"
echo 'Open the authenticated desktop Secure Link. Verify ICE completion and video in the browser.'
