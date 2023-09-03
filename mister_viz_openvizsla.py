#!/usr/bin/env python3

import gi, subprocess, os, sys, signal, ptyprocess, fcntl, binascii, re, jlib, datetime, time, queue, multiprocessing
ov_dir = "/home/jayson/Git/ov_ftdi/software/host"
sys.path.append(ov_dir)
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject
import openvizsla_parse
from projects.framework import server
import mister_viz
import math
import LibOV
import zipfile
import openvizsla_parse

def plot_course(start_point, direction, distance):# {{{
	"""
	Given a starting point, an angle (in radians), and a distance,
	returns the point resulting from travelling from the starting point
	at said angle for said distance.
	"""
	return (start_point[0] + math.sin(direction) * distance, start_point[1] + math.cos(direction) * distance)
# }}}



	
def byte_to_block(b):
	import jlib
	start = 0x2580
	level = jlib.round_properly((b / 255) * 8)
	if level == 0:
		return ' '
	else:
		return chr(start + level)

def byte_to_blockpair(b):
	import jlib
	start = 0x2590
	level = jlib.round_properly((b / 255) * 16)
	ret = ''
	if level > 8:
		ret += '\u2588'
		level = level - 8
	if level == 0:
		ret += ' '
	else:
		ret += chr(start - level)
	if len(ret) == 1:
		ret += ' '
	return ret

class UsbDataEvent:
	def __init__(self, **kwargs):
		self.timestamp = None
		self.direction = None
		self.target    = None
		self.payload   = None
		for k, v in kwargs.items():
			setattr(self, k, v)
	def __repr__(self):
		if self.payload is not None:
			payload_text = binascii.hexlify(self.payload).decode()
		else:
			payload_text = ""
		return f"<UsbDataEvent({self.direction}: {self.target}: {payload_text})>"

class OpenVizslaParser(GObject.GObject):
	__gsignals__ = {
		"event": (GObject.SignalFlags.RUN_FIRST, None, [GObject.TYPE_PYOBJECT]),
	}
	def __init__(self):
		super().__init__()
		self.packet_buffer = []
	def line_handler(self, widget, timestamp, line):
		#print("line handler", file=sys.stderr)
		obj = openvizsla_parse.parse_line(line)
		self.append(obj)
	def packet_handler(self, widget, timestamp, packet):
		self.append(packet)
	def append(self, obj):
		if isinstance(obj, openvizsla_parse.OpenVizslaLineEvent):
			if obj.pkttype in ['SETUP', 'IN', 'OUT']:
				self.packet_buffer = [obj]
			elif obj.pkttype in ['NAK', 'ACK']:
				event_kwargs = {}
				target_packet_candidates = [ x for x in self.packet_buffer if x.pkttype in ['SETUP', 'IN', 'OUT'] ]
				if len(target_packet_candidates) > 0:
					target_packet = [ x for x in self.packet_buffer if x.pkttype in ['SETUP', 'IN', 'OUT'] ][0]
					event_kwargs['target'] = target_packet.payload
					try:
						payload_packet = [ x for x in self.packet_buffer if x.pkttype in ['DATA0', 'DATA1', 'DATA2'] ][0]
						event_kwargs['payload'] = payload_packet.payload
					except IndexError:
						event_kwargs['payload'] = None
					if target_packet.pkttype == 'IN':
						event_kwargs['direction'] = 'IN'
					else:
						event_kwargs['direction'] = 'OUT'
					event_kwargs['timestamp'] = self.packet_buffer[0].timestamp

					event = UsbDataEvent(**event_kwargs)
					event.packet_buffer = self.packet_buffer
					self.emit("event", event)
				self.packet_buffer = []
			elif obj.pkttype.startswith("DATA"):
				self.packet_buffer.append(obj)
		elif isinstance(obj, openvizsla_parse.OpenVizslaUnknownEvent):
			if obj.line.strip().startswith("AssertionError"):
				print("ovctl assertion error, booting it")
				do_restart = True
		do_restart = False
		if do_restart:
			pass
			#self.shutdown()
			#reset_device = None
			#for device in usbreset():
			#	if device['devicename'] == "ov3p1":
			#		reset_device = f"{device['busnum']}/{device['devnum']}"
			#		break
			#if reset_device is not None:
			#	print(f"Resetting {reset_device}")
			#	usbreset(reset_device)
			#GLib.timeout_add(10000, self.startup)




class OpenVizslaSniffer(GObject.GObject):
	__gsignals__ = {
		"event": (GObject.SignalFlags.RUN_FIRST, None, [GObject.TYPE_PYOBJECT]),
		"line":  (GObject.SignalFlags.RUN_FIRST, None, [float, str]),
	}
	def __init__(self, ovctl_path="/home/jayson/Git/ov_ftdi/software/host/ovctl.py", speed="fs", startup=False, log_file=None):
		super().__init__()
		self.proc = None
		self.io_source = None
		self.ovctl_path = ovctl_path
		self.speed = speed
		self.log_file = log_file
		self.log_fh = None
		if startup:
			self.startup()
	def startup(self):
		if self.proc is not None:
			self.shutdown()
		self.buf = b''
		self.data_packet_received = False
		self.sequential_utilization_qty = 0
		procargs = [self.ovctl_path, '-l', "sniff", self.speed]
		self.proc = ptyprocess.PtyProcess.spawn(procargs)
		fcntl.fcntl(self.proc.fileno(), fcntl.F_SETFL, fcntl.fcntl(self.proc.fileno(), fcntl.F_GETFL) | os.O_NONBLOCK)
		self.io_source = GLib.io_add_watch(self.proc.fileno(), GLib.IO_IN | GLib.IO_HUP, self.stdout_handler)
	def shutdown(self):
		if self.proc is not None:
			if self.proc.isalive():
				self.proc.kill(signal.SIGKILL)
			self.proc = None
		if self.io_source is not None:
			GLib.source_remove(self.io_source)
			self.io_source = None
	def stdout_handler(self, fd, flags):
		nao = time.time()
		if flags & GLib.IO_IN:
			data = os.read(fd, 8192)
			self.buf += data
			lines = self.buf.splitlines(keepends=True)
			if len(lines) > 0:
				if not lines[-1].endswith(b"\n"):
					self.buf = lines[-1]
					lines = lines[:-1]
				else:
					self.buf = b''
			for line in lines:
				line = line.decode().strip()
				#print(line)
				self.emit("line", nao, line)
				#print(obj)
		return True

class OpenVizslaTranslator(GObject.GObject):
	__gsignals__ = {
		"dirty": (GObject.SignalFlags.RUN_FIRST, None, []),
	}
	def __init__(self, resources, **kwargs):
		#print("OpenVizslaTranslator __init__()", file=sys.stderr)
		super().__init__()
		self.res = resources
		self.dirty_flag = False
		for k, v in kwargs.items():
			setattr(self, k, v)
	def reset_dirty(self):
		self.dirty_flag = False
	def set_dirty(self):
		if not self.dirty_flag:
			self.dirty_flag = True
			self.emit("dirty")
	

class OVHelper:
	def __init__(self, pipe, outq):
		self.pipe = pipe
		self.outq = outq
	def handle_packet(self, ts, pkt, flags):
		timestamp = time.time()
		#print("owo")
		self.outq.put([timestamp, [ts, pkt, flags]])
		self.pipe.send(b"!")

class OpenVizslaReader(GObject.GObject):
	__gsignals__ = {
		'packet': (GObject.SignalFlags.RUN_FIRST, None, [float, GObject.TYPE_PYOBJECT]),
	}
	def __init__(self, speed="fs"):
		super().__init__()
		self.fw_zipfile = zipfile.ZipFile(os.path.join(ov_dir, "ov3.fwpkg"), "r")
		self.speed = speed
	def startup(self):
		print(f"OpenVizslaReader.startup() called!", file=sys.stderr)

		self.pipe_src, self.pipe_sink = multiprocessing.Pipe(duplex=False)
		self.packet_queue = queue.Queue()

		helper = OVHelper(self.pipe_sink, self.packet_queue)

		GLib.io_add_watch(self.pipe_src.fileno(), GLib.IO_IN, self.pipe_handler)

		self.dev = LibOV.OVDevice(mapfile=self.fw_zipfile.open("map.txt", "r"))
		err = self.dev.open(bitstream=self.fw_zipfile.open("ov3.bit", "r"))
		if err:
			print("USB: Unable to find device")
			sys.exit(1)
		self.dev.regs.LEDS_MUX_2.wr(0)
		self.dev.regs.LEDS_OUT.wr(0)
														 
		# LEDS 0/1 to FTDI TX/RX
		self.dev.regs.LEDS_MUX_0.wr(2)
		self.dev.regs.LEDS_MUX_1.wr(2)
														 
		# enable SDRAM buffering
		ring_base = 0
		ring_size = 16 * 1024 * 1024
		ring_end = ring_base + ring_size
		self.dev.regs.SDRAM_SINK_GO.wr(0)
		self.dev.regs.SDRAM_HOST_READ_GO.wr(0)
		self.dev.regs.SDRAM_SINK_RING_BASE.wr(ring_base)
		self.dev.regs.SDRAM_SINK_RING_END.wr(ring_end)
		self.dev.regs.SDRAM_HOST_READ_RING_BASE.wr(ring_base)
		self.dev.regs.SDRAM_HOST_READ_RING_END.wr(ring_end)
		self.dev.regs.SDRAM_SINK_GO.wr(1)
		self.dev.regs.SDRAM_HOST_READ_GO.wr(1)
														 
		# clear perfcounters
		self.dev.regs.OVF_INSERT_CTL.wr(1)
		self.dev.regs.OVF_INSERT_CTL.wr(0)

		if not self.dev.regs.ucfg_stat.rd():
			print("ULPI clock not started")
			sys.exit(1)
		

		# set to non-drive; set FS or HS as requested
		if self.speed == "hs":
			self.dev.ulpiregs.func_ctl.wr(0x48)
			self.dev.rxcsniff.service.highspeed = True
		elif self.speed == "fs":
			self.dev.ulpiregs.func_ctl.wr(0x49)
			self.dev.rxcsniff.service.highspeed = False
		elif self.speed == "ls":
			self.dev.ulpiregs.func_ctl.wr(0x4a)
			self.dev.rxcsniff.service.highspeed = False
		else:
			assert 0,"Invalid Speed"

		self.dev.rxcsniff.service.handlers = [helper.handle_packet]

		self.dev.regs.CSTREAM_CFG.wr(1)

	def shutdown(self):
		print(f"OpenVizslaReader.shutdown() called!", file=sys.stderr)
		self.dev.regs.SDRAM_SINK_GO.wr(0)
		self.dev.regs.SDRAM_HOST_READ_GO.wr(0)
		self.dev.regs.CSTREAM_CFG.wr(0)
		self.dev.close()
		self.pipe_src.close()
		self.pipe_sink.close()

	def pipe_handler(self, fd, flags):
		#print("pipe_handler")
		if self.pipe_src.fileno() == fd:
			#print("weewoo")
			thang = self.pipe_src.recv()
			#print(thang)
		while True:
			try:
				timestamp, payload = self.packet_queue.get(block=False)
				#print(payload)
				ret = openvizsla_parse.parse_ovpacket(*payload)
				#print("queue got")
				if ret is not None:
					self.emit("packet", timestamp, ret)
					if len(ret.flags) > 0:
						print(f"Packet with timestamp {timestamp:18.7f} had flags: {ret.flags}", file=sys.stderr)
					if "HFO_LAST" in ret.flags:
						print(f"Packet had HFO_LAST flag set, triggering OpenVizslaReader reinit!", file=sys.stderr)
						self.shutdown()
						self.startup()
						return False
			except queue.Empty:
				break
		return True

pat_usbreset_device = re.compile("Number " +
	"(?P<busnum>\d+)\/(?P<devnum>\d+)  ID " +
	"(?P<vendorid>[0-9a-f]+):(?P<productid>[0-9a-f]+)  " +
	"(?P<devicename>.*)$")
def usbreset(device=None):
	if device is None:
		ret = []
		proc = subprocess.run(['usbreset'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
		lines = proc.stdout.decode().splitlines()
		for line in lines:
			mat = pat_usbreset_device.search(line)
			if mat:
				ret.append(mat.groupdict())
		return ret
	else:
		proc = subprocess.run(['usbreset', device])
		return proc.returncode


class DumpLogger:
	def __init__(self, log_file):
		self.log_file = log_file
		self.log_fh = None
	def line_handler(self, widget, timestamp, line):
		if self.log_fh is None:
			self.log_fh = open(self.log_file, "a")
		print(f"{timestamp} {line}", file=self.log_fh)
	def packet_handler(self, widget, timestamp, packet):
		if self.log_fh is None:
			self.log_fh = open(self.log_file, "a")
		print(f"{timestamp:18.7f} {packet.to_json()}", file=self.log_fh)
	def shutdown(self):
		if self.log_fh is not None:
			self.log_fh.close()
			self.log_fh = None
	

def line_dump_handler(widget, timestamp, line):
	print(f"{timestamp:18.7f} {line}")

def packet_dump_handler(widget, timestamp, packet):
	print(f"{timestamp:18.7f} {packet.to_json()}")
	



if __name__ == '__main__':
	config_basedir = mister_viz.get_yaml_basedir()
	available_modules = [ os.path.splitext(x)[0][len("openvizsla_"):] for x in os.listdir(config_basedir) if os.path.splitext(x)[1] == ".py" ]
	print(f"Available modules: {available_modules}")
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("module_name", action="store", choices=available_modules, help="Translation module to invoke")
	parser.add_argument("-l", "--log-file", action="store", dest="log_file", default=None, help="Write usb dump to log file LOG_FILE. Use magic name \":auto:\" to auto-create based on time and date.")
	parser.add_argument("-p", "--ptt", action="store", dest="ptt_state", default=None, help="Use this state as the push-to-talk button.  Format: type:name:minval:maxval")
	parser.add_argument("-c", "--console", action="store_true", dest="do_console", default=False, help="Spawn REPL on stdin/stdout")
	parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
	parser.add_argument("--linedump", action="store_true", dest="line_dump", default=False, help="Write usb dump to stdout.")
	args = parser.parse_args()

	module_path = os.path.join(config_basedir, f"openvizsla_{args.module_name}.py")

	import importlib.util
	spec = importlib.util.spec_from_file_location("abcxyz", module_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)

	if args.log_file == ':auto:':
		nao = datetime.datetime.now()
		naostr = nao.strftime("%F %T").replace(":", "_")
		log_file = f"openvizsla__{naostr}.log"
	else:
		log_file = args.log_file

	#loop = GLib.MainLoop()
	sniffer = None
	reader = None
	sniffer = OpenVizslaSniffer()
	#reader = OpenVizslaReader()
	stub = mister_viz.MisterVizStub()
	stub.debug = args.debug
	res = mister_viz.SvgControllerResources(os.path.join(mister_viz.get_yaml_basedir(), module.svg_filename))
	window = mister_viz.MisterVizWindow(stub, controller_resource=res)
	stub.windows[window.window_id] = window
	translator = module.Translator(res)

	def translator_dirty_handler(widget):
		#print(f"{time.time()} translator_dirty_handler()", file=sys.stderr)
		window.darea.queue_draw()
		widget.reset_dirty()

	translator.connect("dirty", translator_dirty_handler)

	global angle
	angle = 0

	def periodic_handler():
		global angle
		global window
		global res
		angle += 1
		while angle >= 360:
			angle -= 360
		newpoint = plot_course((127, 127), angle, 127)
		#print(newpoint)
		res.sticks['lstick'].x_axis.set_value(newpoint[0])
		res.sticks['lstick'].y_axis.set_value(newpoint[1])
		window.darea.queue_draw()
		return True
	
	#GLib.timeout_add(int(1000 / 60), periodic_handler)

	if args.ptt_state is not None:
		print(f"Setting up push-to-talk on {args.ptt_state}", file=sys.stderr)
		ptt_widget = mister_viz.JackPushToTalk()
		frags = args.ptt_state.split(":")
		ptt_swtype = frags[0]
		ptt_swname = frags[1]
		ptt_minval = int(frags[2])
		ptt_maxval = int(frags[3])
		for k in 'ptt_swtype ptt_swname ptt_minval ptt_maxval'.split():
			print(f"  {k}: {globals()[k]}", file=sys.stderr)
		if ptt_swtype == 'axis':
			control = res.axes[ptt_swname]
		elif ptt_swtype == 'button':
			control = res.buttons[ptt_swname]

		def ptt_handler(widget):
			if control.value >= ptt_minval and control.value <= ptt_maxval:
				ptt_widget.set_value(True)
			else:
				ptt_widget.set_value(False)

		translator.connect("dirty", ptt_handler)

	

	

	if log_file is not None:
		print(f"Logging to {log_file}", file=sys.stderr)
		dumper = DumpLogger(log_file)
		if sniffer is not None:
			sniffer.connect("line", dumper.line_handler)
		if reader is not None:
			reader.connect("packet", dumper.packet_handler)
	parser = OpenVizslaParser()
	parser.connect("event", translator.event_handler)
	if sniffer is not None:
		sniffer.connect("line", parser.line_handler)
		if args.line_dump:
			sniffer.connect("line", line_dump_handler)
	if reader is not None:
		reader.connect("packet", parser.packet_handler)
		if args.line_dump:
			reader.connect("packet", packet_dump_handler)

	#reader.connect("packet", packet_printer)

	def shutdown_handler():
		if sniffer is not None:
			sniffer.shutdown()
		if reader is not None:
			reader.shutdown()
		if log_file is not None:
			dumper.shutdown()
		stub.shutdown()
		Gtk.main_quit()


	def sigint_handler(sig, frame):
		print("SIGINT HANDLER CALLED")
		shutdown_handler()
	
	def window_destroy_handler(window):
		shutdown_handler()

	import signal
	signal.signal(signal.SIGINT, sigint_handler)
	window.connect("destroy", window_destroy_handler)
	if sniffer is not None:
		sniffer.startup()
	if reader is not None:
		reader.startup()
	if args.do_console:
		import debugrepl, glib_editingline
		cli = glib_editingline.CliInterpreter(None, namespace=globals())
		def cli_controlc_handler(*args):
			shutdown_handler()

		cli.connect("control-c", cli_controlc_handler)
	Gtk.main()
