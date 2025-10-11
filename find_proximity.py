#!/usr/bin/env python3

# ~/Git/mister_viz/find_proximity.py /media/Recordings/games/raw 'recording__2024-03-25 16_34_18__audiofixed.mkv' 'recording__2024-03-27 16_16_59__audiofixed.mkv' 'recording__2024-04-01 16_47_44__audiofixed.mkv' 'recording__2024-04-03 17_52_17__audiofixed.mkv' 'recording__2024-04-04 16_45_42__audiofixed.mkv' 'recording__2024-04-05 15_54_19__audiofixed.mkv' 'recording__2024-04-06 14_15_24__audiofixed.mkv' 'recording__2024-04-08 16_49_47__audiofixed.mkv' 'recording__2024-04-12 14_50_59__audiofixed.mkv' 'recording__2024-04-14 19_27_09__audiofixed.mkv' 'recording__2024-04-15 16_54_25__audiofixed.mkv' 'recording__2024-04-20 14_26_27__audiofixed.mkv' 'recording__2024-04-21 15_01_44__audiofixed.mkv' 'recording__2024-04-21 19_27_55__audiofixed.mkv' 'recording__2024-04-22 08_47_53__audiofixed.mkv' 'recording__2024-04-22 16_54_33__audiofixed.mkv' 'recording__2024-04-23 17_52_27__audiofixed.mkv' 'recording__2024-04-24 16_55_25__audiofixed.mkv' 'recording__2024-04-25 15_46_07__audiofixed.mkv' 'recording__2024-04-27 23_30_45__audiofixed.mkv' 'recording__2024-04-29 16_56_44__audiofixed.mkv' 'recording__2024-05-01 18_45_27__audiofixed.mkv' 'recording__2024-05-02 16_25_22__audiofixed.mkv' 'recording__2024-05-03 18_55_37__audiofixed.mkv' 'recording__2024-05-04 04_29_39__audiofixed.mkv' 'recording__2024-05-05 04_50_58__audiofixed.mkv' 'recording__2024-05-05 16_11_36__audiofixed.mkv' 'recording__2024-05-06 16_07_45__audiofixed.mkv' 'recording__2024-05-08 19_07_41__audiofixed.mkv' 'recording__2024-05-09 02_19_01__audiofixed.mkv' 'recording__2024-05-09 17_11_49__audiofixed.mkv' 'recording__2024-05-10 01_34_15__audiofixed.mkv' 'recording__2024-05-10 16_23_18__audiofixed.mkv' 'recording__2024-05-10 21_54_13__audiofixed.mkv' 'recording__2024-05-11 20_55_40__audiofixed.mkv' | while IFS= read -r X ; do /home/jayson/Git/mister_viz/mister_viz_render_openvizsla.py pro2d "$X" -r 60.0 -w 256 -f button:rpaddle:0 --ffmpeg-args 2>/dev/null ; done

import os, sys, dateutil.parser, re, vidinfo, pytz.reference, datetime, jlib, functools
from jlib import natsort


VIZ_PREFIXES = [
	'mister_viz',
	'openvizsla',
	'snes',
	'nes',
	'playstation2',
	'gamecube',
	'n64',
	'genesis',
]

VIZ_SUFFIXES = [
	'.log',
]

VIZ_BLACKLISTS = [
	'_keynotes_',
]

VIZ_PREFIXES_COMMADELIM = [
	'mister_viz',
]

pat_timestamp = re.compile(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hour>\d{2})_(?P<minute>\d{2})_(?P<second>\d{2})')

def pat_timestamp_to_datetime(mat, tzinfo=pytz.reference.Local):
	text_ymd = '-'.join([ mat.group(x) for x in ['year', 'month', 'day'] ])
	text_hms = ':'.join([ mat.group(x) for x in ['hour', 'minute', 'second'] ])
	text_timestamp = ' '.join([text_ymd, text_hms])
	datetime_timestamp = dateutil.parser.parse(text_timestamp).replace(tzinfo=tzinfo)
	return datetime_timestamp

def is_within(a_start, a_end, b_start, b_end):
	"""
	Returns true if the time range specified by b_start and b_end lies, at least in part,
	inside the range specified by a_start and a_end.
	"""
	return a_start <= b_end and b_start <= a_end

def find_log_end_timestamp(path):
	import file_read_backwards
	fn = os.path.split(path)[1]
	comma_delim = False
	for prefix in VIZ_PREFIXES_COMMADELIM:
		if fn.startswith(prefix):
			comma_delim = True
			break
	frb = file_read_backwards.FileReadBackwards(path)
	timestamp = None
	try:
		while True:
			line = frb.readline()
			if len(line) == 0:
				raise ValueError
			frags = line.split(',' if comma_delim else ' ')
			try:
				timestamp = float(frags[0])
				break
			except ValueError:
				continue
	finally:
		frb.close()
	return jlib.timestamp_to_utcdatetime(timestamp)



if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("viz_log_dir")
	parser.add_argument("video_files", nargs="+")
	args = parser.parse_args()

	log_files = []

	for fn in sorted(os.listdir(args.viz_log_dir), key=natsort.nocase):
		path = os.path.join(args.viz_log_dir, fn)
		if not os.path.isfile(path):
			#print(f"{path} disqualified")
			continue
		suffix_matches = functools.reduce(lambda x, y: x | y, [ fn.endswith(x) for x in VIZ_SUFFIXES ])
		if not suffix_matches:
			#print(f"{path} disqualified")
			continue
		prefix_matches = functools.reduce(lambda x, y: x | y, [ fn.startswith(x) for x in VIZ_PREFIXES ])
		if not prefix_matches:
			#print(f"{path} disqualified")
			continue
		blacklist_matches = functools.reduce(lambda x, y: x | y, [ x in fn for x in VIZ_BLACKLISTS ])
		if blacklist_matches:
			#print(f"{path} disqualified (blacklist)")
			continue
		#print(f"checking {path}")
		mat = pat_timestamp.search(fn)
		start_timestamp = pat_timestamp_to_datetime(mat)
		try:
			end_timestamp = find_log_end_timestamp(path)
		except ValueError:
			#print(f"{path} disqualified")
			continue

		log_files.append([path, start_timestamp, end_timestamp])
		#print(f"{path} start {start_timestamp} end {end_timestamp}")


	for path in args.video_files:
		fn = os.path.split(path)[1]
		mat = pat_timestamp.search(fn)
		start_timestamp = pat_timestamp_to_datetime(mat)
		v = vidinfo.vidinfo(path)
		duration = datetime.timedelta(seconds=v['duration'])
		end_timestamp = start_timestamp + duration
		#print(f"{fn} start {start_timestamp} end {end_timestamp} duration {jlib.timedelta_to_DHMS(duration)}")
		for (log_path, log_start, log_end) in log_files:
			if is_within(start_timestamp, end_timestamp, log_start, log_end):
				#print(f"    {os.path.split(log_path)[1]}")
				print(log_path)
