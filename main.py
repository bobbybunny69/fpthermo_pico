"""
Fishpond thermometer for HASS using MQTT
"""
import machine
from secret import wifi, dbg_svr
from lpfwk import LPFWK
from ds18x20 import DS18X20
from onewire import OneWire
from fp2mqtt import FP2MQTT_Sensor
import gc

DS18B20_PIN = machine.Pin(20)
PWR_PIN = machine.Pin(22, machine.Pin.OUT)
WIFI_RETRIES= DS18B20_RETRIES = 10
SLEEP_SECS = 600
LED_PIN = machine.Pin("LED", machine.Pin.OUT)

def get_temperature() -> None | float:
    #Setup the DS18B20 data line and read ROMS
    PWR_PIN.on()
    lpf.sleep_ms(200)
    ds_bus = DS18X20(OneWire(DS18B20_PIN))
    roms = ds_bus.scan()
    lpf.print("Found DS devices: {}".format(roms))
    ds_bus.convert_temp()
    lpf.sleep_ms(750)
    reading = ds_bus.read_temp(roms[0])
    if(reading==None):
        lpf.print("Bad CRC reading sensor")
        reading = None
    elif(reading>50.0): 
        lpf.print("Suspiscous reading on sensor")
        reading = None
    PWR_PIN.off()
    return reading

def get_vbatt() -> None | float:
    """
    On Pico-W procedure is complex due to Pin-29 functioning as WF clock
    and reading batt voltage so must read before enabling Wi-Fi
    Procedure is:
        Set GPIO-29 as Input (this is ADC-3)
        Set GPIO25 High
        Read ADC-3
        Return GPIO 29 and 25 to original state - poss not needed?
    """
    machine.Pin(29, machine.Pin.IN)
    machine.Pin(25, machine.Pin.OUT).on()

    adc = machine.ADC(3)
    raw_value = adc.read_u16()
    conversion_factor = 3.3 / 65535
    voltage = raw_value * 3.0 * conversion_factor
    lpf.print("Batt voltage: {}".format(voltage))
    return voltage

VBUS_PIN = machine.Pin("WL_GPIO2", machine.Pin.IN)
"""
NOTE Use VBUS pin to detect USB connection and select between
    Developer mode or Mission mode
"""
if VBUS_PIN.value():
    lpf = LPFWK(dbg_svr['ip'], dbg_svr['port'], dev_mode=True)  # Disable WD if running from USB
    lpf.print("Running from USB power")
else:
    lpf = LPFWK(dbg_svr['ip'], dbg_svr['port'], dev_mode=False)
    lpf.print("Running from VSYS")

uid = machine.unique_id()
uid = '{:02x}{:02x}'.format(uid[2],uid[3])
fp_mqtt_sensor = None
wifi_isconnected = False

while True:
    voltage = get_vbatt()
    gc.collect()
    lpf.print("Memory free: {}".format(gc.mem_free()))
    # Connect to WiFi
    if not wifi_isconnected:
        wifi_isconnected = lpf.connect_wifi(wifi['ssid'], wifi['pw'])

    if fp_mqtt_sensor == None and wifi_isconnected:
        #Setup the MQTT client sensor for HASS for fp_thermo and unique id
        lpf.print("Setting up MQTT client")
        try:
            fp_mqtt_sensor = FP2MQTT_Sensor("fp_thermo", uid, lpf)
            fp_mqtt_sensor.add_temperature()
            fp_mqtt_sensor.add_battery()
            lpf.print("Sensors setup and added")
        except Exception as e:
            lpf.print("Failed to connect MQTT: {}".format(e))

    try:
        reading = get_temperature()
        if(reading==None):
            lpf.print("Reading failed on sensor")
            reading = 0.0
        else:
            lpf.print("Temperature: {}".format(reading))
    except Exception as e:
        lpf.print("Reading failed on sensor {}".format(e))
        reading = 0.0

    if fp_mqtt_sensor != None and wifi_isconnected:
        fp_mqtt_sensor.publish_state(reading, voltage)
        fp_mqtt_sensor.disconnect()
    
    lpf.disconnect_wifi()
    wifi_isconnected = False
    lpf.deep_sleep(SLEEP_SECS)
