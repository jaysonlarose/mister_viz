import mister_viz, mister_viz_openvizsla

svg_filename = "procontroller.svg"


class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	def __init__(self, resources):
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.axis_limits = {
			'lstick': {
				'x': [None, None, None],
				'y': [None, None, None],
			},
			'rstick': {
				'x': [None, None, None],
				'y': [None, None, None],
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

	def event_handler(self, widget, event):
		if event.direction == "IN" and event.payload is not None:
			payload = event.payload

			state = set()

			dpad = payload[5]
			if dpad & 0x04:
				state.add("right")
			if dpad & 0x01:
				state.add("down")
			if dpad & 0x08:
				state.add("left")
			if dpad & 0x02:
				state.add("up")

			if payload[3] & 0x40:
				state.add('r')
			if payload[3] & 0x80:
				state.add('zr')
			if payload[3] & 0x04:
				state.add('b')
			if payload[3] & 0x01:
				state.add('y')
			if payload[3] & 0x02:
				state.add('x')
			if payload[3] & 0x08:
				state.add('a')

			if payload[5] & 0x40:
				state.add('l')
			if payload[5] & 0x80:
				state.add('zl')

			if payload[4] & 0x01:
				state.add('-')
			if payload[4] & 0x02:
				state.add('+')

			if payload[4] & 0x20:
				state.add('screenshot')
			if payload[4] & 0x10:
				state.add('home')

			if payload[4] & 0x08:
				state.add('lstick')
			if payload[4] & 0x04:
				state.add('rstick')

			dirty = False
			for k, v in self.button_elements.items():
				if k in state:
					new_value = 1
				else:
					new_value = 0
				if new_value != v.value:
					v.set_value(new_value)
					dirty = True


			for stickname in ['lstick', 'rstick']:
				limits = self.axis_limits[stickname]
				stickvals = {}
				if stickname == 'lstick':
					stickvals['x'] = payload[6]
					stickvals['x'] += (payload[7] & 0x0f) << 8
					stickvals['y'] = (payload[7] & 0xf0) >> 4
					stickvals['y'] += payload[8] << 4
				elif stickname == 'rstick':
					stickvals['x'] = payload[9]
					stickvals['x'] += (payload[10] & 0x0f) << 8
					stickvals['y'] = (payload[10] & 0xf0) >> 4
					stickvals['y'] = payload[11] << 4
				resso = {
					'x': self.res.sticks[stickname].x_axis,
					'y': self.res.sticks[stickname].y_axis,
				}
				for axisname in ['x', 'y']:
					if limits[axisname][0] is None:
						limits[axisname][0] = stickvals[axisname]
						#resso[axisname].min_value = stickvals[axisname]
					if limits[axisname][1] is None:
						limits[axisname][1] = stickvals[axisname]
						#resso[axisname].max_value = stickvals[axisname]
					limits[axisname][2] = stickvals[axisname]
					if stickvals[axisname] < limits[axisname][0]:
						limits[axisname][0] = stickvals[axisname]
						#resso[axisname].min_value = stickvals[axisname]
					if stickvals[axisname] > limits[axisname][1]:
						limits[axisname][1] = stickvals[axisname]
						#resso[axisname].max_value = stickvals[axisname]


			for stick in self.axis_limits:
				for axis in ['x', 'y']:
					lim = self.axis_limits[stick][axis]
					mid = ((lim[1] - lim[0]) / 2) + lim[0]
					axrange = lim[1] - mid
					offset = lim[2] - mid
					pos = (int((offset / axrange) * 127))
					if axis == 'y':
						pos *= -1
					pos += 127
					print(f"{stick} {axis} {lim[0]}, {lim[1]}, {axrange} {pos} {lim[2]}")
					if axis == 'x':
						if self.res.sticks[stick].x_axis.value != pos:
							self.res.sticks[stick].x_axis.set_value(pos)
							dirty = True
					elif axis == 'y':
						if self.res.sticks[stick].y_axis.value != pos:
							self.res.sticks[stick].y_axis.set_value(pos)
							dirty = True
			if dirty:
				self.set_dirty()
