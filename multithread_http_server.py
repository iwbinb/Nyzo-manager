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


import socket
import threading
import time
from http.server import HTTPServer


class MultiThreadHttpServer:

	def __init__(self, host, parallelism, HTTPHandler, request_callback=None):
		"""
		:param host: host to bind. example: '127.0.0.1:80'
		:param parallelism: number of thread listener and backlog
		:param HTTPHandler: the handler class
		:param request_callback: callback on incoming request. This method can be accede in the HTTPHandler instance.
				Example: self.server.request_callback('GET',  # specify http method
														self  # pass the HTTPHandler instance
													)
		"""

		self.host = host
		self.parallelism = parallelism
		self.HTTPHandler = HTTPHandler
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.request_callback = request_callback

	def start(self):
		self.socket.bind(self.host)
		self.socket.listen(self.parallelism)

		for i in range(self.parallelism):
			h = ConnectionHandler(self.socket, self.HTTPHandler, self.request_callback)
			h.start()

		while True:
			time.sleep(9e5)


class ConnectionHandler(threading.Thread, HTTPServer):

	def __init__(self, socket, HTTPHandler, request_callback=None):
		HTTPServer.__init__(self, socket.getsockname(), HTTPHandler, False)
		self.socket = socket
		self.server_bind = self.server_close = lambda self: None
		self.HTTPHandler = HTTPHandler
		self.request_callback = request_callback

		threading.Thread.__init__(self)
		self.daemon = True

	def run(self):
		self.serve_forever()  # each thread process request forever

