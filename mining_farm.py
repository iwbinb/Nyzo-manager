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


import sys
import argparse
import getpass
import logging
import json
import threading
import miner_statistics

from multithread_http_server import MultiThreadHttpServer
from mining_farm_http_handler import MiningFarmHTTPHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from miner import MinerConfig
from encryption import AESCipher


LOG_LEVEL = logging.INFO


# must set the log level as function so child process can be configured as well
def set_log_level(log_level=None):
	if log_level is None:
		log_level = LOG_LEVEL
	logging.basicConfig(level=log_level)
	logging.getLogger("paramiko").setLevel(logging.WARNING)


class MiningFarm:

	def __init__(self, html_repository, farm_config_path, password=None, bind="127.0.0.1:80", http_parallelism=5, stat_parallelism=2, stat_heartbeat=30, log=None):

		self.stop_requested = False

		if log is None:
			self.log = logging.getLogger("farm")
		else:
			self.log = log

		self.html_repository = html_repository
		config_file = open(farm_config_path, 'r')
		config = json.load(config_file)
		config_file.close()
		self.miners = []
		self.stat_lock = threading.Lock()
		self.cipher = None

		miner_ids = []
		for miner_config in config["miners"]:
			config = MinerConfig(miner_id=miner_config["id"], host=self.__parse_sensitive_field(miner_config, "host", password), user=self.__parse_sensitive_field(miner_config, "user", password))

			if config.miner_id in miner_ids:
				raise Exception("Miner id "+config.miner_id+" already exists")
			else:
				miner_ids.append(config.miner_id)

			config.password = self.__parse_sensitive_field(miner_config, "password", password)
			config.private_key_path = self.__parse_sensitive_field(miner_config, "privateKeyPath", password)
			config.start_command = self.__parse_sensitive_field(miner_config, "startCommand", password)
			config.stop_command = self.__parse_sensitive_field(miner_config, "stopCommand", password)
			config.log_command = self.__parse_sensitive_field(miner_config, "logCommand", password)

			miner = config.build()
			self.miners.append(miner)

		buffer = bind.split(':')
		self.host = buffer[0].strip()
		self.port = int(buffer[1].strip())
		self.http_parallelism = http_parallelism

		self.statistic_pool = miner_statistics.StatisticsProcessingPool(self, stat_parallelism, stat_heartbeat)

	def start(self):
		self.statistic_pool.start()
		self.start_server()

	def stop(self):
		self.stop_requested = True
		self.statistic_pool.stop()

	def start_server(self):
		self.log.info("Binding server to "+self.host+":"+str(self.port))
		server = MultiThreadHttpServer((self.host, self.port), self.http_parallelism, MiningFarmHTTPHandler, request_callback=self.http_handler)
		server.start()

	def get_miner(self, miner_id):
		for miner in self.miners:
			if miner.miner_id == miner_id:
				return miner
		return None

	def get_miners(self):
		copy = []
		copy.extend(self.miners)
		return copy

	def get_statistics(self, *args):
		if len(args) >= 1:
			return self.statistic_pool.get_statistics(args[0])

		farm_statistics = {}
		farm_statistics["totalHPS"] = 0
		farm_statistics["totalSolved"] = 0
		solving_count = 0
		statuses = []
		farm_statistics["farm"] = statuses

		for miner in self.miners:
			status = self.get_statistics(miner.miner_id)
			if status is None:
				continue

			if "hps" in status:
				farm_statistics["totalHPS"] += float(status["hps"])

			if "solved" in status:
				farm_statistics["totalSolved"] += int(status["solved"])

			if "solving" in status and status["solving"]:
				solving_count += 1

			statuses.append(status)

		if len(statuses) > 0:
			farm_statistics["solvingRate"] = 100 * float(solving_count / len(statuses))
		else:
			farm_statistics["solvingRate"] = 0

		return farm_statistics

	def clear_statistics(self, miner_id):
		self.statistic_pool.init_statistics(miner_id)

	def http_handler(self, http_request):

		url = urlparse(http_request.path)

		if len(url.path) <= 1:
			http_request.send_response(301)
			http_request.send_header('Location', "/dashboard.html?refresh=10000")
			http_request.end_headers()
		elif url.path.upper().endswith(".HTML"):
			html_page = Path(MINING_FARM.html_repository + url.path)
			if html_page.is_file():
				self.log.info("Serving HTML page " + str(html_page.absolute()))
				http_request.send_response(200)
				http_request.send_header('Content-type', 'text/html')
				http_request.end_headers()
				http_request.wfile.write(html_page.absolute().read_bytes())
			else:
				self.log.info("HTML file " + url.path + " not found")
				http_request.send_response(404)
		elif url.path.upper() == "/STATUS":
			http_request.send_response(200)
			http_request.send_header('Content-type', 'application/json')
			http_request.end_headers()
			farm_statistics = self.get_statistics()
			http_request.wfile.write(bytes(json.dumps(farm_statistics, indent=4), "utf-8"))
		elif url.path.upper() == "/MINER":
			miner_id = MiningFarm.__get_parameter(url.query, 'id')
			miner = self.get_miner(miner_id)

			if miner is None:
				http_request.send_response(400)
				http_request.send_header('Content-type', 'application/json')
				http_request.end_headers()
				http_request.wfile.write(bytes("{\"error\": \"Miner not found\"}", "utf-8"))
			else:
				http_request.send_response(200)
				http_request.send_header('Content-type', 'application/json')
				http_request.end_headers()
				statistics = self.get_statistics(miner.miner_id)
				http_request.wfile.write(bytes(json.dumps(statistics, indent=4), "utf-8"))
		elif url.path.upper() == "/COMMAND":
			miner_id = MiningFarm.__get_parameter(url.query, 'id')
			miner = self.get_miner(miner_id)

			if miner is None:
				http_request.send_response(400)
				http_request.send_header('Content-type', 'application/json')
				http_request.end_headers()
				http_request.wfile.write(bytes("{\"error\": \"Miner not found\"}", "utf-8"))
			else:
				command = MiningFarm.__get_parameter(url.query, 'cmd')
				if command is None:
					http_request.send_response(400)
					http_request.send_header('Content-type', 'application/json')
					http_request.end_headers()
					http_request.wfile.write(bytes("{\"error\": \"Command not found\"}", "utf-8"))
				elif command.upper() == "START":
					if miner.start():
						http_request.send_response(200)
						self.clear_statistics(miner.miner_id)
					else:
						http_request.send_response(500)
				elif command.upper() == "STOP":
					if miner.stop():
						http_request.send_response(200)
						self.clear_statistics(miner.miner_id)
					else:
						http_request.send_response(500)
				else:
					http_request.send_response(400)
					http_request.send_header('Content-type', 'application/json')
					http_request.end_headers()
					http_request.wfile.write(bytes("{\"error\": \"Command not found\"}", "utf-8"))
		else:
			http_request.send_response(404)

	@staticmethod
	def __get_parameter(query, parameter_id):
		params = parse_qs(query)[parameter_id]

		if len(params) != 1:  # params is a list
			return None
		else:
			return params[0]

	def __parse_sensitive_field(self, miner_config, field_name, password):

		if field_name in miner_config and miner_config[field_name] is not None:
			return miner_config[field_name]
		else:
			encrypted_field_name = "encrypted"+field_name[0].upper()+field_name[1:]
			if encrypted_field_name in miner_config:

				if self.cipher is None:  # check cipher
					if password is None:
						password = getpass.getpass("Farm configuration file password:")
						self.cipher = AESCipher(password)

				return self.cipher.decrypt_as_string(miner_config[encrypted_field_name])  # decrypt field

		return None


if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='Mochimo Farm Manager')
	parser.add_argument('html_repository', help="The HTML directory")
	parser.add_argument('farm_file', help="The farm configuration file")
	parser.add_argument('-pwd', dest="password", default=None, help="Farm configuration file password")
	parser.add_argument('-b', dest="bind", default="127.0.0.1:80", help="Host to bind")
	parser.add_argument('-hp', dest="http_parallelism", type=int, default=5, help="Number of http handlers")
	parser.add_argument('-sp', dest="stat_parallelism", type=int, default=3,  help="Number of process for statistics computing")
	parser.add_argument('-sh', dest="stat_heartbeat", type=int, default=30, help="Delay between statistic computation in seconds")
	parser.add_argument('-ll', dest="log_level", type=str, default="INFO", help="Log level (DEBUG, INFO, WARNING, WARN, ERROR)")

	args = parser.parse_args(sys.argv[1:])

	LOG_LEVEL = args.log_level.upper()

	if args.log_level.upper() == "DEBUG":
		LOG_LEVEL = logging.DEBUG
	elif args.log_level.upper() == "WARNING":
		LOG_LEVEL = logging.WARNING
	elif args.log_level.upper() == "WARN":
		LOG_LEVEL = logging.WARN
	elif args.log_level.upper() == "ERROR":
		LOG_LEVEL = logging.ERROR
	else:
		LOG_LEVEL = logging.INFO

	set_log_level()

	log = logging.getLogger("farm")
	try:
		MINING_FARM = MiningFarm(args.html_repository, args.farm_file, args.password, args.bind, http_parallelism=args.http_parallelism, stat_parallelism=args.stat_parallelism, stat_heartbeat=args.stat_heartbeat, log=log)
		MINING_FARM.start()
	except KeyboardInterrupt:
		MINING_FARM.stop()
		log.info("HTTP server stopped")
	except Exception as e:
		log.error(str(e))
		sys.exit(-1)
