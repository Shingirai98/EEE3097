#!/bin/bash

# set envirmonetal variable for apache path 
export smart_alarm_path=/home/pi/smart_alarm/smart_alarm

# activate alternative GIPO function ALT5 for gpio18 which
# is pwm1 and enables rpi-zero audio
gpio_alt -p 18 -f 5

# run smart_alarm main script
python $smart_alarm_path/smart_alarm.py &

# change rights of data.xml to make it editable
sudo chmod o+w $smart_alarm_path/data.xml

# start pigpio deamon to enable changing gpio functions via python
#sudo pigpiod
