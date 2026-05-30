#!/usr/bin/env python3

import gi, os, sys, serial, signal, jlib, datetime, time, binascii
from gi.repository import GLib, GObject

import mister_viz
import mister_viz_openvizsla


class Reader(GObject.GObject):
	__gsignals__ = {
		"event": (GObject.SignalFlags.RUN_FIRST, None, [GObject.TYPE_PYOBJECT, GObject.TYPE_PYOBJECT]),
		"line":  (GObject.SignalFlags.RUN_FIRST, None, [float, str]),
	}
	def __init__(self, port):
		super().__init__()
		self.port = port
		self.buf = b''
	def startup(self):
		self.ser = serial.Serial(self.port, 115200)
		self.ser.timeout = 0
		self.io_source = GLib.io_add_watch(self.ser, GLib.IO_IN, self.serial_handler)
	def serial_handler(self, fd, flags):
		nao = time.time()
		data = self.ser.read(128)
		if len(data) > 0:
			self.buf += data
			lines = self.buf.splitlines(keepends=True)
			if len(lines) > 0:
				if not lines[-1].endswith(b"\n"):
					self.buf = lines[-1]
					lines = lines[:-1]
				else:
					self.buf = b''
			for line in lines:
				value = line.decode().strip()
				self.emit("line", nao, value)
		return True
	def shutdown(self):
		self.ser.close()
		if self.io_source is not None:
			GLib.source_remove(self.io_source)
			self.io_source = None

class Event:
	__slots__ = ['timestamp', 'payload']
	def __init__(self, timestamp, value):
		self.timestamp = timestamp
		self.payload = value

class Parser(GObject.GObject):
	__gsignals__ = {
		"event": (GObject.SignalFlags.RUN_FIRST, None, [GObject.TYPE_PYOBJECT]),
	}
	def __init__(self):
		super().__init__()
	def line_handler(self, widget, timestamp, line):
		value = line.replace(" ", "")
		#print(repr(line))
		value = binascii.unhexlify(value)
		event = Event(timestamp, value)
		self.emit("event", event)

if __name__ == '__main__':
	config_basedir = mister_viz.get_yaml_basedir()
	sys.path.append(config_basedir)
	available_personalities = [ os.path.splitext(x)[0][len("teensy_"):] for x in os.listdir(config_basedir) if x.startswith("teensy_") and os.path.splitext(x)[1] == ".py" ]
	print(f"Available personalities: {available_personalities}")
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("port")
	parser.add_argument("personality", action="store", choices=available_personalities, help="Personality module to invoke")
	parser.add_argument("-l", "--log-file", action="store", dest="log_file", default=None, help="Write usb dump to log file LOG_FILE. Use magic name \":auto:\" to auto-create based on time and date.")
	parser.add_argument("-c", "--console", action="store_true", dest="do_console", default=False, help="Spawn REPL on stdin/stdout")
	args = parser.parse_args()

	personality_path = os.path.join(config_basedir, f"teensy_{args.personality}.py")

	import importlib.util
	spec = importlib.util.spec_from_file_location("abcxyz", personality_path)
	personality = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(personality)

	if args.log_file == ':auto:':
		nao = datetime.datetime.now()
		naostr = nao.strftime("%F %T").replace(":", "_")
		log_file = f"{personality.NAME}__{naostr}.log"
	else:
		log_file = args.log_file


	loop = GLib.MainLoop()
	reader = Reader(args.port)
	stub = mister_viz.MisterVizStub()
	res = mister_viz.SvgControllerResources(os.path.join(config_basedir, personality.SVG_FILENAME))

	window = mister_viz.MisterVizWindow(stub, controller_resource=res)
	stub.windows[window.window_id] = window
	translator = personality.Translator(res)

	def translator_dirty_handler(widget):
		window.darea.queue_draw()
		widget.reset_dirty()

	translator.connect("dirty", translator_dirty_handler)

	if log_file is not None:
		print(f"Logging to {log_file}")
		dumper = mister_viz_openvizsla.DumpLogger(log_file)
		reader.connect("line", dumper.line_handler)
	
	parser = Parser()
	parser.connect("event", translator.event_handler)
	reader.connect("line", parser.line_handler)

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
