#!/usr/bin/env python3
import os, sys
from mister_viz import *

from fake_events import InputEvent as evdev_InputEvent
from fake_events import categorize as evdev_categorize
import fake_ecodes as ecodes

if __name__ == '__main__':
	import argparse
	import pprint
	parser = argparse.ArgumentParser()
	parser.add_argument("log_dir")
	args = parser.parse_args()

	vid = 0x2dc8
	pid = 0x6006

	tallies = {}
	presses = {}
	releases = {}
	for root, dirs, files in os.walk(args.log_dir):
		for f in files:
			if not (f.startswith("mister_viz") and f.endswith(".log")):
				continue
			path = os.path.join(root, f)
			print(path)

			log_fh = open(path, "r")
			for line in log_fh:
				try:
					log_event = parse_logline(line)
				except ValueError:
					break
				if not isinstance(log_event, LogEvent):
					continue
				if log_event.pid != pid:
					continue
				if log_event.vid != vid:
					continue

				if log_event.ev_type != ecodes.EV_KEY:
					continue

				#if log_event.ev_value != 1:
				#	continue

				keyname = ecodes.BTN[log_event.ev_code]
				if isinstance(keyname, list):
					keyname = keyname[0]
				if log_event.ev_value == 1:
					if keyname not in presses:
						presses[keyname] = 0
					presses[keyname] += 1
				elif log_event.ev_value == 0:
					if keyname not in releases:
						releases[keyname] = 0
					releases[keyname] += 1
				#if keyname not in tallies:
				#	tallies[keyname] = 0
				#tallies[keyname] += 1

				#superevent = log_event.get_event()
				#if hasattr(superevent, 'event'):
				#	event = superevent.event
				#else:
				#	event = superevent
				#ts_text = format_timestamp(timestamp_to_localdatetime(log_event.get_timestamp()), omit_tz=True, precision=3)
				#print(f"{keyname} {ts_text} {superevent}")

			#pprint.pprint(tallies)
			pprint.pprint(presses)
			pprint.pprint(releases)
