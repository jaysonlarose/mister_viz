#!/usr/bin/env python3
import os, sys, decimal, re

pat_smpte = re.compile(r"^(-?)(\d{2}):(\d{2}):(\d{2})\.(\d{2})$")

def smpte_to_seconds(timestamp, framerate):# {{{
	mat = pat_smpte.search(timestamp)
	ret = decimal.Decimal(0.0)
	hours, minutes, seconds, frames = [ decimal.Decimal(int(x)) for x in mat.groups()[1:] ]
	ret += (hours * 3600)
	ret += (minutes * 60)
	ret += seconds
	ret += (frames / framerate)
	if mat.group(1) == '-':
		ret *= -1
	return ret
# }}}
def seconds_to_smpte(seconds, framerate):# {{{
	hours = 0
	minutes = 0
	millis = 0
	if seconds > 3600:
		hours = int(seconds // 3600)
		seconds = seconds % 3600
	if seconds > 60:
		minutes = int(seconds // 60)
		seconds = seconds % 60
	frames = jlib.round_properly((seconds - int(seconds)) * framerate)
	seconds = int(seconds)
	return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{frames:02d}"
# }}}

# Git/mister_viz/calculate_fudgefactor.py --fps 60 --begin-skew 00:00:11.33 --end-skew 00:00:11.54 --begin-sync 00:03:52.12 --end-sync 02:13:20.16


if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser(allow_abbrev=False)
	parser.add_argument("--fps", action="store", dest="fps", type=str, required=True, help="Frame rate of the Kdenlive project used to find sync points — Used to convert to/from SMPTE timestamps.")
	parser.add_argument("--begin-skew", action="store", dest="begin_skew", type=str, required=True, help="SMPTE timestamp of point in gameplay timeline that the viz timeline should start in order for sync point \"begin\" to align.")
	parser.add_argument("--end-skew", action="store", dest="end_skew", type=str, required=True, help="SMPTE timestamp of point in gameplay timeline that the viz timeline should start in order for sync point \"end\" to align.")
	parser.add_argument("--begin-sync", action="store", dest="begin_sync", type=str, required=True, help="SMPTE timestamp of point in gameplay timeline that sync point \"begin\" occurs at.")
	parser.add_argument("--end-sync", action="store", dest="end_sync", type=str, required=True, help="SMPTE timestamp of point in gameplay timeline that sync point \"end\" occurs at.")
	parser.add_argument("--precision", action="store", dest="precision", type=int, default=128, help="Precision value to pass to decimal.getcontext().prec")
	args = parser.parse_args()

	decimal.getcontext().prec = args.precision

	fps = decimal.Decimal(args.fps)

	begin_skew = smpte_to_seconds(args.begin_skew, fps)
	end_skew   = smpte_to_seconds(args.end_skew, fps)
	begin_sync = smpte_to_seconds(args.begin_sync, fps)
	end_sync   = smpte_to_seconds(args.end_sync, fps)


	# Find time lapse between the sync points on the gameplay footage
	game_dur = end_sync - begin_sync

	# Find time lapse between the sync points on the viz footage
	viz_dur = (end_sync - end_skew) - (begin_sync - begin_skew)

	# L + Ratio
	fudge_factor = game_dur / viz_dur

	print(f"Sync point \"begin\":")
	print(f"  Viz starts at {begin_skew},")
	print(f"  sync occurs at {begin_sync}.")
	print()
	print(f"Sync point \"end\":")
	print(f"  Viz starts at {end_skew},")
	print(f"  sync occurs at {end_sync}.")
	print()
	print(f"Between sync points,")
	print(f"  {game_dur} seconds elapse in the gameplay timeline,")
	print(f"  {viz_dur} seconds elapse in the viz timeline.")
	print()
	print(f"Fudge factor: {fudge_factor}")
	
