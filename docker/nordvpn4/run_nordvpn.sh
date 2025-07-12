#!/bin/bash
set -euo pipefail

# Enable debug mode if requested
[[ -n ${DEBUG:-} ]] && set -x

# Logging function
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >&2
}

# Configuration and defaults
CONNECT=${CONNECT:-${COUNTRY:-}}
DOCKER_NET="$(ip -o addr show dev eth0 | awk '$3 == "inet" {print $4}' 2>/dev/null || echo "")"
MAX_RETRIES=3

# Validate required variables
if [[ -z ${NORDVPN_TOKEN:-} ]]; then
    log "ERROR: NORDVPN_TOKEN is required"
    exit 1
fi

# Validate network detection
if [[ -z $DOCKER_NET ]]; then
    log "WARNING: Could not detect Docker network"
fi

setup_nordvpn() {
    log "Starting NordVPN setup..."
    
    # Start NordVPN daemon
    /etc/init.d/nordvpn start
    
    # Wait for daemon with timeout
    local timeout=30
    local count=0
    while [ ! -S /run/nordvpn/nordvpnd.sock ]; do
        if [ $count -ge $timeout ]; then
            log "ERROR: NordVPN daemon failed to start within ${timeout}s"
            exit 1
        fi
        sleep 1
        ((count++))
    done
    
    log "NordVPN daemon started successfully"
    
    # Login to NordVPN
    if ! echo "n" | nordvpn login --token "$NORDVPN_TOKEN"; then
        log "ERROR: Failed to login to NordVPN"
        exit 1
    fi
    
    log "Successfully logged in to NordVPN"
    
    # Configure NordVPN settings
    log "Configuring NordVPN settings..."
    
    # Enable meshnet if requested
    if [[ -n ${MESHNET:-} ]]; then
        log "Enabling meshnet..."
        nordvpn set meshnet on
    fi
    
    # Core settings
    nordvpn set killswitch on
    nordvpn set cybersec off
    nordvpn set tray disabled
    nordvpn set notify disabled
    nordvpn set analytics disabled
    
    # Configure DNS if specified
    if [[ -n ${DNS:-} ]]; then
        log "Setting DNS servers: ${DNS}"
        nordvpn set dns ${DNS//[;,]/ }
    fi
    
    # Whitelist Docker network
    if [[ -n ${DOCKER_NET} ]]; then
        log "Whitelisting Docker network: ${DOCKER_NET}"
        nordvpn whitelist add subnet "${DOCKER_NET}"
    fi
    
    # Whitelist additional networks
    if [[ -n ${NETWORK:-} ]]; then
        log "Whitelisting additional networks: ${NETWORK}"
        for net in ${NETWORK//[;,]/ }; do
            nordvpn whitelist add subnet "${net}"
        done
    fi
    
    # Whitelist ports
    if [[ -n ${PORTS:-} ]]; then
        log "Whitelisting ports: ${PORTS}"
        for port in ${PORTS//[;,]/ }; do
            nordvpn whitelist add port "${port}"
        done
    fi
    
    # Display version and settings
    nordvpn -version
    nordvpn settings
    
    log "NordVPN setup completed successfully"
}

validate_config() {
    log "Validating configuration..."
    
    # Check if NordVPN is accessible
    if ! timeout 10 nordvpn countries >/dev/null 2>&1; then
        log "ERROR: Cannot access NordVPN service"
        exit 1
    fi
    
    # Validate connection target if specified
    if [[ -n ${CONNECT} ]]; then
        if ! nordvpn countries | grep -qi "${CONNECT}"; then
            log "WARNING: '${CONNECT}' may not be a valid country/server"
        fi
    fi
    
    log "Configuration validation completed"
}

connect_vpn() {
    local max_retries=${MAX_RETRIES}
    local retry=0
    local target="${CONNECT:-auto}"
    
    while [ $retry -lt $max_retries ]; do
        log "Attempting to connect to ${target} (attempt $((retry + 1))/$max_retries)"
        
        if nordvpn connect "${target}"; then
            log "Successfully connected to VPN"
            return 0
        fi
        
        ((retry++))
        if [ $retry -lt $max_retries ]; then
            log "Connection failed, retrying in 10 seconds..."
            sleep 10
        fi
    done
    
    log "ERROR: Failed to connect after $max_retries attempts"
    return 1
}

clean_meshnet() {
    if [[ -z ${MESHNET:-} ]]; then
        return 0
    fi
    
    log "Cleaning up meshnet configuration..."
    
    if [ -f "/config/mesh_peer_name" ]; then
        local peer_name
        peer_name=$(cat /config/mesh_peer_name)
        log "Removing meshnet peer: ${peer_name}"
        
        if nordvpn mesh peer remove "${peer_name}"; then
            log "Successfully removed meshnet peer"
        else
            log "WARNING: Failed to remove meshnet peer"
        fi
    else
        log "No mesh_peer_name found, skipping peer removal"
    fi
    
    # Get new mesh name if script exists
    if [[ -x "/get_mesh_name.sh" ]]; then
        log "Getting new mesh name..."
        /get_mesh_name.sh
    fi
}

kill_process_if_running() {
	local process_name="$1"
	if pgrep -x "$process_name" >/dev/null; then
		pkill -x "$process_name"
		log "Killed process: $process_name"
	else
		log "Process not running: $process_name"
	fi
}

cleanup() {
    log "Received shutdown signal, cleaning up..."
    
    # Clean meshnet first
    clean_meshnet
    
    # Disconnect VPN
    if nordvpn status | grep -q "Status: Connected"; then
        log "Disconnecting from VPN..."
        nordvpn disconnect || log "WARNING: Failed to disconnect cleanly"
    fi
    
    # Stop daemon
    log "Stopping NordVPN daemon..."
    /etc/init.d/nordvpn stop || log "WARNING: Failed to stop daemon cleanly"
    
    log "Cleanup completed"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT EXIT

# Main execution
main() {
    log "Starting NordVPN Docker container..."
    
    # Setup NordVPN
    setup_nordvpn
    
    # Validate configuration
    validate_config
    
    # Connect to VPN
    if ! connect_vpn; then
        log "ERROR: Initial VPN connection failed"
        exit 1
    fi
    
    # Show connection status
    nordvpn status
    
    # Initial wait for connection to stabilize
    log "Waiting for connection to stabilize..."
    sleep 30
    
    # Clean up any existing meshnet configuration
    clean_meshnet
    
    # Run meshnet setup periodically if enabled
    if [[ -n ${MESHNET:-} ]] && [[ -x "/add_to_meshnet.sh" ]]; then
        log "Starting meshnet maintenance loop..."
        while true; do
            /add_to_meshnet.sh || log "WARNING: Meshnet setup failed"

            kill_process_if_running "norduserd"
	        kill_process_if_running "nordfileshare"

            sleep 15m
        done
    else
        log "VPN setup complete, keeping container alive..."
        # Keep container running
        while true; do
            kill_process_if_running "norduserd"
	        kill_process_if_running "nordfileshare"

            sleep 1h
        done
    fi
}

# Run main function
main "$@"