# Python3 script to check cpu load, cpu temperature and free space etc.
# on a Raspberry Pi or Ubuntu computer and publish the data to a MQTT server.
# RUN pip install paho-mqtt
# RUN sudo apt-get install python-pip

import json
import os
import socket
import subprocess
import time
from typing import Any, Dict

import paho.mqtt.client as paho

import config

# get device host name - used in mqtt topic
hostname = socket.gethostname()


def check_used_space(path):
	st = os.statvfs(path)
	free_space = st.f_bavail * st.f_frsize
	total_space = st.f_blocks * st.f_frsize
	used_space = int(100 - ((free_space / total_space) * 100))
	return used_space


def check_cpu_load():
	# bash command to get cpu load from uptime command
	p = subprocess.Popen("uptime", shell=True, stdout=subprocess.PIPE).communicate()[0]
	cores = subprocess.Popen("nproc", shell=True, stdout=subprocess.PIPE).communicate()[0]
	cpu_load = str(p).split("average:")[1].split(", ")[0].replace(' ', '').replace(',', '.')
	cpu_load = float(cpu_load) / int(cores) * 100
	return round(float(cpu_load), 1)


def check_voltage():
	try:
		full_cmd = "vcgencmd measure_volts | cut -f2 -d= | sed 's/000//'"
		voltage = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
		return voltage.strip()[:-1]
	except Exception:
		return 0


def check_swap():
	full_cmd = "free -t | awk 'NR == 3 {print $3/$2*100}'"
	swap = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
	return round(float(swap.decode("utf-8").replace(",", ".") or 0), 1)


def check_memory():
	full_cmd = "free -t | awk 'NR == 2 {print $3/$2*100}'"
	memory = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
	return round(float(memory.decode("utf-8").replace(",", ".")))


def check_cpu_temp():
	full_cmd = "cat /sys/class/thermal/thermal_zone*/temp 2> /dev/null | sed 's/\(.\)..$//' | tail -n 1"
	try:
		p = subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]
		cpu_temp = p.decode("utf-8").replace('\n', ' ').replace('\r', '')
	except Exception:
		cpu_temp = 0
	return cpu_temp


def check_sys_clock_speed():
	full_cmd = "awk '{printf (\"%0.0f\",$1/1000); }' </sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
	return subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]


def check_uptime():
	full_cmd = "awk '{print int($1/3600/24)}' /proc/uptime"
	return int(subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0])


def check_model_name():
	full_cmd = "cat /proc/cpuinfo | grep Model | sed 's/Model.*: //g'"
	return subprocess.Popen(full_cmd, shell=True, stdout=subprocess.PIPE).communicate()[0].decode("utf-8")


def publish_to_mqtt():

	data: Dict[str, Any] = {}

	# collect the monitored values
	if config.cpu_load:
		data["CPULoad"] = check_cpu_load()
	if config.cpu_temp:
		data["CPUTemperature"] = float(check_cpu_temp())
		data["TempUnit"] = "C"
	if config.used_space:
		data["UsedSpace"] = check_used_space('/')
	if config.voltage:
		data["Voltage"] = float(check_voltage())
	if config.sys_clock_speed:
		data["ClockSpeed"] = int(check_sys_clock_speed())
	if config.swap:
		data["UsedSwap"] = check_swap()
	if config.memory:
		data["UsedMemory"] = check_memory()
	if config.uptime:
		data["UptimeDays"] = check_uptime()

	values = json.dumps(data)

	# connect to mqtt server
	client = paho.Client()
	client.username_pw_set(config.mqtt_user, config.mqtt_password)
	client.connect(config.mqtt_host, int(config.mqtt_port))

	# publish monitored values to MQTT
	client.publish(config.mqtt_topic_prefix + "/" + hostname, values, qos=1)

	# disconnect from mqtt server
	client.disconnect()


if __name__ == '__main__':
	# delay the execution of the script
	time.sleep(config.random_delay)

	# Publish messages to MQTT
	publish_to_mqtt()
