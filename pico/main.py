import network
import socket
import time
import re
import uasyncio as asyncio
from machine import UART, Pin, RTC

from pump import *

#ws_name = "Inside Plants ya"
ver = "2.0"
PORT = 31415

# Set up watering system
ws = WateringSystem("config.json")
rtc = machine.RTC()
        
def set_time_from_file():
    # Set localtime based on set_localtime.txt file
    if exists("localtime.txt"):
        tf = open("localtime.txt", "r")
        time_string = tf.read()
        time_tuple = [ int(s) for s in time_string.split(",") ]
        rtc.datetime(time_tuple)
        print("Set localtime from file: " + time_str())
        tf.close()
        
async def save_time_to_file():
    while(True):
        # Save current localtime to file every 5 minutes or so
        tf = open("localtime.txt", "w")
        tf.write(", ".join([str(i) for i in rtc.datetime()]))
        tf.close()
        print("Saved localtime to file: " + time_str())
        await asyncio.sleep(300)
        
def time_str():
    '''
    Tuple format: (year, month, mday, hour, minute, second, weekday, yearday)
    '''
    (year, month, mday, hour, minute, second, weekday, yearday) = time.localtime()
    return "{} {} {}, {} {}:{}".format(number2weekday[weekday], number2month[month], mday, year, hour, minute)
        
def print_banner(writer):
    bf = open("banner.txt", "r")
    banner = bf.read()
    writer.write(banner)
    
    intro_str =  "\n\nWelcome to version {}!\n".format(ver)
    intro_str += "Watering System Name: {}\n".format(ws.name)
    intro_str += "Current Time: " + time_str() + "\n\n"
    intro_str += "Enter a command (type \"help\" for list of valid commands):\n"
    writer.write(intro_str)
    #writer.write("\n\nWelcome to version {}!\nWatering System Name: {}\n\nEnter a command (type \"help\" for list of valid commands):\n".format(ver, ws_name))
    
    
def process_command(command, writer):
    print(command)
    m_water = re.match(r"water (\w+)(\s([0-9.]+))*", command)
    m_update_config = re.match(r"update_config (.*)", command)
    m_update_time = re.match(r"update_time ([0-9]+)/([0-9]+)/([0-9]+) ([0-9]+):([0-9]+)", command)
    
    if m_water:
        domain_name = m_water.group(1)
        if m_water.group(3):
            duration = float(m_water.group(3))
            if (duration <= 0) or (duration > 60):
                writer.write("Error: watering duration must be between 0 and 60 seconds\n")
            else:
                status = ws.water_domain(domain_name, duration)
                writer.write(status + "\n")
        else:        
            status = ws.water_domain(domain_name)
            writer.write(status + "\n")
    elif command == "info":
        writer.write(ws.print_info())
    elif command == "print_config":
        writer.write(ws.print_config() + "\n")
    elif m_update_config:
        json_str = m_update_config.group(1)
        status = ws.update_config(json_str)
        writer.write(status + "\n")
    elif command == "print_time":
        writer.write("Current Time: " + time_str() + "\n\n")
    elif m_update_time:
        month   = int(m_update_time.group(1))
        mday    = int(m_update_time.group(2))
        year    = int(m_update_time.group(3))
        hour    = int(m_update_time.group(4))
        minute  = int(m_update_time.group(5))
        rtc.datetime((year, month, mday, 0, hour, minute, 0, 0))
        writer.write("Time updated to: " + time_str() + "\n\n")
    elif command == "help":
        help_str = "The following commands are valid: \n"
        help_str += "  water <domain> [duration]    : water a domain\n"
        help_str += "  info                         : print info about watering system configuration\n"
        help_str += "  print_config                 : print json configuration file\n"
        help_str += "  update_config <json string>  : update json configuration file\n"
        help_str += "  print_time                   : print the current local date and time\n"
        help_str += "  update_time MM/DD/YYYY HH:MM : update the local date and time\n"
        help_str += "  quit                         : close the connection\n"
        help_str += "  help                         : list valid commands\n"
        writer.write(help_str)
    elif command == "quit":
        return 1
    else:
        writer.write("Invalid command, try again\n")
    return 0

def connect_to_network(wlan, max_wait=10):
    wlan.active(True)
    wlan.config(pm = 0xa11140) # Disable power-save mode
    with open("wifi_config.json", "r") as f:
        data = json.load(f)
        ssid = data["ssid"]
        password = data["password"]
    wlan.connect(ssid, password)

    while max_wait > 0:
        if wlan.status() < 0 or wlan.status() >= 3:
            break
        max_wait -= 1
        print('waiting for connection...')
        time.sleep(1)

    if wlan.status() != 3:
        #raise RuntimeError('network connection failed')
        return None
    else:
        print('connected')
        status = wlan.ifconfig()
        print('ip = ' + status[0])
        
    return wlan

async def uart_term(uart):
    print_banner(uart)
 
    while(True):
        nchars = uart.any()
        while nchars == 0:
            await asyncio.sleep(.2)
            nchars = uart.any()
            
        # Continue reading characters until a newline
        command_line = ""
        while ("\r" not in command_line) and ("\n" not in command_line):
            rdata = uart.read()
            if rdata:
                command_line += rdata.decode()
            await asyncio.sleep(.2)

        if command_line:
            command = command_line.rstrip()
            uart.write(command + "\n")
            process_command(command, uart)
                
            
async def serve_client(reader, writer):
    print("Client connected")
    print_banner(writer)
    
    # Command loop
    while(True):
        command_line = await reader.readline()
        command = command_line.decode().rstrip()
        stop = process_command(command, writer)
        if stop:
            break

    await writer.drain()
    await writer.wait_closed()
    print("Client disconnected")

async def main():
    
    #Set the localtime from file
    set_time_from_file()
    
    if hasattr(network, "WLAN"):
        print("I'm a pico w!")
        wlan = network.WLAN(network.STA_IF)
        print('Connecting to Network...')
        ret = None
        while ret == None:
            ret = connect_to_network(wlan, 60)
        
        print('Setting up socket...')
        asyncio.create_task(asyncio.start_server(serve_client, "0.0.0.0", PORT))

    
    print('Setting up uart...')
    uart1 = UART(1, baudrate=9600, tx=Pin(4), rx=Pin(5))
    asyncio.create_task(uart_term(uart1))
    
    #Launch the task that saves the current time to a file periodically
    asyncio.create_task(save_time_to_file())
    
    while True:
        print(time.localtime())
        await asyncio.sleep(5)
   
        if hasattr(network, "WLAN") and (wlan.status() != 3):
            print("Lost wifi connection, reconnecting...")
            ret = None
            while ret == None:
                ret = connect_to_network(60)   
        
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()


        