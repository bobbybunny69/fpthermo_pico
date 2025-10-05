"""
Class with functions/framework for embedded low-power programs
"""
import machine
import time
from socket import socket, AF_INET, SOCK_STREAM
from network import WLAN, STA_IF

# ----------------------------------
FILENAME = "log.txt"
WIFI_RETRIES = 10
WDT_MAX_MS = 8300
# ----------------------------------

class LPFWK:
    def __init__(self, dbg_svr_ip, dbg_svr_port, dev_mode):
        self.dbg_svr_ip = dbg_svr_ip
        self.dbg_svr_port = dbg_svr_port
        self.LED = machine.Pin("LED", machine.Pin.OUT)
        self.dev_mode = dev_mode
        self.wlan = WLAN(STA_IF)
        self.socket_isconnected = False
        # Magic number => 300ms to do stuff before WDT expires
        self.timeout_ms = WDT_MAX_MS - 300
        if dev_mode == False:
            self.print("Enabling Watchdog {}".format(WDT_MAX_MS))
            self.wdt = machine.WDT(timeout=WDT_MAX_MS)
        self.print("Reason for reset: {}".format(machine.reset_cause()))
    
    def connect_wifi(self, ssid, pwd):
        """
        Connect Wi-Fi and the connect to the debeug server socket
        only returns status of Wi-Fi connection
        Debug server connections status getts managed within this class
        """
        self.wlan.active(True)
        self.wlan.connect(ssid, pwd)
        for i in range(0,WIFI_RETRIES):
            self.LED.on()
            self.sleep_ms(200)
            self.print('Waiting for connection...')
            self.LED.off()
            self.sleep_ms(800)
            if self.wlan.isconnected():
                ip_addr = self.wlan.ifconfig()[0]
                self.print("Connected to Wi-Fi. My IP Address: {}".format(ip_addr))
                try:
                    self.socket = socket(AF_INET, SOCK_STREAM)
                    self.socket.settimeout(3)
                    self.socket.connect((self.dbg_svr_ip, self.dbg_svr_port))
                except OSError:
                    self.print("Socket connect error:  is server running?")
                    return True   #  Becasue Wi-Fi is connected to get here
                self.print("Socket connected - starting CONN/ACK sequence")
                self.socket.send("CONN")
                try:
                    resp = self.socket.recv(3)
                    self.print("RESP:  {}".format(resp))
                    if resp == b'ACK':
                        self.socket_isconnected = True
                        time_sent = self.socket.recv(1025)
                        self.set_rtc(bytearray(time_sent))
                except:
                    self.print("No ACK received - timeout")
                return True   #  Becasue Wi-Fi is connected to get here
        return False
    
    def disconnect_wifi(self):
        if self.socket_isconnected:
            self.print("Closing socket...")
            self.socket.send('^A')
            self.sleep_ms(250)  # Pause to flush buffer at far end
            self.socket.close()
            self.socket_isconnected = False
        self.sleep_ms(1000)      
        self.print("Closing Wi-Fi...")
        self.wlan.disconnect()
        self.wlan.active(False)
    
    def print(self, string: str):
        """
        Timestamp then send string to socket on dbg_svr running on speckly or log to file 
        """
        rtc = machine.RTC()
        t = rtc.datetime()
        time_str = str(t[2])+'/'+str(t[1])+'/'+str(t[0])+' '+str(t[4])+':'+str(t[5])+':'+str(t[6])+' => '
        if self.dev_mode:
            print(time_str + string)
        file = open(FILENAME, 'a')
        file.write(time_str + string +'\n')
        file.close()
        if self.socket_isconnected:
            file = open(FILENAME, 'r')
            for line in file.readlines():
                self.socket.send(line)
            file.close()
            file = open(FILENAME, 'w')  # All lines sent so blank file
            file.close()

    def sleep_ms(self, sleep_ms):
        if self.dev_mode == False:
            self.wdt.feed()
            while sleep_ms > 0:
                if sleep_ms >= self.timeout_ms:
                    time.sleep_ms(self.timeout_ms)
                    sleep_ms -= self.timeout_ms
                else:
                    time.sleep_ms(sleep_ms)
                    sleep_ms = 0
                self.wdt.feed()
        else:
            time.sleep_ms(sleep_ms)
            
    def deep_sleep(self, sleep_secs):
        sleep_ms = sleep_secs * 1000
        if self.dev_mode == False:
            self.print("Sleeping for {} minutes".format(sleep_secs))
            self.wlan.deinit()   # Need to deactivate WF to get into low-power state
            self.wdt.feed()
            while sleep_ms > 0:
                if sleep_ms >= self.timeout_ms:
                    machine.lightsleep(self.timeout_ms)
                    sleep_ms -= self.timeout_ms
                else:
                    machine.lightsleep(sleep_ms)
                    sleep_ms = 0
                self.wdt.feed()
        else:
            self.print("Dev mode so sleep for 1 minute")
            time.sleep_ms(60000)

    def set_rtc(self, time_bytes:bytearray):
        """ RTC is sent on initial connection and uses 2 bytes per feild (big endian):
            YYYY, MM, DD, DOW, HH, MM, SS"""
        time_list = []
        for i in range(7):
            time_list.append(int(time_bytes[i*2]*256+time_bytes[i*2+1]))
        time_list.append(0)
        time_tuple = tuple(time_list)
        self.print("Setting RTC => {}".format(time_tuple))
        rtc=machine.RTC()
        rtc.datetime(time_tuple)

        
