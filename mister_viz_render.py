#!/usr/bin/env python3
import os, sys, hashlib, struct
from mister_viz import *

from fake_events import InputEvent as evdev_InputEvent
from fake_events import categorize as evdev_categorize
import fake_ecodes as ecodes
import decimal

# Set to either 'qtrle' or 'png'
OUTPUT_TYPE='qtrle'

# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v hevc_nvenc -f matroska ~/mister_viz.mkv
# 1.86x
# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v libvpx-vp9 -row-mt 1 -threads 8 -speed 4 -f matroska ~/mister_viz.mkv
# 1.23x
# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v libvpx-vp9 -row-mt 1 -f matroska ~/mister_viz.mkv
# Git/mister_viz/mister_viz_render.py '/media/Recordings/games/raw/mister_viz__2023-01-09 06_19_03.log' -v 1a61 -p 2049 -y Git/mister_viz/resources/utility_jaystech_nes_to_nes30pro2.yaml -r 59.73 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 59.73 -i - -c:v png -f matroska 'mister_viz__2023-01-09 06_19_03.mkv'

if __name__ == '__main__':
	import locale
	locale.setlocale(locale.LC_ALL, "")
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("log_file")
	parser.add_argument("-w", "--width", dest="width", type=int, default=None, help="Specify scale width")
	parser.add_argument("-v", "--vid", dest="vid", default=None, help="vendorID")
	parser.add_argument("-p", "--pid", dest="pid", default=None, help="productID")
	parser.add_argument("-r", "--framerate", dest="framerate", default=None, type=float, help="frame rate")
	parser.add_argument("-y", "--yaml", dest="yaml_file", default=None, help="Explicitly force this YAML file to be used")
	parser.add_argument("--fudgefactor", dest="fudgefactor", default=None, type=str, help="Specify decimal.Decimal fudge factor to alter timestamps by")
	parser.add_argument("--project", dest="project", default=None, type=str, help="Add a project name to the output video metadata")
	# PARTIALLY IMPLEMENTED.  I GOT FRUSTRATED
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
		

	vid = None
	pid = None
	res = None

	force_states = []


	if args.vid is not None:
		vid = int(args.vid, 16)
	if args.pid is not None:
		pid = int(args.pid, 16)

	if args.yaml_file is not None:
		res = MisterVizResourceMap(args.yaml_file)
	else:
		yaml_files = get_yaml_files(get_yaml_basedir())
		resources = {}
		res_lookup = {}
		for yaml_file in yaml_files:
			try:
				resource = MisterVizResourceMap(yaml_file)
				if not resource.config['primary']:
					continue
				if resource.config['name'] not in resources:
					resources[resource.config['name']] = {}
				print(f"Found resource \"{resource.config['name']}\"", file=sys.stderr)
				resources[resource.config['name']] = resource
			except Exception as e:
				print(f"Error occurred trying to parse {yaml_file}:", file=sys.stderr)
				for line in traceback.format_exc().splitlines():
					print(f"  exception: {line}", file=sys.stderr)

		res_lookup = {}
		for rname in resources:
			res = resources[rname]
			config = res.config
			if config['vid'] not in res_lookup:
				res_lookup[config['vid']] = {}
			if config['pid'] not in res_lookup[config['vid']]:
				res_lookup[(config['vid'], config['pid'])] = res
		
		print(res_lookup.keys(), file=sys.stderr)
		if vid is not None and pid is not None:
			res = res_lookup[(vid, pid)]
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

		
	log_fh = open(args.log_file, "rb")
	sha1 = hashlib.sha1()
	while True:
		data = log_fh.read(65536)
		if len(data) > 0:
			sha1.update(data)
		else:
			break
	seed = struct.unpack(">Q", sha1.digest()[:8])[0]
	log_fh = open(args.log_file, "r")
	if args.ffmpeg_args or args.jffmpeg_args or args.jffmpeg:
		vidpid_qtys = {}
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
	# Framechanges is a dict.  It is keyed by video frame number, and contains a list of input events which occurred
	# during that frame.
	framechanges = {}
	for line in log_fh:
		log_event = parse_logline(line)
		local_timestamp = log_event.local_timestamp
		if fudgefactor is not None:
			local_timestamp = float(decimal.Decimal(local_timestamp) * fudgefactor)
		if isinstance(log_event, LogDisconnection) or isinstance(log_event, LogConnection):
			if ts_start is None:
				continue
			connected_val = isinstance(log_event, LogConnection)
			if tsdelta is not None:
				compensated_timestamp = local_timestamp - tsdelta
			else:
				compensated_timestamp = local_timestamp
			frameno = get_frameno(ts_start, args.framerate, compensated_timestamp)
			if frameno not in framechanges:
				framechanges[frameno] = [True, []]
			else:
				framechanges[frameno][0] = True
			#print(f"{frameno} connected: {connected_val}", file=sys.stderr)
		else:
			ts = log_event.get_timestamp()
			if fudgefactor is not None:
				ts = float(decimal.Decimal(ts) * fudgefactor)
			tsdelta = local_timestamp - ts
			if ts_start is None:
				ts_start = ts
			if vid is not None and log_event.vid != vid:
				continue
			if pid is not None and log_event.pid != pid:
				continue
			if args.ffmpeg_args or args.jffmpeg_args or args.jffmpeg:
				key = (log_event.vid, log_event.pid)
				if key not in vidpid_qtys:
					vidpid_qtys[key] = 0
				vidpid_qtys[key] += 1
			frameno = get_frameno(ts_start, args.framerate, ts)
			superevent = log_event.get_event()
			if hasattr(superevent, 'event'):
				event = superevent.event
			else:
				event = superevent
			if args.parse_events:
				ts_seconds = frameno // args.framerate
				ts_frames  = int(frameno % args.framerate)
				ts_minutes = int(ts_seconds // 60)
				ts_seconds = int(ts_seconds % 60)
				ts_hours   = int(ts_minutes // 60)
				ts_minutes = int(ts_minutes % 60)
				print(f"{ts_hours:02d}:{ts_minutes:02d}:{ts_seconds:02d}:{ts_frames:02d}: {superevent}")
				#print(f"{ts} {frameno} {superevent}")
		#	else:
		#		print(f"{frameno} ({tsdelta}): {superevent}", file=sys.stderr)
			if frameno not in framechanges:
				framechanges[frameno] = [False, []]
			framechanges[frameno][1].append(event)

	if args.ffmpeg_args or args.jffmpeg_args or args.jffmpeg:
		import shlex
		vidpids_by_qty = [ x[0] for x in sorted([ x for x in vidpid_qtys.items() ], key=lambda x: x[1], reverse=True) ]
		res = [ res_lookup[x] for x in vidpids_by_qty if x in res_lookup ][0]
		renderer = MisterVizRenderer(res, width=args.width, bgcolor=None, seed=seed)

		procargs_lhs = []
		procargs_lhs.append(sys.argv[0])
		procargs_lhs.append(args.log_file)
		procargs_lhs.append('-v')
		procargs_lhs.append(f"{res.vid:04x}")
		procargs_lhs.append('-p')
		procargs_lhs.append(f"{res.pid:04x}")
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
		for state_spec in args.force_states:
			procargs_lhs.extend(['-f', state_spec])

	if args.ffmpeg_args:
		procargs_rhs = []
		procargs_rhs.extend(['ffmpeg', '-y', '-f', 'rawvideo', '-pix_fmt', 'bgra'])
		if args.timestamps:
			procargs_rhs.extend(['-video_size', f"{renderer.width}x{renderer.height + timestamp_dims[1] + 5}"])
		else:
			procargs_rhs.extend(['-video_size', f"{renderer.width}x{renderer.height}"])
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
			if os.path.exists(output_file):
				import JaysTerm
				JaysTerm.Term.init()
				print(f"Output file ({output_file}) exists!", file=sys.stderr)
				print(f"Delete it? [y/n]", file=sys.stderr)
				keychar = JaysTerm.Term.getkey()
				if keychar == b'y':
					os.unlink(output_file)
				else:
					print(f"Bailing out!", file=sys.stderr)
			import subprocess
			shim_proc = subprocess.Popen(procargs_rhs, stdin=subprocess.PIPE)
		else:
			sys.exit(0)


	if not args.pretend and not args.parse_events:
		new_framechanges = {}
		for frameno in sorted(framechanges)[:]:
			do_reset, events = framechanges[frameno]
			if do_reset:
				renderer.reset()
			for event in events:
				renderer.push_event(event)
			for control, val in force_states:
				control.set_value(val)
			state = res.dump_state()
			new_framechanges[frameno] = state
			if res.has_rumble and res.rumbling:
				if frameno + 1 not in framechanges:
					res.rumbling = False
					state = res.dump_state()
					new_framechanges[frameno + 1] = state
		del framechanges
		framechanges = new_framechanges
		framechange_qty = len(framechanges)
		#for i, frameno in enumerate(sorted(framechanges), 1):
		#	state = framechanges[frameno]
		#	print(f"{frameno} {state}", file=sys.stderr)
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
			res.load_state(state)
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
			current_frame = frameno
			#print("render", file=sys.stderr)
			surface = renderer.render()

		if args.jffmpeg:
			shim_proc.stdin.close()
			shim_proc.wait()
