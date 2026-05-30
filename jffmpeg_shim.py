#!/usr/bin/env python3

"""
This is a shim to adapt jffmpeg, which is a script I haven't published,
so that it can be used to provide a pretty progress bar to
mister_viz_render's encoding procedure.
"""

import jlib
import gi
from gi.repository import GLib, GObject
import jffmpeg
import JaysTerm
import signal
import os
import sys

pix_fmt_stridelut = {
	'bgra': 4,
}
class StdinCliEncoder(jffmpeg.CliEncoderStub):
	def __init__(self, input_kwargs, output_file, mutator_kwargs={}, verbose=False, pretend=False, sltop_lambda=None, loop=None):
		interrogator = {}
		for k in ['width', 'height', 'frames', 'fps']:
			interrogator[k] = input_kwargs[k]
		interrogator['duration'] = interrogator['frames'] / interrogator['fps']
		interrogator['size'] = interrogator['height'] * interrogator['width'] * interrogator['frames'] * pix_fmt_stridelut[input_kwargs['pix_fmt']]

		mutator_kwargs['input_pix_fmt'] = input_kwargs['pix_fmt']
		mutator_kwargs['inputformat'] = 'rawvideo'
		mutator_kwargs['input_framerate'] = input_kwargs['fps']
		mutator_kwargs['input_videosize'] = f"{input_kwargs['width']}x{input_kwargs['height']}"
		
		super().__init__(input_files=['-'], output_file=output_file, mutator_kwargs=mutator_kwargs, video_interrogator=interrogator, verbose=verbose, pretend=pretend, sltop_lambda=sltop_lambda, tagless=True, loop=loop)

if __name__ == '__main__':
	globals().update(jlib.get_fabulous())
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("--width", action="store", type=int, dest="width")
	parser.add_argument("--height", action="store", type=int, dest="height")
	parser.add_argument("--frames", action="store", type=int, dest="frames")
	parser.add_argument("--fps", action="store", type=float, dest="fps")
	parser.add_argument("--fudgefactor", action="store", dest="fudgefactor", default=None)
	parser.add_argument("--project", action="store", dest="project", default=None)
	parser.add_argument("output_file")
	args = parser.parse_args()

	input_kwargs = {
		'width': args.width,
		'height': args.height,
		'frames': args.frames,
		'fps': args.fps,
		'pix_fmt': 'bgra',
	}
	mutator_kwargs = {
		'movflags': 'use_metadata_tags',
		'map_metadata': '0',
		'mov': None,
		'qtrle': None,
	}

	metadata_nuggets = []
	if args.fudgefactor is not None:
		metadata_nuggets.append(f"fudgefactor={args.fudgefactor}")
	if args.project is not None:
		metadata_nuggets.append(f"project={args.project}")
	if len(metadata_nuggets) > 0:
		mutator_kwargs['metadata'] = metadata_nuggets

	JaysTerm.Term.init()
	sltop = JaysTerm.UpdatingLine(clear_on_close=True)
	def slprint(*args, **kwargs):
		sltop.line(*args, **kwargs)
	origprint, print = print, slprint

	sltop_lambda = lambda x: sltop.update("Output: {}".format(green(x)))

	loop = GLib.MainLoop()

	encoder = StdinCliEncoder(loop=loop, input_kwargs=input_kwargs, output_file=args.output_file, mutator_kwargs=mutator_kwargs, sltop_lambda=sltop_lambda)

	def started_handler(encoder):
		JaysTerm.Term.disableCursor()
		def stdin_handler(fh, flags):
			if flags & GLib.IO_IN:
				chunk_size = args.width * args.height * 4
				data = fh.read(chunk_size)
				#print(f"read {len(data)} bytes")
				if len(data) == 0:
					print(f"Hit end of stdin data")
					encoder.proc.stdin.close()
					return False
				else:
					encoder.proc.stdin.write(data)
			if flags & GLib.IO_HUP:
				encoder.proc.stdin.close()
				return False
			return True
		GLib.io_add_watch(sys.stdin.buffer, GLib.IO_IN | GLib.IO_HUP, stdin_handler)

	def finished_handler(encoder):
		JaysTerm.Term.enableCursor()
		loop.quit()

	encoder.encoder.connect("finished", finished_handler)
	encoder.encoder.connect("started", started_handler)

	encoder.encoder.encode(pretend=False)

	def sigint_handler(sig, frame):
		encoder.encoder.abort()
	signal.signal(signal.SIGINT, sigint_handler)

	loop.run()

	signal.signal(signal.SIGINT, signal.SIG_DFL)
