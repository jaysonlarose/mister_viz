#!/usr/bin/env python3

import glib_editingline, os, sys, yaml, jlib, json, dbus, jdbus, dbus.mainloop.glib, subprocess
sys.path.append("/home/common/bin/projects/framework")
from gi.repository import GObject, GLib
import server, websocket_server

DBUS_SERVICE = 'org.interlaced.websocket_highlight'
DBUS_IFACE   = 'org.interlaced.WebsocketHighlight'
DBUS_PATH    = '/org/interlaced/WebsocketHighlight'

SOCKET_CONFIG = {
	'bind address': '127.0.0.1',
	'bind port':    53177,
	'ssl enable':   False,
}

class DBusServer(jdbus.Object):
	__properties__ = {}
	def __init__(self, parent, bus):
		self.parent = parent
		self.bus = bus
		self.bus_name = dbus.service.BusName(DBUS_SERVICE, self.bus)
		dbus.service.Object.__init__(self, self.bus, dbus.ObjectPath(DBUS_PATH), self.bus_name)

	@dbus.service.method(DBUS_IFACE, in_signature='i', out_signature='')
	def mod(self, val):
		self.parent.mod(val)
	@dbus.service.method(DBUS_IFACE, in_signature='i', out_signature='')
	def mod_major(self, val):
		self.parent.mod_major(val)


class State:
	def __init__(self, conf, bus):
		self.conf = conf
		self.server = server.GLibSocketServer(self.conf)
		self.ws_server = websocket_server.GLibWebsocketServer(self.server)
		self.ws_server.connect("client-message-received", self.message_handler)
		self.ws_server.connect("client-authenticated", self.newclient_handler)
		self.ws_server.connect("client-disconnected", self.client_close_handler)
		self.server.startup()

		self.dbus_server = DBusServer(self, bus)

	def mod(self, val):
		data = {}
		data['type'] = "highlight"
		data['value'] = val
		print(data)
		packet = json.dumps(data).encode()
		for client in self.ws_server.clients.get():
			client.send(packet)
	def mod_major(self, val):
		data = {}
		data['type'] = "highlight_major"
		data['value'] = val
		print(data)
		packet = json.dumps(data).encode()
		for client in self.ws_server.clients.get():
			client.send(packet)



	def newclient_handler(self, server, client):
		print(f"New websocket connection from {client.addr}!")
	def message_handler(self, server, client, message):
		print(f"Message received from {client.addr}: {message}")
	def client_close_handler(self, server, client, code, reason):
		reason_frags = []
		if code is not None:
			if code in close_codes:
				reason_frags.append(f"{code} {close_codes[code]}")
			else:
				reason_frags.append(f"{code}")
		if reason is not None:
			reason_frags.append(reason.decode())
		print(f"Client {client.addr} closing: {' '.join(reason_frags)}")

# headers = list(app.server.clients._lut.values())[0].ws_state['headers']

if __name__ == '__main__':
	import atexit
	dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
	bus = dbus.SessionBus()
	app = State(SOCKET_CONFIG, bus)
	proc = subprocess.Popen(['python3', '-m', 'http.server', '-d', '/home/common/bin/resources/html', '--bind', '127.0.0.1', '51342'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
	def proc_killer():
		proc.kill()
	atexit.register(proc_killer)

	loop = GLib.MainLoop()
	cli = glib_editingline.CliInterpreter(loop, namespace=globals())
	orig_print = print
	print = cli.editor.ed.line
	try:
		loop.run()
	except KeyboardInterrupt:
		proc.kill()
