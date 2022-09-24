from machine import Pin
import time
import json
import os

number2weekday = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
weekday2number = {"MON": 0, "TUE": 1, "WED": 2, "THU": 3, "FRI": 4, "SAT": 5, "SUN": 6}

# Utility functions for filesystem
def exists(filename):
    """Check if file exists in current directory"""
    for (fname, t, inode, sz) in os.ilistdir("."):
        if fname == filename:
            return True
    return False

def file_copy(infilename, outfilename):
    """Copy input file to output file"""
    outfile = open(outfilename, "w")
    infile = open(infilename, "r")
    contents = infile.read()
    outfile.write(contents)
    outfile.close()
    infile.close()

class WateringSystem:
    def __init__(self, name, configfile=None):
        self.name = name
        if configfile:
            self.read_configfile(configfile)
        else:
            self.configfile = None
            print("Watering system \"{}\" initialized without configuration file.".format(name))
        

    def read_configfile(self, configfile):
        print("Loading configuration file {}...".format(configfile))
        with open(configfile, "r") as f:
            self.config_data = self.get_config(json.load(f))
            if self.config_data:
                print("Succesfully loaded configuration file")
                self.configfile = configfile
            else:
                self.configfile = None
                print("Error loading configuration file.")

    def get_config(self, config_data):
        """Read configuration from dictionary pulled from json file or string
           and update the class members if succesful"""
        try:
            domains = dict()
            # Mode is either network or local
            mode = config_data["mode"]
            if not (mode == "network" or mode == "local"):
                print("Error: Invalid mode (please choose \"local\" or \"network\")")
                return None
            # Get domain information
            for d in config_data["domains"]:
                domains[d["name"]] = Domain(d["name"], d["gpio"], d["duration"])
                # Check if there is a schedule associated with the domain
                if "schedule" in d:
                    schd = d["schedule"]                        
                    ret = domains[d["name"]].add_schedule(schd)
                    if ret > 0:
                        return None
                
            # Update the class members
            self.domains = domains
            self.mode = mode
            return config_data
        
        except:
            return None
            
    def water_domain(self, name, duration=None):
        if name in self.domains:
            ret_str = self.domains[name].water(duration)
            #ret_str = "Watered domain {}".format(name)
        else:
            ret_str = "There is no domain \"{}\" defined in the watering system".format(name)
        
        print(ret_str)
        return ret_str
    
    def check_schedule(self, curr_dt):
        """Provided the current date and time from time.localtime(), check the schedule for all domains and water"""
        for d in self.domains.values():
            ret_str = d.check_schedule(curr_dt)
            print(ret_str)
                
    def print_info(self):
        """Print information about the watering domains and return the string"""
        s = "Name: {}\n".format(self.name)
        if self.configfile:
            s += "Configuration file: {}\n".format(self.configfile)
            s += "There are {} watering domains configured:\n".format(len(self.domains))
            for d in self.domains.values():
                s += " * Domain \"{}\" is using GPIO {} and has a watering duration of {} seconds\n".format(d.name, d.gpio, d.duration)
                if d.last_watered:
                    (year, month, mday, h, m, wday) = d.last_watered
                    s += "  * Last watered: {} {:02}-{:02}-{:04} @ {:02}:{:02}\n".format(number2weekday[wday], month, mday, year, h, m)
                if d.schd:
                    s += "  * Watering Schedule\n"
                    for (weekday, times) in d.schd.items():
                        times_formatted = ["{:02}:{:02}".format(h,m) for h, m in times]
                        s += "   * {} @ {}\n".format(weekday, ",".join(times_formatted))
                else:
                    s += "  * No watering schedule specified in configuration.\n"
        else:
            s = "Watering sytem is not configured yet.  Please run update_config.\n"
        print(s)
        return s
                
    def print_config(self):
        """Print the json configuration file and return the string"""
        if self.configfile:
            json_str = json.dumps(self.config_data)
            print(json_str)
            return json_str
        else:
            return "Watering sytem is not configured yet.  Please run update_config.\n"
        
    def update_config(self, json_string):
        """Update the config file using json_string"""
        data = self.get_config(json.loads(json_string))
        if data:
            self.config_data = data
            if self.configfile is None:
                self.configfile = "config.json"
            with open(self.configfile, "w") as f:
                json.dump(data, f)
            ret_str = "Successfully updated configuration and saved to {}".format(self.configfile)
        else:
            ret_str = "Failed to update configuration"
        
        print(ret_str)
        return ret_str
                
            
class Domain:
    def __init__(self, name, gpio, duration):
        self.name = name
        self.gpio = gpio
        self.duration = duration
        self.pump = Pin(gpio, Pin.OUT, value=0)
        self.schd = None
        self.last_watered = None
        print("Created \"{}\" domain using GPIO {}".format(name, gpio))
        
    def add_schedule(self, schd):
        """ Add schedule taken from the config file to the domain.
            Schedule is a list of dictionaries each with format { weekday => DAYOFWEEK, times => [hr:min, hr:min, ...] }
        """
        domain_schd = dict()
        for entry in schd:
            weekday = entry["weekday"]
            if weekday in weekday2number:
                domain_schd[weekday] = []
                for t in entry["times"]:
                    (h, m) = t.split(":")
                    h = int(h)
                    m = int(m)
                    if (h >= 0) and (h < 24) and (m >= 0) and (m < 60):
                        domain_schd[weekday].append((h,m))
                    else:
                        print("Error: times must be in the format hr:min where hr is between 0 and 23 and min between 0 and 59.")
                        return 1
                
            else:
                print("Error: {} is not a properly formatted day of the week".format(weekday))
                return 1
            
        self.schd = domain_schd
        return 0
    
    def check_schedule(self, curr_dt):
        """Provided the current date and time from time.localtime(), check the schedule and water"""
        if self.schd:
            (year, month, mday, h, m, s, wday, yrday) = curr_dt
            # Don't water if we already watered
            if self.last_watered:
                if (year, month, mday, h, m, wday) == self.last_watered:
                    return ""
            if number2weekday[wday] in self.schd:
                for t in self.schd[number2weekday[wday]]:
                    if t == (h, m):
                        ret_str = self.water()
                        return ret_str
        return ""
        
    def water(self, duration=None):
        self.pump.value(1)
        if duration:
            time.sleep(duration)
        else:
            time.sleep(self.duration)
        self.pump.value(0)
        
        # Record the time of watering
        (year, month, mday, h, m, s, wday, yrday) = time.localtime()
        self.last_watered = (year, month, mday, h, m, wday)
        ret_str = "Watered domain \"{}\" on {} {:02}-{:02}-{:04} @ {:02}:{:02}\n".format(self.name, number2weekday[wday], month, mday, year, h, m)
        return ret_str

    
def test_pump():
    """Test functionality of WateringSytem and Domain classes"""
    
    # Create a copy of test_config_orig.json in test_config.json
    file_copy("test_config_orig.json", "test_config.json")
    
    # If config.json exists, make a backup then restore at the end of the test
    if exists("config.json"):
        file_copy("config.json","config_orig.json")
    
    # Try handling an incorrect config file first then a correct one
    ws = WateringSystem("test error", "test_config_err.json")
    ws = WateringSystem("test", "test_config.json")
    
    # Try watering domains that exist and don't exist
    ws.water_domain("herbs")
    ws.water_domain("succulents")
    ws.water_domain("poo")
    
    # Test printing functions
    info_str = ws.print_info()
    print(info_str)
    
    config_str = ws.print_config()
    print(config_str)
    
    # Test updating with incorrect configuration then correct one
    status = ws.update_config("""{"mode": "wrong", "domains": [{"gpio": 0, "name": "herbs", "duration": 10}, {"gpio": 1, "name": "succulents", "duration": 5}]}""")
    print(status)
    
    status = ws.update_config("""{"mode": "network", "domains": [{"gpio": 0, "name": "herbs", "duration": 5}, {"gpio": 1, "name": "succulents", "duration": 2}, {"gpio": 2, "name": "bonsai", "duration": 8}]}""")
    
    info_str = ws.print_info()
    
    status = ws.water_domain("bonsai")
    print(status)
    ws.water_domain("herbs")
    ws.water_domain("succulents")
    status = ws.water_domain("poo")
    print(status)
 
    # Get rid of the modified test_config.json file
    os.remove("test_config.json")
    
    # Test creating a watering system with no config file specified
    ws1 = WateringSystem("test no config")
    ws1.update_config("""{"mode": "network", "domains": [{"gpio": 0, "name": "herbs", "duration": 5}, {"gpio": 1, "name": "succulents", "duration": 2}, {"gpio": 2, "name": "bonsai", "duration": 8}]}""")
    
    # Restore original config.json file and delete config_orig.json
    if exists("config_orig.json"):
        file_copy("config_orig.json","config.json")
        os.remove("config_orig.json")
        
def test_pump_schd():
    ws = WateringSystem("test schd", "test_config_schedule.json")
    print(ws.print_info())
    ws.water_domain("herbs")
    print(ws.print_info())
    
if __name__ == "__main__":
    test_pump()
    #test_pump_schd()