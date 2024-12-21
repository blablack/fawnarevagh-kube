#!/usr/bin/env python

from flask import Flask, render_template, jsonify
import datetime

DNSMASQ_LEASES_FILE = "/var/lib/misc/dnsmasq.leases"

app = Flask(__name__)


class LeaseEntry:
    def __init__(self, leasetime, macAddress, ipAddress, name):
        self.leasetime = datetime.datetime.fromtimestamp(int(leasetime))
        self.macAddress = macAddress.upper()
        self.ipAddress = ipAddress
        self.name = name

    def serialize(self):
        return {
            "leasetime": self.leasetime.strftime("%Y-%m-%d %H:%M:%S"),
            "macAddress": self.macAddress,
            "ipAddress": self.ipAddress,
            "name": self.name,
        }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/healthz")
def healthz():
    return jsonify({"status": "healthy"})


@app.route("/leases")
def getLeases():
    leases = []
    with open(DNSMASQ_LEASES_FILE) as f:
        leases = [
            LeaseEntry(elements[0], elements[1], elements[2], elements[3]).serialize()
            for line in f
            if (elements := line.split()) and len(elements) == 5
        ]

    return jsonify(leases=leases)


if __name__ == "__main__":
    app.run("0.0.0.0")
