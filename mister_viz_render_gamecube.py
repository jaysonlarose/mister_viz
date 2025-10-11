#!/usr/bin/env python3
import os, sys, gi, mister_viz
from mister_viz import *
from gi.repository import GLib, GObject

progname = os.path.split(sys.argv[0])[1]
featurename = os.path.splitext(progname)[0].split('_')[-1]
modulename = f"mister_viz_{featurename}"

import importlib
module = importlib.import_module(modulename)
import decimal

# Set to either 'qtrle' or 'png'
OUTPUT_TYPE='qtrle'

class LogReader(GObject.GObject):
	__gsignals__ = {
		"line": (GObject.SignalFlags.RUN_FIRST, None, [float, str]),
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
			frags = line.split(' ', 1)
			if len(frags) == 1:
				return True
			ts_text, line = frags
			self.last_timestamp = float(ts_text)
			if self.first_timestamp is None:
				self.first_timestamp = self.last_timestamp
			#print(line, file=sys.stderr)
			self.emit("line", self.last_timestamp, line)
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
	import locale
	locale.setlocale(locale.LC_ALL, "")
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("log_file")
	parser.add_argument("-w", "--width", dest="width", type=int, default=None, help="Specify scale width")
	parser.add_argument("-r", "--framerate", dest="framerate", default=None, type=float, help="frame rate")
	parser.add_argument("-y", "--yaml", dest="yaml_file", default=None, help="Explicitly force this YAML file to be used")
	parser.add_argument("--fudgefactor", dest="fudgefactor", default=None, type=str, help="Specify decimal.Decimal fudge factor to alter timestamps by")
	parser.add_argument("--project", dest="project", default=None, type=str, help="Add a project name to the output video metadata")
	parser.add_argument("-f", "--force-state", action="append", dest="force_states", default=[], help="Force this state to the specified value when rendering. Can be specified multiple times. Format: type:name:value")
	parser.add_argument("--get-dims", action="store_true", dest="get_dims", default=False, help="Run me to get final output dimensions")
	parser.add_argument("--pretend", action="store_true", dest="pretend", default=False, help="do everything except output frame data")
	parser.add_argument("--parse-events", action="store_true", dest="parse_events", default=False, help="instead of outputting frames, just output the event that each log entry describes")
	parser.add_argument("--ffmpeg-args", action="store_true", dest="ffmpeg_args", default=False, help="Output sample args suitable for ffmpeg")
	parser.add_argument("--jffmpeg-args", action="store_true", dest="jffmpeg_args", default=False, help="blah blah shim")
	parser.add_argument("--jffmpeg", action="store_true", dest="jffmpeg", default=False, help="blah blah go")
	parser.add_argument("--timestamps", action="store_true", dest="timestamps", default=False, help="Add event timestamps to rendered output")
	args = parser.parse_args()

	if args.timestamps:
		fw = FontWriter("Monospace", "Regular", 10)
		dummy_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 200)
		dummy_context = cairo.Context(dummy_surface)
		fw.set_context(dummy_context)
		timestamp_dims = [ int(x) for x in fw.get_dims(format_timestamp(now_tzaware(), omit_tz=True, precision=3)) ]
		
	if args.fudgefactor:
		decimal.getcontext().prec = 128
		fudgefactor = decimal.Decimal(args.fudgefactor)
	else:
		fudgefactor = None

	res = None
	res = SvgControllerResources(os.path.join(mister_viz.get_yaml_basedir(), module.SVG_FILENAME))

	translator = module.Translator(res)

	force_states = []

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

		for state_spec in args.force_states:
			frags = state_spec.split(":")
			swtype = frags[0]
			swname = frags[1]
			swval  = int(frags[2])
			if swtype == 'axis':
				control = res.axes[swname]
			elif swtype == 'button':
				control = res.buttons[swname]
			force_states.append([control, swval])
		
	log_fh = open(args.log_file, "r")
	# ts_start gets set to the timestamp of the first event in the log
	global ts_start
	ts_start = None
	# each mister_viz event log entry has two timestamps: wallclock time of the input event as determined by
	# the MiSTer's internal timekeeping, and the wllclock time of the network packet received by the machine
	# running mister_viz. We render the log using the MiSTer's clock as the primary time source, but we don't
	# receive the MiSTer's timestamp for disconnect events, because, well, we lost connection with the MiSTer.
	# tsdelta stores the difference between these two timestamps, so we can apply it to the disconnect
	# events.
	tsdelta = None
	current_frame = 0


	loop = GLib.MainLoop()

	reader = LogReader(log_fh)

	parser = module.Parser()
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
		#ts = reader.last_timestamp - reader.first_timestamp
		ts = widget.last_event.timestamp
		if fudgefactor is not None:
			ts = float(decimal.Decimal(ts) * fudgefactor)
		global ts_start
		if ts_start is None:
			ts_start = ts
		ts = ts - ts_start
		frameno = get_frameno(0.0, args.framerate, ts)
		if frameno not in framechanges:
			framechanges[frameno] = []
		for control, val in force_states:
			control.set_value(val)
		framechanges[frameno].append(res.dump_state())
		#print(widget.last_event.timestamp, file=sys.stderr)
		#sys.stderr.write(f"{widget.last_event.timestamp}\r")
		#sys.stderr.flush()
		widget.reset_dirty()

	translator.connect("dirty", dirty_handler)
	reader.startup()
	
	loop.run()
	sys.stderr.write("\n")
	sys.stderr.flush()

	
	print(f"{len(framechanges)} frame changes", file=sys.stderr)

	if args.ffmpeg_args or args.jffmpeg_args or args.jffmpeg:
		import shlex
		renderer = MisterVizRenderer(res, width=args.width, bgcolor=None)

		procargs_lhs = []
		procargs_lhs.append(sys.argv[0])
		procargs_lhs.append(args.log_file)
		output_file = os.path.basename(args.log_file)
		output_file = os.path.splitext(output_file)[0]
		if args.fudgefactor:
			output_file = f"{output_file}__fudged"
		if OUTPUT_TYPE == 'png':
			output_file = f"{output_file}.mkv"
		elif OUTPUT_TYPE == 'qtrle':
			output_file = f"{output_file}.mov"
		procargs_lhs.extend(['-r', f"{args.framerate}"])
		if args.timestamps:
			procargs_lhs.append("--timestamps")
		if args.width:
			procargs_lhs.extend([f"-w", f"{args.width}"])
		if args.fudgefactor:
			procargs_lhs.extend(['--fudgefactor', f"{args.fudgefactor}"])
	if args.ffmpeg_args:
		procargs_rhs = []
		procargs_rhs.extend(['ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgra'])
		if args.timestamps:
			procargs_rhs.extend(['-video_size', f"{renderer.width}x{renderer.height + timestamp_dims[1] + 5}"])
		else:
			procargs_rhs.extend(['-video_size', f"{renderer.width}x{renderer.height}"])
		for state_spec in args.force_states:
			procargs_lhs.extend(['-f', state_spec])
		procargs_rhs.extend(['-framerate', f"{args.framerate}"])
		procargs_rhs.extend(['-i', '-'])
		if OUTPUT_TYPE == 'png':
			procargs_rhs.extend(['-c:v', 'png', '-f', 'matroska'])
		elif OUTPUT_TYPE == 'qtrle':
			procargs_rhs.extend(['-c:v', 'qtrle'])

		if args.fudgefactor:
			if OUTPUT_TYPE == 'qtrle':
				procargs_rhs.extend(['-movflags', 'use_metadata_tags'])
			procargs_rhs.extend(['-metadata', f"fudgefactor={args.fudgefactor}"])
		if args.project:
			procargs_rhs.extend(['-metadata', f"project={args.project}"])
		procargs_rhs.extend([output_file])
		print(f"{shlex.join(procargs_lhs)} | {shlex.join(procargs_rhs)}")
		sys.exit(0)
	if args.jffmpeg_args or args.jffmpeg:
		procargs_rhs = []
		procargs_rhs.extend(['/home/jayson/Git/mister_viz/jffmpeg_shim.py'])
		if args.timestamps:
			procargs_rhs.extend(['--width', f"{renderer.width}", '--height', f"{renderer.height + timestamp_dims[1] + 5}"])
		else:
			procargs_rhs.extend(['--width', f"{renderer.width}", '--height', f"{renderer.height}"])
		procargs_rhs.extend(['--frames', f"{max(list(framechanges.keys()))}"])
		procargs_rhs.extend(['--fps', f"{args.framerate}"])
		if args.fudgefactor:
			procargs_rhs.extend(['--fudgefactor', f"{args.fudgefactor}"])
		if args.project:
			procargs_rhs.extend(['--project', f"{args.project}"])
		procargs_rhs.extend([output_file])
		print(f"{shlex.join(procargs_lhs)} | {shlex.join(procargs_rhs)}")
		if args.jffmpeg:
			import subprocess
			shim_proc = subprocess.Popen(procargs_rhs, stdin=subprocess.PIPE)
		else:
			sys.exit(0)



	#for fc in sorted(framechanges):
	#	if len(framechanges[fc]) > 1:
	#		print(f"{fc} {len(framechanges[fc])}", file=sys.stderr)
	#		for val in framechanges[fc]:
	#			print(f"  {val}", file=sys.stderr)
	

	#for i, frameno in enumerate(sorted(framechanges), 1):
	#	print(f"i {i} frameno {frameno}", file=sys.stderr)


	surface_cache = {}
	# Boil down frames that have multiple changes associated with them down to the most "interesting" version.
	new_framechanges = {}
	for frameno in sorted(framechanges)[:]:
		states = framechanges[frameno]
		most_interesting_state = sorted(states, key=lambda x: sum(x[0]), reverse=True)[0]
		new_framechanges[frameno] = most_interesting_state
		if most_interesting_state != states[-1]:
			if frameno + 1 not in framechanges:
				new_framechanges[frameno + 1] = states[-1]
	del framechanges
	framechanges = new_framechanges
	framechange_qty = len(framechanges)

	if args.parse_events:
		for frameno in sorted(framechanges):
			state = framechanges[frameno]
			res.load_state(state)
			ts_seconds = frameno // args.framerate
			ts_frames  = int(frameno % args.framerate)
			ts_minutes = int(ts_seconds // 60)
			ts_seconds = int(ts_seconds % 60)
			ts_hours   = int(ts_minutes // 60)
			ts_minutes = int(ts_minutes % 60)
			#print(f"{ts_hours}:{ts_minutes}:{ts_seconds}:{ts_frames}: {res.format_state()}")

			print(f"{ts_hours:02d}:{ts_minutes:02d}:{ts_seconds:02d}:{ts_frames:02d}: {res.format_state()}")

	if not args.pretend and not args.parse_events:
		if args.jffmpeg:
			output_fh = shim_proc.stdin
		else:
			output_fh = sys.stdout.buffer
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


			state = framechanges[frameno]
			#sys.stderr.write("\x1b[2K\x1b[1G")
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
			for j in range(frame_gap):
				#print(f"frame {frameno - (frame_gap - j)} frameno {frameno} gap {j}/{frame_gap}", file=sys.stderr)
				output_fh.write(surface_bytes)
			if state not in surface_cache:
				res.load_state(state)
				#print("render", file=sys.stderr)
				surface = renderer.render()
				surface_cache[state] = surface
			else:
				surface = surface_cache[state]
			current_frame = frameno

		if args.jffmpeg:
			shim_proc.stdin.close()
			shim_proc.wait()
