# Influx script for Telstra Modems

A script to pull data from a Telstra Smart Modem and push it to InfluxDB.

## GHCR Docker Image

The recommended way to run the script is via the Docker image.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEM_IP` | The IP address of the modem | `"192.168.0.1"` |
| `MODEM_USERNAME` | The username to use to authenticate with the modem | `"admin"` |
| `MODEM_PASSWORD` | The password to use to authenticate with the modem | `"Telstra"` |
| `INFLUX_URL` | The URL of the InfluxDB instance | `http://influx:8086` |
| `INFLUX_TOKEN` | The token to use to authenticate with InfluxDB | `None` |
| `INFLUX_ORG` | The organisation to use with InfluxDB | `"default"` |
| `INFLUX_BUCKET` | The bucket to use with InfluxDB | `"default"` |
| `MEASUREMENT` | The measurement to use with InfluxDB | `"modem"` |

### Docker Compose

```yaml
version: "3.9"
services:
  modem:
    image: ghcr.io/steve-tech/influx-telstra-modem:main
    restart: always
    environment:
      #- "MODEM_IP=192.168.0.1"
      #- "MODEM_USERNAME=admin"
      - "MODEM_PASSWORD=Telstra"
      - "INFLUX_URL=http://influx:8086"
      - "INFLUX_TOKEN=FillThisInWithYourInfluxAPIToken"
      - "INFLUX_ORG=organisation"
      - "INFLUX_BUCKET=python"
      #- "MEASUREMENT=modem"
```

## Running without Docker

### Requirements

* Python 3.10+
* InfluxDB 2.0+
* A Telstra Smart Modem (or compatible?, Tested on the Gen 2)
* Python modules in `requirements.txt`

### Instructions

1. Clone the repository
2. Install the requirements `pip install -r requirements.txt`
3. Edit the variables in `main.py` or set the environment variables as above
4. Run the script `python3 main.py`
