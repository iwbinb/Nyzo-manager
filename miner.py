#!/usr/bin/env python
"""
MIT License

Copyright (c) 2018 Ortis (cao.ortis.org@gmail.com)

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import paramiko
import re
import logging
import time


class MinerConfig:
	def __init__(self, miner_id, host, user, password=None, private_key_path=None, start_command=None, stop_command=None, log_command=None):
		self.miner_id = miner_id
		self.host = host
		self.user = user
		self.password = password
		self.private_key_path = private_key_path
		self.start_command = start_command
		self.stop_command = stop_command
		self.log_command = log_command

	def build(self):
		return Miner(self)


class Miner:

	TOP_CPU_LOAD_SEPARATOR = re.compile("%|( )")
	CMD_TIMEOUT = 20  # timeout in seconds

	def __init__(self, config, log=None):

		self.config = config
		self.miner_id = config.miner_id
		self.host = config.host
		self.user = config.user
		self.password = config.password
		self.private_key_path = config.private_key_path
		self.start_command = config.start_command
		self.stop_command = config.stop_command
		self.log_command = config.log_command

		if log is None:
			self.log = logging.getLogger(self.miner_id)
		else:
			self.log = log

	def start(self):
		ssh_session = Miner.__ssh_connect(host=self.host, username=self.user, password=self.password, prv_key_file=self.private_key_path, log=self.log)

		# don't start multiple instance
		if len(self.__parse_pids(ssh_session)) > 0:
			return True

		self.log.info("Starting")
		ssh_session.exec_command(self.start_command, timeout=Miner.CMD_TIMEOUT)
		time.sleep(3)  # let the process spawn
		success = len(self.__parse_pids(ssh_session)) > 0
		ssh_session.close()
		return success

	def stop(self):
		ssh_session = Miner.__ssh_connect(host=self.host, username=self.user, password=self.password, prv_key_file=self.private_key_path, log=self.log)

		if self.stop_command is None:
			self.log.info("Stopping with Kill Command (Deal 3 damage. If you have a Beast, deal 5 damage instead.)")
			# get mochimo pids and kill them all !
			pids = self.__parse_pids(ssh_session)
			kill_command = "date"
			for pid in pids:
				kill_command += " && kill "+pid
			ssh_session.exec_command(kill_command)
		else:
			self.log.info("Stopping")
			ssh_session.exec_command(self.stop_command)

		time.sleep(3)  # let the process vanish
		success = len(self.__parse_pids(ssh_session)) == 0
		ssh_session.close()
		return success

	def state(self):
		ssh_session = Miner.__ssh_connect(host=self.host, username=self.user, password=self.password, prv_key_file=self.private_key_path, log=self.log)
		stdin, stdout, stderr = ssh_session.exec_command("ps faux | grep mochi", timeout=Miner.CMD_TIMEOUT)
		stderr_str = stderr.read().decode("utf-8")
		state = "Unknown"

		if len(stderr_str) > 0:
			self.log.warning("Error while parsing processes: " + stderr_str)
		else:
			stdout_str = stdout.read().decode("utf-8")

			if len(stdout_str.splitlines()) > 0:
				state = "Running"
			else:
				state = "Stopped"

		ssh_session.close()
		return state

	def statistics(self):
		ssh_session = Miner.__ssh_connect(host=self.host, username=self.user, password=self.password, prv_key_file=self.private_key_path, log=self.log)
		report = {}

		# parse cpu load
		stdin, stdout, stderr = ssh_session.exec_command("top -bcn1", timeout=Miner.CMD_TIMEOUT)
		# stdin, stdout, stderr = ssh_session.exec_command("top -c -b -n 1")
		stderr_str = stderr.read().decode("utf-8")

		if len(stderr_str) > 0:
			report["error_cpu_load"] = stderr_str
			self.log.warning("Error while parsing cpu load: " + report["error_cpu_load"])
		else:
			stdout_str = stdout.read().decode("utf-8")
			for process in stdout_str.splitlines():

				if "Cpu(s): " in process:
					buffer = process[8:].split(",")
					load = 0
					for b in buffer:
						if "id" in b:
							continue
						# bb = b.split('%')
						bb = Miner.TOP_CPU_LOAD_SEPARATOR.split(b.strip())
						load += float(bb[0].strip())

					report["cpu"] = float(round(load, 2))

		# parse process with ps faux because top have different behavior across plateform
		stdin, stdout, stderr = ssh_session.exec_command("ps faux | grep mochi")
		stderr_str = stderr.read().decode("utf-8")

		if len(stderr_str) > 0:
			report["error_processes"] = stderr_str
			self.log.warning("Error while parsing processes: " + report["error_processes"])
		else:
			stdout_str = stdout.read().decode("utf-8")
			report["process"] = []
			for process in stdout_str.splitlines():
				if " grep " in process:
					continue
				elif "gomochi" in process:
					report["process"].append("gomochi")
				else:
					buffer = process.split("mochimo ")
					if len(buffer) > 1:
						report["process"].append(str(buffer[1]).strip())

		report["process"].sort()
		report["gomochi"] = False
		report["listen"] = False
		report["solving"] = False

		for process in report["process"]:
			if process == "gomochi":
				report["gomochi"] = True
			elif "listen" in process:
				report["listen"] = True
			elif "solving" in process:
				report["solving"] = True

		if self.log_command is not None:
			# parse log
			stdin, stdout, stderr = ssh_session.exec_command(self.log_command, timeout=Miner.CMD_TIMEOUT)
			stderr_str = stderr.read().decode("utf-8")
			if len(stderr_str) > 0:
				report["error_logs"] = stderr_str
				self.log.warning("Error while parsing logs: " + report["error_logs"])
			else:
				stdout_str = stdout.read().decode("utf-8")
				for log in stdout_str.splitlines():
					log = re.sub(' +', ' ', log)  # remove consecutive space
					if "Haiku/second:" in log:
						buffer = log.split()
						for i in range(0, len(buffer)-1, 2):
							report[buffer[i][:-1]] = buffer[i+1]
					elif ": 0x" in log:
						buffer = log.split(": 0x")
						buffer = buffer[1].split()[0]
						report["Block"] = "0x"+buffer


		ssh_session.close()
		return report

	def __parse_pids(self, ssh_session=None):

		if ssh_session is None:
			ssh_session = Miner.__ssh_connect(host=self.host, username=self.user, password=self.password,  prv_key_file=self.private_key_path, log=self.log)

		stdin, stdout, stderr = ssh_session.exec_command("ps faux | grep mochi")
		stderr_str = stderr.read().decode("utf-8")
		if len(stderr_str) > 0:
			raise Exception(stderr_str)

		pids = []
		stdout_str = stdout.read().decode("utf-8")
		for process in stdout_str.splitlines():
			if " grep " in process:
				continue
			buffer = process.split()
			pids.append(buffer[1].strip())

		return pids

	@staticmethod
	def __ssh_connect(host, username, password=None, prv_key_file=None, log=None):

		ssh_session = paramiko.SSHClient()
		ssh_session.set_missing_host_key_policy(paramiko.AutoAddPolicy())

		if prv_key_file is None:
			if log is not None:
				log.debug("Connecting to " + host + " using password...")

			port = 22
			if ":" in host:
				buffer = host.split(':')
				host = buffer[0]
				port = int(buffer[1])

			ssh_session.connect(hostname=host, port=port, username=username, password=password)

		else:
			if log is not None:
				log.debug("Connecting to " + host + " using private key...")
			pk = paramiko.RSAKey.from_private_key_file(prv_key_file)
			ssh_session.connect(hostname=host, username=username, pkey=pk)

		if log is not None:
			log.debug("Connected")

		return ssh_session

