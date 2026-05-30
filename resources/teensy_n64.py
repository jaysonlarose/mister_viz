import mister_viz_openvizsla
import struct

NAME = "n64"
SVG_FILENAME = "n64.svg"

class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	remapping = {}
	def __init__(self, resources):
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None

		self.axis_limits = {
			'stick': {
				'x': [-127, 127, None],
				'y': [-127, 127, None],
			},
		}
		self.res.sticks['stick'].x_axis.min_value = -127 
		self.res.sticks['stick'].x_axis.max_value = 127
		self.res.sticks['stick'].x_axis.default_value = 0 
		self.res.sticks['stick'].y_axis.min_value = -127 
		self.res.sticks['stick'].y_axis.max_value = 127
		self.res.sticks['stick'].y_axis.default_value = 0 

	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		state = set()
		payload = event.payload
		if len(payload) != 4:
			return
		if payload[0] & 0x01:
			state.add("right")
		if payload[0] & 0x02:
			state.add("left")
		if payload[0] & 0x04:
			state.add("down")
		if payload[0] & 0x08:
			state.add("up")
		if payload[0] & 0x10:
			state.add("start")
		if payload[0] & 0x20:
			state.add("z")
		if payload[0] & 0x40:
			state.add("b")
		if payload[0] & 0x80:
			state.add("a")
		if payload[1] & 0x01:
			state.add("c_right")
		if payload[1] & 0x02:
			state.add("c_left")
		if payload[1] & 0x04:
			state.add("c_down")
		if payload[1] & 0x08:
			state.add("c_up")
		if payload[1] & 0x10:
			state.add("r")
		if payload[1] & 0x20:
			state.add("l")


		for k, v in self.button_elements.items():
			k = self.remapping.get('button', {}).get(k, k)
			if k in state:
				new_value = 1
			else:
				new_value = 0
			if new_value != v.value:
				v.set_value(new_value)
				dirty = True

		limits = self.axis_limits['stick']
		stick_x = struct.unpack("b", bytes([payload[2]]))[0]
		stick_y = struct.unpack("b", bytes([payload[3]]))[0]
		limits['x'][2] = stick_x
		limits['y'][2] = stick_y * -1

		for stick in self.axis_limits:
			stick_res = self.res.sticks[self.remapping.get('stick', {}).get(stick, stick)]
			for axis in ['x', 'y']:
				lim = self.axis_limits[stick][axis]
				mid = ((lim[1] - lim[0]) / 2) + lim[0]
				axrange = lim[1] - mid
				offset = lim[2] - mid
				pos = (int((offset / axrange) * 127))
				#if axis == 'y':
				#	pos *= -1
				#pos += 127
				#print(f"{stick} {axis} {lim[0]}, {lim[1]}, {axrange} {pos} {lim[2]}")
				if axis == 'x':
					if stick_res.x_axis.value != pos:
						stick_res.x_axis.set_value(pos)
						dirty = True
				elif axis == 'y':
					if stick_res.y_axis.value != pos:
						stick_res.y_axis.set_value(pos)
						dirty = True
		if dirty:
			#print(state)
			#print(self.res.axes['l'].value)
			#print(self.res.axes['r'].value)
			self.set_dirty()
