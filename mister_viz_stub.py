#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
import mister_viz, multiprocessing

if __name__ == '__main__':
	# Required for pyinstaller
	# https://stackoverflow.com/questions/24944558/pyinstaller-built-windows-exe-fails-with-multiprocessing
	multiprocessing.freeze_support()
	app = mister_viz.MisterViz(None)
	Gtk.main()
