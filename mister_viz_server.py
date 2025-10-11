#!/usr/bin/env python3

import evdev, gi, os, sys, struct

sys.path.append("/home/common/bin/projects/framework")

import server

gi.require_version("GUdev", "1.0")

from gi.repository import GLib, GObject, GUdev

import socket

MISTER_STRUCT = "<BBHHHHiII"
MISTER_STRUCT_SIZE = struct.calcsize(MISTER_STRUCT)

OP_INPUT = 0
OP_PING  = 1
OP_PONG  = 2

socket_conf = {
	'bind address': "0.0.0.0",
	'bind port': 22101,
	'ssl enable': False,
}

def create_inputdevice(gudev_obj):
	try:
		inputdevice = InputDevice(gudev_obj)
		return inputdevice
	except RuntimeError:
		return None

class InputDevice(GObject.GObject):
	__gsignals__ = {
		'hangup': (GObject.SignalFlags.RUN_FIRST, None, []),
		'input-event': (GObject.SignalFlags.RUN_FIRST, None, [GObject.TYPE_PYOBJECT]),
	}
	def __init__(self, gudev_obj):
		super().__init__()
		self.closed = False
		self.gudev_obj = gudev_obj
		self.device_file = self.gudev_obj.get_device_file()
		if self.device_file is None:
			raise RuntimeError("GUdev object has no device file!")
		if not os.path.split(self.device_file)[1].startswith('event'):
			raise RuntimeError("device file is not an event device!")
		self.evdev_obj = evdev.InputDevice(self.device_file)
		parent_device = self.gudev_obj
		self.vid = None
		self.pid = None
		while parent_device is not None:
			keys = parent_device.get_sysfs_attr_keys()
			if 'id/vendor' in keys and 'id/product' in keys:
				self.vid = int(parent_device.get_sysfs_attr('id/vendor'), 16)
				self.pid = int(parent_device.get_sysfs_attr('id/product'), 16)
				break
			parent_device = parent_device.get_parent()
		if self.vid is None or self.pid is None:
			raise RuntimeError("device file did not have vendorID or productID!")
		GLib.io_add_watch(self.evdev_obj, GLib.IO_IN | GLib.IO_HUP, self.input_handler)
	def input_handler(self, fh, flags):
		print("input_handler()")
		if flags & GLib.IO_HUP:
			self.evdev_obj.close()
			self.closed = True
			self.emit("hangup")
			return False
		event_generator = self.evdev_obj.read()
		for event in event_generator:
			#print(f"{event.sec}, {event.usec}, {event.type}, {event.code}, {event.value}")
			vals = [
				0, # inputno
				0, # player_id
				self.vid,
				self.pid,
				event.type,
				event.code,
				event.value,
				event.sec,
				event.usec,
			]
			self.emit("input-event", vals)
			#print(vals)
		return True
	def shutdown(self):
		if not self.closed:
			self.evdev_obj.close()
			self.closed = True
	@property
	def device_name(self):
		return self.evdev_obj.name

class State:
	def __init__(self, loop, gudev_client):
		self.devs = {}
		self.loop = loop
		self.gudev_client = gudev_client
		self.gudev_client.connect("uevent", self.gudev_uevent_handler)
		for gudev_obj in self.gudev_client.query_by_subsystem("input"):
			self.gudev_uevent_handler(self.gudev_client, "add", gudev_obj)
		self.socketserver = server.GLibSocketServer(socket_conf)
		self.socketserver.connect("client-connected", self.connect_handler)
		self.socketserver.connect("client-authenticated", self.auth_handler)
		self.socketserver.connect("client-disconnected", self.disconnect_handler)
		self.socketserver.startup()
	def gudev_uevent_handler(self, client, event, gudev_obj):
		print(f"gudev event: {event}")
		if event != "add":
			return False
		input_obj = create_inputdevice(gudev_obj)
		if input_obj is None:
			return False
		print(f"Adding {input_obj.device_name} to devs")
		self.devs[input_obj.device_file] = input_obj
		input_obj.connect("hangup", self.input_hangup_handler)
		input_obj.connect("input-event", self.input_event_handler)
	def input_hangup_handler(self, input_obj):
		if input_obj.device_file in self.devs:
			print(f"Removing {input_obj.device_name} from devs")
			del self.devs[input_obj.device_file]
	def input_event_handler(self, input_obj, vals):
		packet = bytes([OP_INPUT]) + struct.pack(MISTER_STRUCT, *vals)
		printvals = vals[:]
		printvals[2] = f"{printvals[2]:04x}"
		printvals[3] = f"{printvals[3]:04x}"
		print(printvals)
		for client in self.socketserver.clients:
			if client.ssl_authenticated:
				client.send(packet)
	def connect_handler(self, server, client):
		print(f"Client connected: {client.addr}")

	def auth_handler(self, server, client):
		print(f"Client authenticated: {client.addr}")
		client.state = {}
		client.connect("data-received", self.client_recv_handler)
	
	def disconnect_handler(self, server, client):
		print(f"Client disconnect: {client.addr}")

	def client_recv_handler(self, client, data):
		if len(data) > 0:
			opcode = data[0]
			if opcode == OP_PING:
				client.send(bytes([OP_PONG]))
			else:
				print(f"Unknown opcode {opcode}, dropping client")
				client.close()


if __name__ == '__main__':
	print(MISTER_STRUCT_SIZE)
	gudev_client = GUdev.Client(subsystems=['input'])
	loop = GLib.MainLoop()
	app = State(loop, gudev_client)
	loop.run()
