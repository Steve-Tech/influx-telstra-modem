import telstra_smart_modem
from telstra_smart_modem.base import ModemBase, HTTP_TIMEOUT
import bs4
import re
import json
from time import sleep
from datetime import datetime
from influxdb import InfluxDBClient

IP = '192.168.0.1'
USERNAME = 'admin'
PASSWORD = 'Telstra'

tsm = telstra_smart_modem.Modem(IP, USERNAME, PASSWORD)

client = InfluxDBClient(host='10.0.6.2', port=8086)

def getModal(modal):
	response = ModemBase.session.get(
		f"http://{IP}/modals/{modal}.lp",
		timeout=HTTP_TIMEOUT
	).text
	
	return response

def getMobileAjax():
	response = ModemBase.session.get(
		f"http://{IP}/ajax/mobiletab.lua",
		timeout=HTTP_TIMEOUT
	)
	value = json.loads(response.text)
	return value

def parseModal(modal, id):
	soup = bs4.BeautifulSoup(modals[modal], 'html.parser')
	value = soup.find('span', attrs={
		"id": id
	}).getText()
	if not value is None:
		return value
	else:
		return "null"


def toEpoch(uptime):
	try:
		re_uptime = re.findall("([0-9]+) day.{0,1} ([0-9]{1,2}) hour.{0,1} ([0-9]{1,2}) minute.{0,1} ([0-9]{1,2}) second.{0,1}", uptime)[0]
		return int(re_uptime[0]) * 86400 + int(re_uptime[1]) * 3600 + int(re_uptime[2]) * 60 + int(re_uptime[3])
	except IndexError:
		return "null"

def getGatewayModal():
	return '"' + parseModal("gateway-modal", "Uptime") + '"'

def getDSLStatus():
	return '"' + parseModal("broadband-modal", "DSL Status") + '"'
def getDSLUptime():
	return '"' + parseModal("broadband-modal", "DSL Uptime") + '"'
def getDSLType():
	return '"' + parseModal("broadband-modal", "DSL Type") + '"'
def getDSLMode():
	return '"' + parseModal("broadband-modal", "DSL Mode") + '"'
def getDSLMaxRate():
	value = parseModal("broadband-modal", "Maximum Line rate")
	if value != "null":	
		return value.replace(' ', '').split("Mbps")[0:2]
	else: return value
def getDSLLineRate():
	value = parseModal("broadband-modal", "Line Rate")
	if value != "null":	
		return value.replace(' ', '').split("Mbps")[0:2]
	else: return value
def getDSLData():
	value = parseModal("broadband-modal", "Data Transferred")
	if value != "null":	
		return value.replace(' ', '').split("MBytes")[0:2]
	else: return value
def getDSLPower():
	value = parseModal("broadband-modal", "Output Power")
	if value != "null":	
		return value.replace(' ', '').split("dBm")[0:2]
	else: return value
def getDSLAttenuation():
	value = parseModal("broadband-modal", "Line Attenuation")
	if value != "null":	
		return value.replace(' ', '').split("dB")[0:2]
	else: return value
def getDSLNoise():
	value = parseModal("broadband-modal", "Noise Margin")
	if value != "null":	
		return value.replace(' ', '').split("dB")[0:2]
	else: return value

def getInternetIP():
	return '"' + parseModal("internet-modal", "IP address") + '"'
def getInternetIPv6():
	return '"' + parseModal("internet-modal", "IPv6 Address") + '"'
def getInternetLeaseObtained():
	return '"' + parseModal("internet-modal", "Lease obtained") + '"'
def getInternetLeaseExpires():
	return '"' + parseModal("internet-modal", "Lease expires") + '"'
	
def getLTETemp():
	return parseModal("lte-modal", "Temperature:")

#def getTelstraAirUsers():
#	return parseModal("fon-modal", "")
#def getFonWiFiUsers():
#	return parseModal("fon-modal", "")

while True:
	try:
		status = '"' + tsm.getModemStatus() + '"' # Make telstra_smart_modem check if timed-out

		modals = {"gateway-modal": getModal("gateway-modal"), "broadband-modal": getModal("broadband-modal"), "internet-modal": getModal("internet-modal"), "lte-modal": getModal("lte-modal")}

		data = "modem status=" + status + \
			",uptime=" + getGatewayModal() + \
			",uptime_epoch=" + str(toEpoch(getGatewayModal())) + \
			",dslstatus=" + getDSLStatus() + \
			",dsluptime=" + getDSLUptime() + \
			",dsltype=" + getDSLType() + \
			",dslmode=" + getDSLMode() + \
			",dslmaxrateup=" + getDSLMaxRate()[0] + \
			",dslmaxratedown=" + getDSLMaxRate()[1] + \
			",dsllinerateup=" + getDSLLineRate()[0] + \
			",dsllineratedown=" + getDSLLineRate()[1] + \
			",dsldataup=" + getDSLData()[0] + \
			",dsldatadown=" + getDSLData()[1] + \
			",dslpowerup=" + getDSLPower()[0] + \
			",dslpowerdown=" + getDSLPower()[1] + \
			",dslattenuationup=\"" + getDSLAttenuation()[0] + '"' + \
			",dslattenuationdown=\"" + getDSLAttenuation()[1] + '"' + \
			",dslnoiseup=" + getDSLNoise()[0] + \
			",dslnoisedown=" + getDSLNoise()[1] + \
			",dslinternetip=" + getInternetIP() + \
			",dslinternetipv6=" + getInternetIPv6() + \
			",dslinternetleaseobtained=" + getInternetLeaseObtained() + \
			",dslinternetleaseexpires=" + getInternetLeaseExpires() + \
			""

		print(data)
		client.write(data, {'db':'docker'}, 204, 'line')
	except Exception as e: print(e)
	sleep(60 - datetime.utcnow().second)