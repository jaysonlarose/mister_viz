#!/usr/bin/env python3

import os, sys

import gi
import random
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Gdk, GdkPixbuf, GObject
import cairosvg, cairo, io, PIL.Image, struct, yaml, lxml.etree, copy, math, socket, subprocess, atexit, multiprocessing, queue, time, traceback, psutil, datetime, random, base64, math, numpy

gi.require_version("PangoCairo", "1.0")
from gi.repository import PangoCairo, Pango

if sys.platform == "linux":
	random.seed(open("/dev/random", "rb").read(64))


def xmlwalk(tree):
	yield tree
	for item in tree:
		yield from xmlwalk(item)
class FontWriter:# {{{
	def __init__(self, font_name, font_face, font_size, antialias=None):
		"""
		FontWriter is a convenience class for working with text in
		a Cairo surface.

		Parameters:
		font_name — The name of the font to use (ie, "Tahoma")
		font_face — The name of the subfont variation to use
		     (ie, "Regular", "Bold", "Italic"...)
		font_size — Font size, in points(?)
		antialias — if you set to any of:
		    * cairo.Antialias.BEST
		    * cairo.Antialias.DEFAULT
		    * cairo.Antialias.FAST
		    * cairo.Antialias.GOOD
		    * cairo.Antialias.GRAY
		    * cairo.Antialias.NONE
		    * cairo.Antialias.SUBPIXEL
		  , it will use those antialiasing settings.

		After this class is instantiated, assign a Cairo context to
		it using the `set_context()` method, find the size the text
		will take up with `get_dims()`, and write the text to the
		Cairo surface using `render()`.
		"""
		fontmap = PangoCairo.font_map_get_default()
		fam = [ x for x in fontmap.list_families() if x.get_name() == font_name ][0]
		fac = [ x for x in fam.list_faces() if x.get_face_name() == font_face ][0]
		self.font_description = fac.describe()
		self.font_description.set_size(font_size * Pango.SCALE)
		self.antialias = antialias
		self.fontoptions = None
		if self.antialias is not None:
			self.fontoptions = cairo.FontOptions()
			self.fontoptions.set_antialias(self.antialias)
		self.context = None
	@classmethod
	def list_fonts(cls):
		"""
		Lists available fonts.
		"""
		fontmap = PangoCairo.font_map_get_default()
		return [ x.get_name() for x in fontmap.list_families() ]
	@classmethod
	def list_faces_for_font(cls, font_name):
		"""
		Returns a list of faces available for the specified font.
		"""
		fontmap = PangoCairo.font_map_get_default()
		fam = [ x for x in fontmap.list_families() if x.get_name() == font_name ][0]
		return [ x.get_face_name() for x in fam.list_faces() ]
	def set_context(self, context):
		"""
		Assigns the supplied Cairo context to this FontWriter.
		"""
		self.context = context
		self.layout = PangoCairo.create_layout(self.context)
		self.layout.set_font_description(self.font_description)
		PangoCairo.update_layout(self.context, self.layout)
		if self.fontoptions is not None:
			self.context.set_font_options(self.fontoptions)
	def _set_text(self, text):
		self.layout.set_text(text, len(text.encode()))
	def get_dims(self, text):
		"""
		Returns the width and height that the supplied text
		would take up if rendered.
		"""
		self._set_text(text)
		return [ x / Pango.SCALE for x in self.layout.get_size() ]
	def render(self, text, x, y):
		"""
		Writes out the supplied text to the currently assigned context's surface,
		at the position x, y.
		If you want to change the text color, call the context's `set_source_rgb`
		or `set_source_rgba` method first.
		"""
		if self.context is None:
			raise RuntimeError("Use set_context() to assign a context to this FontWriter first!")
		self._set_text(text)
		self.context.move_to(x, y)
		PangoCairo.show_layout(self.context, self.layout)
# }}}

def now_tzaware():# {{{
	# doc {{{
	"""
	Convenience function, equivalent to 
	`datetime.datetime.now(tz=pytz.reference.Local)`
	"""
	# }}}
	import pytz.reference, datetime
	return datetime.datetime.now(tz=pytz.reference.Local)
# }}}
def format_timestamp(dt, omit_tz=False, alt_tz=False, precision=6):# {{{
	# doc {{{
	"""\
	Takes a timezone-aware datetime object and makes it look like:

	2019-01-21 14:38:21.123456 PST

	Or, if you call it with omit_tz=True:

	2019-01-21 14:38:21.123456

	The precision parameter controls how many digits past the decimal point you
	get. 6 gives you all the microseconds, 0 avoids the decimal point altogether
	and you just get whole seconds.
	"""
	# }}}
	tz_format = "%Z"
	if alt_tz:
		tz_format = "%z"
	timestamp_txt = dt.strftime("%F %T")
	if precision > 0:
		timestamp_txt = "{}.{}".format(timestamp_txt, "{:06d}".format(dt.microsecond)[:precision])
	if not omit_tz and dt.tzinfo is not None:
		timestamp_txt = "{} {}".format(timestamp_txt, dt.strftime("%z"))
	return timestamp_txt
# }}}
def timestamp_to_localdatetime(ts):# {{{
	# doc {{{
	"""
	Like `datetime.datetime.fromtimestamp()`, except it returns a
	timezone-aware datetime object.
	"""
	# }}}
	import pytz.reference, datetime, decimal
	if isinstance(ts, decimal.Decimal):
		ts = float(ts)
	return datetime.datetime.fromtimestamp(ts).replace(tzinfo=pytz.reference.Local)
# }}}
def plot_course(start_point, direction, distance):# {{{
	"""
	Given a starting point, an angle (in radians), and a distance,
	returns the point resulting from travelling from the starting point
	at said angle for said distance.
	"""
	return (start_point[0] + math.sin(direction) * distance, start_point[1] + math.cos(direction) * distance)
# }}}

global print
global orig_print

try:
	import jack
	jack_disabled = False
except ImportError:
	jack_disabled = True

# We used to use the real evdev.ecodes library, now we don't.
# This is completely because evdev.ecodes starts having problems when
# dealing with more than 12 joystick buttons.
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
def get_yaml_basedir():# {{{
	if sys.platform == "win32":
		return os.path.expanduser("~/mister_viz")
	else:
		return os.path.join(get_userconfig_dir(), "mister_viz")
# }}}
def get_yaml_files(yaml_basedir):# {{{
	yaml_files = [ x for x in [ os.path.join(yaml_basedir, x) for x in [ x for x in os.listdir(yaml_basedir) if os.path.splitext(x)[1] == '.yaml' and not x.startswith('_') ] ] if os.path.isfile(x) ]
	return yaml_files
# }}}

# Functions and classes in support of parsing and working with event logs
class LogEvent:# {{{
	"""
	Class for parsing and manipulating event log entries.
	"""
	__slots__ = ['comment', 'local_timestamp', 'tv_sec', 'tv_usec', 'inputno', 'player_id', 'vid', 'pid', 'ev_type', 'ev_code', 'ev_value']
	def __init__(self, line):# {{{
		frags = [ x.strip() for x in line.strip().split("#", 1) ]
		if len(frags) > 1:
			self.comment = frags[1]
		else:
			self.comment = None
		frags = frags[0].split(',')
		self.local_timestamp = float(frags[0])
		self.tv_sec = int(frags[1])
		self.tv_usec = int(frags[2])
		self.inputno = int(frags[3])
		self.player_id = int(frags[4])
		self.vid = int(frags[5], 16)
		self.pid = int(frags[6], 16)
		self.ev_type = int(frags[7])
		self.ev_code = int(frags[8])
		self.ev_value = int(frags[9])
	# }}}
	def get_event(self):# {{{
		event_vals = [self.tv_sec, self.tv_usec, self.ev_type, self.ev_code, self.ev_value]
		return evdev_categorize(evdev_InputEvent(*event_vals))
	# }}}
	def get_timestamp(self):# {{{
		return self.tv_sec + (self.tv_usec / 1000000)
	# }}}
# }}}
class LogDisconnection:# {{{
	"""
	Class which represents mister_viz losing connection with the MiSTer.
	"""
	__slots__ = ['comment', 'local_timestamp']
	def __init__(self, line):# {{{
		frags = [ x.strip() for x in line.strip().split("#", 1) ]
		if len(frags) > 1:
			self.comment = frags[1]
		else:
			self.comment = None
		frags = frags[0].split()
		assert frags[0] == "disconnected"
		self.local_timestamp = float(frags[1])
	# }}}
# }}}
class LogConnection:# {{{
	"""
	Class which represents mister_viz establishing a connection with the MiSTer.
	"""
	__slots__ = ['comment', 'local_timestamp']
	def __init__(self, line):# {{{
		frags = [ x.strip() for x in line.strip().split("#", 1) ]
		if len(frags) > 1:
			self.comment = frags[1]
		else:
			self.comment = None
		frags = frags[0].split()
		assert frags[0] == "connected"
		self.local_timestamp = float(frags[1])
	# }}}
# }}}
def parse_logline(line):# {{{
	"""
	Accepts an event log line and returns an object
	of the appropriate class
	"""
	line = line.strip()
	if line.startswith("disconnected "):
		return LogDisconnection(line)
	elif line.startswith("connected "):
		return LogConnection(line)
	else:
		return LogEvent(line)
# }}}
def get_frameno(start, rate, timestamp):# {{{
	"""
	Given a start timestamp and a framerate, returns which frame that the provided timestamp
	would occur in.
	"""
	offset = timestamp - start
	return math.ceil(offset * rate)
# }}}


# Functions for dealing with "display:inline;fill:#4a4a4a;stroke:#848484"-style
# sub-attributes in SVG files.
def xmlattrib_to_dict(attrib):# {{{
	"""
	Converts a string containing XML subattributes into a dict.
	"""
	if len(attrib) == 0:
		return {}
	return dict([ x.split(':', 1) for x in attrib.split(';') ])
# }}}
def dict_to_xmlattrib(d):# {{{
	"""
	Converts a dict of string key-value pairs into an sub-attribute string.
	"""
	return ';'.join([ f"{key}:{value}" for key, value in d.items() ])
# }}}
def get_xmlsubattrib(tag, key, subkey):# {{{
	"""
	Given lxml element `tag`, attribute name `key`, and sub-attribute name `subkey`,
	retrieves said sub attribute from the key attribute in tag.  If said sub-attribute is
	not defined, or the entire attribute doesn't exist, returns None.
	"""
	if key not in tag.attrib:
		return None
	d = xmlattrib_to_dict(tag.attrib[key])
	if subkey not in d:
		return None
	return d[subkey]
# }}}
def set_xmlsubattrib(tag, key, subkey, value):# {{{
	"""
	adds or modifies sub-attribute `subkey` in attribute `key` of lmxl element `tag`,
	setting it's value to `value`.
	"""
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
def old_mangle(tree, state, debug=False):# {{{
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
	A style of 'display:inline' is handled differently depending on whether the state parameter
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
				#else:
				#	elem.getparent().remove(elem)
				#	continue
			#elif state is not None:
			#	if display_val == 'none':
			#		elem.getparent().remove(elem)
			#	else:
			#		set_xmlsubattrib(elem, 'style', 'display', 'none')
		mangle(elem, state)
# }}}

def mangle(tree, state, debug=False):# {{{
	"""
	Newer, kinder, gentler mangle.

	Find all "g" elements. Add each one that has 'data-type' and 'data-state' attributes to a dict that's keyed
	to these attributes.

	Set all of these g elements' style attrib to "display:none".

	If state is None, we're processing the background SVG, and are finished.

	Otherwise, the g element that matches the state parameter is our key.
	Inspect all g elements: if it is a descendent of our key, leave it alone. Otherwise,
	if it has a style of "display:inline", change it to "display:none".

	Finally, starting from our key element, walk upwards:
	  Set current element's style to "display:inline".
	  If this isn't the root level, set any other sibling element's style to "display:none"
	"""
	groups = tree.findall(f".//{SVG_PREFIX}g")
	state_elems = {}
	for g in groups:
		if 'data-state' in g.attrib and 'data-type' in g.attrib:
			key = f"{g.attrib['data-type']}:{g.attrib['data-state']}"
			state_elems[key] = g

	for elem in state_elems.values():
		set_xmlsubattrib(elem, "style", "display", "none")

	if state is not None and state in state_elems:
		key_elem = state_elems[state]
		for g in groups:
			display_val = get_xmlsubattrib(g, 'style', 'display')
			is_descendant = False
			p = g
			while p is not None:
				if p == key_elem:
					is_descendant = True
					break
				p = p.getparent()
			if not is_descendant:
				set_xmlsubattrib(g, "style", "display", "none")
		set_xmlsubattrib(key_elem, "style", "display", "inline")
		p = key_elem.getparent()
		golden_child = key_elem
		while p is not None:
			if p.getparent() is not None:
				for child in p.getchildren():
					if child != golden_child:
						set_xmlsubattrib(child, "style", "display", "none")
			set_xmlsubattrib(p, "style", "display", "inline")
			golden_child = p
			p = p.getparent()
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

MISTER_STRUCT = "<BBHHHHiII"
MISTER_STRUCT_SIZE = struct.calcsize(MISTER_STRUCT)
SVG_PREFIX = '{http://www.w3.org/2000/svg}'
DUMP_RENDERS = False
SOCKET_KEEPALIVE_INTERVAL = 2000
SOCKET_KEEPALIVE_TIMEOUT  = 2000
SOCKET_CONNECT_TIMEOUT    = 2000
OP_INPUT = 0
OP_PING  = 1
OP_PONG  = 2

def call_dbus_method(bus, service, path, interface, method, *args, **kwargs):# {{{
	return bus.get_object(service, path).get_dbus_method(method, interface)(*args, **kwargs)
# }}}
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

class Control(GObject.GObject):# {{{
	__gsignals__ = {
		"value-changed": (GObject.SignalFlags.RUN_FIRST, None, []),
		"reset":         (GObject.SignalFlags.RUN_FIRST, None, []),
	}
	def __init__(self, reset=True, parent_control=None):# {{{
		super().__init__()
		self.parent_control = parent_control
		if reset:
			self.reset()
	# }}}
	def set_value(self, value, emit=True):# {{{
		if hasattr(self, "value"):
			orig_value = self.value
		else:
			orig_value = None
		self.value = value
		if self.parent_control is not None:
			self.parent_control.set_value(value, emit=emit)
		if orig_value != self.value and emit:
			self.emit("value-changed")
	# }}}
	def reset(self):# {{{
		self.set_value(None, emit=False)
		self.emit("reset")
	# }}}
	def get_state(self):# {{{
		return set()
	# }}}
	def all_states(self):# {{{
		return set()
	# }}}
# }}}
class Stick(Control):# {{{
	"""
	This class represents a typical gamepad
	analog control stick. It contains an x axis,
	a y axis, and optionally a button.
	"""
	def __init__(self, x_axis=None, y_axis=None, button=None):
		self.x_axis = x_axis
		self.y_axis = y_axis
		self.button = button
		super().__init__(reset=False)
		if self.x_axis is not None:
			self.x_axis.connect("value-changed", self.value_change_propagator)
		if self.y_axis is not None:
			self.y_axis.connect("value-changed", self.value_change_propagator)
		if self.button is not None:
			self.button.connect("value-changed", self.value_change_propagator)
		self.reset()
	@property
	def has_button(self):
		return self.button is not None
	def value_change_propagator(self, *args):
		self.emit("value-changed")
	def reset(self):
		if self.x_axis is not None:
			self.x_axis.reset()
		if self.y_axis is not None:
			self.y_axis.reset()
		self.emit("reset")
# }}}
class Button(Control):# {{{
	def __init__(self, element):
		super().__init__(reset=False)
		self.element = element
		#self.ptt = None
		self.stick = None
		self.reset()
	def reset(self):
		self.set_value(0, emit=False)
		self.emit("reset")
	@property
	def on_stick(self):
		if self.stick is not None:
			return True
		return False
	#def set_value(self, value, emit=True):
	#	if self.ptt is not None:
	#		self.ptt.set_value(value)
	#	old_value = self.value
	#	self.value = value
	#	if self.value != old_value and emit:


	def get_state(self):
		if self.value > 0:
			return set([f"button:{self.element}"])
		return set()
	def all_states(self):
		return set([f"button:{self.element}"])
# }}}
class Axis(Control):# {{{
	def __init__(self, spec):
		super().__init__(reset=False)
		#self.ptt = None
		self.ptt_range = None
		self.spec = spec
		self.states = set()
		self.rangemap = []
		self.is_stick = False
		self.is_binary = False
		self.is_analog = False
		self.stickname = None
		self.min_value = None
		self.max_value = None
		self.default_value = 0
		self.min_pos = None
		self.max_pos = None
		self.svg_res = None
		# Presence of an 'svg_res' attribute means this is an axis for a MisterVizResourceMap
		if 'svg_res' in self.spec:
			self.svg_res = self.spec['svg_res']
		# Presence of a 'binary' attribute means this is an axis for a MisterVizResourceMap
		if 'binary' in self.spec:
			self.is_binary = True
			for k, v in self.spec['binary'].items():
				self.rangemap.append([v[0], v[1], f"button:{k}"])
		# Presence of an 'analog' attribute means this is an axis for a MisterVizResourceMap
		if 'analog' in self.spec:
			self.is_analog = True
			# this attribute should have 'mapped_to', 'min_value', and 'max_value' subattributes.
			self.mapped_to = self.spec['analog']['mapped_to']
			self.min_value = self.spec['analog']['min_value']
			self.max_value = self.spec['analog']['max_value']
			self.segments = self.svg_res.axes[self.mapped_to].segments
			self.parent_control = self.svg_res.axes[self.mapped_to]
		# Presence of a 'stick' attribute means this is an axis for a MisterVizResourceMap
		if 'stick' in self.spec:
			for k, v in self.spec['stick'].items():
				self.stickname = k
				for k, v in v.items():
					self.stickaxis = k
					if self.svg_res is not None:
						svgres_key = f"{self.stickname}:{self.stickaxis}"
						if svgres_key in self.svg_res.axes:
							svgres_axis = self.svg_res.axes[svgres_key]
							self.parent_control = svgres_axis
							for attrname in ['min_value', 'max_value', 'default_value', 'min_pos', 'max_pos']:
								attrval = getattr(svgres_axis, attrname)
								if attrval is not None:
									print(f"Setting stick {self.stickname} axis {self.stickaxis} attr {attrname} to {attrval} (inherited from svg_res)", file=sys.stderr)
									setattr(self, attrname, attrval)
					for k in ['min_value', 'max_value', 'default_value', 'min_pos', 'max_pos']:
						if k in v:
							print(f"Setting stick {self.stickname} axis {self.stickaxis} attr {k} to {v[k]}", file=sys.stderr)
							setattr(self, k, v[k])
			self.is_stick = True
		# Presence of a 'segments' attribute means this is an axis for a SvgControllerResources
		if 'segments' in self.spec:
			self.is_analog = True
			self.element = self.spec['element']
			self.segments = self.spec['segments']
		if 'default_value' in self.spec:
			self.default_value = int(self.spec['default_value'])
		if 'ptt' in self.spec:
			self.ptt_range = self.spec['ptt']
		self.reset()
	#def set_value(self, value):
	#	if self.ptt is not None and self.ptt_range is not None:
	#		fromval, toval = self.ptt_range
	#		if value >= fromval and value <= toval:
	#			self.ptt.set_value(1)
	#		else:
	#			self.ptt.set_value(0)
	#	self.value = value
	def get_state(self):
		ret = set()
		if self.value is None:
			return ret
		if self.is_binary:
			for fromval, toval, elem in self.rangemap:
				if self.value >= fromval and self.value <= toval:
					ret.add(elem)
		if self.is_analog:
			segment_num = translate_constrainedint(self.value, self.min_value, self.max_value, 0, self.segments - 1)
			ret.add(f"axis:{self.mapped_to}:{segment_num}")
		return ret
	def all_states(self):
		ret = set()
		if self.is_binary:
			for fromval, toval, elem in self.rangemap:
				ret.add(elem)
		return ret
	def reset(self):
		self.set_value(self.default_value, emit=False)
		self.emit("reset")
		#if self.ptt is not None:
		#	self.ptt.set_value(0)

# }}}

class JackPushToTalk:# {{{
	def __init__(self):
		import dbus, dbus.mainloop.glib
		dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
		self.dbus = dbus.SessionBus()
		self.lastval = False

	def set_value(self, value):
		self.value = value
		if self.value == 1:
			setval = True
		else:
			setval = False
		if setval != self.lastval:
			call_dbus_method(self.dbus, "org.interlaced.jack_ptt", "/org/interlaced/jack_ptt", "org.freedesktop.DBus.Properties", "Set", "org.interlaced.jack_ptt", "attach", setval)
			self.lastval = setval
# }}}
def svg_to_pixbuf(svg_bytes, scale_factor):# {{{
	fobj = io.BytesIO(cairosvg.svg2png(svg_bytes, scale=scale_factor))
	pil_img = PIL.Image.open(fobj)
	pixbuf = pil_to_pixbuf(pil_img, mode="RGBA")
	return pixbuf
# }}}

def modify_gradient(tree, axis_name, fract):# {{{
	axis_groups = [ x for x in xmlwalk(tree) if 'data-type' in x.attrib and 'data-state' in x.attrib and x.attrib['data-type'] == 'axis' and x.attrib['data-state'] == axis_name ]
	axis_group = axis_groups[0]
	gradient_axis_elems = [ [x[0], x[1]['fill']] for x in [ [x, xmlattrib_to_dict(x.attrib['style'])] for x in xmlwalk(axis_group) if 'style' in x.attrib ] if 'fill' in x[1] and x[1]['fill'].startswith("url(#linearGradient") ]

	if len(gradient_axis_elems) < 1:
		return None
	elem, raw_url = gradient_axis_elems[0]
	url = raw_url.split("#", 1)[1].split(")", 1)[0]
	gradient_element = [ x for x in xmlwalk(tree) if 'id' in x.attrib and x.attrib['id'] == url ][0]
	gradientdef_href = gradient_element.attrib['{http://www.w3.org/1999/xlink}href']
	if gradientdef_href.startswith('#'):
		gradientdef_href = gradientdef_href[1:]
	gradientdef = [ x for x in xmlwalk(tree) if 'id' in x.attrib and x.attrib['id'] == gradientdef_href ][0]
	for stop_elem in gradientdef[1:3]:
		stop_elem.attrib['offset'] = f"{fract}"
# }}}
def svg_state_split(svg_bytes, debug=False):# {{{
	ret = {}
	tree = lxml.etree.fromstring(svg_bytes)
	flat = walk(tree)
	states = []
	for elem in flat:
		if elem.tag == SVG_PREFIX + 'g':
			dt = elem.get("data-type", None)
			ds = elem.get("data-state", None)
			if dt is not None and ds is not None:
				key = f"{dt}:{ds}"
				states.append(key)
				set_xmlsubattrib(elem, 'style', 'display', 'none')
	states.append(None)
	for state in states:
		print(f"state: {state}", file=sys.stderr)
		chip = copy.deepcopy(tree)
		mangle(chip, state, debug=debug)
		devastate(chip, debug=debug)

		handled = False
		if state is not None:
			dt, ds = state.split(":", 1)
			if dt == "axis":
				axis_groups = [ x for x in xmlwalk(tree) if 'data-type' in x.attrib and 'data-state' in x.attrib and x.attrib['data-type'] == 'axis' and x.attrib['data-state'] == ds ]
				print(f"axis_groups: {axis_groups}", file=sys.stderr)
				axis_group = axis_groups[0]
				if 'data-segments' in axis_group.attrib:
					seg_qty = int(axis_group.attrib['data-segments'])
					for val, fract in [ [x, x / (seg_qty - 1)] for x in range(seg_qty) ]:
						crumb = copy.deepcopy(chip)
						key = f"{dt}:{ds}:{val}"
						modify_gradient(crumb, ds, fract)
						ret[key] = lxml.etree.tostring(crumb)
				handled = True
		if not handled:
			ret[state] = lxml.etree.tostring(chip)
	return ret
# }}}


class SvgControllerResources:# {{{
	def __init__(self, svg_filename):# {{{
		self.base_dir = os.path.dirname(svg_filename)
		base = os.path.splitext(os.path.basename(svg_filename))[0]
		self.base_name = os.path.splitext(base)[0]
		self.base_svg = open(svg_filename, "rb").read()
		self.tree = lxml.etree.fromstring(self.base_svg)
		self.buttons = {}
		self.axes = {}
		self.sticks = {}
		self.vid = 0xffff
		self.pid = 0xffff
		self.has_rumble = False
		self.rumbling = False
		self.last_rumble = None

		if 'data-name' in self.tree.attrib:
			self.name = self.tree.attrib['data-name']
		if 'data-scale' in self.tree.attrib:
			self.scale = float(self.tree.attrib['data-scale'])

		group_elems = self.tree.findall(f".//{SVG_PREFIX}g")
		state_elems = [ x for x in group_elems if 'data-state' in x.attrib ]
		for elem in state_elems:
			state_value = elem.attrib['data-state']
			if 'data-type' not in elem.attrib:
				raise RuntimeError(f"SVG ERROR ({svg_filename}): group with data-state {elem.attrb['data-state']} has no data-type!")
			type_value = elem.attrib['data-type']
			if type_value == 'button':
				self.buttons[state_value] = Button(state_value)
			elif type_value == 'axis':
				axis_spec = {
					'element': state_value,
				}
				if 'data-segments' in elem.attrib:
					axis_spec['segments'] = int(elem.attrib['data-segments'])
				self.axes[state_value] = Axis(axis_spec)
			elif type_value == 'stick':
				if 'data-extents-x' not in elem.attrib:
					raise RuntimeError(f"SVG ERROR ({svg_filename}): group ({elem.attrib}) with data-type 'stick' has no data-extents-x!")
				if 'data-extents-y' not in elem.attrib:
					raise RuntimeError(f"SVG ERROR ({svg_filename}): group ({elem.attrib}) with data-type 'stick' has no data-extents-y!")
				extents_x = [ int(x) for x in elem.attrib['data-extents-x'].split() ]
				extents_y = [ int(x) for x in elem.attrib['data-extents-y'].split() ]
				axis_spec = {
					'stick': {
						state_value: {
							'x': {
								'min_pos': extents_x[0],
								'max_pos': extents_x[1],
							},
						},
					},
				}
				self.axes[f"{state_value}:x"] = Axis(axis_spec)
				axis_spec = {
					'stick': {
						state_value: {
							'y': {
								'min_pos': extents_y[0],
								'max_pos': extents_y[1],
							},
						},
					},
				}
				self.axes[f"{state_value}:y"] = Axis(axis_spec)

				stick_obj = Stick()
				stick_obj.x_axis = self.axes[f"{state_value}:x"]
				stick_obj.y_axis = self.axes[f"{state_value}:y"]
				self.sticks[state_value] = stick_obj
		for k, v in self.sticks.items():
			if k in self.buttons:
				v.button = self.buttons[k]
				self.buttons[k].stick = v
		# Process svg file
		self.svgs = svg_state_split(self.base_svg)
	# }}}
	def dump_svgs(self):# {{{
		for k in self.svgs:
			outfile = f"{k.replace(':', '_')}.svg"
			open(outfile, "wb").write(self.svgs[k])
	# }}}
	def dump_state(self):# {{{
		ret = []
		sub = []
		for k in sorted(self.buttons.keys()):
			sub.append(self.buttons[k].value)
		ret.append(tuple(sub))
		sub = []
		for k in sorted(self.axes.keys()):
			sub.append(self.axes[k].value)
		ret.append(tuple(sub))
		if self.has_rumble:
			ret.append(self.rumbling)
		return tuple(ret)
	# }}}
	def load_state(self, dump):# {{{
		for i, k in enumerate(sorted(self.buttons.keys())):
			self.buttons[k].set_value(dump[0][i])
		for i, k in enumerate(sorted(self.axes.keys())):
			self.axes[k].set_value(dump[1][i])
		if self.has_rumble:
			self.rumbling = dump[2]
	# }}}
	def format_state(self):# {{{
		frags = []
		orphan_axes = dict(self.axes.items())
		for k in sorted(self.sticks):
			stick = self.sticks[k]
			frags.append(f"{k}: {stick.x_axis.value},{stick.y_axis.value}")
			for ak in list(orphan_axes.keys()):
				for ax in [stick.x_axis, stick.y_axis]:
					if orphan_axes[ak] == ax:
						del orphan_axes[ak]
						break
		for k in sorted(orphan_axes):
			axis = orphan_axes[k]
			frags.append(f"{k}: {axis.value}")
		for k in sorted(self.buttons):
			button = self.buttons[k]
			if button.value > 0:
				frags.append(f"{k}")
		return " ".join(frags)
	# }}}
# }}}
class MisterVizResourceMap:# {{{
	"""
	This reads in a YAML file and uses it to Linux input subsystem events
	onto SvgControllerResources.
	"""
	def __init__(self, yaml_filename):# {{{
		self.base_dir = os.path.dirname(yaml_filename)
		base = os.path.splitext(os.path.basename(yaml_filename))[0]
		self.base_name = os.path.splitext(base)[0]
		self.base_yaml = open(yaml_filename, "r").read()
		self.config = yaml.load(self.base_yaml, Loader=yaml.Loader)
		svg_filename = os.path.join(self.base_dir, f"{self.config['svg']}")

		self.svg_res = SvgControllerResources(svg_filename)
		self.connected = False
		if 'primary' not in self.config:
			self.config['primary'] = True

		c = self.config
		#self.buttons = self.svg_res.buttons
		#self.axes    = self.svg_res.axes
		self.sticks  = self.svg_res.sticks
		self.vid = c['vid']
		self.pid = c['pid']
		self.buttons = {}
		if 'buttons' in c:
			for k, v in c['buttons'].items():
				self.buttons[k] = self.svg_res.buttons[v]
		self.axes = {}
		if 'axes' in c:
			for k, v in c['axes'].items():
				v['svg_res'] = self.svg_res
				self.axes[k] = Axis(v)
		for axis in self.axes.values():
			if axis.is_stick:
				#if axis.stickname not in self.sticks:
				#	self.sticks[axis.stickname] = Stick()
				if axis.stickaxis == 'x':
					self.sticks[axis.stickname].x_axis = axis
				elif axis.stickaxis == 'y':
					self.sticks[axis.stickname].y_axis = axis
		all_buttons = set()
		for x in self.buttons.values():
			all_buttons |= x.all_states()
		for x in self.axes.values():
			all_buttons |= x.all_states()
		# Process svg file
		#self.svgs = svg_state_split(self.base_svg)
		self.svgs = self.svg_res.svgs
	# }}}
	@property # name{{{
	def name(self):
		if 'name' in self.config:
			return self.config['name']
		if hasattr(self, 'name'):
			return self.name
		return None
	# }}}
	@property # has_rumble{{{
	def has_rumble(self):
		if 'has_rumble' in self.config:
			return self.config['has_rumble']
		return self.svg_res.has_rumble
	# }}}
	@property # rumbling{{{
	def rumbling(self):
		return self.svg_res.rumbling
	@rumbling.setter
	def rumbling(self, val):
		self.svg_res.rumbling = val
	# }}}
	@property # last_rumble{{{
	def last_rumble(self):
		return self.svg_res.last_rumble
	@last_rumble.setter
	def last_rumble(self, val):
		self.svg_res.last_rumble = val
	# }}}
	def dump_svgs(self):# {{{
		for k in self.svgs:
			outfile = f"{k}.svg"
			open(outfile, "wb").write(self.svgs[k])
	# }}}
	def dump_state(self):# {{{
		ret = []
		sub = []
		for k in sorted(self.buttons.keys()):
			sub.append(self.buttons[k].value)
		ret.append(tuple(sub))
		sub = []
		for k in sorted(self.axes.keys()):
			sub.append(self.axes[k].value)
		ret.append(tuple(sub))
		if self.has_rumble:
			ret.append(self.rumbling)
		return tuple(ret)
	# }}}
	def load_state(self, dump):# {{{
		for i, k in enumerate(sorted(self.buttons.keys())):
			self.buttons[k].set_value(dump[0][i])
		for i, k in enumerate(sorted(self.axes.keys())):
			self.axes[k].set_value(dump[1][i])
		if self.has_rumble:
			self.rumbling = dump[2]
	# }}}
	def format_state(self):# {{{
		frags = []
		orphan_axes = dict(self.axes.items())
		for k in sorted(self.sticks):
			stick = self.sticks[k]
			frags.append(f"{k}: {stick.x_axis.value},{stick.y_axis.value}")
			for ak in list(orphan_axes.keys()):
				for ax in [stick.x_axis, stick.y_axis]:
					if orphan_axes[ak] == ax:
						del orphan_axes[ak]
						break
		for k in sorted(orphan_axes):
			axis = orphan_axes[k]
			frags.append(f"{k}: {axis.value}")
		for k in sorted(self.buttons):
			button = self.buttons[k]
			if button.value > 0:
				frags.append(f"{k}")
		return " ".join(frags)
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
	"""
	parses a queue item for the scaler, returning the resultant pixbuf.
	"""
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
	#print(f"cropping image with dimensions {pil_img.width}, {pil_img.height}")
	# Crop left hand side
	x_offset = 0
	img = pil_img
	while x_offset < img.width:
		try:
			img_slice = img.crop((x_offset, 0, x_offset + 1, img.height))
			img_slice_bytes = img_slice.tobytes()
			slice_height = img_slice.height * 4
			if sum([ img_slice_bytes[x] for x in range(3, slice_height, 4) ]) == 0:
				x_offset += 1
			else:
				break
		except SystemError:
			print("SystemError cropping left")
			break
	# Crop top side
	img = img.crop((x_offset, 0, img.width, img.height))
	y_offset = 0
	while y_offset < img.height:
		try:
			img_slice = img.crop((0, y_offset, img.width, y_offset + 1))
			img_slice_bytes = img_slice.tobytes()
			slice_width = img_slice.width * 4
			if sum([ img_slice_bytes[x] for x in range(3, slice_width, 4) ]) == 0:
				y_offset += 1
			else:
				break
		except SystemError:
			print("SystemError cropping top")
			break
	# Crop right hand side
	img = img.crop((0, y_offset, img.width, img.height))
	right_offset = img.width
	while right_offset > 0:
		try:
			img_slice = img.crop((right_offset - 1, 0, right_offset, img.height))
			img_slice_bytes = img_slice.tobytes()
			slice_height = img_slice.height * 4
			if sum([ img_slice_bytes[x] for x in range(3, slice_height, 4) ]) == 0:
				right_offset -= 1
			else:
				break
		except SystemError:
			print("SystemError cropping right")
			break
	# Crop bottom
	img = img.crop((0, 0, right_offset, img.height))
	bottom_offset = img.height
	while bottom_offset > 0:
		try:
			img_slice = img.crop((0, bottom_offset - 1, img.width, bottom_offset))
			img_slice_bytes = img_slice.tobytes()
			slice_width = img_slice.width * 4
			if sum([ img_slice_bytes[x] for x in range(3, slice_width, 4) ]) == 0:
				bottom_offset -= 1
			else:
				break
		except SystemError:
			print("SystemError cropping bottom")
			break
	img = img.crop((0, 0, img.width, bottom_offset))
	return (img, x_offset, y_offset)
# }}}
class MultiprocSvgScaler(GObject.GObject):# {{{
	"""
	A GObject which farms out the tasks of taking SVGs, scaling them, and converting them to
	pixbufs to one or more scaler_process_func processes.

	SVGs are fed in via the `scale_svg()` method, and are returned via the `result` signal.
	"""
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
				# If this is an OS that has proper functioning pipes, use pipe objects
				# attached to each process for detecting completed queue items.
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
			# If this is windows, pipes don't work right.
			# Set up a polling schedule to check for completed items.
			self.last_poll_activity = time.monotonic()
			self.queue_poller_handle = GLib.timeout_add(250, self.queue_poller)
# }}}
	def pipe_handler(self, fd, flags):# {{{
		print("pipe_handler()")
		for proc_dict in self.processes:
			if proc_dict['pipe'].fileno() == fd:
				proc_dict['pipe'].recv()
				break
		payload = self.outq.get()
		stuff = scaler_queue_payload_to_pixbuf(payload)
		print("scaled")
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
		#print(f"scale_svg({key}), ..., {factor}")
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
	"""
	This gets run as a multiprocessing.Process and does the actual scaling work for 
	MultiprocSvgScaler
	"""
	while True:
		try:
			payload = inq.get(block=True)
			#print(f"payload: {payload}", file=sys.stderr)
			key, svg, factor = payload
			window_id, state = key
			try:
				png_bytes = cairosvg.svg2png(svg, scale=factor)
			except ValueError:
				continue
			fobj = io.BytesIO(png_bytes)
			img = PIL.Image.open(fobj)
			if img.mode != "RGBA":
				img = img.convert(mode="RGBA")
			if state != None:
				cropped_img, x_offset, y_offset = autocrop(img)
			else:
				# Do not crop base image
				cropped_img, x_offset, y_offset = (img, 0, 0)
			#print(f"processing key {key} factor {factor} output {cropped_img.width}x{cropped_img.height} offset {x_offset},{y_offset}")
			img_packet = [cropped_img.tobytes(), cropped_img.width, cropped_img.height, x_offset, y_offset]
			outq.put([key, img_packet, factor])
			if pipe is not None:
				pipe.send(b"!")
		except queue.Empty:
			break
# }}}

class MisterVizStub:# {{{
	def __init__(self, debug=False):# {{{
		self.res_lookup = {}
		self.procs = []
		self.windows = {}
		self.debug = debug
		self.in_shutdown = False
		self.scaler = MultiprocSvgScaler(process_count=1)
		self.scaler.connect("result", self.scaler_handler)
		yaml_basedir = get_yaml_basedir()
		print(f"yaml basedir: {yaml_basedir}")
		if not os.path.exists(yaml_basedir):
			print(f"yaml basedir not found, creating it.")
			os.makedirs(yaml_basedir)
		yaml_files = get_yaml_files(yaml_basedir)
		print(f"yaml files: {yaml_files}")
		if len(yaml_files) == 0:
			print(f"No YAML files found in {yaml_basedir}! Put some YAML and SVG files in there and try running me again.")

		resources = {}
		for yaml_file in yaml_files:
			try:
				resource = MisterVizResourceMap(yaml_file)
				if not resource.config['primary']:
					continue
				#if resource.config['name'] not in resources:
				#	resources[resource.config['name']] = {}
				if resource.name is not None:
					print(f"Found resource \"{resource.name}\"")
					resources[resource.name] = resource
			except Exception as e:
				print(f"Error occurred trying to parse {yaml_file}:")
				for line in traceback.format_exc().splitlines():
					print(f"  exception: {line}")

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
		#print("scaler_handler()")
		key, pixbuf, x_offset, y_offset, factor = payload
		key, state = key
		#key = f"{vid:04x}:{pid:04x}"
		#print(f"key: {key}")
		if key in self.windows:
			print("Found window")
			self.windows[key].pixbuf_receive_handler(state, pixbuf, x_offset, y_offset, factor)
# }}}
	def shutdown(self, *args):# {{{
		if not self.in_shutdown:
			self.in_shutdown = True
			print("shutdown() called", file=sys.stderr)
			#self.disconnect()
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
	def sigint_handler(self, sig, frame):# {{{
		print(f"Signal {sig} caught!", file=sys.stderr)
		self.shutdown()
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

class MisterViz:# {{{
	"""
	This is the primary piece of code for mister_viz.
	"""
	def __init__(self, hostname, do_window=True, do_viz=True, debug=False, log_file=None, ptt_states=[], width=None):# {{{
		self.hostname = hostname
		self.do_window = do_window
		self.do_viz = do_viz
		self.sock = None
		self.debug = debug
		self.log_file = log_file
		self.log_fh = None
		self.width = width
		self.connection_status = "disconnected"
		self.connect_handle = None
		self.socket_handle = None
		self.in_shutdown = False
		if self.hostname is not None:
			self.connect_handle = GLib.idle_add(self.connect_handler)
		self.window = None
		self.seen_window = None
		self.windows = {}
		self.event_handlers = {}
		self.res_lookup = {}
		self.seen_events = {}
		# keepalive_state:
		# * "idle" - waiting to send ping (keepalive_handle is for timer to send next ping)
		# * "wait" - waiting for pong (keepalive handle is for timer to detect timeout)
		self.keepalive_state = None
		self.keepalive_handle = None
		self.ptt_states = ptt_states


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


		if self.do_window:
			self.window = Gtk.Window()
			self.window.connect("destroy", self.ownwindow_destroy_handler)
			vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
			label = Gtk.Label()
			label.set_text("Host:")
			tooltip_text = "The hostname or IP address of the MiSTer to connect to"
			label.set_tooltip_text(tooltip_text)
			hbox.pack_start(label, False, False, 0)
			self.hostname_entry = Gtk.Entry()
			self.hostname_entry.set_tooltip_text(tooltip_text)
			self.hostname_entry.connect("activate", self.connect_button_handler)
			hbox.pack_start(self.hostname_entry, False, False, 0)
			self.connect_button = Gtk.Button(label="Connect")
			self.connect_button.connect("clicked", self.connect_button_handler)
			hbox.pack_start(self.connect_button, False, False, 0)
			vbox.pack_start(hbox, False, False, 0)

			hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
			label = Gtk.Label()
			label.set_text("Logfile:")
			tooltip_text = "The name of the file to write input events to. Leave blank to auto-generate based on the current time."
			label.set_tooltip_text(tooltip_text)
			hbox.pack_start(label, False, False, 0)
			self.logfile_entry = Gtk.Entry()
			self.logfile_entry.set_tooltip_text(tooltip_text)
			self.logfile_entry.connect("activate", self.logfile_entry_activate_handler)
			hbox.pack_start(self.logfile_entry, False, False, 0)
			self.logfile_switch = Gtk.Switch()
			self.logfile_switch.connect("state-set", self.logfile_switch_handler)
			hbox.pack_start(self.logfile_switch, False, False, 0)
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
			but = Gtk.Button(label="Quit")
			but.connect("clicked", self.quit_button_handler)
			hbox.pack_start(but, True, True, 0)
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


		if self.log_file is not None:
			print(f"Logging input events to {self.log_file}")
		if self.do_viz:
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
			yaml_basedir = get_yaml_basedir()
			print(f"yaml basedir: {yaml_basedir}")
			if not os.path.exists(yaml_basedir):
				print(f"yaml basedir not found, creating it.")
				os.makedirs(yaml_basedir)
			yaml_files = get_yaml_files(yaml_basedir)
			print(f"yaml files: {yaml_files}")
			if len(yaml_files) == 0:
				print(f"No YAML files found in {yaml_basedir}! Put some YAML and SVG files in there and try running me again.")

			resources = {}
			for yaml_file in yaml_files:
				try:
					resource = MisterVizResourceMap(yaml_file)
					if not resource.config['primary']:
						continue
					if resource.config['name'] not in resources:
						resources[resource.config['name']] = {}
					print(f"Found resource \"{resource.config['name']}\"")
					resources[resource.config['name']] = resource
				except Exception as e:
					print(f"Error occurred trying to parse {yaml_file}:")
					for line in traceback.format_exc().splitlines():
						print(f"  exception: {line}")

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
		window_id, state = key
		print(f"scaler handler handling {window_id}:{state}")
		if window_id in self.windows:
			self.windows[window_id].pixbuf_receive_handler(state, pixbuf, x_offset, y_offset, factor)
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
	def logfile_entry_activate_handler(self, widget):# {{{
		pass
	# }}}
	def logfile_switch_handler(self, widget, event):# {{{
		pass
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
	def quit_button_handler(self, widget):# {{{
		self.shutdown()
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
		local_timestamp = time.time()
		# Tear down the socket
		if self.sock is not None:
			self.sock.close()
		self.sock = None
		# Remove the io watch for the socket
		if self.socket_handle is not None:
			GLib.source_remove(self.socket_handle)
			self.socket_handle = None
		# Reset button state on any open viz windows
		for handler in self.event_handlers.values():
			handler.reset()
			handler.set_dirty()
		#for win in self.windows.values():
		#	win.reset()
		# Indicate in the logfile that a reset occurred.
		if self.log_file is not None:
			if self.log_fh is None:
				self.log_fh = open(self.log_file, "a")
			print(f"disconnected {local_timestamp}", file=self.log_fh)
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
			if self.log_fh is not None:
				self.log_fh.close()
				self.log_fh = None
		else:
			self.connection_status = "connecting"
			if self.connect_handle is not None:
				GLib.source_remove(self.connect_handle)
				self.connect_handle = None
			self.connect_handle = GLib.timeout_add(100, self.connect_handler)
			
		print("Disconnected!")
	# }}}
	def setup_joystick_ptt(self):# {{{
		self.ptt = JackPushToTalk()
	# }}}
	def connect_handler(self):# {{{
		if self.connect_handle is not None:
			GLib.source_remove(self.connect_handle)
			self.connect_handle = None
		if self.socket_handle is not None:
			# socket_handle holds our IO_OUT watch while we're connecting,
			# holds our IO_IN watch after we're connected.
			GLib.source_remove(self.socket_handle)
			self.socket_handle = None
		if self.keepalive_handle is not None:
			# keepalive_handle holds our connection timeout source when we're connecting
			# holds our keepalive timeout source when we're connected.
			GLib.source_remove(self.keepalive_handle)
			self.keepalive_handle = None
		if self.sock is not None:
			self.sock.close()
			self.sock = None
		if self.window is not None:
			self.connect_button.set_label("Cancel")
			self.hostname_entry.set_text(self.hostname)
			self.hostname_entry.set_sensitive(False)
		self.connection_status = "connecting"
		try:
			self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
			self.sock.setblocking(False)
			print("Connecting...")
			try:
				self.sock.connect((self.hostname, 22101))
			except BlockingIOError:
				self.socket_handle = GLib.io_add_watch(self.sock, GLib.IO_OUT, self.connect_finish_handler)
				self.keepalive_handle = GLib.timeout_add(SOCKET_CONNECT_TIMEOUT, self.connect_timeout_handler)
		except OSError:
			print("Connection failed!")
			if self.connection_status == "connecting":
				self.connect_handle = GLib.timeout_add(100, self.connect_handler)
			return False
	# }}}

	def connect_finish_handler(self, fh, flags):# {{{
		self.socket_handle = None
		if self.keepalive_handle is not None:
			# keepalive_handle holds our connection timeout source when we're connecting
			# holds our keepalive timeout source when we're connected.
			GLib.source_remove(self.keepalive_handle)
			self.keepalive_handle = None

		local_timestamp = time.time()
		print("Connected!")
		if self.log_file is not None:
			if self.log_fh is None:
				self.log_fh = open(self.log_file, "a")
			print(f"connected {local_timestamp}", file=self.log_fh)
		if self.window is not None:
			self.connect_button.set_label("Disconnect")
		self.connection_status = "connected"
		self.socket_handle = GLib.io_add_watch(self.sock, GLib.IO_IN | GLib.IO_HUP, self.socket_handler)
		if self.keepalive_handle is not None:
			GLib.source_remove(self.keepalive_handle)
			self.keepalive_handle = None
		self.keepalive_handle = GLib.timeout_add(SOCKET_KEEPALIVE_INTERVAL, self.keepalive_handler)
		return False
	# }}}
	def connect_timeout_handler(self):
		self.keepalive_handle = None
		if self.sock is not None:
			self.sock.close()
			self.sock = None
		print("Connection timeout!")
		self.connect_handle = GLib.timeout_add(100, self.connect_handler)
		return False
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
			local_timestamp = time.time()
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
				except (ConnectionResetError, OSError):
					data = b''
				#print(f"got {len(data)} bytes")
				if len(data) == 0:
					self.disconnect()
					print("Socket handler senses disconnection!")
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
				player_id = vals[1]
				vid = vals[2]
				pid = vals[3]
				vid_text = f"{vid:04x}"
				pid_text = f"{pid:04x}"
				key = f"{vid_text}:{pid_text}"
				tv_sec = vals[7]
				tv_usec = vals[8]
				timestamp = tv_sec + (tv_usec / 1000000)
				event_vals = [tv_sec, tv_usec] + list(vals[4:7])
				event = evdev_categorize(evdev_InputEvent(*event_vals))
				superevent = event
				if hasattr(event, 'event'):
					event = event.event
				print_event = True
				if ecodes.EV[event.type] == 'EV_SYN':
					print_event = False
				elif ecodes.EV[event.type] == 'EV_MSC':
					print_event = False
				elif ecodes.EV[event.type] == 'EV_KEY':
					if event.value == 2:
						print_event = False
				if print_event:
					print(superevent)
					print(f"  input {timestamp} {inputno} player {player_id} {vid_text}:{pid_text}: {event}")
				if self.log_file is not None:
					if self.log_fh is None:
						self.log_fh = open(self.log_file, "a")
					print(",".join([ str(x) for x in [local_timestamp, tv_sec, tv_usec, inputno, player_id, vid_text, pid_text, event.type, event.code, event.value] ]), file=self.log_fh)

				if key in self.event_handlers:
					handler = self.event_handlers[key]
					ev_type = ecodes.EV[event.type]
					if ev_type == 'EV_SYN':
						handler.apply_event_queue()
						handler.set_dirty()
					else:
						handler.append(event)
				#if key in self.windows:
				#	win = self.windows[key]
				#	ev_type = ecodes.EV[event.type]
				#	if ev_type == 'EV_SYN':
				#		win.apply_event_queue()
				#	else:
				#		win.event_queue.append(event)
				else:
					if vid in self.res_lookup:
						if pid in self.res_lookup[vid]:
							"""
							We've found a vid/pid match in our resource lookups, initialize
							"""
							print(f"Found resource for vid/pid {vid:04x}:{pid:04x}, instantiating window")
							res = self.res_lookup[vid][pid]
							win = MisterVizWindow(parent=self, controller_resource=res, window_id=key)
							self.windows[key] = win
							win.connect("destroy", self.window_destroy_handler)
							if self.width is not None:
								def resize_handler():
									self.windows[key].resize(self.width, self.width)
								GLib.timeout_add(500, resize_handler)
							handler = MisterVizEventHandler(controller_resource=res)
							self.event_handlers[key] = handler
							"""
							Check to see if there are push to talk state(s) defined for this device.
							"""
							if self.ptt is not None and len(self.ptt_states) > 0:
								for ptt_state in self.ptt_states:
									ptt_args = None
									frags = ptt_state.split(":")
									if len(frags) == 5:
										# This state is defined by controller name
										if res.name is not None and frags[0].lower() == res.name.lower():
											ptt_args = frags[1:]
									elif len(frags) == 6:
										# This state is defined by vid+pid
										if frags[0] == f"{vid:04x}" and frags[1] == f"{pid:04x}":
											ptt_args = frags[2:]
									else:
										raise RuntimeError("Incorrect number of frags for ptt_state!")

									if ptt_args is not None:
										print(f"Using this resource as a push-to-talk widget.")
										ptt_swtype = ptt_args[0]
										ptt_swname = ptt_args[1]
										ptt_minval = int(ptt_args[2])
										ptt_maxval = int(ptt_args[3])
										print(f"ptt_swtype: {ptt_swtype}")
										print(f"ptt_swname: {ptt_swname}")
										print(f"ptt_minval: {ptt_minval}")
										print(f"ptt_maxval: {ptt_maxval}")
										if ptt_swtype == 'axis':
											control = handler.res.svg_res.axes[ptt_swname]
										elif ptt_swtype == 'button':
											control = handler.res.svg_res.buttons[ptt_swname]

										def ptt_handler(widget):
											print(f"ptt_handler ({control.value})")
											if control.value >= ptt_minval and control.value <= ptt_maxval:
												self.ptt.set_value(True)
											else:
												self.ptt.set_value(False)

										handler.connect("dirty", ptt_handler)

							def dirty_handler(widget):
								win.trigger_draw()
								widget.reset_dirty()

							handler.connect("dirty", dirty_handler)

				if self.window:
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
				del self.event_handlers[key]
		elif isinstance(window, MisterSeenEventsWindow):
			if self.seen_window is not None:
				self.seen_window = None
		if self.window == None and self.seen_window is None and len(self.windows) == 0:
			self.shutdown()
	# }}}
	def shutdown(self, *args):# {{{
		if not self.in_shutdown:
			self.in_shutdown = True
			print("shutdown() called", file=sys.stderr)
			self.disconnect()
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
	def sigint_handler(self, sig, frame):# {{{
		print(f"Signal {sig} caught!", file=sys.stderr)
		self.shutdown()
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
def svg_scale_to_pixbuf(svg, factor, crop=True):# {{{
	png_bytes = cairosvg.svg2png(svg, scale=factor)
	fobj = io.BytesIO(png_bytes)
	img = PIL.Image.open(fobj)
	if img.mode != "RGBA":
		img = img.convert(mode="RGBA")
	if crop:
		cropped_img, x_offset, y_offset = autocrop(img)
	else:
		cropped_img, x_offset, y_offset = (img, 0, 0)
	cropped_img_bytes = cropped_img.tobytes()
	pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(GLib.Bytes(cropped_img_bytes), GdkPixbuf.Colorspace.RGB, True, 8, cropped_img.width, cropped_img.height, cropped_img.width * 4)
	ret = proppadict()
	ret.pixbuf = pixbuf
	ret.width = cropped_img.width
	ret.height = cropped_img.height
	ret.x_offset = x_offset
	ret.y_offset = y_offset
	return ret
# }}}
class MisterVizRenderer:# {{{
	def __init__(self, controller_resource, width=None, bgcolor=(1, 0, 1, 1), seed=None):# {{{
		self.res = controller_resource
		self.pixbufs = {}
		self.event_queue = []
		self.global_x_offset = 0
		self.global_y_offset = 0
		if seed is not None:
			self.rng = numpy.random.default_rng(numpy.random.PCG64(seed))
		else:
			self.rng = numpy.random.default_rng()
		if width is None:
			self.scalefactor = 1.0
		else:
			# Perform resize on None for scalefactor 1.0 to find native dimensions
			#print("Rendering initial", file=sys.stderr)
			native = svg_scale_to_pixbuf(self.res.svgs[None], 1.0, crop=False)
			# Determine scalefactor based on requested width
			new_dims = resize_aspect(native.width, native.height, width=width)
			self.scalefactor = new_dims[2]
		self.bgcolor = bgcolor
		
		# Scale pixbufs
		for key in self.res.svgs:
			#print(f"Rendering {key} (crop {key is not None})", file=sys.stderr)
			pixbuf = svg_scale_to_pixbuf(self.res.svgs[key], self.scalefactor, key is not None)
			self.pixbufs[key] = [pixbuf.pixbuf, pixbuf.x_offset, pixbuf.y_offset]
	# }}}
	def rumble_handler(self, event):
		print(f"rumble handler {event}", file=sys.stderr)
		#self.global_x_offset, self.global_y_offset = plot_course((0, 0), self.rng.random() * (math.pi * 2), 30)
	def apply_event_queue(self):# {{{
		if not self.res.connected:
			self.res.connected = True
		if self.res.has_rumble:
			self.res.rumbling = False
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
			elif ev_type == 'EV_FF':
				self.res.rumbling = True
				if hasattr(self.res, "rumble_handler"):
					self.res.rumble_handler(event)
		self.event_queue = []
	# }}}
	def reset(self):# {{{
		try:
			self.res.connected = False
			for widget in list(self.res.buttons.values()) + list(self.res.axes.values()) + list(self.res.sticks.values()):
				widget.reset()
			if self.res.has_rumble:
				self.res.rumbling = False
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
	@property # width{{{
	def width(self):
		return self.pixbufs[None][0].get_width()
	# }}}
	@property # height{{{
	def height(self):
		return self.pixbufs[None][0].get_height()
	# }}}
	def push_event(self, event):# {{{
		ev_type = ecodes.EV[event.type]
		if ev_type == 'EV_SYN':
			self.apply_event_queue()
		else:
			self.event_queue.append(event)
	# }}}
	def render(self):# {{{
		if self.res.rumbling:
			self.global_x_offset, self.global_y_offset = plot_course((0, 0), self.rng.random() * (math.pi * 2), 30)
		else:
			self.global_x_offset = 0
			self.global_y_offset = 0
		surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.pixbufs[None][0].get_width(), self.pixbufs[None][0].get_height())
		cr = cairo.Context(surface)
		if self.bgcolor is not None:
			cr.set_source_rgba(*self.bgcolor)
			cr.paint()
		Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[None][0], self.pixbufs[None][1] + self.global_x_offset, self.pixbufs[None][2] + self.global_y_offset)
		cr.paint()
		allstate = set()
		for x in self.res.buttons.values():
			if x.on_stick:
				continue
			allstate |= x.get_state()
		for x in self.res.axes.values():
			allstate |= x.get_state()

		for state in allstate:
			if state in self.res.sticks:
				continue
			if state in self.pixbufs:
				Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[state][0], self.pixbufs[state][1] + self.global_x_offset, self.pixbufs[state][2] + self.global_y_offset)
				cr.paint()

		for k, stick in self.res.sticks.items():
			if stick.has_button:
				if stick.button.value:
					pixkey = f"button:{k}"
				else:
					pixkey = f"stick:{k}"
			else:
				pixkey = f"stick:{k}"
			if pixkey in self.pixbufs:
				offsets = {
					'x': 0,
					'y': 0,
				}
				for off in offsets:
					axis = getattr(stick, f"{off}_axis")
					if axis is not None and axis.value is not None:
						offsets[off] = translate_constrainedint(axis.value, axis.min_value, axis.max_value, axis.min_pos, axis.max_pos)
				if stick.x_axis is not None and stick.y_axis is not None:
					circularize = True
					for attr in ['min_value', 'max_value', 'min_pos', 'max_pos']:
						if getattr(stick.x_axis, attr) != getattr(stick.y_axis, attr):
							circularize= False
							break
					if circularize:
						maxrange = stick.x_axis.max_pos - stick.x_axis.min_pos
						angle = math.atan2(offsets['y'], offsets['x'])
						magnitude = math.sqrt(offsets['x'] * offsets['x'] + offsets['y'] * offsets['y'])
						if magnitude > (maxrange // 2):
							magnitude = maxrange // 2
						offsets['x'] = magnitude * math.cos(angle)
						offsets['y'] = magnitude * math.sin(angle)

				Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[pixkey][0], (offsets['x'] * self.scalefactor) + self.pixbufs[pixkey][1] + self.global_x_offset, (offsets['y'] * self.scalefactor) + self.pixbufs[pixkey][2] + self.global_y_offset)
				cr.paint()
		return surface
		# }}}
# }}}


class MisterVizEventHandler(GObject.GObject):# {{{
	__gsignals__ = {
		"dirty": (GObject.SignalFlags.RUN_FIRST, None, []),
	}
	def __init__(self, controller_resource=None):# {{{
		super().__init__()
		self.res = controller_resource
		self.event_queue = []
		self.dirty_flag = False
	# }}}
	def reset_dirty(self):# {{{
		self.dirty_flag = False
	# }}}
	def set_dirty(self):# {{{
		if not self.dirty_flag:
			self.dirty_flag = True
			self.emit("dirty")
	# }}}
	def apply_event_queue(self):# {{{
		print(f"apply_event_queue ({len(self.event_queue)})")
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
			elif ev_type == 'EV_FF':
				if hasattr(self.res, "rumble_handler"):
					self.res.rumble_handler(event)
				#rumble_delta = 0
				#if self.res.last_rumble is not None:
				#	rumble_delta = event.timestamp() - self.res.last_rumble
				#print(f"RUMBURU {rumble_delta}", file=sys.stderr)
				#self.res.last_rumble = event.timestamp()
		self.event_queue = []
	# }}}
	def append(self, event):# {{{
		self.event_queue.append(event)
	# }}}
	def reset(self, event=None):# {{{
		self.res.connected = False
		try:
			for widget in list(self.res.buttons.values()) + list(self.res.axes.values()) + list(self.res.sticks.values()):
				widget.reset()
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
# }}}


class MisterVizWindow(Gtk.Window):# {{{
	def __init__(self, parent, window_id=None, controller_resource=None, permit_alpha=True):# {{{
		super().__init__()
		self.res = controller_resource
		self.res.rumble_handler = self.rumble_handler
		self.parent = parent
		self.permit_alpha = permit_alpha
		self.event_queue = []
		self.rumble_vect = 0.0
		self.rumble_handler_source = None
		self.global_x_offset = 0
		self.global_y_offset = 0
		if window_id is None:
			self.window_id = base64.b64encode(random.randbytes(32)).decode()
		else:
			self.window_id = window_id

		if hasattr(self.res, 'name'):
			self.set_title(self.res.name)
		if hasattr(self.res, 'scale'):
			self.scalefactor = self.res.scale
		else:
			self.scalefactor = 1.0
		self.connect("screen-changed", self.screen_changed_handler)
		# This needs to be set for transparency, or everything goes all Doom hall of mirrors.
		self.set_app_paintable(True)
		# screen_changed_handler needs to be manually called at least once to enable transparency.
		self.screen_changed_handler(self, None)

		#self.pixbufs = dict([ [x, None] for x in self.res.svgs.keys() ])
		self.pixbufs = {}
		# Resize_handler_id and resize_timer_id store GLib sources related to window resize operations.
		self.resize_handler_id = None
		self.resize_timer_id = None
		# Submit an SVG resize request to the scaler to find our initial pixbuf dimensions.
		#print("Kicking off scaler")
		self.parent.scaler.scale_svg([self.window_id, None], self.res.svgs[None], 1.0)
		self.inflight = True

		#self.viz_width = self.pixbufs[None].get_width()
		#self.viz_height = self.pixbufs[None].get_height()
		# viz_width and viz_height store the "native" width and height for the visualization pixbufs
		# at scalefactor 1.0. They are populated asynchronously in pixbuf_receive_handler.
		self.viz_width = None
		self.viz_height = None
		# win_dims stores the last known dimensions for the actual window, so we can
		# determine if pixbuf resizing needs to happen.
		self.win_dims = None
		self.darea = Gtk.DrawingArea()
		self.darea.connect("draw", self.draw_handler)
		self.add(self.darea)
		#self.resize(int(self.viz_width * scalefactor), int(self.viz_height * scalefactor))
		#self.darea.connect("realize", self.darea_realize_handler)
		self.show_all()
		if DUMP_RENDERS:
			self.res.dump_svgs()
	# }}}
	def screen_changed_handler(self, widget, old_screen):# {{{
		screen = widget.get_screen()
		visual = screen.get_rgba_visual()

		if visual is None or not self.permit_alpha:
			self.has_alpha = False
			visual = screen.get_system_visual()
		else:
			self.has_alpha = True
		widget.set_visual(visual)
	# }}}
	def pixbuf_receive_handler(self, key, pixbuf, x_offset, y_offset, scalefactor):# {{{
		print(f"Receiving pixbuf for state: {key} (scale factor {scalefactor})")
		if key is None:
			# A key of None means we're receiving a base pixbuf
			if self.viz_width is None and self.viz_height is None:
				# If our viz_width and viz_height values are None, we're receiving our first pixbuf,
				# which is of scalefactor 1.0. We use this pixbuf's dimensions to set viz_width and viz_height.
				self.viz_width = pixbuf.get_width()
				self.viz_height = pixbuf.get_height()
				#print(f"Setting viz dimensions to {self.viz_width}x{self.viz_height}")
				if self.scalefactor != 1.0:
					# If our actual desired scalefactor isn't 1.0, resubmit a scale request for the proper
					# desired scalefactor.
					#print(f"Resubmitting SVG for scalefactor {self.scalefactor}")
					self.parent.scaler.scale_svg([self.window_id, None], self.res.svgs[None], self.scalefactor)
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
			#print(f"Adding pixbuf for state {key}")
			self.pixbufs[key] = [pixbuf, x_offset, y_offset]

		next_pixbuf_key = None
		allstate = set()
		for x in self.res.buttons.values():
			if x.on_stick:
				continue
			allstate |= x.get_state()
		for x in self.res.axes.values():
			allstate |= x.get_state()
		if key in allstate:
			self.darea.queue_draw()
		# Populate sticks first
		for k, stick in self.res.sticks.items():
			if stick.has_button:
				if stick.button.value:
					pixkey = f"button:{k}"
				else:
					pixkey = f"stick:{k}"
			else:
				pixkey = f"stick:{k}"
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
			self.parent.scaler.scale_svg([self.window_id, next_pixbuf_key], self.res.svgs[next_pixbuf_key], self.scalefactor)
	# }}}
	def reset(self):# {{{
		self.res.connected = False
		try:
			for widget in list(self.res.buttons.values()) + list(self.res.axes.values()) + list(self.res.sticks.values()):
				widget.reset()
			self.darea.queue_draw()
		except Exception as e:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}")
	# }}}
	def darea_realize_handler(self, widget):# {{{
		#print("darea_realize_handler")
		self.connect("size-allocate", self.resize_handler)
	# }}}
	def resize_handler(self, widget, other):# {{{
		if self.resize_timer_id is not None:
			GLib.source_remove(self.resize_timer_id)
			self.resize_timer_id = None
		self.resize_timer_id = GLib.timeout_add(1000, self.resize_finisher)
	
	# }}}
	def resize_finisher(self):# {{{
		self.resize_timer_id = None
		curr_dims = (self.get_allocated_width(), self.get_allocated_height())
		if curr_dims != self.win_dims:
			self.win_dims = curr_dims
			new_dims = resize_aspect(self.viz_width, self.viz_height, width=curr_dims[0])
			self.scalefactor = new_dims[2]
			self.parent.scaler.scale_svg([self.window_id, None], self.res.svgs[None], self.scalefactor)
	# }}}
	def update_buttonstate(self, new_state):# {{{
		self.buttonstate = set()
		for k, v in self.res.buttonmap.items():
			if new_state & k:
				self.buttonstate.add(v)
		self.darea.queue_draw()
	# }}}
	def trigger_draw(self, *args):# {{{
		self.darea.queue_draw()
	# }}}
	def rumble_handler(self, event):# {{{
		print("rumble handler", file=sys.stderr)
		if self.res.last_rumble is not None:
			print(event.timestamp() - self.res.last_rumble, file=sys.stderr)
			if event.timestamp() - self.res.last_rumble < (1 / 60):
				print("rumble handler DENIED", file=sys.stderr)
				return
		self.res.last_rumble = event.timestamp()

		self.global_x_offset, self.global_y_offset = plot_course((0, 0), random.random() * (math.pi * 2), 30)
		#self.darea.queue_draw()
		if self.rumble_handler_source is not None:
			GLib.source_remove(self.rumble_handler_source)
			self.rumble_handler_source = None
		GLib.timeout_add(int(1000 / 10), self.rumble_finished_handler)
	# }}}
	def rumble_finished_handler(self):# {{{
		if self.rumble_handler_source is not None:
			GLib.source_remove(self.rumble_handler_source)
			self.rumble_handler_source = None
		self.global_x_offset = 0
		self.global_y_offset = 0
		self.darea.queue_draw()
	# }}}
	def draw_handler(self, widget, cr):# {{{
		if self.parent.debug:
			print(f"{time.time()} draw_handler begin", file=sys.stderr)
		try:
			if self.has_alpha:
				cr.set_operator(cairo.OPERATOR_SOURCE)
				cr.set_source_rgba(0, 0, 0, 0)
			else:
				cr.set_source_rgba(1, 0, 1, 1)
			cr.paint()
			cr.set_operator(cairo.OPERATOR_OVER)
			if None not in self.pixbufs:
				return
			# TODO: was this good good?
			#if self.res.has_rumble:
			#	if self.res.rumbling:
			#		print("RUMBLING!", file=sys.stderr)
			#		self.res.rumbling = False
			#		self.rumble_handler()

			Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[None][0], self.pixbufs[None][1] + self.global_x_offset, self.pixbufs[None][2] + self.global_y_offset)
			cr.paint()
			allstate = set()
			for x in self.res.buttons.values():
				if x.on_stick:
					continue
				allstate |= x.get_state()
			for x in self.res.axes.values():
				allstate |= x.get_state()

			for state in allstate:
				if state in self.res.sticks:
					#print(f"state {state} in self.res.sticks")
					continue
				if state in self.pixbufs:
					#print(f"state {state} in self.pixbufs")
					Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[state][0], self.pixbufs[state][1] + self.global_x_offset, self.pixbufs[state][2] + self.global_y_offset)
					cr.paint()
				else:
					pass
					#print(f"state {state} unhandled")

			for k, stick in self.res.sticks.items():
				if stick.has_button:
					if stick.button.value:
						pixkey = f"button:{k}"
					else:
						pixkey = f"stick:{k}"
				else:
					pixkey = f"stick:{k}"
				if pixkey in self.pixbufs:
					offsets = {
						'x': 0,
						'y': 0,
					}
					for off in offsets:
						axis = getattr(stick, f"{off}_axis")
						if axis is not None and axis.value is not None:
							offsets[off] = translate_constrainedint(axis.value, axis.min_value, axis.max_value, axis.min_pos, axis.max_pos)
					if stick.x_axis is not None and stick.y_axis is not None:
						circularize = True
						for attr in ['min_value', 'max_value', 'min_pos', 'max_pos']:
							if getattr(stick.x_axis, attr) != getattr(stick.y_axis, attr):
								circularize= False
								break
						if circularize:
							maxrange = stick.x_axis.max_pos - stick.x_axis.min_pos
							angle = math.atan2(offsets['y'], offsets['x'])
							magnitude = math.sqrt(offsets['x'] * offsets['x'] + offsets['y'] * offsets['y'])
							if magnitude > (maxrange // 2):
								magnitude = maxrange // 2
							offsets['x'] = magnitude * math.cos(angle)
							offsets['y'] = magnitude * math.sin(angle)

					Gdk.cairo_set_source_pixbuf(cr, self.pixbufs[pixkey][0], (offsets['x'] * self.scalefactor) + self.pixbufs[pixkey][1] + self.global_x_offset, (offsets['y'] * self.scalefactor) + self.pixbufs[pixkey][2] + self.global_y_offset)
					cr.paint()
		except Exception:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}", file=sys.stderr)
		if self.parent.debug:
			print(f"{time.time()} draw_handler finish", file=sys.stderr)
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
					ev_code = sorted(ev_code, key=lambda x: [0 if x.startswith("JOYBUTTON_") else 1, len(x)])[0]
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
		parser.add_argument("-n", "--no-window", action="store_false", dest="do_window", default=True, help="Don't create a main window")
		parser.add_argument("-N", "--no-viz", action="store_false", dest="do_viz", default=True, help="Don't spawn visualization windows")
		parser.add_argument("-c", "--console", action="store_true", dest="do_console", default=False, help="Spawn REPL on stdin/stdout")
		parser.add_argument("-l", "--log-file", action="store", dest="log_file", default=None, help="Write events to log file LOG_FILE. Use magic name \":auto:\" to auto-create based on time and date.")
		parser.add_argument("-p", "--ptt", action="append", dest="ptt_states", default=[], help="Add this state to the list of push-to-talk buttons. Can be specified multiple times Format: vid:pid:type:name:minval:maxval or controllername:type:name:minval:maxval")
		parser.add_argument("-w", "--width", action="store", dest="width", default=None, type=int)
		args = parser.parse_args()
		if args.log_file == ':auto:':
			nao = datetime.datetime.now()
			naostr = nao.strftime("%F %T").replace(":", "_")
			log_file = f"mister_viz__{naostr}.log"
		else:
			log_file = args.log_file
		app = MisterViz(args.hostname, debug=args.debug, do_window=args.do_window, do_viz=args.do_viz, log_file=log_file, ptt_states=args.ptt_states, width=args.width)
	else:
		app = MisterViz(None)

	#if ser is None:
	if sys.platform == "linux" and args.do_console:
		import debugrepl, glib_editingline
		cli = glib_editingline.CliInterpreter(None, namespace=globals())
		cli.connect("control-c", app.shutdown)
	else:
		import signal
		signal.signal(signal.SIGINT, app.sigint_handler)
	Gtk.main()
