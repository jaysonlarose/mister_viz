#!/usr/bin/env python3
import os, sys
from mister_viz import *

from fake_events import InputEvent as evdev_InputEvent
from fake_events import categorize as evdev_categorize
import fake_ecodes as ecodes
import math

# ./mister_viz_render.py ~/mister_viz__2022-11-29\ 21_25_56.log -v 2dc8 -p 2865 -r 60.1 | ffmpeg -f rawvideo -pix_fmt bgra -video_size 602x293 -framerate 60.1 -i - -c:v hevc_nvenc -f matroska ~/mister_viz.mkv

class LogEvent:
	def __init__(self, line):
		frags = line.strip().split(',')
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
	def get_event(self):
		event_vals = [self.tv_sec, self.tv_usec, self.ev_type, self.ev_code, self.ev_value]
		return evdev_categorize(evdev_InputEvent(*event_vals))
	def get_timestamp(self):
		return self.tv_sec + (self.tv_usec / 1000000)

def get_frameno(start, rate, timestamp):
	"""
	Given a start timestamp and a framerate, returns which frame that the provided timestamp
	would occur in.
	"""
	offset = timestamp - start
	return math.ceil(offset * rate)


if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("log_file")
	parser.add_argument("-w", "--width", dest="width", type=int, default=None, help="Specify scale width")
	parser.add_argument("-v", "--vid", dest="vid", default=None, help="vendorID")
	parser.add_argument("-p", "--pid", dest="pid", default=None, help="productID")
	parser.add_argument("-r", "--framerate", dest="framerate", default=None, type=float, help="frame rate")
	parser.add_argument("--get-dims", action="store_true", dest="get_dims", default=False, help="Run me to get final output dimensions")
	parser.add_argument("--pretend", action="store_true", dest="pretend", default=False, help="do everything except output frame data")
	parser.add_argument("--parse-events", action="store_true", dest="parse_events", default=False, help="instead of outputting frames, just output the event that each log entry describes")
	args = parser.parse_args()

	vid = int(args.vid, 16)
	pid = int(args.pid, 16)

	yaml_files = get_yaml_files(get_yaml_basedir())
	resources = {}
	res_lookup = {}
	for yaml_file in yaml_files:
		try:
			resource = ControllerResources(yaml_file)
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
			res_lookup[config['vid']][config['pid']] = res
	
	print(res_lookup.keys(), file=sys.stderr)
	res = res_lookup[vid][pid]
	res.connected = True
	renderer = MisterVizRenderer(res, width=args.width)
	surface = renderer.render()

	if args.get_dims:
		print(f"{renderer.width}x{renderer.height}")
		sys.exit(0)
	
	log_fh = open(args.log_file, "r")
	ts_start = None
	tsdelta = None
	current_frame = 0
	framechanges = {}
	for line in log_fh:
		line = line.strip()
		if line.startswith("disconnected ") or line.startswith('connected '):
			if ts_start is None:
				continue
			frags = line.split()
			if frags[0] == "disconnected":
				connected_val = False
			else:
				connected_val = True
			local_timestamp = float(frags[1])
			if tsdelta is not None:
				compensated_timestamp = local_timestamp - tsdelta
			else:
				compensated_timestamp = local_timestamp
			frameno = get_frameno(ts_start, args.framerate, compensated_timestamp)
			if frameno not in framechanges:
				framechanges[frameno] = [connected_val, []]
			else:
				framechanges[frameno][0] = connected_val
			print(f"{frameno} connected: {connected_val}", file=sys.stderr)
		else:
			log_event = LogEvent(line)
			ts = log_event.get_timestamp()
			tsdelta = log_event.local_timestamp - ts
			if ts_start is None:
				ts_start = ts
			if log_event.vid != vid:
				continue
			if log_event.pid != pid:
				continue
			frameno = get_frameno(ts_start, args.framerate, ts)
			superevent = log_event.get_event()
			if hasattr(superevent, 'event'):
				event = superevent.event
			else:
				event = superevent
			if args.parse_events:
				print(f"{ts} {frameno} {superevent}")
			else:
				print(f"{frameno} ({tsdelta}): {superevent}", file=sys.stderr)
			if frameno not in framechanges:
				framechanges[frameno] = [True, []]
			framechanges[frameno][1].append(event)

	if not args.pretend and not args.parse_events:
		for frameno in sorted(framechanges):
			do_reset, events = framechanges[frameno]
			if do_reset:
				renderer.reset()
			for event in events:
				renderer.push_event(event)
			frame_gap = frameno - current_frame
			surface_bytes = bytes(list(surface.get_data()))
			for i in range(frame_gap):
				sys.stdout.buffer.write(surface_bytes)
			current_frame = frameno
			surface = renderer.render()


