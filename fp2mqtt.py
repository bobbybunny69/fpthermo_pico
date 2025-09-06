"""
MQTT sensor:  publish the Pico Brew device on HASS with all sensors, buttons and controllers (thermos?) 
"""
from json import dumps
from umqtt.simple import MQTTClient
from secret import mqtt
from log import sprint


class FP2MQTT_Sensor:
    def __init__(self, device_name, uid):
        self.dev_name = device_name + '_' + uid
        sprint("Creating FP2MQTT device class for device_name and uid: {}".format(self.dev_name))
        self.device_cfg = {
                    "identifiers": self.dev_name,
                    "name": "Fishpond Thermo",
                    "model": "Raspbery Pico",
                    "sw": "0.3",
                    "manufacturer": "Robby" 
                    }
        self.state_topic = "homeassistant/sensor/"+self.dev_name+"/state"
        self.availability_topic = "homeassistant/sensor/"+self.dev_name+"/availability"
                
        self.client = MQTTClient(self.dev_name, mqtt['server'])
        self.client.set_last_will(self.availability_topic, 'offline')
        
        result =  self.client.connect()
        sprint('MQTT connect to server result: {}'.format(result))

    def disconnect(self):
        sprint('Disconnecting MQTT client...')
        self.client.publish(self.availability_topic, 'offline')
        self.client.disconnect()

    def reconnect_client(self):
        try:
            self.client.connect()
        except OSError as e:
            raise RuntimeError('MQTT failed to re-connect to server')
        sprint('MQTT re-connected to server')

        subscribe_topic = "homeassistant/+/" + self.dev_name + "/+/set/#" 
        sprint("re-subscribing : {}".format(subscribe_topic)) # commands for thermo from HA
        self.client.subscribe(subscribe_topic)   # subscribe to commands for thermo from HA
 
    def add_temperature(self):
        u_id = "temp_" + self.dev_name
        config_payload = {
                "name": "Temperature",
                "device_class": "temperature",
                "unit_of_measurement": "°C",
                "value_template": "{{ value_json.temperature }}",
                "state_topic": self.state_topic,
                "availability_topic": self.availability_topic,
                "unique_id": u_id,
                "device": self.device_cfg,
                }
        config_topic = "homeassistant/sensor/" + u_id + "/config"
        sprint("Topic: {}".format(config_topic))
        sprint("Payload: {}".format(dumps(config_payload)))
        self.client.publish(config_topic, bytes(dumps(config_payload), 'utf-8'), retain=True)

    def add_battery(self):
        u_id = "batt_" + self.dev_name
        config_payload = {
                "name": "Battery",
                "device_class": "voltage",
                "unit_of_measurement": "V",
                "value_template": "{{ value_json.battery }}",
                "state_topic": self.state_topic,
                "availability_topic": self.availability_topic,
                "unique_id": u_id,
                "device": self.device_cfg,
                }
        config_topic = "homeassistant/sensor/" + u_id + "/config"
        sprint("Topic: {}".format(config_topic))
        sprint("Payload: {}".format(dumps(config_payload)))
        self.client.publish(config_topic, bytes(dumps(config_payload), 'utf-8'))

    def publish_state(self, temperature, vbatt):
        payload = {
            "temperature": "{:.1f}".format(temperature),
            "battery": "{:.2f}".format(vbatt), 
            }
        sprint("Topic: {}".format(self.state_topic))
        sprint("Payload: {}".format((payload)))
        self.client.publish(self.availability_topic, 'online')
        self.client.publish(self.state_topic, bytes(dumps(payload), 'utf-8'))
