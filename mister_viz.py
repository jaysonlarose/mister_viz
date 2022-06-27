#!/usr/bin/env python3

import os, sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, GObject
import cairosvg, cairo, io, PIL.Image, struct, yaml, lxml.etree, copy, math, socket, subprocess, atexit, multiprocessing, queue, time, traceback, psutil

global print
global orig_print

try:
	import jack
	jack_disabled = False
except ImportError:
	jack_disabled = True

try:
	from evdev import InputEvent as evdev_InputEvent
	from evdev.util import categorize as evdev_categorize
	from evdev import ecodes
except ImportError:
	print("ImportError using evdev, faking it")
	from fake_events import InputEvent as evdev_InputEvent
	from fake_events import categorize as evdev_categorize
	import fake_ecodes as ecodes

def get_userconfig_dir():# {{{
	"""
	I wrote this because apparently some desktop environments don't
	bother setting XDG_CONFIG_HOME. So what this does, is it uses
	that environment variable if it exists, otherwise returns a
	canned reply that points to ~/.config.
	"""
	if 'XDG_CONFIG_HOME' in os.environ:
		return os.environ['XDG_CONFIG_HOME']
	return os.path.join(os.environ['HOME'], '.config')
# }}}
def xmlattrib_to_dict(attrib):# {{{
	if len(attrib) == 0:
		return {}
	return dict([ x.split(':', 1) for x in attrib.split(';') ])
# }}}
def dict_to_xmlattrib(d):# {{{
	return ';'.join([ f"{key}:{value}" for key, value in d.items() ])
# }}}
def get_xmlsubattrib(tag, key, subkey):# {{{
	if key not in tag.attrib:
		return None
	d = xmlattrib_to_dict(tag.attrib[key])
	if subkey not in d:
		return None
	return d[subkey]
# }}}
def set_xmlsubattrib(tag, key, subkey, value):# {{{
	if key not in tag.attrib:
		d = {}
	else:
		d = xmlattrib_to_dict(tag.attrib[key])
	d[subkey] = value
	tag.attrib[key] = dict_to_xmlattrib(d)
# }}}

def resize_aspect(orig_width, orig_height, width=None, height=None, factor=None): # {{{
	if width is not None:
		factor = float(width) / float(orig_width)
		height = int(orig_height * factor)
	elif height is not None:
		factor = float(height) / float(orig_height)
		width = int(orig_width * factor)
	else:
		width = int(orig_width * factor)
		height = int(orig_height * factor)
	return width, height, factor
# }}}
def pil_to_pixbuf(img, transposition=None, mode='RGB'): # {{{
	i = img
	if transposition is not None:
		i = i.transpose(transposition)
	bytesperpx = 3
	if mode == "RGB":
		bytesperpx = 3
		has_alpha = False
	elif mode == "RGBA":
		bytesperpx = 4
		has_alpha = True
	else:
		raise RuntimeError("Not smart enough to convert to that!")
	if i.mode != mode:
		i = i.convert(mode=mode)
	buf = i.tobytes()
	pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes.new(buf), GdkPixbuf.Colorspace.RGB, has_alpha, 8, i.width, i.height, i.width * bytesperpx)
	return pixbuf
# }}}
def walk(tree):# {{{
	ret = []
	for elem in tree:
		ret.append(elem)
		ret.extend(walk(elem))
	return ret
# }}}
def mangle(tree, state, debug=False):# {{{
	"""
	Steps recursively through the xml tree and inspects the "g" elements, aka layers.

	If the g element contains an attribute named "data-state", the value of that attribute
	is compared against the supplied state parameter.
	If the two match, that element, along with all of its parent nodes, will all have their
	'style' attribute changed to 'display:inline' if they were previously 'display:none'.
	If the two don't match, the element is just straight up deleted.

	If the g element doesn't contain a data-state attribute, it's checked to see if it has
	a style attrib. A style of 'display:none' indicates that this was a layer that started
	out hidden, so we just delete it.
	A style of 'display:inline' is handled differently depending on wheter the state parameter
	is None or not. If state is None, it means we're processing the background SVG, so the
	element gets left as-is.  If state is defined, then we're processing a control element,
	so we set the style to 'display:none'. (After we finish this pass, we'll step through
	the g layer elements again. When we do that, any of the elements that still have their
	style set as 'display:none' don't have any children that we're supposed to be rendering,
	so it's safe to delete them.
	"""
	for elem in tree[:]:
		if debug:
			print(f"state {state} inspecting elem {elem}")
		if elem.tag == SVG_PREFIX + 'g':
			display_val = get_xmlsubattrib(elem, 'style', 'display')
			if 'data-state' in elem.attrib:
				if elem.attrib['data-state'] == state:
					parent = elem
					while parent is not None:
						parent_display_val = get_xmlsubattrib(parent, 'style', 'display')
						if parent_display_val == 'none':
							set_xmlsubattrib(parent, 'style', 'display', 'inline')
						parent = parent.getparent()
				else:
					elem.getparent().remove(elem)
					continue
			elif state is not None:
				if display_val == 'none':
					elem.getparent().remove(elem)
				else:
					set_xmlsubattrib(elem, 'style', 'display', 'none')
		mangle(elem, state)
# }}}

def devastate(tree, debug=False):# {{{
	"""
	This performs the third processing pass.  `mangle()` performs the second, and the
	first happens in `svg_state_split()`.

	Namely, this goes through and finds any "g" elements that their 'style' attrib set to
	"display:none", and performs a coup de grace on them.
	"""
	for elem in tree[:]:
		if elem.tag == SVG_PREFIX + 'g':
			if get_xmlsubattrib(elem, 'style', 'display') == 'none':
				elem.getparent().remove(elem)
				continue
		devastate(elem)
# }}}

MISTER_STRUCT = "<BHHHHi"
MISTER_STRUCT_SIZE = struct.calcsize(MISTER_STRUCT)
PTT_ALSA_DEVICE = "hw:CARD=Device,DEV=0"
PTT_SAMPLE_RATE = 48000
PTT_CHANNEL_QTY = 1
PTT_INPUT_NAME = "ptt_mic"
PTT_INPUT_PREFIX = f"{PTT_INPUT_NAME}:"
PTT_OUTPUT_PREFIX = "OBS Jack 1:"
#PTT_OUTPUT_PREFIX = "sc_compressor_stereo:in_"
SVG_PREFIX = '{http://www.w3.org/2000/svg}'
DUMP_RENDERS = False
SOCKET_KEEPALIVE_INTERVAL = 5000
SOCKET_KEEPALIVE_TIMEOUT  = 5000
OP_INPUT = 0
OP_PING  = 1
OP_PONG  = 2

def translate_constrainedint(sensor_val, in_from, in_to, out_from, out_to):# {{{
	out_range = out_to - out_from
	in_range = in_to - in_from
	in_val = sensor_val - in_from
	val=(float(in_val) / in_range) * out_range
	out_val = int(out_from + val)
	if out_val < out_from:
		out_val = out_from
	if out_val > out_to:
		out_val = out_to

	#import sys
	#print(f"{sensor_val} {in_from} {in_to} {out_from} {out_to} {out_val}", file=sys.stderr)
	return out_val
# }}}

class Stick:# {{{
	def __init__(self):
		self.x_axis = None
		self.y_axis = None
		self.has_button = False
		self.reset()
	def reset(self):
		pass
# }}}
class MisterButton:# {{{
	def __init__(self, element):
		self.element = element
		self.ptt = None
		self.reset()
	def set_value(self, value):
		self.value = value
		if self.ptt is not None:
			self.ptt.set_value(value)
	def get_state(self):
		if self.value > 0:
			return set([self.element])
		return set()
	def all_states(self):
		return set([self.element])
	def reset(self):
		self.value = 0
# }}}
class MisterAxis:# {{{
	def __init__(self, spec):
		self.spec = spec
		self.value = None
		self.states = set()
		self.rangemap = []
		self.is_stick = False
		self.is_binary = False
		self.stickname = None
		if 'binary' in self.spec:
			self.is_binary = True
			for k, v in self.spec['binary'].items():
				self.rangemap.append([v[0], v[1], k])
		if 'stick' in self.spec:
			for k, v in self.spec['stick'].items():
				self.stickname = k
				for k, v in v.items():
					self.stickaxis = k
					self.minval, self.minpos = v[0]
					self.maxval, self.maxpos = v[1]
			self.is_stick = True
		self.reset()
	def set_value(self, value):
		self.value = value
	def get_state(self):
		ret = set()
		if self.value is None:
			return ret
		if self.is_binary:
			for fromval, toval, elem in self.rangemap:
				if self.value >= fromval and self.value <= toval:
					ret.add(elem)
		return ret
	def all_states(self):
		ret = set()
		if self.is_binary:
			for fromval, toval, elem in self.rangemap:
				ret.add(elem)
		return ret
	def reset(self):
		pass
# }}}

class JackPushToTalk:# {{{
	def __init__(self, client_name, input_prefix, output_prefix):
		self.jack_client = jack.Client(client_name)
		self.input_prefix = input_prefix
		self.output_prefix = output_prefix
		self.value = 0
		self.jack_client.set_port_registration_callback(self.port_reg_callback)
		self.enumerate_ports()
	def enumerate_ports(self):
		print("enumerating jack ports")
		self.jack_inputs = [ x for x in self.jack_client.get_ports() if x.name.startswith(self.input_prefix) ]
		self.jack_outputs = [ x for x in self.jack_client.get_ports() if x.name.startswith(self.output_prefix) ]
		self.set_value(self.value)
# }}}
	def port_reg_callback(self, port, registering):# {{{
		"""
		port_reg_callback originates from the jack client object
		and probably lives in a different thread/process.

		we use it to schedule a call to port_reg_handler, so it's
		all happy with GLib.
		"""
		argies = [port, registering]
		GLib.idle_add(self.port_reg_handler, argies)
	def port_reg_handler(self, argies):
		self.enumerate_ports()
	def set_value(self, value):
		self.value = value
		for inport in self.jack_inputs:
			for outport in self.jack_outputs:
				if self.value == 1:
					print(f"connecting ports: {inport.name} -> {outport.name}")
					try:
						self.jack_client.connect(inport, outport)
					except jack.JackErrorCode:
						pass
				else:
					print(f"disconnecting ports: {inport.name} -> {outport.name}")
					try:
						self.jack_client.disconnect(inport, outport)
					except jack.JackErrorCode:
						pass
# }}}
def svg_to_pixbuf(svg_bytes, scale_factor):# {{{
	fobj = io.BytesIO(cairosvg.svg2png(svg_bytes, scale=scale_factor))
	pil_img = PIL.Image.open(fobj)
	pixbuf = pil_to_pixbuf(pil_img, mode="RGBA")
	return pixbuf
# }}}
def svg_state_split(svg_bytes, debug=False):# {{{
	ret = {}
	tree = lxml.etree.fromstring(svg_bytes)
	flat = walk(tree)
	states = []
	for elem in flat:
		if elem.tag == SVG_PREFIX + 'g':
			ds = elem.get("data-state", None)
			if ds is not None:
				states.append(ds)
				set_xmlsubattrib(elem, 'style', 'display', 'none')
	states.append(None)
	for state in states:
		chip = copy.deepcopy(tree)
		mangle(chip, state, debug=debug)
		devastate(chip, debug=debug)
		ret[state] = lxml.etree.tostring(chip)
	return ret
# }}}

class ControllerResources:# {{{
	def __init__(self, yaml_filename):# {{{
		self.base_dir = os.path.dirname(yaml_filename)
		base = os.path.splitext(os.path.basename(yaml_filename))[0]
		self.base_name = os.path.splitext(base)[0]
		self.base_yaml = open(yaml_filename, "r").read()
		self.config = yaml.load(self.base_yaml, Loader=yaml.Loader)
		svg_filename = os.path.join(self.base_dir, f"{self.config['svg']}")
		self.base_svg  = open(svg_filename, "rb").read()

		c = self.config
		self.buttons = {}
		self.axes = {}
		self.sticks = {}
		self.vid = c['vid']
		self.pid = c['pid']
		if 'buttons' in c:
			for k, v in c['buttons'].items():
				self.buttons[k] = MisterButton(v)
		if 'axes' in c:
			for k, v in c['axes'].items():
				self.axes[k] = MisterAxis(v)
		for axis in self.axes.values():
			if axis.is_stick:
				if axis.stickname not in self.sticks:
					self.sticks[axis.stickname] = Stick()
				if axis.stickaxis == 'x':
					self.sticks[axis.stickname].x_axis = axis
				elif axis.stickaxis == 'y':
					self.sticks[axis.stickname].y_axis = axis
		all_buttons = set()
		for x in self.buttons.values():
			all_buttons |= x.all_states()
		for x in self.axes.values():
			all_buttons |= x.all_states()
		for k, v in self.sticks.items():
			if k in all_buttons:
				v.has_button = True
		# Process svg file
		self.svgs = svg_state_split(self.base_svg)

	def dump_svgs(self):		
		for k in self.svgs:
			outfile = f"{k}.svg"
			open(outfile, "wb").write(self.svgs[k])
# }}}
# }}}
class proppadict(dict):# {{{
	def __getattr__(self, attr):
		if attr in self:
			return self[attr]
		else:
			raise AttributeError
	def __setattr__(self, attr, val):
			self[attr] = val
	def __delattr__(self, attr):
			del(self[attr])
	def copy(self):
		return proppadict(self.items())
# }}}
def scaler_queue_payload_to_pixbuf(payload):# {{{
	ret = proppadict()
	ret.key, img_packet, ret.factor = payload
	img_bytes, ret.width, ret.height, ret.x_offset, ret.y_offset = img_packet
	if DUMP_RENDERS:
		img = PIL.Image.frombytes("RGBA", (ret.width, ret.height), img_bytes)
		img.save(f"mister_viz__{ret.key}.png")
	ret.pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes(img_bytes), GdkPixbuf.Colorspace.RGB, True, 8, ret.width, ret.height, ret.width * 4)
	return ret
# }}}
def autocrop(pil_img):# {{{
	"""
	Takes an RGBA PIL image, crops out all of the transparent bits,
	and returns the cropped image along with its x and y offset.
	"""
	# Crop left hand side
	x_offset = 0
	img = pil_img
	while x_offset < img.width:
		img_slice = img.crop((x_offset, 0, x_offset + 1, img.height))
		img_slice_bytes = img_slice.tobytes()
		slice_height = img_slice.height * 4
		if sum([ img_slice_bytes[x] for x in range(3, slice_height, 4) ]) == 0:
			x_offset += 1
		else:
			break
	# Crop top side
	img = img.crop((x_offset, 0, img.width, img.height))
	y_offset = 0
	while y_offset < img.height:
		img_slice = img.crop((0, y_offset, img.width, y_offset + 1))
		img_slice_bytes = img_slice.tobytes()
		slice_width = img_slice.width * 4
		if sum([ img_slice_bytes[x] for x in range(3, slice_width, 4) ]) == 0:
			y_offset += 1
		else:
			break
	# Crop right hand side
	img = img.crop((0, y_offset, img.width, img.height))
	right_offset = img.width
	while right_offset > 0:
		img_slice = img.crop((right_offset - 1, 0, right_offset, img.height))
		img_slice_bytes = img_slice.tobytes()
		slice_height = img_slice.height * 4
		if sum([ img_slice_bytes[x] for x in range(3, slice_height, 4) ]) == 0:
			right_offset -= 1
		else:
			break
	# Crop bottom
	img = img.crop((0, 0, right_offset, img.height))
	bottom_offset = img.height
	while bottom_offset > 0:
		img_slice = img.crop((0, bottom_offset - 1, img.width, bottom_offset))
		img_slice_bytes = img_slice.tobytes()
		slice_width = img_slice.width * 4
		if sum([ img_slice_bytes[x] for x in range(3, slice_width, 4) ]) == 0:
			bottom_offset -= 1
		else:
			break
	img = img.crop((0, 0, img.width, bottom_offset))
	return (img, x_offset, y_offset)
# }}}
class MultiprocSvgScaler(GObject.GObject):# {{{
	__gsignals__ = {
		"result": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
	}
	def __init__(self, process_count=multiprocessing.cpu_count()):# {{{
		super().__init__()
		self.process_count = process_count
		self.processes = []
		self.inq = multiprocessing.Queue()
		self.outq = multiprocessing.Queue()
		for i in range(self.process_count):
			proc_dict = {}
			procargs = [self.inq, self.outq]
			if sys.platform != "win32":
				proc_dict['pipe'], pipe_sink = multiprocessing.Pipe(duplex=False)
				procargs.append(pipe_sink)
				GLib.io_add_watch(proc_dict['pipe'].fileno(), GLib.IO_IN, self.pipe_handler)
			else:
				procargs.append(None)
			proc = multiprocessing.Process(target=scaler_process_func, args=procargs) 
			proc_dict['proc'] = proc
			self.processes.append(proc_dict)
			proc.start()
		if sys.platform == "win32":
			self.last_poll_activity = time.monotonic()
			self.queue_poller_handle = GLib.timeout_add(250, self.queue_poller)
# }}}
	def pipe_handler(self, fd, flags):# {{{
		for proc_dict in self.processes:
			if proc_dict['pipe'].fileno() == fd:
				proc_dict['pipe'].recv()
				break
		payload = self.outq.get()
		stuff = scaler_queue_payload_to_pixbuf(payload)
		self.emit("result", [stuff.key, stuff.pixbuf, stuff.x_offset, stuff.y_offset, stuff.factor])
		return True
# }}}
	def queue_poller(self):# {{{
		if self.queue_poller_handle is not None:
			GLib.source_remove(self.queue_poller_handle)
			self.queue_poller_handle = None
		try:
			while True:
				payload = self.outq.get(block=False, timeout=0)
				self.last_poll_activity = time.monotonic()
				stuff = scaler_queue_payload_to_pixbuf(payload)
				self.emit("result", [stuff.key, stuff.pixbuf, stuff.x_offset, stuff.y_offset, stuff.factor])
		except queue.Empty:
			pass
		nao = time.monotonic()
		nextpoll_interval = 250
		if nao - self.last_poll_activity < 5.0:
			nextpoll_interval = 100
		if nao - self.last_poll_activity < 2.5:
			nextpoll_interval = 50
		if nao - self.last_poll_activity < 1.0:
			nextpoll_interval = 10
		if nao - self.last_poll_activity < 0.5:
			nextpoll_interval = 2
		self.queue_poller_handle = GLib.timeout_add(nextpoll_interval, self.queue_poller)
		return False
# }}}
	def scale_svg(self, key, svg_bytes, factor):# {{{
		self.inq.put([key, svg_bytes, factor])
# }}}
	def shutdown(self, *args):# {{{
		while len(self.processes) > 0:
			for proc_dict in list(self.processes):
				if proc_dict['proc'].is_alive():
					proc_dict['proc'].kill()
				else:
					proc_dict['proc'].join()
					if 'pipe' in proc_dict:
						proc_dict['pipe'].close()
					self.processes.remove(proc_dict)
# }}}
# }}}
def scaler_process_func(inq, outq, pipe=None):# {{{
	while True:
		try:
			payload = inq.get(block=True)
			key, svg, factor = payload
			try:
				png_bytes = cairosvg.svg2png(svg, scale=factor)
			except ValueError:
				continue
			fobj = io.BytesIO(png_bytes)
			img = PIL.Image.open(fobj)
			if img.mode != "RGBA":
				img = img.convert(mode="RGBA")
			cropped_img, x_offset, y_offset = autocrop(img)
			img_packet = [cropped_img.tobytes(), cropped_img.width, cropped_img.height, x_offset, y_offset]
			outq.put([key, img_packet, factor])
			if pipe is not None:
				pipe.send(b"!")
		except queue.Empty:
			break
# }}}

class MisterViz:# {{{
	def __init__(self, hostname, do_window=True, debug=False):# {{{
		self.hostname = hostname
		self.sock = None
		self.debug = debug
		self.connection_status = "disconnected"
		self.connect_handle = None
		self.socket_handle = None
		if self.hostname is not None:
			self.connect_handle = GLib.idle_add(self.connect_handler)
		self.window = None
		self.seen_window = None
		self.windows = {}
		self.res_lookup = {}
		self.seen_events = {}
		# keepalive_state:
		# * "idle" - waiting to send ping (keepalive_handle is for timer to send next ping)
		# * "wait" - waiting for pong (keepalive handle is for timer to detect timeout)
		self.keepalive_state = None
		self.keepalive_handle = None


		if sys.platform == "win32":
			my_pid = os.getpid()
			vizprocs = [ x for x in psutil.process_iter() if x.name() == "mister_viz.exe" and x.pid != my_pid ]
			if len(vizprocs) > 0:
				dialog = Gtk.MessageDialog(parent=None, type=Gtk.MessageType.WARNING, message_format="It looks like some other mister_viz processes are running. This is usually indicative of a mister_viz session that bit the shed, or you tried to run mister_viz twice. Click OK to kill the other processes and continue running, or Cancel to leave them alone and quit.")
				dialog.add_button(Gtk.STOCK_OK, Gtk.ResponseType.OK)
				dialog.add_button(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL)
				response = dialog.run()
				dialog.destroy()
				if response == Gtk.ResponseType.OK:
					vizprocs = [ x for x in psutil.process_iter() if x.name() == "mister_viz.exe" and x.pid != my_pid ]
					while len(vizprocs) > 0:
						[ x.kill() for x in vizprocs ]
						vizprocs = [ x for x in psutil.process_iter() if x.name() == "mister_viz.exe" and x.pid != my_pid ]
				elif response == Gtk.ResponseType.CANCEL:
					sys.exit(0)

		self.procs = []
		self.scaler = MultiprocSvgScaler(process_count=1)
		self.scaler.connect("result", self.scaler_handler)


		if do_window:
			self.window = Gtk.Window()
			self.window.connect("destroy", self.ownwindow_destroy_handler)
			vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
			hbox.pack_start(Gtk.Label(label="Host:"), False, False, 0)
			self.hostname_entry = Gtk.Entry()
			self.hostname_entry.connect("activate", self.connect_button_handler)
			hbox.pack_start(self.hostname_entry, False, False, 0)
			self.connect_button = Gtk.Button(label="Connect")
			self.connect_button.connect("clicked", self.connect_button_handler)
			hbox.pack_start(self.connect_button, False, False, 0)
			vbox.pack_start(hbox, False, False, 0)
			sw = Gtk.ScrolledWindow()
			tv = Gtk.TextView()
			tv.set_editable(False)
			sw.add(tv)
			self.scroll = sw
			self.textbuf = tv.get_buffer()
			self.textbuf_max_lines = 10000
			vbox.pack_start(sw, True, True, 0)
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
			but = Gtk.Button(label="Clear")
			but.connect("clicked", self.clear_button_handler)
			hbox.pack_start(but, True, True, 0)
			but = Gtk.Button(label="Copy")
			but.connect("clicked", self.copy_button_handler)
			hbox.pack_start(but, True, True, 0)
			but = Gtk.Button(label="Seen")
			but.connect("clicked", self.seen_button_handler)
			hbox.pack_start(but, True, True, 0)
			self.seen_but = but
			self.seen_but.set_sensitive(False)
			vbox.pack_start(hbox, False, False, 0)
			self.window.add(vbox)
			self.window.resize(640, 480)
			self.window.show_all()
			global print
			global orig_print
			orig_print = print
			print = self.window_print

			def handle_exception(exc_type, exc_value, exc_traceback):
				if isinstance(exc_type, KeyboardInterrupt):
					sys.__excepthook__(exc_type, exc_value, exc_traceback)
					return
				for line in traceback.format_exc().splitlines():
					print(line)
			sys.excepthook = handle_exception
		atexit.register(self.shutdown)

		if not jack_disabled:
			self.setup_joystick_ptt()
		else:
			self.ptt = None


		controller_resources = {}
		# Read all yaml files in the script dir except those that start with '_'
		if sys.platform == "win32":
			yaml_basedir="c:\\mister_viz"
			import winreg
			software_key = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, "SOFTWARE\\", access=winreg.KEY_READ | winreg.KEY_WRITE)
			vendor_key = winreg.CreateKeyEx(software_key, "Interlaced", access=winreg.KEY_READ | winreg.KEY_WRITE)
			product_key = winreg.CreateKeyEx(vendor_key, "MiSTer Viz", access=winreg.KEY_READ | winreg.KEY_WRITE)
			try:
				last_host = winreg.QueryValueEx(product_key, "last_host")[0]
				self.hostname_entry.set_text(last_host)
			except FileNotFoundError:
				pass
			product_key.Close()
			vendor_key.Close()
			software_key.Close()
			yaml_basedir = os.path.expanduser("~/mister_viz")
		else:
			yaml_basedir = os.path.join(get_userconfig_dir(), "mister_viz")
		print(f"yaml basedir: {yaml_basedir}")
		if not os.path.exists(yaml_basedir):
			print(f"yaml basedir not found, creating it.")
			os.makedirs(yaml_basedir)
		yaml_files = [ x for x in [ os.path.join(yaml_basedir, x) for x in [ x for x in os.listdir(yaml_basedir) if os.path.splitext(x)[1] == '.yaml' and not x.startswith('_') ] ] if os.path.isfile(x) ]
		print(f"yaml files: {yaml_files}")
		if len(yaml_files) == 0:
			print(f"No YAML files found in {yaml_basedir}! Put some YAML and SVG files in there and try running me again.")

		resources = {}
		for yaml_file in yaml_files:
			resource = ControllerResources(yaml_file)
			if resource.config['name'] not in resources:
				resources[resource.config['name']] = {}
			print(f"Found resource \"{resource.config['name']}\"")
			resources[resource.config['name']] = resource

		self.resources = resources

		for rname in self.resources:
			res = self.resources[rname]
			config = res.config
			if config['vid'] not in self.res_lookup:
				self.res_lookup[config['vid']] = {}
			if config['pid'] not in self.res_lookup[config['vid']]:
				self.res_lookup[config['vid']][config['pid']] = res
# }}}
	def scaler_handler(self, scaler, payload):# {{{
		key, pixbuf, x_offset, y_offset, factor = payload
		vid, pid, state = key
		key = f"{vid:04x}:{pid:04x}"
		if key in self.windows:
			self.windows[key].pixbuf_receive_handler(state, pixbuf, x_offset, y_offset, factor)
# }}}
	def window_print(self, *values, sep=' ', end='', file=None, **kwargs):# {{{
		msg = sep.join([ str(x) for x in values ])
		if file is not None and file is not sys.stdout and file is not sys.stderr:
			file.write(msg + "\n")
			return
		prefix = f"{time.monotonic():10.2f} "
		self.textbuf.insert(self.textbuf.get_end_iter(), prefix + msg + "\n")
		line_count = self.textbuf.get_line_count()
		if line_count > self.textbuf_max_lines:
			self.textbuf.delete(self.textbuf.get_start_iter(), self.textbuf.get_iter_at_line(line_count - self.textbuf_max_lines))
		GLib.idle_add(self.scroll_handler)
# }}}
	def scroll_handler(self):# {{{
		vadj = self.scroll.get_vadjustment()
		vadj.set_value(vadj.get_upper())
# }}}
	def clear_button_handler(self, widget):# {{{
		self.textbuf.delete(self.textbuf.get_start_iter(), self.textbuf.get_end_iter())
# }}}
	def copy_button_handler(self, widget):# {{{
		text = self.textbuf.get_text(self.textbuf.get_start_iter(), self.textbuf.get_end_iter(), True)
		clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
		clipboard.set_text(text, len(text.encode()))
	# }}}
	def seen_button_handler(self, widget):# {{{
		print("seen button clicked")
		if self.seen_window is None:
			print("Spawning seen events window")
			self.seen_window = MisterSeenEventsWindow(self)
			self.seen_window.connect("destroy", self.window_destroy_handler)
	# }}}
	def connect_button_handler(self, widget):# {{{
		self.hostname = self.hostname_entry.get_text()
		print(f"connection status: {self.connection_status}")
		if self.connection_status == "disconnected":
			self.connect_handle = GLib.idle_add(self.connect_handler)
		elif self.connection_status == "connecting":
			self.disconnect()
		elif self.connection_status == "connected":
			self.disconnect()
			if self.window is not None:
				for key in list(self.windows):
					self.windows[key].destroy()
# }}}
	def disconnect(self, reconnect=False):# {{{
		# Tear down the socket
		if self.sock is not None:
			self.sock.close()
		self.sock = None
		# Remove the io watch for the socket
		if self.socket_handle is not None:
			GLib.source_remove(self.socket_handle)
			self.socket_handle = None
		# Reset button state on any open viz windows
		for win in self.windows.values():
			win.reset()
		# Update connect button and hostname entrybox
		if self.window is not None:
			if not reconnect:
				self.connect_button.set_label("Connect")
				self.hostname_entry.set_sensitive(True)
			else:
				self.connect_button.set_label("Cancel")
		# Tear down the keepalive stuff
		if self.keepalive_handle is not None:
			GLib.source_remove(self.keepalive_handle)
			self.keepalive_handle = None
			self.keepalive_state  = None
		if not reconnect:
			self.connection_status = "disconnected"
		else:
			self.connection_status = "connecting"
			if self.connect_handle is not None:
				GLib.source_remove(self.connect_handle)
				self.connect_handle = None
			self.connect_handle = GLib.timeout_add(100, self.connect_handler)
			
		print("Disconnected!")
	# }}}
	def setup_joystick_ptt(self):# {{{
		procargs = ['alsa_in', '-d', PTT_ALSA_DEVICE, '-c', f"{PTT_CHANNEL_QTY}", '-j', PTT_INPUT_NAME, '-r', f"{PTT_SAMPLE_RATE}"]
		proc = subprocess.Popen(procargs, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
		self.procs.append(proc)
		self.ptt = JackPushToTalk("joystick_ptt", PTT_INPUT_PREFIX, PTT_OUTPUT_PREFIX)
	# }}}
	def connect_handler(self):# {{{
		if self.connect_handle is not None:
			GLib.source_remove(self.connect_handle)
			self.connect_handle = None
		if self.socket_handle is not None:
			GLib.source_remove(self.socket_handle)
			self.socket_handle = None
		if self.window is not None:
			self.connect_button.set_label("Cancel")
			self.hostname_entry.set_text(self.hostname)
			self.hostname_entry.set_sensitive(False)
		self.connection_status = "connecting"
		try:
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
			print("Connecting...")
			sock.connect((self.hostname, 22101))
			print("Connected!")
			if self.window is not None:
				self.connect_button.set_label("Disconnect")
			self.connection_status = "connected"
			self.sock = sock
			self.socket_handle = GLib.io_add_watch(self.sock, GLib.IO_IN | GLib.IO_HUP, self.socket_handler)
			if self.keepalive_handle is not None:
				GLib.source_remove(self.keepalive_handle)
				self.keepalive_handle = None
			self.keepalive_handle = GLib.timeout_add(10000, self.keepalive_handler)
			return False
		except OSError:
			print("Connection failed!")
			if self.connection_status == "connecting":
				self.connect_handle = GLib.timeout_add(100, self.connect_handler)
			return False
	# }}}
	def keepalive_handler(self):# {{{
		if not self.sock._closed:
			self.sock.send(bytes([OP_PING]))
		if self.keepalive_handle is not None:
			GLib.source_remove(self.keepalive_handle)
			self.keepalive_handle = None
		self.keepalive_state = "wait"
		self.keepalive_handle = GLib.timeout_add(SOCKET_KEEPALIVE_TIMEOUT, self.keepalive_timeout_handler)
	# }}}
	def keepalive_timeout_handler(self):# {{{
		if self.connect_handle is not None:
			GLib.source_remove(self.connect_handle)
			self.connect_handle = None
		print("Timeout!")
		self.disconnect()
		if self.window is not None:
			self.connect_button.set_label("Cancel")
		
		self.connect_handle = GLib.timeout_add(100, self.connect_handler)
		return False
	# }}}
	def socket_handler(self, fd, flags):# {{{
		try:
			# Handle incoming data packet
			if flags & GLib.IO_IN:
				try:
					opcode_pkt = self.sock.recv(1)
					if len(opcode_pkt) == 0:
						data = b''
					elif opcode_pkt[0] == OP_PONG:
						if self.keepalive_handle is not None:
							GLib.source_remove(self.keepalive_handle)
							self.keepalive_handle = None
						self.keepalive_state = "idle"
						self.keepalive_handle = GLib.timeout_add(SOCKET_KEEPALIVE_INTERVAL, self.keepalive_handler)
						return True
					elif opcode_pkt[0] == OP_INPUT:
						data = self.sock.recv(MISTER_STRUCT_SIZE)
					else:
						print(f"Unknown opcode {opcode}")
						data = b''
				except ConnectionResetError:
					data = b''
				#print(f"got {len(data)} bytes")
				if len(data) == 0:
					self.disconnect()
					print("Disconnected!")
					self.connection_status = "connecting"
					if self.window is not None:
						self.connect_button.set_label("Cancel")
					if self.connect_handle is not None:
						GLib.source_remove(self.connect_handle)
						self.connect_handle = None
					self.connect_handle = GLib.timeout_add(100, self.connect_handler)
					return False
				vals = struct.unpack(MISTER_STRUCT, data)
				inputno = vals[0]
				vid = vals[1]
				pid = vals[2]
				key = f"{vid:04x}:{pid:04x}"
				event_vals = [0, 0] + list(vals[3:])
				event = evdev_categorize(evdev_InputEvent(*event_vals))
				superevent = event
				if hasattr(event, 'event'):
					event = event.event
				print_event = True
				if ecodes.EV[event.type] == 'EV_SYN':
					print_event = False
				if ecodes.EV[event.type] == 'EV_KEY':
					if event.value == 2:
						print_event = False
				if print_event:
					print(superevent)
					print(f"  input {inputno} {vid:04x}:{pid:04x}: {event}")
				if key in self.windows:
					win = self.windows[key]
					ev_type = ecodes.EV[event.type]
					if ev_type == 'EV_SYN':
						win.apply_event_queue()
					else:
						win.event_queue.append(event)
				else:
					if vid in self.res_lookup:
						if pid in self.res_lookup[vid]:
							print(f"Found resource for vid/pid {vid:04x}:{pid:04x}, instantiating window")
							win = MisterVizWindow(self.res_lookup[vid][pid], self)
							self.windows[key] = win
							win.connect("destroy", self.window_destroy_handler)
							if 'ptt' in win.res.config and self.ptt is not None:
								ptt_elem = win.res.config['ptt']
								if ptt_elem in win.res.buttons:
									win.res.buttons[ptt_elem].ptt = self.ptt

				update_seen_window = False
				if key not in self.seen_events:
					self.seen_events[key] = {}
					if not self.seen_but.get_sensitive():
						self.seen_but.set_sensitive(True)
					update_seen_window = True
				subkey = f"{event.type}:{event.code}"
				if subkey not in self.seen_events[key]:
					self.seen_events[key][subkey] = [event.value, event.value]
					update_seen_window = True
				else:
					if event.value < self.seen_events[key][subkey][0]:
						self.seen_events[key][subkey][0] = event.value
						update_seen_window = True
					if event.value > self.seen_events[key][subkey][1]:
						self.seen_events[key][subkey][1] = event.value
						update_seen_window = True

				if update_seen_window and self.seen_window is not None:
					GLib.idle_add(self.seen_window.update)
			# One of many ways a socket can signal that it's going away.
			elif flags & GLib.IO_HUP:
				self.disconnect(reconnect=True)
				return False

			return True
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
	def ownwindow_destroy_handler(self, window):# {{{
		self.window = None
		global print
		global orig_print
		print = orig_print
		orig_print = None
		if sys.platform == "win32":
			if len(self.hostname_entry.get_text()) > 0:
				import winreg
				software_key = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, "SOFTWARE\\", access=winreg.KEY_READ | winreg.KEY_WRITE)
				vendor_key = winreg.CreateKeyEx(software_key, "Interlaced", access=winreg.KEY_READ | winreg.KEY_WRITE)
				product_key = winreg.CreateKeyEx(vendor_key, "MiSTer Viz", access=winreg.KEY_READ | winreg.KEY_WRITE)
				winreg.SetValueEx(product_key, "last_host", 0, winreg.REG_SZ, self.hostname_entry.get_text())
				product_key.Close()
				vendor_key.Close()
				software_key.Close()
			
		if len(self.windows) == 0:
			self.shutdown()
# }}}
	def window_destroy_handler(self, window):# {{{
		if isinstance(window, MisterVizWindow):
			key = f"{window.res.config['vid']:04x}:{window.res.config['pid']:04x}"
			if key in self.windows:
				del self.windows[key]
		elif isinstance(window, MisterSeenEventsWindow):
			if self.seen_window is not None:
				self.seen_window = None
		if self.window == None and self.seen_window is None and len(self.windows) == 0:
			self.shutdown()
# }}}
	def shutdown(self):# {{{
		self.scaler.shutdown()
		for proc in self.procs:
			if isinstance(proc, subprocess.Popen):
				if proc.poll() is None:
					proc.terminate()
			else:
				raise ValueError("unknown proc type: {}".format(proc))
		for proc in list(self.procs):
			if isinstance(proc, subprocess.Popen):
				if proc.poll() is not None:
					self.procs.remove(proc)
			else:
				raise ValueError("unknown proc type: {}".format(proc))
		if len(self.procs) > 0:
			GLib.timeout_add(100, self.murder_handler)
		else:
			Gtk.main_quit()
	# }}}
	def murder_handler(self):# {{{
		for proc in self.procs:
			if isinstance(proc, subprocess.Popen):
				proc.kill()
			else:
				raise ValueError("unknown proc type: {}".format(proc))
		Gtk.main_quit()
		return False
	# }}}
# }}}
class MisterVizWindow(Gtk.Window):# {{{
	def __init__(self, controller_resource, parent):# {{{
		super().__init__()
		self.res = controller_resource
		self.parent = parent
		self.event_queue = []
		if 'name' in self.res.config:
			self.set_title(self.res.config['name'])
		if 'scale' in self.res.config:
			self.scalefactor = self.res.config['scale']
		else:
			self.scalefactor = 1.0
		#self.pixbufs = dict([ [x, None] for x in self.res.svgs.keys() ])
		self.pixbufs = {}
		self.resize_handler_id = None
		self.parent.scaler.scale_svg([self.res.vid, self.res.pid, None], self.res.svgs[None], 1.0)
		self.inflight = True

		#self.viz_width = self.pixbufs[None].get_width()
		#self.viz_height = self.pixbufs[None].get_height()
		self.viz_width = None
		self.viz_height = None
		self.win_dims = None
		self.resize_timer_id = None
		self.darea = Gtk.DrawingArea()
		self.darea.connect("draw", self.draw_handler)
		self.add(self.darea)
		#self.resize(int(self.viz_width * scalefactor), int(self.viz_height * scalefactor))
		#self.darea.connect("realize", self.darea_realize_handler)
		self.show_all()
		if DUMP_RENDERS:
			self.res.dump_svgs()
		self.reset()
	# }}}
	def pixbuf_receive_handler(self, key, pixbuf, x_offset, y_offset, scalefactor):# {{{
		print(f"Receiving pixbuf for state: {key} (scale factor {scalefactor})")
		if key is None:
			if self.viz_width is None and self.viz_height is None:
				self.viz_width = pixbuf.get_width()
				self.viz_height = pixbuf.get_height()
				if self.scalefactor != 1.0:
					self.parent.scaler.scale_svg([self.res.vid, self.res.pid, None], self.res.svgs[None], self.scalefactor)
					return
			self.pixbufs = {}
			self.pixbufs[key] = [pixbuf, x_offset, y_offset]
			self.darea.queue_draw()
			self.inflight = False
			self.scalefactor = scalefactor
			#self.resize_handler_id = self.connect("size-allocate", self.resize_handler)
			if self.resize_handler_id is not None:
				self.disconnect(self.resize_handler_id)
				self.resize_handler_id = None
			self.resize(int(self.viz_width * self.scalefactor), int(self.viz_height * self.scalefactor))
			self.resize_handler_id = self.connect("size-allocate", self.resize_handler)
		else:
			if scalefactor != self.scalefactor:
				return
			print(f"Adding pixbuf for state {key}")
			self.pixbufs[key] = [pixbuf, x_offset, y_offset]

		next_pixbuf_key = None
		allstate = set()
		for x in self.res.buttons.values():
			allstate |= x.get_state()
		for x in self.res.axes.values():
			allstate |= x.get_state()
		if key in allstate:
			self.darea.queue_draw()
		# Populate sticks first
		for k, stick in self.res.sticks.items():
			if stick.has_button:
				if k in allstate:
					pixkey = f"{k} active"
				else:
					pixkey = f"{k} idle"
			else:
				pixkey = k
			if pixkey not in self.pixbufs:
				next_pixbuf_key = pixkey
		# Done with sticks? See if there's anything currently being pressed we need to populate.
		if next_pixbuf_key is None:
			for key in allstate:
				if key in self.res.svgs and key not in self.pixbufs:
					next_pixbuf_key = key
					break
		# Done with stuff in state? Cache up anything else.
		if next_pixbuf_key is None:
			for k in self.res.svgs:
				if k not in self.pixbufs:
					next_pixbuf_key = k
					break

		if next_pixbuf_key is not None:
			self.parent.scaler.scale_svg([self.res.vid, self.res.pid, next_pixbuf_key], self.res.svgs[next_pixbuf_key], self.scalefactor)
# }}}
	def reset(self):# {{{
		try:
			for widget in list(self.res.buttons.values()) + list(self.res.axes.values()) + list(self.res.sticks.values()):
				widget.reset()
			self.darea.queue_draw()
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
	def apply_event_queue(self):# {{{
		for event in self.event_queue:
			ev_type = ecodes.EV[event.type]
			if ev_type == 'EV_KEY':
				if event.code in ecodes.KEY:
					ev_code = ecodes.KEY[event.code]
				else:
					ev_code = ecodes.BTN[event.code]
				if isinstance(ev_code, str):
					ev_code = [ev_code]
				for code in ev_code:
					if code in self.res.buttons:
						#print(f"code {code} value {event.value}")
						self.res.buttons[code].set_value(event.value)
						break
			elif ev_type == 'EV_ABS':
				ev_code = ecodes.ABS[event.code]
				if ev_code in self.res.axes:
					self.res.axes[ev_code].set_value(event.value)
		self.event_queue = []
		self.darea.queue_draw()
	# }}}
	def darea_realize_handler(self, widget):# {{{
		print("darea_realize_handler")
		self.connect("size-allocate", self.resize_handler)
# }}}
	def resize_handler(self, widget, other):# {{{
		if self.resize_timer_id is not None:
			GLib.source_remove(self.resize_timer_id)
			self.resize_timer_id = None
		self.resize_timer_id = GLib.timeout_add(1000, self.resize_finisher)
	
	def resize_finisher(self):
		self.resize_timer_id = None
		curr_dims = (self.get_allocated_width(), self.get_allocated_height())
		if curr_dims != self.win_dims:
			self.win_dims = curr_dims
			new_dims = resize_aspect(self.viz_width, self.viz_height, width=curr_dims[0])
			self.scalefactor = new_dims[2]
			self.parent.scaler.scale_svg([self.res.vid, self.res.pid, None], self.res.svgs[None], self.scalefactor)
# }}}
	def update_buttonstate(self, new_state):# {{{
		self.buttonstate = set()
		for k, v in self.res.buttonmap.items():
			if new_state & k:
				self.buttonstate.add(v)
		self.darea.queue_draw()
	# }}}
	def draw_handler(self, widget, cr):# {{{
		if self.parent.debug:
			print("draw_handler begin")
		try:
			cr.set_source_rgba(0, 0, 0, 1)
			cr.paint()
			if None not in self.pixbufs:
				return
			Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[None][0], self.pixbufs[None][1], self.pixbufs[None][2])
			cr.paint()
			allstate = set()
			for x in self.res.buttons.values():
				allstate |= x.get_state()
			for x in self.res.axes.values():
				allstate |= x.get_state()

			for state in allstate:
				if state in self.res.sticks:
					continue
				if state in self.pixbufs:
					Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[state][0], self.pixbufs[state][1], self.pixbufs[state][2])
					cr.paint()

			for k, stick in self.res.sticks.items():
				if stick.has_button:
					if k in allstate:
						pixkey = f"{k} active"
					else:
						pixkey = f"{k} idle"
				else:
					pixkey = k
				if pixkey in self.pixbufs:
					offsets = {
						'x': 0,
						'y': 0,
					}
					for off in offsets:
						axis = getattr(stick, f"{off}_axis")
						if axis is not None and axis.value is not None:
							offsets[off] = translate_constrainedint(axis.value, axis.minval, axis.maxval, axis.minpos, axis.maxpos)
					if stick.x_axis is not None and stick.y_axis is not None:
						circularize = True
						for attr in ['minval', 'maxval', 'minpos', 'maxpos']:
							if getattr(stick.x_axis, attr) != getattr(stick.y_axis, attr):
								circularize= False
								break
						if circularize:
							maxrange = stick.x_axis.maxpos - stick.x_axis.minpos
							angle = math.atan2(offsets['y'], offsets['x'])
							magnitude = math.sqrt(offsets['x'] * offsets['x'] + offsets['y'] * offsets['y'])
							if magnitude > (maxrange // 2):
								magnitude = maxrange // 2
							offsets['x'] = magnitude * math.cos(angle)
							offsets['y'] = magnitude * math.sin(angle)

					Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[pixkey][0], (offsets['x'] * self.scalefactor) + self.pixbufs[pixkey][1], (offsets['y'] * self.scalefactor) + self.pixbufs[pixkey][2])
					cr.paint()
		except Exception:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
		if self.parent.debug:
			print("draw_handler finish")

	# }}}
# }}}

class MisterSeenEventsWindow(Gtk.Window):# {{{
	def __init__(self, parent):# {{{
		try:
			self.parent = parent
			super().__init__()
			self.current_key = sorted(self.parent.seen_events)[0]
			
			vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
			sw = Gtk.ScrolledWindow()
			tv = Gtk.TextView()
			tv.set_editable(False)
			sw.add(tv)
			self.textbuf = tv.get_buffer()
			vbox.pack_start(sw, True, True, 0)
			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
			but = Gtk.Button(label="< Prev")
			but.connect("clicked", self.prev_button_handler)
			self.prev_but = but
			hbox.pack_start(but, True, True, 0)
			but = Gtk.Button(label="Copy")
			but.connect("clicked", self.copy_button_handler)
			hbox.pack_start(but, True, True, 0)
			but = Gtk.Button(label="Next >")
			but.connect("clicked", self.next_button_handler)
			hbox.pack_start(but, True, True, 0)
			vbox.pack_start(hbox, False, False, 0)
			self.add(vbox)
			self.next_but = but
			self.prev_but.set_sensitive(False)
			self.next_but.set_sensitive(False)
			self.resize(800, 600)
			self.show_all()
			GLib.idle_add(self.update)
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
	def update(self):# {{{
		try:
			self.textbuf.delete(self.textbuf.get_start_iter(), self.textbuf.get_end_iter())
			def tprint(*values, sep=' ', end='', file=None, **kwargs):
				msg = sep.join([ str(x) for x in values ])
				self.textbuf.insert(self.textbuf.get_end_iter(), msg + "\n")
			seen_keys = sorted(self.parent.seen_events)
			current_index = seen_keys.index(self.current_key)
			if current_index > 0:
				self.prev_but.set_sensitive(True)
			else:
				self.prev_but.set_sensitive(False)
			if current_index == len(seen_keys) - 1:
				self.next_but.set_sensitive(False)
			else:
				self.next_but.set_sensitive(True)
			events_dict = self.parent.seen_events[self.current_key]

			vid, pid = self.current_key.split(":", 1)

			tprint(f"name: <controller name>")
			tprint(f"vid: 0x{vid}")
			tprint(f"pid: 0x{pid}")
			tprint(f"svg: <svg file>.svg")

			button_defs = []
			axis_defs = []
			for key, data in events_dict.items():
				ev_typenum, ev_codenum = [ int(x) for x in key.split(":", 1) ]
				ev_type = ecodes.EV[ev_typenum]
				minval = data[0]
				maxval = data[1]
				if ev_type == 'EV_KEY':
					if ev_codenum in ecodes.KEY:
						ev_code = ecodes.KEY[ev_codenum]
					else:
						ev_code = ecodes.BTN[ev_codenum]
					if isinstance(ev_code, str):
						ev_code = [ev_code]
					# Shorter is better
					ev_code = sorted(ev_code, key=lambda x: len(x))[0]
					button_defs.append(ev_code)
				elif ev_type == 'EV_ABS':
					ev_code = ecodes.ABS[ev_codenum]
					axis_defs.append([ev_code, minval, maxval])

			if len(button_defs) > 0:
				tprint("buttons:")
				for k in sorted(button_defs):
					tprint(f"  {k}: <svg state>")

			if len(axis_defs) > 0:
				tprint("axes:")
				for spec in sorted(axis_defs, key=lambda x: x[0]):
					axname, minval, maxval = spec

					tprint(f"  {axname}:")
					tprint(f"    # start of binary axis definition. delete me if you're defining a stick!")
					tprint(f"    binary:")
					tprint(f"      <svg_state>: [{minval}, {minval}]")
					tprint(f"      <svg_state>: [{maxval}, {maxval}]")
					tprint(f"    # end of binary axis definition.")
					tprint(f"    # start of stick axis definition. delete me if you're defining a binary axis!")
					tprint(f"    stick:")
					tprint(f"      <stick_name>:")
					tprint(f"        <x_or_y>:")
					tprint(f"          - [{minval}, -30]")
					tprint(f"          - [{maxval}, 30]")
					tprint(f"    # end of stick axis definition.")

		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")

		return False
# }}}
	def prev_button_handler(self, widget):# {{{
		try:
			seen_keys = sorted(self.parent.seen_events)
			current_index = seen_keys.index(self.current_key)
			current_index -= 1
			self.current_key = seen_keys[current_index]
			GLib.idle_add(self.update)
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
# }}}
	def next_button_handler(self, widget):# {{{
		try:
			seen_keys = sorted(self.parent.seen_events)
			current_index = seen_keys.index(self.current_key)
			current_index += 1
			self.current_key = seen_keys[current_index]
			GLib.idle_add(self.update)
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
# }}}
	def copy_button_handler(self, widget):# {{{
		try:
			text = self.textbuf.get_text(self.textbuf.get_start_iter(), self.textbuf.get_end_iter(), True)
			clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
			clipboard.set_text(text, len(text.encode()))
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
# }}}


if __name__ == '__main__':
	multiprocessing.freeze_support()
	do_argparse = True
	if sys.platform == "win32":
		if getattr(sys, "frozen", False):
			do_argparse = False
	if do_argparse:
		import argparse
		parser = argparse.ArgumentParser()
		parser.add_argument("hostname", default=None, nargs="?")
		parser.add_argument("-d", "--debug", action="store_true", dest="debug", default=False)
		args = parser.parse_args()
		app = MisterViz(args.hostname, debug=args.debug)
	else:
		app = MisterViz(None)

	#if ser is None:
	if sys.platform == "linux":
		import debugrepl, glib_editingline
		cli = glib_editingline.CliInterpreter(Gtk, namespace=globals())
	Gtk.main()
