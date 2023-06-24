#!/usr/bin/env python3
import os, sys, gi
from mister_viz import *
from mister_viz_openvizsla import *

from gi.repository import GLib, GObject

from fake_events import InputEvent as evdev_InputEvent
from fake_events import categorize as evdev_categorize
import fake_ecodes as ecodes


class LogReader(GObject.GObject):
	__gsignals__ = {
		"line": (GObject.SignalFlags.RUN_FIRST, None, [GObject.TYPE_PYOBJECT]),
		"finished": (GObject.SignalFlags.RUN_FIRST, None, []),
	}
	def __init__(self, fh):
		super().__init__()
		self.fh = fh
		self.last_timestamp = None
		self.first_timestamp = None
	def startup(self):
		GLib.io_add_watch(self.fh, GLib.IO_IN | GLib.IO_HUP, self.line_handler)

	def line_handler(self, fh, flags):
		if flags & GLib.IO_IN:
			line = self.fh.readline()
			if len(line) == 0:
				self.emit("finished")
				return False
			line = line.strip()
			ts_text, line = line.split(' ', 1)
			self.last_timestamp = float(ts_text)
			if self.first_timestamp is None:
				self.first_timestamp = self.last_timestamp
			#print(line, file=sys.stderr)
			self.emit("line", line)
			return True
		if flags & GLib.IO_HUP:
			self.fh.close()
			return False


# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v hevc_nvenc -f matroska ~/mister_viz.mkv
# 1.86x
# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v libvpx-vp9 -row-mt 1 -threads 8 -speed 4 -f matroska ~/mister_viz.mkv
# 1.23x
# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v libvpx-vp9 -row-mt 1 -f matroska ~/mister_viz.mkv
# Git/mister_viz/mister_viz_render.py '/media/Recordings/games/raw/mister_viz__2023-01-09 06_19_03.log' -v 1a61 -p 2049 -y Git/mister_viz/resources/utility_jaystech_nes_to_nes30pro2.yaml -r 59.73 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 59.73 -i - -c:v png -f matroska 'mister_viz__2023-01-09 06_19_03.mkv'

if __name__ == '__main__':
	config_basedir = get_yaml_basedir()
	available_modules = [ os.path.splitext(x)[0][len("openvizsla_"):] for x in os.listdir(config_basedir) if os.path.splitext(x)[1] == ".py" ]
	import locale
	locale.setlocale(locale.LC_ALL, "")
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("module_name", action="store", choices=available_modules, help="Translation module to invoke")
	parser.add_argument("log_file")
	parser.add_argument("-w", "--width", dest="width", type=int, default=None, help="Specify scale width")
	parser.add_argument("-r", "--framerate", dest="framerate", default=None, type=float, help="frame rate")
	parser.add_argument("-y", "--yaml", dest="yaml_file", default=None, help="Explicitly force this YAML file to be used")
	parser.add_argument("--get-dims", action="store_true", dest="get_dims", default=False, help="Run me to get final output dimensions")
	parser.add_argument("--pretend", action="store_true", dest="pretend", default=False, help="do everything except output frame data")
	parser.add_argument("--parse-events", action="store_true", dest="parse_events", default=False, help="instead of outputting frames, just output the event that each log entry describes")
	parser.add_argument("--ffmpeg-args", action="store_true", dest="ffmpeg_args", default=False, help="Output sample args suitable for ffmpeg")
	parser.add_argument("--timestamps", action="store_true", dest="timestamps", default=False, help="Add event timestamps to rendered output")
	args = parser.parse_args()

	module_path = os.path.join(config_basedir, f"openvizsla_{args.module_name}.py")

	import importlib.util
	spec = importlib.util.spec_from_file_location("abcxyz", module_path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)

	if args.timestamps:
		fw = FontWriter("Monospace", "Regular", 10)
		dummy_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 200)
		dummy_context = cairo.Context(dummy_surface)
		fw.set_context(dummy_context)
		timestamp_dims = [ int(x) for x in fw.get_dims(format_timestamp(now_tzaware(), omit_tz=True, precision=3)) ]
		

	res = None
	res = SvgControllerResources(os.path.join(mister_viz.get_yaml_basedir(), module.svg_filename))

	translator = module.Translator(res)

	if res is not None:
		res.connected = True
		renderer = MisterVizRenderer(res, width=args.width, bgcolor=None)
		surface = renderer.render()

		if args.get_dims:
			if args.timestamps:
				print(f"{renderer.width}x{renderer.height + timestamp_dims[1] + 5}")
			else:
				print(f"{renderer.width}x{renderer.height}")
			sys.exit(0)
		
	log_fh = open(args.log_file, "r")
	# ts_start gets set to the timestamp of the first event in the log
	ts_start = None
	# each mister_viz event log entry has two timestamps: wallclock time of the input event as determined by
	# the MiSTer's internal timekeeping, and the wllclock time of the network packet received by the machine
	# running mister_viz. We render the log using the MiSTer's clock as the primary time source, but we don't
	# receive the MiSTer's timestamp for disconnect events, because, well, we lost connection with the MiSTer.
	# tsdelta stores the difference between these two timestamps, so we can apply it to the disconnect
	# events.
	tsdelta = None
	current_frame = 0



	if args.ffmpeg_args:
		import shlex
		renderer = MisterVizRenderer(res, width=args.width, bgcolor=None)

		procargs_lhs = []
		procargs_lhs.append(sys.argv[0])
		procargs_lhs.append(args.module_name)
		procargs_lhs.append(args.log_file)
		procargs_lhs.extend(['-r', f"{args.framerate}"])
		if args.timestamps:
			procargs_lhs.append("--timestamps")
		if args.width:
			procargs_lhs.extend([f"-w", f"{args.width}"])
		procargs_rhs = []
		procargs_rhs.extend(['ffmpeg', '-f', 'rawvideo', '-pix_fmt', 'bgra'])
		if args.timestamps:
			procargs_rhs.extend(['-video_size', f"{renderer.width}x{renderer.height + timestamp_dims[1] + 5}"])
		else:
			procargs_rhs.extend(['-video_size', f"{renderer.width}x{renderer.height}"])
		procargs_rhs.extend(['-framerate', f"{args.framerate}"])
		procargs_rhs.extend(['-i', '-', '-c:v', 'png', '-f', 'matroska', 'mister_viz.mkv'])
		print(f"{shlex.join(procargs_lhs)} | {shlex.join(procargs_rhs)}")
		sys.exit(0)


	loop = GLib.MainLoop()

	reader = LogReader(log_fh)

	parser = OpenVizslaParser()
	translator = module.Translator(res)
	reader.connect("line", parser.line_handler)

	def reader_finished_handler(widget):
		loop.quit()

	reader.connect("finished", reader_finished_handler)

	parser.connect("event", translator.event_handler)

	# Framechanges is a dict.  It is keyed by video frame number, and contains a list of input events which occurred
	# during that frame.
	framechanges = {}
	def dirty_handler(widget):
		ts = reader.last_timestamp - reader.first_timestamp
		frameno = get_frameno(0.0, args.framerate, ts)
		if frameno not in framechanges:
			framechanges[frameno] = []
		framechanges[frameno].append(res.dump_state())
		#print(widget.last_event.timestamp, file=sys.stderr)
		sys.stderr.write(f"{widget.last_event.timestamp}\r")
		sys.stderr.flush()
		widget.reset_dirty()

	translator.connect("dirty", dirty_handler)
	reader.startup()
	
	loop.run()
	sys.stderr.write("\n")
	sys.stderr.flush()

	

	for fc in sorted(framechanges):
		if len(framechanges[fc]) > 1:
			print(f"{fc} {len(framechanges[fc])}", file=sys.stderr)
			for val in framechanges[fc]:
				print(f"  {val}", file=sys.stderr)
	


	if not args.pretend and not args.parse_events:
		for frameno in sorted(framechanges)[:]:
			states = framechanges[frameno]
			most_interesting_state = sorted(states, key=lambda x: sum(x[0]), reverse=True)[0]
			if most_interesting_state != states[-1]:
				if frameno + 1 not in framechanges:
					framechanges[frameno + 1] = [states[-1]]
		framechange_qty = len(framechanges)
		for i, frameno in enumerate(sorted(framechanges), 1):
			if args.timestamps:
				#print("timestamps", file=sys.stderr)
				timestamp_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, *timestamp_dims)
				timestamp_context = cairo.Context(timestamp_surface)
				fw.set_context(timestamp_context)
				timestamp_context.set_source_rgba(1.0, 1.0, 1.0, 1.0)
				timestamp_context.rectangle(0, 0, *timestamp_dims)
				timestamp_context.fill()
				timestamp_context.set_source_rgba(0.0, 0.0, 0.0, 1.0)
				frame_timestamp = ts_start + (frameno / args.framerate)
				frame_timestamp_text = format_timestamp(timestamp_to_localdatetime(frame_timestamp), omit_tz=True, precision=3)
				fw.render(frame_timestamp_text, 0, 0)


			states = framechanges[frameno]
			most_interesting_state = sorted(states, key=lambda x: sum(x[0]), reverse=True)[0]
			sys.stderr.write("\x1b[2K\x1b[1G")
			res.load_state(most_interesting_state)
			frame_gap = frameno - current_frame
			if args.timestamps:
				#print("compositing", file=sys.stderr)
				composite_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, surface.get_width(), surface.get_height() + timestamp_surface.get_height() + 5)
				context = cairo.Context(composite_surface)
				context.set_source_surface(surface, 0, 0)
				context.paint()
				context.set_source_surface(timestamp_surface, 0, surface.get_height() + 5)
				context.paint()
				surface_bytes = bytes(list(composite_surface.get_data()))
			else:
				surface_bytes = bytes(list(surface.get_data()))
			for i in range(frame_gap):
				#print(f"frame {frameno - (frame_gap - i)} frameno {frameno} gap {i}/{frame_gap}", file=sys.stderr)
				sys.stdout.buffer.write(surface_bytes)
			current_frame = frameno
			#print("render", file=sys.stderr)
			surface = renderer.render()


