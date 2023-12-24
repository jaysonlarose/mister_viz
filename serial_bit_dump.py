#!/usr/bin/env python3

import os, sys, serial, bitstring, binascii

from gi.repository import GLib, GObject

import mister_viz_gamecube


class Parser(mister_viz_gamecube.Parser):
	def __init__(self):
		super().__init__()
		self.last_timestamp = None
	def line_handler(self, widget, timestamp, line):
		#print(timestamp)
		#if self.last_timestamp is not None:
		#	timestamp_delta = timestamp - self.last_timestamp
		#else:
		#	timestamp_delta = 0
		frags = line.split(" ", 1)
		timestamp_delta = int(frags[0])
		line = frags[1]
		value = line.replace(" ", "")
		#print(repr(line))
		value = binascii.unhexlify(value)
		self.last_timestamp = timestamp
		self.emit("event", [value, timestamp_delta])


class Reader(mister_viz_gamecube.Reader):
	pass

def serial_handler(fd, flags):
	data = fd.read(128)
	if len(data) > 0:
		buf 

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("port")
	args = parser.parse_args()


	loop = GLib.MainLoop()
	reader = Reader(args.port)
	parser = Parser()

	def event_handler(widget, val):
		data, delta = val
		for b in data:
			print(f"{hex(b).ljust(6)} = {bitstring.BitString(uint=b, length=8).bin} {delta}")
		

	
	def line_handler(*args):
		print(f"line: {args}")
	
	#reader.connect("line", line_handler)
	reader.connect("line", parser.line_handler)

	parser.connect("event", event_handler)

	reader.startup()
	loop.run()
