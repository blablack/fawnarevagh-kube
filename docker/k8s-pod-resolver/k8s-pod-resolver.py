from dnslib import DNSRecord, DNSHeader, RR, QTYPE, A, PTR
from dnslib.server import DNSServer, DNSHandler, BaseResolver
import kubernetes.client
import kubernetes.config
import os
import ipaddress
import socket
import threading
import logging

class K8sPodResolver(BaseResolver):
    def __init__(self):
        # Initialize kubernetes client
        try:
            kubernetes.config.load_kube_config()  # For local development
        except:
            kubernetes.config.load_incluster_config()  # For in-cluster deployment
            
        self.k8s_api = kubernetes.client.CoreV1Api()
        self.pod_cache = {}
        self.cache_lock = threading.Lock()
        self.cache_timer = threading.Timer(300, self.refresh_cache)
        self.cache_timer.daemon = True
        self.cache_timer.start()
        
        # Initial cache population
        self.refresh_cache()
        
    def refresh_cache(self):
        """Refresh the pod IP to name mapping cache"""
        try:
            pods = self.k8s_api.list_pod_for_all_namespaces(watch=False)
            
            new_cache = {}
            for pod in pods.items:
                if pod.status.pod_ip:
                    # Store both forward and reverse mappings
                    pod_name = f"{pod.metadata.name}.{pod.metadata.namespace}"
                    new_cache[pod.status.pod_ip] = pod_name
                    
            with self.cache_lock:
                self.pod_cache = new_cache

            logging.info(f"Cache refreshed, {len(self.pod_cache)} pods found")
        except Exception as e:
            logging.error(f"Error refreshing cache: {e}")
            
        # Schedule next refresh
        self.cache_timer = threading.Timer(300, self.refresh_cache)
        self.cache_timer.daemon = True
        self.cache_timer.start()
    
    def resolve(self, request, handler):
        """Resolve DNS requests for pod IPs"""
        
        reply = request.reply()
        qname = str(request.q.qname)
        
        if request.q.qtype == QTYPE.PTR:
            if qname.endswith('.in-addr.arpa.'):
                parts = qname.split('.')
                if len(parts) >= 5:
                    # Reverse the octets
                    ip = '.'.join(parts[0:4][::-1])

                    with self.cache_lock:
                        if ip in self.pod_cache:
                            pod_name = self.pod_cache[ip]
                            reply.add_answer(RR(request.q.qname, QTYPE.PTR, rdata=PTR(pod_name)))
                            return reply
        
        return reply

def run_server():
    logging.basicConfig(
        level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    dns_port = int(os.environ.get("DNS_PORT", 53))
    dns_addr = os.environ.get("DNS_BIND_ADDR", "0.0.0.0")

    resolver = K8sPodResolver()
    server = DNSServer(resolver, port=dns_port, address=dns_addr)
    
    logging.info(f"Starting DNS server on {dns_addr}:{dns_port}")
    server.start()

if __name__ == "__main__":
    run_server()