#!/usr/bin/env python3

import mister_viz
import fake_ecodes as ecodes
import fake_events

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("log_file")
	args = parser.parse_args()

	log_fh = open(args.log_file, "r")
	ff_start = None
	for line in log_fh:

		log_event = mister_viz.parse_logline(line)
		if isinstance(log_event, mister_viz.LogDisconnection) or isinstance(log_event, mister_viz.LogConnection):
			continue
		superevent = log_event.get_event()
		if hasattr(superevent, "event"):
			event = superevent.event
		else:
			event = superevent
		print(event)
		print(hex(log_event.vid), hex(log_event.pid), log_event.get_event())
		if event.type == fake_events.EV_FF:
			if event.code == 0:
				if event.value == 1:
					ff_start = log_event
				elif event.value == 0:
					duration = log_event.get_timestamp() - ff_start.get_timestamp()
					ff_start = None
					print(f"ff duration: {duration}")
