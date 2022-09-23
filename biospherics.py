#!/usr/bin/python

import io
import sys
import fcntl
import time
import copy
import string
import thingspeak
import adafruit_scd30
import board
i2c = board.I2C() # uses board.SCL and board.SDA
scd = adafruit_scd30.SCD30(i2c)

from AtlasI2C import (
	 AtlasI2C
)

channel_id = 1406461 # PUT CHANNEL ID HERE
api_key  = 'HQ4AHFTZ028GR5TC' # PUT YOUR WRITE KEY HERE
channel = thingspeak.Channel(id= channel_id, api_key=api_key) 
alist = [0, 0, 0]

def print_devices(device_list, device):
    for i in device_list:
        if(i == device):
            print("--> " + i.get_device_info())
        else:
            print(" - " + i.get_device_info())
    #print("")

def get_devices():
    device = AtlasI2C()
    device_address_list = device.list_i2c_devices()
    device_list = []

    for i in device_address_list:
        device.set_i2c_address(i)
        response = device.query("i")
        
        # check if the device is an EZO device
        checkEzo = response.split(",")
        if len(checkEzo) > 0:
            if checkEzo[0].endswith("?I"):
                # yes - this is an EZO device
                moduletype = checkEzo[1]
                response = device.query("name,?").split(",")[1]
                device_list.append(AtlasI2C(address = i, moduletype = moduletype, name = response))
    return device_list

def print_help_text():
    print('''
>> Atlas Scientific I2C Code
>> Any commands entered are passed to the default target device via I2C except:
  - Help
      brings up this menu
  - List
      lists the available I2C circuits.
      the --> indicates the target device that will receive individual commands
  - xxx:[command]
      sends the command to the device at I2C address xxx
      and sets future communications to that address
      Ex: "102:status" will send the command status to address 102
  - all:[command]
      sends the command to all devices
  - Poll[,x.xx]
      command continuously polls all devices
      the optional argument [,x.xx] lets you set a polling time
      where x.xx is greater than the minimum %0.2f second timeout.
      by default it will poll every %0.2f seconds
  - Calinfo
      will show a tutorial and all commands for calibration

>> Pressing ctrl-c will stop the polling
    ''' % (AtlasI2C.LONG_TIMEOUT, AtlasI2C.LONG_TIMEOUT))

def main():

    device_list = get_devices()

    if len(device_list) == 0:
        print ("No EZO devices found")
        exit()

    device = device_list[0]

    print_help_text()

    print_devices(device_list, device)

    real_raw_input = vars(__builtins__).get('raw_input', input)

    while True:

        user_cmd = real_raw_input(">> Enter command: ")

        # show all the available devices
        if user_cmd.upper().strip().startswith("LIST"):
            print_devices(device_list, device)

        # print the help text
        elif user_cmd.upper().startswith("HELP"):
            print_help_text()
        
        elif user_cmd.upper().startswith("CALINFO"):
            print('''
 >> Calibration 

Make sure to chose the correct sensor before entering the command. Entering "List" returns a sensor list with their numbers


 >> Type following commands to calibrate your pH sensor:
    - cal,mid,n : Single point calibration at midpoint
    - cal,low,n : two point calibration at lowpoint
    - cal,high,n : three point calibration at highpoint 
		- to chose the correct sensor use the number from the devices list
Example:  99: cal,mid,7.0 -> press enter
>> Type following commands to calibrate your ORP sensor:
    - cal,n : Single point calibration at midpoint
         
            ''')

        # continuous polling command automatically polls the board
        elif user_cmd.upper().strip().startswith("POLL"):
            cmd_list = user_cmd.split(',')
            if len(cmd_list) > 1:
                delaytime = float(cmd_list[1])
            else:
                delaytime = device.long_timeout

            # check for polling time being too short, change it to the minimum timeout if too short
            if delaytime < device.long_timeout:
                print("Polling time is shorter than timeout, setting polling time to %0.2f" % device.long_timeout)
                delaytime = device.long_timeout
            try:
                while True:
                    print("-------press ctrl-c to stop the polling")
                    for dev in device_list:
                        dev.write("R")
                         
                    time.sleep(delaytime)
                            
                                          
                    for i, dev in enumerate(device_list):
                        raw = dev.read().split(':')[1].strip()
                        raw_prep = raw.rstrip('\x00')
                        raw_float = float(raw_prep)
                        if i == 0:
                            alist[0] = raw_float                           
                        if i == 1: 
                            alist[1] = raw_float
                                              
                    CO2 = str(scd.CO2)
                    print("Success CO2 :" + CO2 + "ppm")
                    Temp = str(scd.temperature)
                    print("Success Temperature  :" + Temp + "C°" )
                    Hum = str(scd.relative_humidity).strip('.')
                    print("Success Humidity :" + Hum + " % " + "rel" )
                    print("Success ORP :" + str(alist[0]) )
                    print("Success pH :" + str(alist[1]) )
                    channel.update({ 'field1': alist[0],'field2': alist[1], 'field3': scd.CO2, 'field4': scd.temperature,'field5': scd.relative_humidity})               

                        

            except KeyboardInterrupt:       # catches the ctrl-c command, which breaks the loop above
                print("Continuous polling stopped")
                print_devices(device_list, device)

        # send a command to all the available devices
        elif user_cmd.upper().strip().startswith("ALL:"):
            cmd_list = user_cmd.split(":")
            for dev in device_list:
                dev.write(cmd_list[1])

            # figure out how long to wait before reading the response
            timeout = device_list[0].get_command_timeout(cmd_list[1].strip())
            # if we dont have a timeout, dont try to read, since it means we issued a sleep command
            if(timeout):
                time.sleep(timeout)
                for dev in device_list:
                    print(dev.read())

        # if not a special keyword, see if we change the address, and communicate with that device
        else:
            try:
                cmd_list = user_cmd.split(":")
                if(len(cmd_list) > 1):
                    addr = cmd_list[0]

                    # go through the devices to figure out if its available
                    # and swith to it if it is
                    switched = False
                    for i in device_list:
                        if(i.address == int(addr)):
                            device = i
                            switched = True
                    if(switched):
                        print(device.query(cmd_list[1]))
                    else:
                        print("No device found at address " + addr)
                else:
                    # if no address change, just send the command to the device
                    print(device.query(user_cmd))
            except IOError:
                print("Query failed \n - Address may be invalid, use list command to see available addresses")


if __name__ == '__main__':
    main()