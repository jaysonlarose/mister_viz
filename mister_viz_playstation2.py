#!/usr/bin/env python3

import gi, os, sys, serial, signal, jlib, datetime, time, binascii, struct
from gi.repository import GLib, GObject

import mister_viz
import mister_viz_openvizsla
import mister_viz_gamecube

SVG_FILENAME = "dualshock3.svg"


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
				'lstick': {
					'x': [0, 255, 127],
					'y': [0, 255, 127],
				},
				'rstick': {
					'x': [0, 255, 127],
					'y': [0, 255, 127],
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
		self.res.axes['l2'].is_analog = True
		self.res.axes['l2'].mapped_to = "l2"
		self.res.axes['l2'].min_value = 0
		self.res.axes['l2'].max_value = 255
		self.res.axes['r2'].is_analog = True
		self.res.axes['r2'].mapped_to = "r2"
		self.res.axes['r2'].min_value = 0
		self.res.axes['r2'].max_value = 255

	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		state = set()
		payload = event.payload
		if len(payload) == 5 and payload[0] == 0xff and payload[1] == 0x82 and payload[2] == 0x5a:
			inv = [ x ^ 0xff for x in payload ]

			inv_a = inv[3]
			inv_b = inv[4]
			if inv_a & 0x01:
				state.add("left")
			if inv_a & 0x02:
				state.add("down")
			if inv_a & 0x04:
				state.add("right")
			if inv_a & 0x08:
				state.add("up")
			if inv_a & 0x10:
				state.add("start")
			if inv_a & 0x20:
				state.add("rstick")
			if inv_a & 0x40:
				state.add("lstick")
			if inv_a & 0x80:
				state.add("select")

			if inv_b & 0x01:
				state.add("square")
			if inv_b & 0x02:
				state.add("cross")
			if inv_b & 0x04:
				state.add("circle")
			if inv_b & 0x08:
				state.add("triangle")
			if inv_b & 0x10:
				state.add("r1")
			if inv_b & 0x20:
				state.add("l1")

			pos = 255 if inv_b & 0x80 else 0
			if self.res.axes['l2'].value != pos:
				self.res.axes['l2'].set_value(pos)
				dirty = True

			pos = 255 if inv_b & 0x40 else 0
			if self.res.axes['r2'].value != pos:
				self.res.axes['r2'].set_value(pos)
				dirty = True
		elif len(payload) == 9 and payload[1] == 0xce and payload[2] == 0x5a:
			inv = [ x ^ 0xff for x in payload ]
			inv_a = inv[3]
			inv_b = inv[4]

			if inv_a & 0x01:
				state.add("left")
			if inv_a & 0x02:
				state.add("down")
			if inv_a & 0x04:
				state.add("right")
			if inv_a & 0x08:
				state.add("up")
			if inv_a & 0x10:
				state.add("start")
			if inv_a & 0x20:
				state.add("rstick")
			if inv_a & 0x40:
				state.add("lstick")
			if inv_a & 0x80:
				state.add("select")

			if inv_b & 0x01:
				state.add("square")
			if inv_b & 0x02:
				state.add("cross")
			if inv_b & 0x04:
				state.add("circle")
			if inv_b & 0x08:
				state.add("triangle")
			if inv_b & 0x10:
				state.add("r1")
			if inv_b & 0x20:
				state.add("l1")

			pos = 255 if inv_b & 0x80 else 0
			if self.res.axes['l2'].value != pos:
				self.res.axes['l2'].set_value(pos)
				dirty = True

			pos = 255 if inv_b & 0x40 else 0
			if self.res.axes['r2'].value != pos:
				self.res.axes['r2'].set_value(pos)
				dirty = True

			limits = self.axis_limits['lstick']
			stick_x = jlib.bitflip(payload[7])
			stick_y = jlib.bitflip(payload[8])
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			limits = self.axis_limits['rstick']
			stick_x = jlib.bitflip(payload[5])
			stick_y = jlib.bitflip(payload[6])
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y


		elif len(payload) == 21 and payload[0] == 0x80 and payload[1] == 0x9e and payload[2] == 0x5a:
			inv = [ x ^ 0xff for x in payload ]
			inv_a = inv[3]
			inv_b = inv[4]
			if inv_a & 0x01:
				state.add("left")
			if inv_a & 0x02:
				state.add("down")
			if inv_a & 0x04:
				state.add("right")
			if inv_a & 0x08:
				state.add("up")
			if inv_a & 0x10:
				state.add("start")
			if inv_a & 0x20:
				state.add("rstick")
			if inv_a & 0x40:
				state.add("lstick")
			if inv_a & 0x80:
				state.add("select")

			if inv_b & 0x01:
				state.add("square")
			if inv_b & 0x02:
				state.add("cross")
			if inv_b & 0x04:
				state.add("circle")
			if inv_b & 0x08:
				state.add("triangle")
			if inv_b & 0x10:
				state.add("r1")
			if inv_b & 0x20:
				state.add("l1")
			
			limits = self.axis_limits['lstick']
			stick_x = jlib.bitflip(payload[7])
			stick_y = jlib.bitflip(payload[8])
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			limits = self.axis_limits['rstick']
			stick_x = jlib.bitflip(payload[5])
			stick_y = jlib.bitflip(payload[6])
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			pos = jlib.bitflip(payload[19])
			if self.res.axes['l2'].value != pos:
				self.res.axes['l2'].set_value(pos)
				dirty = True

			pos = jlib.bitflip(payload[20])
			if self.res.axes['r2'].value != pos:
				self.res.axes['r2'].set_value(pos)
				dirty = True
		else:
			return


		for k, v in self.button_elements.items():
			if k in state:
				new_value = 1
			else:
				new_value = 0
			if new_value != v.value:
				v.set_value(new_value)
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
		log_file = f"playstation2__{naostr}.log"
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
