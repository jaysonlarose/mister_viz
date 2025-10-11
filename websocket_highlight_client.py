#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, GLib

def call_dbus_method(bus, service, path, interface, method, *args, **kwargs):# {{{
	return bus.get_object(service, path).get_dbus_method(method, interface)(*args, **kwargs)
# }}}

class ClientWindow(Gtk.Window):
	def __init__(self):
		super().__init__()
		self.path = '/org/interlaced/WebsocketHighlight'
		self.connect("destroy", self.destroy_handler)
		import dbus, dbus.mainloop.glib
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		self.dbus = dbus.SessionBus()
		self.box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
		self.prev_button_major = Gtk.Button(label="<<<<")
		self.prev_button_major.connect("clicked", self.prev_button_major_handler)
		self.box.pack_start(self.prev_button_major, False, False, 0)
		self.prev_button = Gtk.Button(label="<<")
		self.prev_button.connect("clicked", self.prev_button_handler)
		self.box.pack_start(self.prev_button, False, False, 0)
		self.next_button = Gtk.Button(label=">>")
		self.box.pack_start(self.next_button, False, False, 0)
		self.next_button.connect("clicked", self.next_button_handler)
		self.next_button_major = Gtk.Button(label=">>>>")
		self.box.pack_start(self.next_button_major, False, False, 0)
		self.next_button_major.connect("clicked", self.next_button_major_handler)
		self.add(self.box)
		self.show_all()

	def destroy_handler(self, widget):
		Gtk.main_quit()

	def prev_button_handler(self, widget):
		call_dbus_method(self.dbus, "org.interlaced.websocket_highlight", self.path, "org.interlaced.WebsocketHighlight", "mod", -1)
		return True

	def next_button_handler(self, widget):
		call_dbus_method(self.dbus, "org.interlaced.websocket_highlight", self.path, "org.interlaced.WebsocketHighlight", "mod", 1)
		return True

	def prev_button_major_handler(self, widget):
		call_dbus_method(self.dbus, "org.interlaced.websocket_highlight", self.path, "org.interlaced.WebsocketHighlight", "mod_major", -1)
		return True

	def next_button_major_handler(self, widget):
		call_dbus_method(self.dbus, "org.interlaced.websocket_highlight", self.path, "org.interlaced.WebsocketHighlight", "mod_major", 1)
		return True


if __name__ == '__main__':
	app = ClientWindow()
	Gtk.main()
