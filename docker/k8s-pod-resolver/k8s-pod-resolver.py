from dnslib import DNSRecord, DNSHeader, RR, QTYPE, A, PTR
from dnslib.server import DNSServer, DNSHandler, BaseResolver
import kubernetes.client
import kubernetes.config
import http.server
import socketserver
import os
import ipaddress
import socket
import threading
import logging
import sys
from concurrent.futures import ThreadPoolExecutor


class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        # Suppress logging for cleaner output
        return


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

    def is_healthy(self):
        """Check if the resolver is healthy"""
        return len(self.pod_cache) > 0

    def resolve(self, request, handler):
        """Resolve DNS requests for pod IPs"""

        reply = request.reply()
        qname = str(request.q.qname)

        if request.q.qtype == QTYPE.PTR:
            if qname.endswith(".in-addr.arpa."):
                parts = qname.split(".")
                if len(parts) >= 5:
                    # Reverse the octets
                    ip = ".".join(parts[0:4][::-1])

                    with self.cache_lock:
                        if ip in self.pod_cache:
                            pod_name = self.pod_cache[ip]
                            logging.info(f"IP: {ip} - {pod_name}")
                            reply.add_answer(
                                RR(request.q.qname, QTYPE.PTR, rdata=PTR(pod_name))
                            )
                            return reply

        return reply


def run_health_server(resolver, port=8080):
    """Run a health check server on the specified port"""

    class CustomHealthHandler(HealthCheckHandler):
        def do_GET(self):
            if self.path == "/healthz":
                if resolver.is_healthy():
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    self.send_response(503)
                    self.send_header("Content-type", "text/plain")
                    self.end_headers()
                    self.wfile.write(b"Service Unavailable")
            else:
                self.send_response(404)
                self.send_header("Content-type", "text/plain")
                self.end_headers()
                self.wfile.write(b"Not Found")

    httpd = socketserver.TCPServer(("", port), CustomHealthHandler)
    logging.info(f"Starting health check server on port {port}")
    httpd.serve_forever()


def run_server():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    dns_port = int(os.environ.get("DNS_PORT", 53))
    dns_addr = os.environ.get("DNS_BIND_ADDR", "0.0.0.0")
    health_port = int(os.environ.get("HEALTH_PORT", 8080))

    resolver = K8sPodResolver()
    server = DNSServer(resolver, port=dns_port, address=dns_addr)

    logging.info(f"Starting DNS server on {dns_addr}:{dns_port}")
    with ThreadPoolExecutor(max_workers=2) as executor:
        executor.submit(run_health_server, resolver, health_port)
        executor.submit(server.start)


if __name__ == "__main__":
    run_server()
