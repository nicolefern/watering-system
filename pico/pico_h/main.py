import time
from pump import *

ws_name = "Inside Plants"
ver = "1.0"

def main():
    # Set localtime based on set_localtime.txt file
    #tf = open("localtime.txt", "r")
    #time_string = tf.read()
    #time_tuple = [ int(s) for s in time_string.split(",") ]
    #rtc = machine.RTC()
    #rtc.datetime(time_tuple)
    
    # Set up watering system
    ws = WateringSystem(ws_name, "inside-plants-config.json")
    while True:
        print(time.localtime())
        ws.check_schedule(time.localtime())
        time.sleep(30)
        
main()