#!/usr/bin/env python3
import gi, os, sys, mister_viz, cairo, traceback, math

gi.require_version("Gtk", "3.0")
gi.require_version("Clutter", "1.0")
gi.require_version("GtkClutter", "1.0")

from gi.repository import GLib, Clutter, GtkClutter, Cogl, Gtk

clutter_init = False

if not clutter_init:
	GtkClutter.init(sys.argv)
	clutter_init = True

SVG_FILENAME = "n64.svg"

def pixbuf_to_actor(pixbuf):# {{{
	data = (
		pixbuf.get_pixels(),
		Cogl.PixelFormat.RGBA_8888 if pixbuf.get_has_alpha() else Cogl.PixelFormat.RGB_888,
		pixbuf.get_width(),
		pixbuf.get_height(),
		pixbuf.get_rowstride(),
	)
	climage = Clutter.Image.new()
	climage.set_data(*data)

	actor = Clutter.Actor.new()
	actor.set_content(climage)
	actor.set_size(pixbuf.get_width(), pixbuf.get_height())
	#actor.set_opacity(255)
	actor.set_reactive(True)

	return actor
# }}}


from mister_viz import MisterVizWindowStub
class MisterVizClutterWindow(MisterVizWindowStub):
	def __init__(self, parent, window_id=None, controller_resource=None, permit_alpha=True, loop=None):
		super().__init__(parent, window_id=window_id, controller_resource=controller_resource, permit_alpha=permit_alpha)
		self.local_x_offset = 0
		self.local_y_offset = 0
		self.actors = {}
		self.cairo_actor = None

		self.clut = GtkClutter.Embed()
		self.clut.set_visible(True)
		self.main_widget = self.clut
		self.stage = self.clut.get_stage()
		self.stage.set_use_alpha(True)
		bg_color = Clutter.Color.from_string("#ffffff00")
		self.stage.set_background_color(bg_color[1])
		self.connect("screen-changed", self.screen_changed_handler)
		self.screen_changed_handler(self, None)
		self.add(self.clut)
		#self.set_property("opacity", 0.5)
		self.set_property("opacity", 1.0)
		self.main_widget.connect("button-press-event", self.darea_click_handler)
		self.show_all()
		#self.main_widget.connect("draw", self.draw_handler)

	def draw_handler(self, widget, ctx, width, height):
		w = width
		h = height
		#print(f"w x h: {w} x {h}")
		ctx.set_operator(cairo.OPERATOR_SOURCE)
		ctx.set_source_rgba(0, 0, 0, 0)
		ctx.paint()
		#ctx.set_source_rgba(1, 1, 1, 1)
		#ctx.move_to(0, 0)
		#ctx.line_to(w, h)
		#ctx.stroke()
		#ctx.paint()
		offsets = {
			'x': 0,
			'y': 0,
		}
		for k, relative in self.res.relatives.items():
			#print(f"{k}")
			pixkey = f"relative:{k}"
			if pixkey in self.pixbufs:
				w = self.pixbufs[pixkey][0].get_width() / 2
				h = self.pixbufs[pixkey][0].get_height() / 2
				center = [self.pixbufs[pixkey][1] + w, self.pixbufs[pixkey][2] + h]
				radius = w
				#print(f"radius: {radius}")
				arrow_width = radius / 5 
				arrow_minlength = radius / 3
				#print(f"arrow_width: {arrow_width}")
				for off in offsets:
					axis = getattr(relative, f"{off}_axis")
					if axis is not None and axis.value is not None:
						offsets[off] = mister_viz.translate_constrainedint(axis.value, axis.min_value, axis.max_value, -radius, radius)
				maxrange = radius * 2
				angle = math.degrees(math.atan2(offsets['y'], offsets['x'])) + 90
				magnitude = math.sqrt(offsets['x'] * offsets['x'] + offsets['y'] * offsets['y']) * 2
				#print(f"Magnitude: {magnitude}")
				#if not hasattr(relative, "reset_source"):
				#	relative.reset_source = None
				#if relative.is_dirty:
				#	if magnitude > 0.0:
				#		if relative.reset_source is not None:
				#			GLib.source_remove(relative.reset_source)
				#			relative.reset_source = None
				#		print(f"scheduling relative reset")
				#		relative.reset_source = GLib.timeout_add(int(1000 / 30), relative.value_change_reset)
				if magnitude > 0.0:
					magnitude = mister_viz.translate_constrainedint(magnitude, 0, maxrange, arrow_minlength, maxrange)
					offsets['x'] = magnitude * math.cos(angle)
					offsets['y'] = magnitude * math.sin(angle)
					arrow_points = mister_viz.rotpoly(mister_viz.make_arrow_points(magnitude, arrow_width), 0, 0, angle)
					arrow_points = mister_viz.transpoly(arrow_points, *center)
					ctx.set_source_rgba(*relative.rgba)
					ctx.move_to(*arrow_points[0])
					for x, y in arrow_points[1:]:
						ctx.line_to(x, y)
					ctx.close_path()
					ctx.fill()
					ctx.stroke()
					#ctx.paint()
					#print(f"{k}: {center} {radius} {magnitude}")
				#relative.is_dirty = False

	def trigger_draw(self, *args):
		import math
		allstate = set()
		opaque_actors = set()
		moved_actors = set()
		opaque_actors.add(None)

		try:
			offsets = {
				'x': 0,
				'y': 0,
			}
			for x in self.res.buttons.values():
				if x.on_stick:
					continue
				allstate |= x.get_state()
			for x in self.res.axes.values():
				allstate |= x.get_state()

			for state in allstate:
				if state in self.res.sticks:
					continue
				if state in self.actors:
					opaque_actors.add(state)

			for k, stick in self.res.sticks.items():
				if stick.has_button:
					if stick.button.value:
						pixkey = f"button:{k}"
					else:
						pixkey = f"stick:{k}"
				else:
					pixkey = f"stick:{k}"
				if pixkey in self.actors:
					opaque_actors.add(pixkey)
					for off in offsets:
						axis = getattr(stick, f"{off}_axis")
						if axis is not None and axis.value is not None:
							#print(f"offsets[off] ({pixkey}) = mister_viz.translate_constrainedint({axis.value}, {axis.min_value}, {axis.max_value}, {axis.min_pos}, {axis.max_pos})")
							offsets[off] = mister_viz.translate_constrainedint(axis.value, axis.min_value, axis.max_value, axis.min_pos, axis.max_pos)
					if stick.x_axis is not None and stick.y_axis is not None:
						circularize = True
						for attr in ['min_value', 'max_value', 'min_pos', 'max_pos']:
							if getattr(stick.x_axis, attr) != getattr(stick.y_axis, attr):
								circularize= False
								break
						if circularize:
							maxrange = stick.x_axis.max_pos - stick.x_axis.min_pos
							angle = math.atan2(offsets['y'], offsets['x'])
							magnitude = math.sqrt(offsets['x'] * offsets['x'] + offsets['y'] * offsets['y'])
							if magnitude > (maxrange // 2):
								magnitude = maxrange // 2
							offsets['x'] = magnitude * math.cos(angle)
							offsets['y'] = magnitude * math.sin(angle)

					self.actors[pixkey].set_position((offsets['x'] * self.scalefactor) + self.pixbufs[pixkey][1] + self.global_x_offset, (offsets['y'] * self.scalefactor) + self.pixbufs[pixkey][2] + self.global_y_offset)
					moved_actors.add(pixkey)
			for k, touchelement in self.res.touchelements.items():
				for slotno, slot in enumerate(touchelement.slots):
					pixkey = f"touchelement:{k}:{slotno}"
					if slot.finger_down:
						if pixkey in self.actors:
							opaque_actors.add(pixkey)
							x_pos = mister_viz.translate_constrainedint(slot.x, 0, touchelement.drange[0], 0, touchelement.extents[0])
							y_pos = mister_viz.translate_constrainedint(slot.y, 0, touchelement.drange[1], 0, touchelement.extents[1])
							self.actors[pixkey].set_position((x_pos * self.scalefactor) + self.pixbufs[pixkey][1] + self.global_x_offset, (y_pos * self.scalefactor) + self.pixbufs[pixkey][2] + self.global_y_offset)
							moved_actors.add(pixkey)
			for akey in self.actors.keys():
				if akey in opaque_actors:
					opacity = 255
				else:
					opacity = 0
				curr_opacity = self.actors[akey].get_opacity()
				if opacity != curr_opacity:
					#print(f"actor {akey} gets opacity {opacity}")
					self.actors[akey].set_opacity(opacity)
			if self.local_x_offset != self.global_x_offset or self.local_y_offset != self.global_y_offset:
				self.local_x_offset = self.global_x_offset
				self.local_y_offset = self.global_y_offset
				for akey in self.actors.keys():
					if akey in moved_actors:
						continue
					self.actors[akey].set_position(self.pixbufs[akey][1] + self.global_x_offset, self.pixbufs[akey][2] + self.global_y_offset)
					moved_actors.add(akey)
			if self.cairo_actor is not None:
				self.cairo_actor.get_content().invalidate()
		except Exception:
			for line in traceback.format_exc().splitlines():
				print(f"exception: {line}", file=sys.stderr)


	def pixbuf_receive_handler(self, key, pixbuf, x_offset, y_offset, scalefactor):# {{{
		print(f"Receiving pixbuf for state: {key} (scale factor {scalefactor})")
		if key is None:
			# A key of None means we're receiving a base pixbuf
			if self.viz_width is None and self.viz_height is None:
				# If our viz_width and viz_height values are None, we're receiving our first pixbuf,
				# which is of scalefactor 1.0. We use this pixbuf's dimensions to set viz_width and viz_height.
				self.viz_width = pixbuf.get_width()
				self.viz_height = pixbuf.get_height()
				#print(f"Setting viz dimensions to {self.viz_width}x{self.viz_height}")
				if self.scalefactor != 1.0:
					# If our actual desired scalefactor isn't 1.0, resubmit a scale request for the proper
					# desired scalefactor.
					#print(f"Resubmitting SVG for scalefactor {self.scalefactor}")
					self.parent.scaler.scale_svg([self.window_id, None], self.res.svgs[None], self.scalefactor)
					return
			self.scalefactor = scalefactor
			self.pixbufs = {}
			self.stage.remove_all_children()
			self.actors = {}
			self.cairo_actor = None
			self.pixbufs[key] = [pixbuf, x_offset, y_offset]
			self.actors[key] = pixbuf_to_actor(self.pixbufs[key][0])
			self.actors[key].set_position(self.pixbufs[key][1] + self.global_x_offset, self.pixbufs[key][2] + self.global_y_offset)
			self.actors[key].set_z_position(0)
			self.stage.add_child(self.actors[key])
			canvas = Clutter.Canvas()
			canvas.set_size(self.pixbufs[key][0].get_width(), self.pixbufs[key][0].get_height())
			self.cairo_actor = Clutter.Actor.new()
			self.cairo_actor.set_content(canvas)
			self.cairo_actor.set_size(self.pixbufs[key][0].get_width(), self.pixbufs[key][0].get_height())
			self.cairo_actor.set_opacity(255)
			self.cairo_actor.set_reactive(True)
			self.cairo_actor.set_z_position(2)
			self.stage.add_child(self.cairo_actor)
			canvas.connect("draw", self.draw_handler)
			self.inflight = False
			#self.resize_handler_id = self.connect("size-allocate", self.resize_handler)
			if self.resize_handler_id is not None:
				self.disconnect(self.resize_handler_id)
				self.resize_handler_id = None
			self.resize_to(int(self.viz_width * self.scalefactor), int(self.viz_height * self.scalefactor))
			#self.resize(int(self.viz_width * self.scalefactor), int(self.viz_height * self.scalefactor))
			GLib.timeout_add(1000, self.resize_handler_reinstate)
			#self.resize_handler_id = self.connect("size-allocate", self.resize_handler)
		else:
			if scalefactor != self.scalefactor:
				return
			#print(f"Adding pixbuf for state {key}")
			self.pixbufs[key] = [pixbuf, x_offset, y_offset]
			self.actors[key] = pixbuf_to_actor(self.pixbufs[key][0])
			self.actors[key].set_position(self.pixbufs[key][1] + self.global_x_offset, self.pixbufs[key][2] + self.global_y_offset)
			self.actors[key].set_z_position(1)
			self.stage.add_child(self.actors[key])
		self.trigger_draw()

		next_pixbuf_key = None
		allstate = set()
		for x in self.res.buttons.values():
			if x.on_stick:
				continue
			allstate |= x.get_state()
		for x in self.res.axes.values():
			allstate |= x.get_state()
		if key in allstate:
			self.trigger_draw()
		# Populate sticks first
		for k, stick in self.res.sticks.items():
			if stick.has_button:
				if stick.button.value:
					pixkey = f"button:{k}"
				else:
					pixkey = f"stick:{k}"
			else:
				pixkey = f"stick:{k}"
			if pixkey not in self.pixbufs:
				next_pixbuf_key = pixkey
		# Done with sticks? See if there's anything currently being pressed we need to populate.
		if next_pixbuf_key is None:
			for key in allstate:
				if key in self.res.svgs and key not in self.pixbufs:
					next_pixbuf_key = key
					break
		# Done with stuff in state? Cache up anything else.
		if next_pixbuf_key is None:
			for k in self.res.svgs:
				if k not in self.pixbufs:
					next_pixbuf_key = k
					break

		if next_pixbuf_key is not None:
			self.parent.scaler.scale_svg([self.window_id, next_pixbuf_key], self.res.svgs[next_pixbuf_key], self.scalefactor)
	# }}}

if __name__ == '__main__':
	loop = GLib.MainLoop()
	stub = mister_viz.MisterVizStub()
	res = mister_viz.SvgControllerResources(os.path.join(mister_viz.get_yaml_basedir(), SVG_FILENAME))

	res.sticks['stick'].x_axis.min_value = -127 
	res.sticks['stick'].x_axis.max_value = 127
	res.sticks['stick'].x_axis.default_value = 0 
	res.sticks['stick'].y_axis.min_value = -127 
	res.sticks['stick'].y_axis.max_value = 127
	res.sticks['stick'].y_axis.default_value = 0 


	#window = mister_viz.MisterVizWindow(stub, controller_resource=res)
	window = MisterVizClutterWindow(stub, controller_resource=res, loop=loop)
	stub.windows[window.window_id] = window
	#window = Gtk.Window()
	window.resize(800, 600)

	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("-c", "--console", action="store_true", dest="do_console", default=False)
	args = parser.parse_args()

	def shutdown_handler(*args):
		window.destroy()
		stub.scaler.shutdown()
		loop.quit()

	window.connect("destroy", shutdown_handler)

	if args.do_console:
		import debugrepl, glib_editingline
		cli = glib_editingline.CliInterpreter(None, namespace=globals())
		def cli_controlc_handler(*args):
			shutdown_handler()

		cli.connect("control-c", cli_controlc_handler)
		from debugrepl import pd
	loop.run()
