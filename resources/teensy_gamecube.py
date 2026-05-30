import mister_viz_openvizsla
import struct

NAME = "gamecube"
SVG_FILENAME = "gamecube.svg"


class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	def __init__(self, resources):
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None

		self.axis_limits = {
			'lstick': {
				'x': [0x00, 0xff, None],
				'y': [0x00, 0xff, None],
			},
			'rstick': {
				'x': [0x00, 0xff, None],
				'y': [0x00, 0xff, None],
			},
		}
		self.res.sticks['lstick'].x_axis.min_value = 0
		self.res.sticks['lstick'].x_axis.max_value = 255
		self.res.sticks['lstick'].x_axis.default_value = 127 
		self.res.sticks['lstick'].y_axis.min_value = 0
		self.res.sticks['lstick'].y_axis.max_value = 255
		self.res.sticks['lstick'].y_axis.default_value = 127 

		self.res.sticks['rstick'].x_axis.min_value = 0
		self.res.sticks['rstick'].x_axis.max_value = 255
		self.res.sticks['rstick'].x_axis.default_value = 127 
		self.res.sticks['rstick'].y_axis.min_value = 0
		self.res.sticks['rstick'].y_axis.max_value = 255
		self.res.sticks['rstick'].y_axis.default_value = 127 
		self.res.axes['l'].is_analog = True
		self.res.axes['l'].mapped_to = "l"
		self.res.axes['l'].min_value = 50
		self.res.axes['l'].max_value = 230

		self.res.axes['r'].is_analog = True
		self.res.axes['r'].mapped_to = "r"
		self.res.axes['r'].min_value = 50
		self.res.axes['r'].max_value = 230

	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		state = set()
		payload = event.payload
		if len(payload) != 8:
			return
		if payload[0] & 0x01:
			state.add("a")
		if payload[0] & 0x02:
			state.add("b")
		if payload[0] & 0x08:
			state.add("y")
		if payload[0] & 0x04:
			state.add("x")
		if payload[0] & 0x10:
			state.add("start")
		if payload[1] & 0x01:
			state.add("left")
		if payload[1] & 0x02:
			state.add("right")
		if payload[1] & 0x04:
			state.add("down")
		if payload[1] & 0x08:
			state.add("up")
		if payload[1] & 0x10:
			state.add("z")
		if payload[1] & 0x20:
			state.add("r")
		if payload[1] & 0x40:
			state.add("l")

		for k, v in self.button_elements.items():
			if k in state:
				new_value = 1
			else:
				new_value = 0
			if new_value != v.value:
				v.set_value(new_value)
				dirty = True

		limits = self.axis_limits['lstick']
		stick_x = payload[2]
		stick_y = payload[3]
		limits['x'][2] = stick_x
		limits['y'][2] = 0xff - stick_y

		limits = self.axis_limits['rstick']
		stick_x = payload[4]
		stick_y = payload[5]
		limits['x'][2] = stick_x
		limits['y'][2] = 0xff - stick_y

		pos = payload[7]
		if self.res.axes['r'].value != pos:
			self.res.axes['r'].set_value(pos)
			dirty = True

		pos = payload[6]
		if self.res.axes['l'].value != pos:
			self.res.axes['l'].set_value(pos)
			dirty = True

		for stick in self.axis_limits:
			for axis in ['x', 'y']:
				lim = self.axis_limits[stick][axis]
				mid = ((lim[1] - lim[0]) / 2) + lim[0]
				axrange = lim[1] - mid
				offset = lim[2] - mid
				pos = (int((offset / axrange) * 127))
				#if axis == 'y':
				#	pos *= -1
				pos += 127
				#print(f"{stick} {axis} {lim[0]}, {lim[1]}, {axrange} {pos} {lim[2]}")
				if axis == 'x':
					if self.res.sticks[stick].x_axis.value != pos:
						self.res.sticks[stick].x_axis.set_value(pos)
						dirty = True
				elif axis == 'y':
					if self.res.sticks[stick].y_axis.value != pos:
						self.res.sticks[stick].y_axis.set_value(pos)
						dirty = True
		if dirty:
			#print(state)
			#print(self.res.axes['l'].value)
			#print(self.res.axes['r'].value)
			self.set_dirty()
