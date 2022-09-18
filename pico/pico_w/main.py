import network
import socket
import time
import re
import uasyncio as asyncio

from pump import *

ws_name = "Inside Plants"
ver = "1.0"
PORT = 31415
wlan = network.WLAN(network.STA_IF)
# Set up watering system
ws = WateringSystem(ws_name, "config.json")

def connect_to_network(max_wait=10):
    wlan.active(True)
    #wlan.config(pm = 0xa11140) # Disable power-save mode
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
        raise RuntimeError('network connection failed')
    else:
        print('connected')
        status = wlan.ifconfig()
        print('ip = ' + status[0])
        
    return wlan

async def serve_client(reader, writer):
    print("Client connected")
    bf = open("banner.txt", "r")
    banner = bf.read()
    writer.write(banner)
    
    #writer.write("*************************************************************\n")
    #writer.write("****  Hello from the Pi Pico Automated Watering System   ****\n")
    #writer.write("*************************************************************\n")
    
    writer.write("\n\nWelcome to version {}!\nWatering System Name: {}".format(ver, ws_name))
    
    # Command loop
    while(True):
        writer.write("\n\nEnter a command (type \"help\" for list of valid commands):\n")
        command_line = await reader.readline()
        command = command_line.decode().rstrip()
        
        m_water = re.match(r"water (\w+)(\s([0-9.]+))*", command)
        m_update_config = re.match(r"update_config (.*)", command)
        
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
        elif command == "help":
            writer.write("The following commands are valid: \n")
            writer.write("  water <domain> [duration]   : water a domain\n")
            writer.write("  info                        : print info about watering system configuration\n")
            writer.write("  print_config                : print json configuration file\n")
            writer.write("  update_config <json string> : update json configuration file\n")
            writer.write("  quit                        : close the connection\n")
            writer.write("  help                        : list valid commands\n")
        elif command == "quit":
            break
        else:
            writer.write("Invalid command, try again\n")

    await writer.drain()
    await writer.wait_closed()
    print("Client disconnected")


async def main():    
    print('Connecting to Network...')
    wlan = connect_to_network()

    print('Setting up socket...')
    asyncio.create_task(asyncio.start_server(serve_client, "0.0.0.0", PORT))
    while True:
        print("heartbeat")
        await asyncio.sleep(5)
        
try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()