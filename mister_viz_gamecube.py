#!/usr/bin/env python3

import gi, os, sys, serial, signal, jlib, datetime, time, binascii
from gi.repository import GLib, GObject

import mister_viz
import mister_viz_openvizsla

SVG_FILENAME = "gamecube.svg"

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
		self.emit("event", value)


class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	def __init__(self, resources):
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None

		self.axis_limits = {
			'lstick': {
				'x': [0x00, 0xff, None],
				'y': [0x00, 0xff, None],
			},
			'rstick': {
				'x': [0x00, 0xff, None],
				'y': [0x00, 0xff, None],
			},
		}
		self.res.sticks['lstick'].x_axis.min_value = 0
		self.res.sticks['lstick'].x_axis.max_value = 255
		self.res.sticks['lstick'].x_axis.default_value = 127 
		self.res.sticks['lstick'].y_axis.min_value = 0
		self.res.sticks['lstick'].y_axis.max_value = 255
		self.res.sticks['lstick'].y_axis.default_value = 127 

		self.res.sticks['rstick'].x_axis.min_value = 0
		self.res.sticks['rstick'].x_axis.max_value = 255
		self.res.sticks['rstick'].x_axis.default_value = 127 
		self.res.sticks['rstick'].y_axis.min_value = 0
		self.res.sticks['rstick'].y_axis.max_value = 255
		self.res.sticks['rstick'].y_axis.default_value = 127 
		self.res.axes['l'].is_analog = True
		self.res.axes['l'].mapped_to = "l"
		self.res.axes['l'].min_value = 50
		self.res.axes['l'].max_value = 230

		self.res.axes['r'].is_analog = True
		self.res.axes['r'].mapped_to = "r"
		self.res.axes['r'].min_value = 50
		self.res.axes['r'].max_value = 230

	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		if len(event) != 8:
			return
		state = set()
		if event[0] & 0x01:
			state.add("a")
		if event[0] & 0x02:
			state.add("b")
		if event[0] & 0x08:
			state.add("y")
		if event[0] & 0x04:
			state.add("x")
		if event[0] & 0x10:
			state.add("start")
		if event[1] & 0x01:
			state.add("left")
		if event[1] & 0x02:
			state.add("right")
		if event[1] & 0x04:
			state.add("down")
		if event[1] & 0x08:
			state.add("up")
		if event[1] & 0x10:
			state.add("z")
		if event[1] & 0x20:
			state.add("r")
		if event[1] & 0x40:
			state.add("l")

		for k, v in self.button_elements.items():
			if k in state:
				new_value = 1
			else:
				new_value = 0
			if new_value != v.value:
				v.set_value(new_value)
				dirty = True

		limits = self.axis_limits['lstick']
		stick_x = event[2]
		stick_y = event[3]
		limits['x'][2] = stick_x
		limits['y'][2] = 0xff - stick_y

		limits = self.axis_limits['rstick']
		stick_x = event[4]
		stick_y = event[5]
		limits['x'][2] = stick_x
		limits['y'][2] = 0xff - stick_y

		pos = event[7]
		if self.res.axes['r'].value != pos:
			self.res.axes['r'].set_value(pos)
			dirty = True

		pos = event[6]
		if self.res.axes['l'].value != pos:
			self.res.axes['l'].set_value(pos)
			dirty = True

		for stick in self.axis_limits:
			for axis in ['x', 'y']:
				lim = self.axis_limits[stick][axis]
				mid = ((lim[1] - lim[0]) / 2) + lim[0]
				axrange = lim[1] - mid
				offset = lim[2] - mid
				pos = (int((offset / axrange) * 127))
				#if axis == 'y':
				#	pos *= -1
				pos += 127
				#print(f"{stick} {axis} {lim[0]}, {lim[1]}, {axrange} {pos} {lim[2]}")
				if axis == 'x':
					if self.res.sticks[stick].x_axis.value != pos:
						self.res.sticks[stick].x_axis.set_value(pos)
						dirty = True
				elif axis == 'y':
					if self.res.sticks[stick].y_axis.value != pos:
						self.res.sticks[stick].y_axis.set_value(pos)
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
		log_file = f"gamecube__{naostr}.log"
	else:
		log_file = args.log_file


	loop = GLib.MainLoop()
	reader = Reader(args.port)
	stub = mister_viz.MisterVizStub()
	res = mister_viz.SvgControllerResources(os.path.join(mister_viz.get_yaml_basedir(), SVG_FILENAME))

	window = mister_viz.MisterVizWindow(stub, controller_resource=res)
	stub.windows[window.window_id] = window
	translator = Translator(res)

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
