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
from random import random

DS18B20_PIN = machine.Pin(20)
WIFI_RETRIES= DS18B20_RETRIES = 10
SLEEP_MINS = 1
LED_PIN = machine.Pin("LED", machine.Pin.OUT)

def my_sleep() -> None:
    sprint("Entering sleep for {} minutes".format(SLEEP_MINS))
    time.sleep(SLEEP_MINS*60)

def get_temperature() -> None | float:
    #Setup the DS18B20 data line and read ROMS
    return random()*50
    ow = OneWire(DS18B20_PIN)
    ow.reset()
    bus = DS18X20(ow)
    for i in range(0,DS18B20_RETRIES):
        roms = bus.scan()
        if len(roms) > 0:
            break
        time.sleep(0.1)
    assert len(roms) == 1, "Not (only) one sensor on the bus"

    bus.convert_temp()
    time.sleep(1)
    reading = bus.read_temp(roms[0])
    if(reading==None):
        sprint("Bad CRC reading sensor")
    elif(reading>50.0): 
        sprint("Suspiscous reading on sensor")
        reading = None
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

try:
    while True:
        try:
            reading = get_temperature()
            if(reading==None):
                sprint("Reading failed on sensor")
            else:
                sprint("Temperature: {}".format(reading))
        except Exception as e:
            sprint("Reading failed on sensor {}".format(e))
            my_sleep()
            continue

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

        fp_mqtt_sensor.publish_state(reading)
        my_sleep()

finally:
    sprint("Exception... finishing")
    if fp_mqtt_sensor != None:
        fp_mqtt_sensor.disconnect()
