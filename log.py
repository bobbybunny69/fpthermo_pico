"""
Logging function
"""
import machine

def sprint(string: str):
    rtc = machine.RTC()
    t = rtc.datetime()
    time_str = str(t[2])+'-'+str(t[1])+'-'+str(t[0])+' '+str(t[4])+':'+str(t[5])+':'+str(t[6])+' => '
    #f = open("log.txt", 'a')
    print(time_str + string)
    #f.write(time_str + string +'\n')
    #f.close()
