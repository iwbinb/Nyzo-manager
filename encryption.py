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
import base64
import hashlib
from Cryptodome import Random
from Cryptodome.Cipher import AES


class AESCipher:

	def __init__(self, key):
		self.bs = 32
		self.key = hashlib.sha256(key.encode()).digest()

	def encrypt(self, raw):
		raw = raw.encode()
		length = AES.block_size - (len(raw) % AES.block_size)
		raw += bytes([length]) * length  # store padding length length'th times
		iv = Random.new().read(AES.block_size)
		aes = AES.new(self.key, AES.MODE_CBC, iv)
		return base64.b64encode(iv + aes.encrypt(raw))

	def encrypt_as_string(self, raw):
		return self.encrypt(raw).decode("utf-8")

	def decrypt(self, encrypted):
		encrypted = base64.b64decode(encrypted)
		iv = encrypted[:AES.block_size]
		aes = AES.new(self.key, AES.MODE_CBC, iv)
		raw = aes.decrypt(encrypted[AES.block_size:])
		raw = raw[:-raw[-1]]  # read last byte and trim
		return raw

	def decrypt_as_string(self, encrypted):
		return self.decrypt(encrypted).decode("utf-8")


if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='AES Encryption/Decryption Tool')
	parser.add_argument("-m", dest="mode", default="e", help="e -> encrypt, d -> decrypt")
	parser.add_argument("-pwd", dest="password", default=None, help="Password")
	parser.add_argument("input", help="Raw input")

	args = parser.parse_args(sys.argv[1:])

	if args.password is None:
		args.password = getpass.getpass("Password:")

	cipher = AESCipher(args.password)

	if args.mode.upper() == "E":
		encrypted_data = cipher.encrypt_as_string(args.input)
		print(encrypted_data)
	elif args.mode.upper() == "D":
		raw_data = cipher.decrypt_as_string(args.input)
		print(raw_data)
	else:
		print("Unhandled mode "+args.mode)
