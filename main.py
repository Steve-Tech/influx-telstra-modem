#!/bin/python3
import telstra_smart_modem
from telstra_smart_modem.base import ModemBase, HTTP_TIMEOUT
import bs4
import re
import json
from os import getenv
from time import sleep
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

IP = getenv("IP", "192.168.0.1")
USERNAME = getenv("USERNAME", "admin")
PASSWORD = getenv("PASSWORD", "Telstra")

tsm = telstra_smart_modem.Modem(IP, USERNAME, PASSWORD)

INFLUX = getenv("INFLUX", "http://172.18.0.2:8086")
bucket = getenv("BUCKET", "default")
org = getenv("ORG", "default")
token = getenv("TOKEN")

client = InfluxDBClient(url=INFLUX, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

measurement = getenv("MEASUREMENT", "modem")


def tryint(value): # Named this way because it originally tried ints, but floats are better.
    try:
        return float(value)
    except ValueError:
        return value


def get_modal(modal):
    response = ModemBase.session.get(
        f"http://{IP}/modals/{modal}.lp",
        timeout=HTTP_TIMEOUT
    ).text
    return response


def get_mobile_ajax():
    response = ModemBase.session.get(
        f"http://{IP}/ajax/mobiletab.lua",
        timeout=HTTP_TIMEOUT
    )
    value = json.loads(response.text)
    return value


def get_string_modal(modal, id):
    soup = bs4.BeautifulSoup(modals[modal], "html.parser")
    value = soup.find("span", attrs={
        "id": id
    }).getText()
    field = id.lower().replace(' ', '_')
    print(field, value)
    return Point(measurement).tag("modal", modal.rstrip("-modal")).field(field, tryint(value))


def get_directional_modal(modal, id, unit):
    soup = bs4.BeautifulSoup(modals[modal], "html.parser")
    value = soup.find("span", attrs={
        "id": id
    }).getText()
    if value is not None:
        splitvalue = value.replace(' ', '').split(unit)[0:2]
    else:
        splitvalue = [None] * 2
    field = id.lower().replace(' ', '_')
    print(field, splitvalue)
    return [Point(measurement).tag("modal", modal.rstrip("-modal")).field(field + "_up", tryint(splitvalue[0])),
            Point(measurement).tag("modal", modal.rstrip("-modal")).field(field + "_down", tryint(splitvalue[1]))]


def get_int_modal(modal, id, *args):
    soup = bs4.BeautifulSoup(modals[modal], "html.parser")
    value = soup.find("span", attrs={
        "id": id
    }).getText()
    field = id.lower().replace(' ', '_')
    if "second" in value:
        intvalue = to_epoch(value)
    else:
        intvalue = tryint(re.sub(r"[^0-9\.]", '', value))
    print(args[0] if len(args) else field, intvalue)
    return Point(measurement).tag("modal", modal.rstrip("-modal")).field(args[0] if len(args) else field, intvalue)


def to_epoch(uptime):
    try:
        re_uptime = \
            re.findall(r"(([0-9]+) days? )?(([0-9]{1,2}) hours? )?(([0-9]{1,2}) minutes? )?([0-9]{1,2}) seconds?",
                       uptime)[0]
        length = re_uptime[1].isdigit() + re_uptime[3].isdigit() + re_uptime[5].isdigit() + re_uptime[6].isdigit()
        if length == 4: return int(re_uptime[1]) * 86400 + int(re_uptime[3]) * 3600 + int(re_uptime[5]) * 60 + int(re_uptime[6])
        elif length == 3: return int(re_uptime[3]) * 3600 + int(re_uptime[5]) * 60 + int(re_uptime[6])
        elif length == 2: return int(re_uptime[5]) * 60 + int(re_uptime[6])
        elif length == 1: return int(re_uptime[6])
        else: return 0
    except IndexError:
        return "null"

while True:
    try:
        status = tsm.getModemStatus()  # Make telstra_smart_modem check if timed-out

        # A dict of the modal pages to reduce loading multiple times
        modals = {"gateway-modal": get_modal("gateway-modal"), "broadband-modal": get_modal("broadband-modal"),
                  "internet-modal": get_modal("internet-modal"), "lte-modal": get_modal("lte-modal")}

        lte_ajax = get_mobile_ajax()  # A json dict of the ajax page to reduce loading multiple times

        data = [
            Point(measurement).tag("modal", "gateway").field("status", status),
            get_string_modal("gateway-modal", "Uptime"),
            get_int_modal("gateway-modal", "Uptime", "uptime_epoch"), # Get Epoch Time
            get_string_modal("broadband-modal", "DSL Status"),
            get_string_modal("broadband-modal", "DSL Uptime"),
            get_string_modal("broadband-modal", "DSL Type"),
            get_string_modal("broadband-modal", "DSL Mode"),
            get_string_modal("internet-modal", "IP address"),
            get_string_modal("internet-modal", "Gateway"),
            get_string_modal("internet-modal", "IPv6 address"),
            get_string_modal("internet-modal", "IPv6 Prefix"),
            get_string_modal("internet-modal", "Lease obtained"),
            get_string_modal("internet-modal", "Lease expires"),
            Point(measurement).tag("modal", "lte-ajax").field("signal_quality", lte_ajax["signal_quality"]),
            Point(measurement).tag("modal", "lte-ajax").field("status", lte_ajax["status"]),
            Point(measurement).tag("modal", "lte-ajax").field("bars", lte_ajax["bars"]),
            get_int_modal("lte-modal", "Temperature:", "temperature") # Get numbers only
        ]

        data.extend(get_directional_modal("broadband-modal", "Maximum Line rate", "Mbps"))
        data.extend(get_directional_modal("broadband-modal", "Line Rate", "Mbps"))
        data.extend(get_directional_modal("broadband-modal", "Data Transferred", "MBytes"))
        data.extend(get_directional_modal("broadband-modal", "Output Power", "dBm"))
        data.extend(get_directional_modal("broadband-modal", "Line Attenuation", "dB"))
        data.extend(get_directional_modal("broadband-modal", "Noise Margin", "dB"))


        write_api.write(bucket, org, data)

    except Exception as e:
        print(e)  # Just in case modem is offline

    print(datetime.utcnow())
    print('-' * 64)

    sleep(60 - datetime.utcnow().second)  # Wait till next minute

