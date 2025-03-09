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
import re
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

        # Initial cache population and start the timer
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

        # Cancel any existing timer before creating a new one
        if hasattr(self, "cache_timer") and self.cache_timer:
            self.cache_timer.cancel()

        # Schedule next refresh
        self.cache_timer = threading.Timer(300, self.refresh_cache)
        self.cache_timer.daemon = True
        self.cache_timer.start()

    def is_healthy(self):
        """Check if the resolver is healthy"""
        return len(self.pod_cache) > 0

    def clean_pod_name(self, full_name):
        # Split namespace if present
        parts = full_name.split(".")
        pod_name = parts[0]
        namespace = parts[1] if len(parts) > 1 else None

        # Pattern 1: deployment format with random hash (longhorn-ui-7cc7f7469-m8kv2)
        match = re.match(r"(.*)-[a-f0-9]{8,10}-[a-z0-9]{5}$", pod_name)
        if match:
            clean_name = match.group(1)

        # Pattern 2: replicaset without deployment (metrics-server-7bf7d58749-lrjgz)
        elif re.match(r"(.*)-[a-z0-9]{9,10}-[a-z0-9]{5}$", pod_name):
            clean_name = re.match(r"(.*)-[a-z0-9]{9,10}-[a-z0-9]{5}$", pod_name).group(
                1
            )

        # Pattern 3: daemonset pods (speaker-d7xtj)
        elif re.match(r"(.*)-[a-z0-9]{5}$", pod_name):
            clean_name = re.match(r"(.*)-[a-z0-9]{5}$", pod_name).group(1)

        # No pattern matched, return original
        else:
            clean_name = pod_name

        # Add namespace back if it was present
        if namespace:
            return f"{clean_name}.{namespace}"
        else:
            return clean_name

    def resolve(self, request, handler):
        """Resolve DNS requests for pod IPs"""

        reply = request.reply()
        qname = str(request.q.qname)

        logging.info(f"Request for {qname}")

        if request.q.qtype == QTYPE.PTR:
            if qname.lower().rstrip(".").endswith(".in-addr.arpa"):
                parts = qname.split(".")
                if len(parts) >= 5:
                    # Reverse the octets
                    ip = ".".join(parts[0:4][::-1])

                    with self.cache_lock:
                        if ip in self.pod_cache:
                            pod_name = self.pod_cache[ip]
                            pod_name = self.clean_pod_name(pod_name)
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
