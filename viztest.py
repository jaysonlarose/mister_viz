#!/usr/bin/env python3

import gi
import math
import mister_viz
import glib_editingline
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib
def plot_course(start_point, direction, distance):# {{{
	"""
	Given a starting point, an angle (in radians), and a distance,
	returns the point resulting from travelling from the starting point
	at said angle for said distance.
	"""
	return (start_point[0] + math.sin(direction) * distance, start_point[1] + math.cos(direction) * distance)
# }}}

if __name__ == '__main__':
	stub = mister_viz.MisterVizStub()
	global res
	res = mister_viz.SvgControllerResources("resources/dualshock3.svg")
	res.sticks['lstick'].x_axis.min_value = 0
	res.sticks['lstick'].x_axis.max_value = 255
	res.sticks['lstick'].x_axis.default_value = 127 
	res.sticks['lstick'].y_axis.min_value = 0
	res.sticks['lstick'].y_axis.max_value = 255
	res.sticks['lstick'].y_axis.default_value = 127 
													 
	res.sticks['rstick'].x_axis.min_value = 0
	res.sticks['rstick'].x_axis.max_value = 255
	res.sticks['rstick'].x_axis.default_value = 127 
	res.sticks['rstick'].y_axis.min_value = 0
	res.sticks['rstick'].y_axis.max_value = 255
	res.sticks['rstick'].y_axis.default_value = 127 
	res.axes['l2'].is_analog = True
	res.axes['l2'].mapped_to = "l2"
	res.axes['l2'].min_value = 0
	res.axes['l2'].max_value = 255
													 
	res.axes['r2'].is_analog = True
	res.axes['r2'].mapped_to = "r2"
	res.axes['r2'].min_value = 0
	res.axes['r2'].max_value = 255

	global window
	window = mister_viz.MisterVizWindow(stub, controller_resource=res)
	stub.windows[window.window_id] = window

	window.darea.queue_draw()

	global angle

	angle = 0
	
	def periodic_handler():
		global angle
		global window
		global res
		angle += 1
		while angle >= 360:
			angle -= 360
		newpoint = plot_course((127, 127), angle, 127)
		#print(newpoint)
		res.sticks['lstick'].x_axis.set_value(newpoint[0])
		res.sticks['lstick'].y_axis.set_value(newpoint[1])
		window.darea.queue_draw()
		return True
	
	GLib.timeout_add(int(1000 / 60), periodic_handler)

	
	#cli = glib_editingline.CliInterpreter(None, namespace=globals())

	Gtk.main()
