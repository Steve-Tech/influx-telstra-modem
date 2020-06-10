import telstra_smart_modem
from telstra_smart_modem.base import ModemBase, HTTP_TIMEOUT
import bs4
import re
import json
from time import sleep
from datetime import datetime
from influxdb import InfluxDBClient

IP = "192.168.0.1"
USERNAME = "admin"
PASSWORD = "Telstra"

tsm = telstra_smart_modem.Modem(IP, USERNAME, PASSWORD)  # Login to the modem

client = InfluxDBClient(host="10.0.6.2", port=8086)  # InfluxDB IP and port


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
    if value is not None:
        return '"' + value + '"'
    else:
        return "null"  # If missing on page return null


def get_int_modal(modal, id):
    soup = bs4.BeautifulSoup(modals[modal], "html.parser")
    value = soup.find("span", attrs={
        "id": id
    }).getText()
    if value is not None:
        return re.sub(r"[^0-9\.]", '', value)  # Replace non digits + decimals (I know it's not really an int)
    else:
        return "null"


def get_list_modal(modal, id, unit):
    soup = bs4.BeautifulSoup(modals[modal], "html.parser")
    value = soup.find("span", attrs={
        "id": id
    }).getText()
    if value is not None:
        return value.replace(' ', '').split(unit)[0:2]  # Slice the units off
    else:
        return ["null"] * 2  # *2 for index errors


def to_epoch(uptime):  # Convert the uptime to a unix style time for grafana graphs
    try:
        re_uptime = \
            re.findall(r"([0-9]+) days? ([0-9]{1,2}) hours? ([0-9]{1,2}) minutes? ([0-9]{1,2}) seconds?",
                       uptime)[0]
        return int(re_uptime[0]) * 86400 + int(re_uptime[1]) * 3600 + int(re_uptime[2]) * 60 + int(re_uptime[3])
    except IndexError:
        return "null"


while True:
    try:
        status = '"' + tsm.getModemStatus() + '"'  # Make telstra_smart_modem check if timed-out (also get the modems status)

        # A dict of the modal pages to reduce loading multiple times
        modals = {"gateway-modal": get_modal("gateway-modal"), "broadband-modal": get_modal("broadband-modal"),
                  "internet-modal": get_modal("internet-modal"), "lte-modal": get_modal("lte-modal")}

        lte_ajax = get_mobile_ajax()  # A json dict of the ajax page to reduce loading multiple times

        data = "modem status=" + status + \
               ",uptime=" + get_string_modal("gateway-modal", "Uptime") + \
               ",uptime_epoch=" + str(to_epoch(get_string_modal("gateway-modal", "Uptime"))) + \
               ",dslstatus=" + get_string_modal("broadband-modal", "DSL Status") + \
               ",dsluptime=" + get_string_modal("broadband-modal", "DSL Uptime") + \
               ",dsltype=" + get_string_modal("broadband-modal", "DSL Type") + \
               ",dslmode=" + get_string_modal("broadband-modal", "DSL Mode") + \
               ",dslmaxrateup=" + get_list_modal("broadband-modal", "Maximum Line rate", "Mbps")[0] + \
               ",dslmaxratedown=" + get_list_modal("broadband-modal", "Maximum Line rate", "Mbps")[1] + \
               ",dsllinerateup=" + get_list_modal("broadband-modal", "Line Rate", "Mbps")[0] + \
               ",dsllineratedown=" + get_list_modal("broadband-modal", "Line Rate", "Mbps")[1] + \
               ",dsldataup=" + get_list_modal("broadband-modal", "Data Transferred", "MBytes")[0] + \
               ",dsldatadown=" + get_list_modal("broadband-modal", "Data Transferred", "MBytes")[1] + \
               ",dslpowerup=" + get_list_modal("broadband-modal", "Output Power", "dBm")[0] + \
               ",dslpowerdown=" + get_list_modal("broadband-modal", "Output Power", "dBm")[1] + \
               ",dslattenuationup=" + '"' + get_list_modal("broadband-modal", "Line Attenuation", "dB")[0] + '"' + \
               ",dslattenuationdown=" + '"' + get_list_modal("broadband-modal", "Line Attenuation", "dB")[1] + '"' + \
               ",dslnoiseup=" + get_list_modal("broadband-modal", "Noise Margin", "dB")[0] + \
               ",dslnoisedown=" + get_list_modal("broadband-modal", "Noise Margin", "dB")[1] + \
               ",dslinternetip=" + get_string_modal("internet-modal", "IP address") + \
               ",dslinternetipv6=" + get_string_modal("internet-modal", "IPv6 Address") + \
               ",dslinternetleaseobtained=" + get_string_modal("internet-modal", "Lease obtained") + \
               ",dslinternetleaseexpires=" + get_string_modal("internet-modal", "Lease expires") + \
               ",ltesignal=" + '"' + lte_ajax["signal_quality"] + '"' + \
               ",ltestatus=" + '"' + lte_ajax["status"] + '"' + \
               ",ltebars=" + lte_ajax["bars"] + \
               ",ltetemp=" + get_int_modal("lte-modal", "Temperature:") + \
               ""

        print(data)
        client.write(data, {'db': 'docker'}, 204, 'line')
    except Exception as e:
        print(e)  # In case modem is offline

    sleep(60 - datetime.utcnow().second)  # Wait till next minute
