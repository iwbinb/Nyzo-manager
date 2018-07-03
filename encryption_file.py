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
import json
from encryption import AESCipher


def encrypt_field(field_name, json_object, cipher):
	encrypted_field_name = "encrypted" + field_name[0].upper() + field_name[1:]
	if (field_name in json_object and json_object[field_name] is not None) and encrypted_field_name not in json_object:
		json_object[encrypted_field_name] = cipher.encrypt_as_string(json_object[field_name])
		json_object.pop(field_name)


def decrypt_field(field_name, json_object, cipher):
	encrypted_field_name = "encrypted" + field_name[0].upper() + field_name[1:]
	if (encrypted_field_name in json_object and json_object[encrypted_field_name] is not None) and field_name not in json_object:
		json_object[field_name] = cipher.decrypt_as_string(json_object[encrypted_field_name])
		json_object.pop(encrypted_field_name)


if __name__ == '__main__':

	parser = argparse.ArgumentParser(description='Pool Configuration File Encryption/Decryption')
	parser.add_argument("-m", dest="mode", default="e", help="e -> encrypt, d -> decrypt")
	parser.add_argument("-pwd", dest="password", default=None, help="Password")
	parser.add_argument("config_file", help="Configuration file path")
	parser.add_argument("output_config_file", help="Output configuration file path")

	args = parser.parse_args(sys.argv[1:])
	# print(args)

	if args.password is None:
		args.password = getpass.getpass("Password:")

	cipher = AESCipher(args.password)

	config_file = open(args.config_file, 'r')
	config = json.load(config_file)
	config_file.close()

	if args.mode.upper() == "E":
		# encrypt all field except id
		for miner_config in config["miners"]:
			encrypt_field("host", miner_config, cipher)
			encrypt_field("user", miner_config, cipher)
			encrypt_field("password", miner_config, cipher)
			encrypt_field("privateKeyPath", miner_config, cipher)
			encrypt_field("startCommand", miner_config, cipher)
			encrypt_field("logCommand", miner_config, cipher)

		print("Writing output file " + args.output_config_file)
		output_config_file = open(args.output_config_file, 'w')
		json.dump(config, output_config_file, indent=4)
		output_config_file.close()
		print("####### DO NOT LET SENSITIVE DATA IN PLAIN TEXT. DELETE "+args.config_file+" IMMEDIATELY #######")
	elif args.mode.upper() == "D":
		# decrypt all field except id
		for miner_config in config["miners"]:
			decrypt_field("host", miner_config, cipher)
			decrypt_field("user", miner_config, cipher)
			decrypt_field("password", miner_config, cipher)
			decrypt_field("privateKeyPath", miner_config, cipher)
			decrypt_field("startCommand", miner_config, cipher)
			decrypt_field("logCommand", miner_config, cipher)

		print("Writing output file " + args.output_config_file)
		output_config_file = open(args.output_config_file, 'w')
		json.dump(config, output_config_file, indent=4)
		output_config_file.close()
	else:
		print("Unhandled mode "+args.mode)
