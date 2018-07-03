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


import logging
import time
import datetime
import threading
import multiprocessing
import mining_farm


def get_statistics(miner):
	statistics = {}
	statistics["minerId"] = miner.miner_id
	statistics["host"] = miner.host
	statistics["user"] = miner.user
	stat = miner.statistics()
	t = time.time()
	statistics["timestamp"] = t
	statistics["datetime"] = datetime.datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M:%S UTC')
	statistics["cpu"] = stat["cpu"]
	statistics["process"] = stat["process"]
	statistics["gomochi"] = stat["gomochi"]
	statistics["listen"] = stat["listen"]
	statistics["solving"] = stat["solving"]

	if "Block" in stat:
		statistics["block"] = stat["Block"]
	else:
		statistics["block"] = None

	if "Haiku/second" in stat:
		statistics["hps"] = stat["Haiku/second"]
	else:
		statistics["hps"] = "0"

	if "Solved" in stat:
		statistics["solved"] = stat["Solved"]
	else:
		statistics["solved"] = "0"

	if "Difficulty" in stat:
		statistics["difficulty"] = stat["Difficulty"]
	else:
		statistics["difficulty"] = None

	return statistics


def _get_statistics_child_process(miner_config):
	try:
		mining_farm.set_log_level()
		# rebuild the miner from the config (intra process communication only support serializable object)
		miner = miner_config.build()
		miner.log.debug("Computing statistics")
		status = get_statistics(miner)

		return miner.miner_id, status

	except Exception as e:
		plog = logging.getLogger("child_process")
		plog.setLevel(logging.INFO)
		plog.error(str(e))


class StatisticsProcessingPool:

	def __init__(self, farm, parallelism, heartbeat=30, log=None):

		if log is None:
			self.log = logging.getLogger("StatisticsProcessingPool")
		else:
			self.log = log

		self.mining_farm = farm
		self.parallelism = parallelism
		self.heartbeat = heartbeat

		self.pending_statistics_ids = []
		self.pending_statistics_ids_lock = threading.RLock()

		self.statistics = []
		self.statistics_lock = threading.RLock()

		self.process_pool = None
		self.stop_requested = False

		global STATISTICS_PROCESSING_POOL
		STATISTICS_PROCESSING_POOL = self

	def start(self):
		self.log.info("Creating process pool (" + str(self.parallelism) + ")")
		self.process_pool = multiprocessing.Pool(self.parallelism)
		self.log.info("Starting update thread")
		thread = threading.Thread(target=self.__statistic_monitor)
		thread.start()

	def stop(self):
		self.stop_requested = True  # supposedly thread safe
		self.process_pool.terminate()
		self.process_pool.join()
		self.log.info("Process pool stopped")

	def set_statistics(self, stat):
		if stat is None:
			self.log.warning("Discarding None statistic")
			return False

		self.statistics_lock.acquire()
		try:
			new_statistic = []
			for s in self.statistics:
				if stat is not None and s["minerId"] == stat["minerId"]:
					new_statistic.append(stat)
					stat = None
				else:
					new_statistic.append(s)

			if stat is not None:  # if the stat was not there before
				new_statistic.append(stat)

			self.statistics.clear()
			self.statistics.extend(new_statistic)

			return True
		finally:
			self.statistics_lock.release()

	def get_statistics(self, miner_id):
		self.statistics_lock.acquire()
		try:
			for stat in self.statistics:
				if stat["minerId"] == miner_id:
					return stat

			return None
		finally:
			self.statistics_lock.release()

	def init_statistics(self, miner_id):
		stat = StatisticsProcessingPool.__get_default_statistic(miner_id)
		self.set_statistics(stat)
		return stat

	def get_pending_ids(self):
		self.pending_statistics_ids_lock.acquire()
		try:
			copy = []
			copy.extend(self.pending_statistics_ids)
			return copy
		finally:
			self.pending_statistics_ids_lock.release()

	def __set_computation_pending(self, miner_id):
		self.pending_statistics_ids_lock.acquire()
		try:
				if self.__is_computation_pending(miner_id):
					return False

				self.pending_statistics_ids.append(miner_id)
				self.log.debug("Statistics job queue size -> " + str(len(self.get_pending_ids())))
				return True
		finally:
			self.pending_statistics_ids_lock.release()

	def __remove_computation_pending(self, miner_id):
		self.pending_statistics_ids_lock.acquire()
		try:
			new_pending_statistics = []

			for id in self.pending_statistics_ids:
				if id == miner_id:
					continue
				new_pending_statistics.append(id)

			self.pending_statistics_ids.clear()
			self.pending_statistics_ids.extend(new_pending_statistics)
			self.log.debug("Statistics job queue size -> " + str(len(self.get_pending_ids())))
		finally:
			self.pending_statistics_ids_lock.release()

	def __remove_all_computation_pending(self):
		self.pending_statistics_ids_lock.acquire()
		try:
			self.pending_statistics_ids.clear()
			self.log.debug("Statistics job queue size -> " + str(len(self.get_pending_ids())))
		finally:
			self.pending_statistics_ids_lock.release()

	def __is_computation_pending(self, miner_id):
		self.pending_statistics_ids_lock.acquire()
		try:
			for id in self.pending_statistics_ids:
				if id == miner_id:
					return True
		finally:
			self.pending_statistics_ids_lock.release()

		return False

	def callback(self, tuple):
		if tuple is None:
			self.log.error("Tuple is None. Clearing all pending statistics")
			self.__remove_all_computation_pending()
			return

		miner_id = tuple[0]
		stat = tuple[1]
		if stat is None:
			self.log.error("New stat of " + miner_id + " is None")
		else:
			self.log.debug("New stat received for " + miner_id + ": " + str(stat))
			self.set_statistics(stat)
			self.__remove_computation_pending(miner_id)

	def __statistic_monitor(self):

		while not self.stop_requested:

			for miner in self.mining_farm.get_miners():

				if self.stop_requested:
					break

				if self.__is_computation_pending(miner.miner_id):
					continue

				stat = self.get_statistics(miner.miner_id)

				if stat is None:
					"""Adding stat"""
					stat = self.init_statistics(miner.miner_id)

				elapsed = time.time() - stat["timestamp"]
				if elapsed > self.heartbeat:
					self.__set_computation_pending(miner.miner_id)
					self.log.debug("Submitting statistics task for miner " + miner.miner_id+" (last update was "+str(elapsed)+" sec ago)")
					self.process_pool.apply_async(_get_statistics_child_process, (miner.config,), callback=self.callback)
					#ret= self.process_pool.apply(_get_statistics_child_process, (miner.config,))

			time.sleep(max(1, self.heartbeat / 10))

		self.process_pool.terminate()
		self.process_pool.join()
		self.log.info("Processing pool stopped")

	@staticmethod
	def __get_default_statistic(miner_id):

		return {'minerId': miner_id, 'timestamp': 0,
				'datetime': datetime.datetime.utcfromtimestamp(0).strftime('%Y-%m-%d %H:%M:%S UTC')}
