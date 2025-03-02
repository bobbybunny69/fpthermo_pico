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

DS18B20_PIN = machine.Pin(20)
PWR_PIN = machine.Pin(22, machine.Pin.OUT)
WIFI_RETRIES= DS18B20_RETRIES = 10
SLEEP_MINS = 10
PWR_BANK_SECS = 15  #  Make sure a factor of 60 secs
PWR_BANK_PULSE_SECS = 0.5
PWR_BANK_PIN = machine.Pin(15, machine.Pin.OUT)
LED_PIN = machine.Pin("LED", machine.Pin.OUT)

def my_sleep() -> None:
    sprint("Entering sleep for {} minutes".format(SLEEP_MINS))
    count = SLEEP_MINS*60 / PWR_BANK_SECS
    while count > 0:
        sprint("Counting down: {}".format(count))
        count -= 1
        time.sleep(PWR_BANK_SECS - PWR_BANK_PULSE_SECS)
        
        PWR_BANK_PIN.on()
        LED_PIN.on()
        time.sleep(PWR_BANK_PULSE_SECS)
        LED_PIN.off()
        PWR_BANK_PIN.off()

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

def connect_wifi(wlan) -> bool:
    # Connect to WiFi
    wlan.connect(wifi['ssid'], wifi['pw'])
    for i in range(0,WIFI_RETRIES):
        LED_PIN.on()
        time.sleep(0.1)
        sprint('Waiting for connection...')
        LED_PIN.off()
        time.sleep(0.8)
        if wlan.isconnected():
            ip_addr = wlan.ifconfig()[0]
            sprint("Connected to Wi-Fi. My IP Address: {}".format(ip_addr))
            break
    return wlan.isconnected()

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
uid = machine.unique_id()
uid = '{:02x}{:02x}'.format(uid[2],uid[3])
fp_mqtt_sensor = None

while True:
    if wlan.isconnected() == False:
        sprint("No connection to Wi-Fi - retrying")
        if connect_wifi(wlan)==False:
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
            wlan.disconnect()
            my_sleep()
            continue
        fp_mqtt_sensor.add_temperature()
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

    fp_mqtt_sensor.publish_state(reading)
    my_sleep()
