#!/usr/bin/env python3

import gi, os, sys, serial, signal, jlib, datetime, time, binascii, struct
from gi.repository import GLib, GObject

import mister_viz
import mister_viz_openvizsla
import mister_viz_gamecube

SVG_FILENAME = "m30.svg"

class Parser(mister_viz_gamecube.Parser):
	pass

class Reader(mister_viz_gamecube.Reader):
	pass

class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	def __init__(self, resources):
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None

		self.axis_limits = {
		}

	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		payload = event.payload
		if len(payload) != 2:
			return
		state = set()
		if payload[0] & 0x01:
			state.add("up")
		if payload[0] & 0x02:
			state.add("down")
		if payload[0] & 0x04:
			state.add("left")
		if payload[0] & 0x08:
			state.add("right")
		if payload[0] & 0x10:
			state.add("a")
		if payload[0] & 0x20:
			state.add("b")
		if payload[0] & 0x40:
			state.add("c")
		if payload[0] & 0x80:
			state.add("start")
		if payload[1] & 0x01:
			state.add("x")
		if payload[1] & 0x02:
			state.add("y")
		if payload[1] & 0x04:
			state.add("z")
		if payload[1] & 0x08:
			state.add("mode")


		for k, v in self.button_elements.items():
			if k in state:
				new_value = 1
			else:
				new_value = 0
			if new_value != v.value:
				v.set_value(new_value)
				dirty = True

		if dirty:
			#print(state)
			#print(self.res.axes['l'].value)
			#print(self.res.axes['r'].value)
			self.set_dirty()

if __name__ == '__main__':

	config_basedir = mister_viz.get_yaml_basedir()
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("port")
	parser.add_argument("-l", "--log-file", action="store", dest="log_file", default=None, help="Write usb dump to log file LOG_FILE. Use magic name \":auto:\" to auto-create based on time and date.")
	parser.add_argument("-c", "--console", action="store_true", dest="do_console", default=False, help="Spawn REPL on stdin/stdout")
	args = parser.parse_args()

	if args.log_file == ':auto:':
		nao = datetime.datetime.now()
		naostr = nao.strftime("%F %T").replace(":", "_")
		log_file = f"genesis__{naostr}.log"
	else:
		log_file = args.log_file


	loop = GLib.MainLoop()
	reader = Reader(args.port)
	stub = mister_viz.MisterVizStub()
	res = mister_viz.SvgControllerResources(os.path.join(mister_viz.get_yaml_basedir(), SVG_FILENAME))

	import mister_viz_clutter
	window = mister_viz_clutter.MisterVizClutterWindow(stub, controller_resource=res)
	stub.windows[window.window_id] = window
	translator = Translator(res)

	def translator_dirty_handler(widget):
		window.trigger_draw()
		widget.reset_dirty()

	translator.connect("dirty", translator_dirty_handler)

	if log_file is not None:
		print(f"Logging to {log_file}")
		dumper = mister_viz_openvizsla.DumpLogger(log_file)
		reader.connect("line", dumper.line_handler)
	
	parser = mister_viz_gamecube.Parser()
	parser.connect("event", translator.event_handler)
	reader.connect("line", parser.line_handler)

	def event_thing(widget, value):
		print(f"event: {value}")

	#parser.connect("event", event_thing)

	def shutdown_handler():
		reader.shutdown()
		if log_file is not None:
			dumper.shutdown()
		stub.shutdown()
		loop.quit()

	
	def sigint_handler(sig, frame):
		print("SIGINT HANDLER CALLED")
		shutdown_handler()
	
	def window_destroy_handler(window):
		shutdown_handler()

	import signal
	signal.signal(signal.SIGINT, sigint_handler)
	window.connect("destroy", window_destroy_handler)
	reader.startup()
	if args.do_console:
		import debugrepl, glib_editingline
		cli = glib_editingline.CliInterpreter(None, namespace=globals())
		def cli_controlc_handler(*args):
			shutdown_handler()

		cli.connect("control-c", cli_controlc_handler)
	loop.run()
