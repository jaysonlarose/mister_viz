#!/usr/bin/env python3
import os, sys
from mister_viz import *

from fake_events import InputEvent as evdev_InputEvent
from fake_events import categorize as evdev_categorize
import fake_ecodes as ecodes

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("log_file")
	args = parser.parse_args()

	log_fh = open(args.log_file, "r")
	lines = [ x.strip() for x in log_fh ]
	max_width = max([ len(x) for x in lines ])
	for line in lines:
		log_event = parse_logline(line)
		if not isinstance(log_event, LogEvent):
			continue
		superevent = log_event.get_event()
		if hasattr(superevent, 'event'):
			event = superevent.event
		else:
			event = superevent
		ts_text = format_timestamp(timestamp_to_localdatetime(log_event.get_timestamp()), omit_tz=True, precision=3)
		print(f"{line.ljust(max_width)} # {ts_text} {superevent}")
