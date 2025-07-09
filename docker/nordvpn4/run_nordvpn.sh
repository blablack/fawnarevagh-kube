#!/bin/bash
[[ -n ${DEBUG} ]] && set -x

[[ -n ${COUNTRY} && -z ${CONNECT} ]] && CONNECT=${COUNTRY}

DOCKER_NET="$(ip -o addr show dev eth0 | awk '$3 == "inet" {print $4}')"

setup_nordvpn() {
	/etc/init.d/nordvpn start

	while [ ! -S /run/nordvpn/nordvpnd.sock ]; do
		sleep 0.25
	done

	echo "n" | nordvpn login --token $NORDVPN_TOKEN 
	
	[[ -n ${MESHNET} ]] && nordvpn set meshnet on

	#nordvpn set technology nordlynx
	#nordvpn set firewall on
	nordvpn set killswitch on
	nordvpn set cybersec off
	nordvpn set tray disabled
	nordvpn set notify disabled
	nordvpn set analytics disabled

	[[ -n ${DNS} ]] && nordvpn set dns ${DNS//[;,]/ }
	[[ -n ${DOCKER_NET} ]] && nordvpn whitelist add subnet ${DOCKER_NET}
	[[ -n ${NETWORK} ]] && for net in ${NETWORK//[;,]/ }; do nordvpn whitelist add subnet "${net}"; done
	[[ -n ${PORTS} ]] && for port in ${PORTS//[;,]/ }; do nordvpn whitelist add port "${port}"; done

	nordvpn -version && nordvpn settings
}

clean_meshnet() {
	if [ -f "/config/mesh_peer_name" ]; then
		echo "Removing meshnet peer:"
		cat /config/mesh_peer_name
		nordvpn mesh peer remove $(cat /config/mesh_peer_name)
	else
		echo "No mesh_peer_name found"
	fi

	[[ -n ${MESHNET} ]] && /get_mesh_name.sh
}

cleanup() {
	nordvpn disconnect

	/etc/init.d/nordvpn stop
	trap - SIGTERM SIGINT EXIT
	exit 0
}
trap cleanup SIGTERM SIGINT EXIT

setup_nordvpn

nordvpn connect ${CONNECT} || exit 1

nordvpn status

sleep 30s

clean_meshnet

while true; do
	[[ -n ${MESHNET} ]] && /add_to_meshnet.sh

	sleep 15m
done
