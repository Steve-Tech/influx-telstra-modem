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

IP = getenv("MODEM_IP", "192.168.0.1")
USERNAME = getenv("MODEM_USERNAME", "admin")
PASSWORD = getenv("MODEM_PASSWORD", "Telstra")

tsm = telstra_smart_modem.Modem(IP, USERNAME, PASSWORD)

INFLUX = getenv("INFLUX_URL", "http://influx:8086")
token = getenv("INFLUX_TOKEN")
org = getenv("INFLUX_ORG", "default")
bucket = getenv("INFLUX_BUCKET", "default")

client = InfluxDBClient(url=INFLUX, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)

measurement = getenv("MEASUREMENT", "modem")


def try_float(value):
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

    return Point(measurement).tag("modal", modal.rstrip("-modal")).field(field, try_float(value))


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

    return [Point(measurement).tag("modal", modal.rstrip("-modal")).field(field + "_up", try_float(splitvalue[0])),
            Point(measurement).tag("modal", modal.rstrip("-modal")).field(field + "_down", try_float(splitvalue[1]))]


def get_numeric_modal(modal, id, *args):
    soup = bs4.BeautifulSoup(modals[modal], "html.parser")

    value = soup.find("span", attrs={
        "id": id
    }).getText()
    field = id.lower().replace(' ', '_')

    if "second" in value:
        num_value = to_epoch(value)
    else:
        num_value = try_float(re.sub(r"[^0-9\.]", '', value))

    print(args[0] if len(args) else field, num_value)
    return Point(measurement).tag("modal", modal.rstrip("-modal")).field(args[0] if len(args) else field, num_value)


def get_ajax(modal, ajax, field):
    value = ajax[field]
    print(field, value)
    return Point(measurement).tag("modal", modal).field(field, value)


def to_epoch(uptime):
    try:
        re_uptime = \
            re.findall(r"(([0-9]+) days? )?(([0-9]{1,2}) hours? )?(([0-9]{1,2}) minutes? )?([0-9]{1,2}) seconds?",
                       uptime)[0]
        length = re_uptime[1].isdigit() + re_uptime[3].isdigit() + \
            re_uptime[5].isdigit() + re_uptime[6].isdigit()
        
        match (length):
            case 4:
                return int(re_uptime[1]) * 86400 + int(re_uptime[3]) * 3600 + int(re_uptime[5]) * 60 + int(re_uptime[6])
            case 3:
                return int(re_uptime[3]) * 3600 + int(re_uptime[5]) * 60 + int(re_uptime[6])
            case 2:
                return int(re_uptime[5]) * 60 + int(re_uptime[6])
            case 1:
                return int(re_uptime[6])
            case _:
                return 0
            
    except IndexError:
        return "null"


while True:
    try:
        status = tsm.getModemStatus()  # Make telstra_smart_modem check if timed-out

        # A dict of the modal pages to reduce loading multiple times
        modals = {"gateway-modal": get_modal("gateway-modal"), "broadband-modal": get_modal("broadband-modal"),
                  "internet-modal": get_modal("internet-modal"), "lte-modal": get_modal("lte-modal")}

        # A json dict of the ajax page to reduce loading multiple times
        lte_ajax = get_mobile_ajax()

        modal_data = [
            (get_string_modal, ("gateway-modal", "Uptime")),
            (get_numeric_modal, ("gateway-modal", "Uptime", "uptime_epoch")), # Get Epoch Time

            (get_string_modal, ("broadband-modal", "DSL Status")),
            (get_string_modal, ("broadband-modal", "DSL Uptime")),
            (get_string_modal, ("broadband-modal", "DSL Type")),
            (get_string_modal, ("broadband-modal", "DSL Mode")),

            (get_string_modal, ("internet-modal", "IP address")),
            (get_string_modal, ("internet-modal", "Gateway")),
            (get_string_modal, ("internet-modal", "IPv6 address")),
            (get_string_modal, ("internet-modal", "IPv6 Prefix")),
            (get_string_modal, ("internet-modal", "Lease obtained")),
            (get_string_modal, ("internet-modal", "Lease expires")),

            (get_ajax, ("lte-ajax", lte_ajax, "signal_quality")),
            (get_ajax, ("lte-ajax", lte_ajax, "status")),
            (get_ajax, ("lte-ajax", lte_ajax, "bars")),
            (get_numeric_modal, ("lte-modal", "Temperature:", "temperature")), # Get numbers only

            (get_directional_modal, ("broadband-modal", "Maximum Line rate", "Mbps")),
            (get_directional_modal, ("broadband-modal", "Line Rate", "Mbps")),
            (get_directional_modal, ("broadband-modal", "Data Transferred", "MBytes")),
            (get_directional_modal, ("broadband-modal", "Output Power", "dBm")),
            (get_directional_modal, ("broadband-modal", "Line Attenuation", "dB")),
            (get_directional_modal, ("broadband-modal", "Noise Margin", "dB")),
        ]

        data = [
            Point(measurement).tag("modal", "gateway").field("status", status)
        ]

        for func, args in modal_data:
            try:
                data.append(func(*args))
            except Exception as e:
                print("Error getting data from", args[0], args[1])

        write_api.write(bucket, org, data)

    except Exception as e:
        print(e)  # Just in case modem is offline

    print(datetime.utcnow())
    print('-' * 64)

    sleep(60 - datetime.utcnow().second)  # Wait until next minute
