#!/usr/bin/env python3

import datetime
import jlib
import re
import os
import sys
from jlib import natsort
import pytz.reference

pat_timestamp = re.compile(r'(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2}) (?P<hour>\d{2})_(?P<minute>\d{2})_(?P<second>\d{2})')

def pat_timestamp_to_datetime(mat, tzinfo=pytz.reference.Local):
	import dateutil.parser
	text_ymd = '-'.join([ mat.group(x) for x in ['year', 'month', 'day'] ])
	text_hms = ':'.join([ mat.group(x) for x in ['hour', 'minute', 'second'] ])
	text_timestamp = ' '.join([text_ymd, text_hms])
	datetime_timestamp = dateutil.parser.parse(text_timestamp).replace(tzinfo=tzinfo)
	return datetime_timestamp

def get_timestamp_from_string(text):
	mat = pat_timestamp.search(text)
	timestamp = pat_timestamp_to_datetime(mat)
	return timestamp

def is_within(a_start, a_end, b_start, b_end):
	"""
	Returns true if the time range specified by b_start and b_end lies, at least in part,
	inside the range specified by a_start and a_end.
	"""
	return a_start <= b_end and b_start <= a_end

def find_log_end_timestamp(path):
	VIZ_PREFIXES_COMMADELIM = []
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

def find_keynotes_files(dirpath):
	files = sorted(os.listdir(dirpath), key=natsort.nocase)
	ret = []
	for f in files:
		if not f.startswith("mister_viz_keynotes__"):
			continue
		if not f.endswith(".log"):
			continue
		ret.append(f)
	return ret

def get_videofile_duration(path):
	import vidinfo
	info = vidinfo.vidinfo(path)
	duration = datetime.timedelta(seconds=info['duration'])
	return duration

def get_videofile_framerate(path):
	import vidinfo
	info = vidinfo.vidinfo(path)
	return info['fps']

def get_bookmarks_from_file(path):
	import jtag
	import json
	tg = jtag.SqliteTagObject()
	ino = tg.get_inode(path)
	ret = {}
	if 'org.interlaced.jmpv_bookmarks' in ino.attrs:
		bm_list = json.loads(ino.attrs['org.interlaced.jmpv_bookmarks'])
		for mark in bm_list:
			ret[mark['time']] = mark['name']
	return ret

def put_bookmarks_to_file(path, bookmarks_dict):
	import jtag
	import json
	print(f"putting bookmarks to {path}")
	tg = jtag.SqliteTagObject()
	ino = tg.get_inode(path)
	bookmarks_list = []
	for key in sorted(bookmarks_dict):
		val = bookmarks_dict[key]
		frag = {'time': key, 'name': val}
		bookmarks_list.append(frag)
	if len(bookmarks_list) > 0:
		bookmarks_json = json.dumps(bookmarks_list)
		ino['org.interlaced.jmpv_bookmarks'] = bookmarks_json
	tg.finish()

def fps_quantize(millis, fps):
	return int(int(millis * fps) / fps)

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("video_file")
	parser.add_argument("-c", "--clear-existing", action="store_true", dest="clear_existing", default=False, help="Remove any existing keynotes from video file")
	parser.add_argument("-o", "--offset", action="store", dest="timestamp_offset", type=float, default=None, help="Add this value (in seconds) to each keynote timestamp. Hint: do like --offset=-2 for negative offsets")
	args = parser.parse_args()


	video_file_path = os.path.abspath(args.video_file)
	if not os.path.exists(video_file_path):
		print("That doesn't exist!")
		sys.exit(1)

	if args.timestamp_offset is not None:
		global_offset = int(args.timestamp_offset * 1000)
	else:
		global_offset = 0
	video_file_dir = os.path.dirname(video_file_path)
	keynotes_files = find_keynotes_files(video_file_dir)
	video_file_name = os.path.basename(video_file_path)
	start_timestamp = get_timestamp_from_string(video_file_name)
	duration = get_videofile_duration(video_file_path)
	framerate = get_videofile_framerate(video_file_path)
	end_timestamp = start_timestamp + duration
	bookmarks = get_bookmarks_from_file(video_file_path)
	if args.clear_existing:
		for k in list(bookmarks.keys()):
			if bookmarks[k] == 'keynote':
				del bookmarks[k]

	print(f"Start timestamp: {start_timestamp}")
	print(f"Duration: {duration}")
	print()

	for kn_fn in keynotes_files:
		kn_path = os.path.join(video_file_dir, kn_fn)
		kn_start = get_timestamp_from_string(kn_fn)
		try:
			kn_end   = find_log_end_timestamp(kn_path)
		except ValueError:
			continue
		if not is_within(start_timestamp, end_timestamp, kn_start, kn_end):
			continue
		print(f"{kn_fn} {kn_start} {kn_end}")
		fh = open(kn_path, "r")
		last_dt = None
		for line in fh:
			line = line.rstrip()
			dt = jlib.timestamp_to_utcdatetime(float(line))
			if last_dt is not None:
				dt_delta = dt - last_dt
				if dt_delta < datetime.timedelta(seconds=2):
					print("skipping")
					last_dt = dt
					continue
			ts_adj = dt - start_timestamp
			offset = int(ts_adj.total_seconds() * 1000) + global_offset
			quantized_offset = fps_quantize(offset, framerate)
			print(f"  {offset} -> {quantized_offset}")
			if offset not in bookmarks:
				bookmarks[quantized_offset] = "keynote"
			last_dt = dt
	
	if len(bookmarks) > 0:
		put_bookmarks_to_file(video_file_path, bookmarks)

