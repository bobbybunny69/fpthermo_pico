"""
Fishpond thermometer for HASS using MQTT
"""
import time
import network
import machine
from ds18x20 import DS18X20
from onewire import OneWire
from fp2mqtt import FP2MQTT_Sensor
from log import sprint
from secret import wifi
import gc

# ----------------------------------
# Watchdog enable
# set to True in Production
# set to False in Development
# Upload with 8.3s to stop continual resets
WATCHDOG_ENABLE=False
# ----------------------------------
WATCHDOG_KICK_PERIOD_SECS = 5 # Note: must be less than 8.3s as this is max Pico supports


DS18B20_PIN = machine.Pin(20)
PWR_PIN = machine.Pin(22, machine.Pin.OUT)
WIFI_RETRIES= DS18B20_RETRIES = 10
SLEEP_SECS = 120
LED_PIN = machine.Pin("LED", machine.Pin.OUT)

def get_temperature() -> None | float:
    #Setup the DS18B20 data line and read ROMS
    PWR_PIN.on()
    time.sleep(0.2)
    ds_bus = DS18X20(OneWire(DS18B20_PIN))
    roms = ds_bus.scan()
    sprint("Found DS devices: {}".format(roms))
    ds_bus.convert_temp()
    time.sleep(0.75)
    reading = ds_bus.read_temp(roms[0])
    if(reading==None):
        sprint("Bad CRC reading sensor")
    elif(reading>50.0): 
        sprint("Suspiscous reading on sensor")
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
    sprint("Batt voltage: {}".format(voltage))
    return voltage

def connect_wifi() -> bool:
    # Connect to WiFi
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(wifi['ssid'], wifi['pw'])
    for i in range(0,WIFI_RETRIES):
        if WATCHDOG_ENABLE == True:
            wdt.feed()
        LED_PIN.on()
        time.sleep(0.1)
        sprint('Waiting for connection...')
        LED_PIN.off()
        time.sleep(0.9)
        if wlan.isconnected():
            ip_addr = wlan.ifconfig()[0]
            sprint("Connected to Wi-Fi. My IP Address: {}".format(ip_addr))
            break
    return wlan.isconnected()

def disconnect_wifi():
        wlan = network.WLAN(network.STA_IF) # Get the interface object again
        wlan.active(False) # Disconnect and deactivate the Wi-Fi chip
        sprint("Wi-Fi disconnected.")

def my_sleep():
    counter = SLEEP_SECS / WATCHDOG_KICK_PERIOD_SECS
    while(counter>0):
        if WATCHDOG_ENABLE == True:
            wdt.feed()
        time.sleep(WATCHDOG_KICK_PERIOD_SECS)
        print("Kick {}".format(counter))
        counter-=1
    if WATCHDOG_ENABLE == True:
        wdt.feed()

if WATCHDOG_ENABLE == True:
    print("Enabling Watchdog")
    wdt = machine.WDT(timeout=8300)
uid = machine.unique_id()
uid = '{:02x}{:02x}'.format(uid[2],uid[3])
fp_mqtt_sensor = None

while True:
    voltage = get_vbatt()
    gc.collect()
    sprint("Memory free: {}".format(gc.mem_free()))
    if connect_wifi()==False:
        sprint("Unable to connect to Wi-Fi - Sleeping")
        my_sleep()
        continue
    
    if fp_mqtt_sensor == None:
        #Setup the MQTT client sensor for HASS for fp_thermo and unique id
        sprint("Setting up MQTT client")
        try:
            fp_mqtt_sensor = FP2MQTT_Sensor("fp_thermo", uid)
        except Exception as e:
            sprint("Failed to connect MQTT: {}".format(e))
            disconnect_wifi()
            my_sleep()
            continue
        fp_mqtt_sensor.add_temperature()
        fp_mqtt_sensor.add_battery()
        sprint("Sensors setup and added")

    try:
        reading = get_temperature()
        if(reading==None):
            sprint("Reading failed on sensor")
            reading = 0.0
        else:
            sprint("Temperature: {}".format(reading))
    except Exception as e:
        sprint("Reading failed on sensor {}".format(e))
        reading = 0.0

    fp_mqtt_sensor.publish_state(reading, voltage)
    time.sleep(1)
    if WATCHDOG_ENABLE == True:
        wdt.feed()
    disconnect_wifi()
    my_sleep()
