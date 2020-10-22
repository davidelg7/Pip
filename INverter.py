from mppsolar import mppUtils
from mppsolar.mppinverter import mppInverter, NoDeviceError
import threading
from datetime import datetime
from paho.mqtt.client import Client
import time
def getVal(_dict, key, ind=None):
    if key not in _dict:
        return ""
    if ind is None:
        return _dict[key]
    else:
        return _dict[key][ind]

class Inverter:


    def __init__(self, serial_device=None, baud_rate=2400, inverter_model='standard',interval=1):
        if (serial_device is None):
            raise NoDeviceError("A serial device must be supplied, e.g. /dev/ttyUSB0")

        def on_message(client, userdata, message):
            topic=message.topic
            payload=message.payload.decode()
            try:
                    if  topic=="Set Mode":
                        self.r=False
                        time.sleep(11)
                        if payload=="Battery Mode":
                            print("provo battery")
                            self.getResponse("POP02")
                        if payload=="Line Mode":
                            self.getResponse("POP00")
                        self.r=True
                        time.sleep(11)

            except Exception as e:
                print(e)


        self.client= Client(client_id = "inverter")
        self.r=True

        self.client.connect(host="192.168.1.5",port=1883)

        self.client.on_message = on_message
        self.client.subscribe("Set Mode")

        self.inverter = mppInverter(serial_device, baud_rate, inverter_model)
        self.topicValue={
            "work_mode":"work_mode",
            "grid_voltage":"Enel voltage",
            "ac_output_voltage":"Inverter voltage",
            "total_output_active_power":"Inverter power",
            "work_mode":"Mode",
            "battery_voltage":"Battery voltage",
            "total_charging_current":"Battery charge",
            "battery_discharge_current":"Battery discharge",
            "pv_input_voltage":"Panel voltage"
        }
        self.data={}
        self.interval=interval
        self.x=threading.Thread(target=self.run)
        self.x.start()
        y=threading.Thread(target=self.client.loop_forever)
        y.setDaemon(True)
        y.start()
        # x.setDaemon(True)

    def run(self):
        while True:
            while self.r:

                try:

                    self.data=self.getFullStatus()
                    d={}
                    for di in self.data:
                        if di in self.topicValue:
                            d[self.topicValue[di]]=self.data[di]["value"]

                    d["Battery current"]=d["Battery charge"]-d["Battery discharge"]-75/d["Battery voltage"]
                    d["Enel current"]=0
                    if d["Mode"]=="Battery Mode":
                        d["Inverter current"] = d["Inverter power"]/d["Inverter voltage"]
                        d["Panel current"]=(d["Inverter power"]+d["Battery current"]*d["Battery voltage"])/d["Panel voltage"]
                        if d["Panel current"]<0:
                            d["Panel current"]=0
                    elif d["Mode"]=="Line Mode":
                        d["Enel current"] = d["Inverter power"] / d["Inverter voltage"]
                        d["Panel current"] = (d["Battery current"] * d["Battery voltage"]) / d["Panel voltage"]
                    for k in d:
                        self.client.publish(topic=k, payload=d[k])

                except Exception as e:
                    print(e)
            time.sleep(10)
    def getFullCommand(self, cmd):
        return self.inverter._getCommand(cmd)

    def getKnownCommands(self):
        return self.inverter.getAllCommands()

    def getResponseDict(self, cmd):
        return self.inverter.getResponseDict(cmd)

    def getInfluxLineProtocol2(self, cmd):
        return self.inverter.getInfluxLineProtocol2(cmd)

    def getInfluxLineProtocol(self, cmd):
        return self.inverter.getInfluxLineProtocol(cmd)

    def getResponse(self, cmd):
        return self.inverter.getResponse(cmd)

    def getSerialNumber(self):
        return self.inverter.getSerialNumber()

    def getFullStatus(self):
        """
        Helper function that returns all the status data
        """
        status = {}
        # serial_number = self.getSerialNumber()
        # data = self.getResponseDict("QPIGS")
        # data.update(self.getResponseDict("Q1"))
        data={}
        # Need to get 'Parallel' info, but dont know what the parallel number for the correct inverter is...
        parallel_data = self.getResponseDict("QPGS0")
        # This 'hack' only works for 2 inverters in parallel.
        if parallel_data['serial_number'][0] != self.getSerialNumber():
          data = self.getResponseDict("QPGS1")
        # status_data.update(parallel_data)

        for item in data.keys():
            key = '{}'.format(item).replace(" ", "_")
            status[key] = {"value": data[key][0], "unit": data[key][1]}
        # Still have 'Device Status' from QPIGS
        # Still have QPGSn
        return status

    def getSettings(self):
        """
        Query inverter for all current settings
        """
        # serial_number = self.getSerialNumber()
        default_settings = self.getResponseDict("QDI")
        current_settings = self.getResponseDict("QPIRI")
        flag_settings = self.getResponseDict("QFLAG")
        # current_settings.update(flag_settings)  # Combine current and flag settings dicts

        settings = {}
        # {"Battery Bulk Charge Voltage": {"unit": "V", "default": 56.4, "value": 57.4}}

        for item in current_settings.keys():
            key = '{}'.format(item).replace(" ", "_")
            settings[key] = {"value": getVal(current_settings, key, 0),
                             "unit": getVal(current_settings, key, 1),
                             "default": getVal(default_settings, key, 0)}
        for key in flag_settings:
            _key = '{}'.format(key).replace(" ", "_")
            if _key in settings:
                settings[_key]['value'] = getVal(flag_settings, key, 0)
            else:
                settings[_key] = {'value': getVal(flag_settings, key, 0), "unit": "", "default": ""}
        return settings
inv= Inverter(serial_device="COM3")

