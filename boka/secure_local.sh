#!/usr/bin/env bash
















set -euo pipefail

SRC_DIR="$(readlink -f "${1:?usage: secure_local.sh /path/to/Boka-code [--strict-firewall]}")"
STRICT_FIREWALL=0
[[ "${2:-}" == "--strict-firewall" ]] && STRICT_FIREWALL=1

BOKA_INSTALL=/opt/boka
BOKA_DATA=/var/lib/boka
BOKA_LOG=/var/log/boka
BOKA_USER=boka
SERVICE=/etc/systemd/system/boka.service

TG_NETS=(91.108.4.0/22 91.108.8.0/21 91.108.16.0/22 91.108.56.0/22 \
         149.154.160.0/20 185.76.151.0/24 2001:b28::/32)

DNS_IPS=(127.0.0.53 127.0.0.1 8.8.8.8 1.1.1.1)

if [[ $EUID -ne 0 ]]; then
    echo "Run as root." >&2
    exit 1
fi

for bin in nft systemctl; do
    command -v "$bin" >/dev/null 2>&1 || {
        echo "Missing required binary: $bin" >&2
        exit 1
    }
done


if ! id "$BOKA_USER" >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir "$BOKA_DATA" \
        --shell /usr/sbin/nologin "$BOKA_USER"
fi


mkdir -p "$BOKA_DATA/sessions" "$BOKA_LOG"
chown -R "$BOKA_USER:$BOKA_USER" "$BOKA_DATA" "$BOKA_LOG"
chmod 0700 "$BOKA_DATA"


rm -rf "$BOKA_INSTALL"
mkdir -p "$BOKA_INSTALL"
cp -a "$SRC_DIR"/. "$BOKA_INSTALL"/
chown -R root:root "$BOKA_INSTALL"
chmod -R a-w "$BOKA_INSTALL"
rm -f "$BOKA_INSTALL/.requirements_hash"
find "$BOKA_INSTALL" -name __pycache__ -type d -prune -exec rm -rf {} + 2>/dev/null || true


if [[ ! -x "$BOKA_DATA/venv/bin/python" ]]; then
    python3 -m venv "$BOKA_DATA/venv"
fi
chown -R "$BOKA_USER:$BOKA_USER" "$BOKA_DATA/venv"

sudo -u "$BOKA_USER" -- \
    "$BOKA_DATA/venv/bin/pip" install --disable-pip-version-check --no-warn-script-location \
    -r "$BOKA_INSTALL/requirements.txt" >/dev/null


TG_ALLOW="$(printf '%s\n' "${TG_NETS[@]}" | tr '\n' ' ')"
FW_ALLOW="127.0.0.1 ::1 $TG_ALLOW"

cat >"$SERVICE" <<EOF
[Unit]
Description=Boka Userbot (hardened, standalone)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$BOKA_USER
Group=$BOKA_USER
WorkingDirectory=$BOKA_INSTALL
Environment=PATH=$BOKA_DATA/venv/bin:/usr/bin:/bin
Environment=PYTHONPATH=$BOKA_INSTALL
ExecStart=$BOKA_DATA/venv/bin/python -m boka --data-root $BOKA_DATA --no-git
ExecReload=/bin/kill -HUP \$MAINPID
Restart=on-failure
RestartSec=5

NoNewPrivileges=yes
PrivateDevices=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$BOKA_DATA $BOKA_LOG
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectKernelLogs=yes
ProtectControlGroups=yes
ProtectProc=invisible
LockPersonality=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes
MemoryDenyWriteExecute=yes
UMask=0077
CapabilityBoundingSet=
AmbientCapabilities=
SystemCallArchitectures=native
SystemCallFilter=@system-service
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6


IPAddressDeny=any
IPAddressAllow=$FW_ALLOW

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable boka.service >/dev/null


if [[ $STRICT_FIREWALL -eq 1 ]]; then
    nft list table inet boka >/dev/null 2>&1 && nft delete table inet boka || true
    DNS_RULES=""
    for ip in "${DNS_IPS[@]}"; do
        DNS_RULES+="        ip daddr $ip accept
"
    done
    cat >/etc/boka-firewall.nft <<EOF
table inet boka {
    chain output {
        type filter hook output priority 100; policy drop;
        ct state established,related accept
        ct state invalid drop
        iif "lo" accept
        ip daddr 127.0.0.0/8 accept
        ip6 daddr ::1/128 accept
${DNS_RULES}        udp dport 53 accept
        tcp dport 53 accept
        ip6 nexthdr tcp dport { 443, 80 } accept
        ip6 daddr 2001:b28::/32 accept
        ip daddr { 91.108.4.0/22, 91.108.8.0/21, 91.108.16.0/22, 91.108.56.0/22, 149.154.160.0/20, 185.76.151.0/24 } accept
    }
}
EOF
    nft -c -f /etc/boka-firewall.nft && echo "[firewall] syntax OK" || {
        echo "[firewall] syntax error; removing file" >&2
        rm -f /etc/boka-firewall.nft
        exit 1
    }
    nft -f /etc/boka-firewall.nft
    mkdir -p /etc/nftables.d
    cp /etc/boka-firewall.nft /etc/nftables.d/01-boka.nft
    systemctl enable nftables >/dev/null 2>&1 || true
    echo "[firewall] global egress enabled (only Telegram + DNS + loopback)."
fi

echo
echo "Boka hardened install complete."
echo "  code (read-only): $BOKA_INSTALL"
echo "  data (rw):        $BOKA_DATA"
echo "  logs:             $BOKA_LOG"
echo "  start preview:    systemctl start boka.service"
echo "  logs:             journalctl -fu boka.service"
if [[ $STRICT_FIREWALL -eq 1 ]]; then
    echo "  WARNING: global egress is locked to Telegram/DNS; non-Telegram "
    echo "           modules (translate, webshot, package installs) will fail."
fi