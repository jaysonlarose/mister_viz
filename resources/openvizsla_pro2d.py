import mister_viz, mister_viz_openvizsla

svg_filename = "pro2.svg"

class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	"""
	8BitDo Pro2 controller in DirectInput mode.
	"""
	def __init__(self, resources):
		#print("Translator __init__()")
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None
		#self.ptt_state = ptt_state
		#if self.ptt_state is not None:
		#	self.ptt = mister_viz.JackPushToTalk()
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
		self.res.axes['l2'].is_analog = True
		self.res.axes['l2'].mapped_to = "l2"
		self.res.axes['l2'].min_value = 0
		self.res.axes['l2'].max_value = 255

		self.res.axes['r2'].is_analog = True
		self.res.axes['r2'].mapped_to = "r2"
		self.res.axes['r2'].min_value = 0
		self.res.axes['r2'].max_value = 255
	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		if event.direction == "IN" and event.payload is not None:
			payload = event.payload

			state = set()

			dpad = payload[1]
			if dpad == 0x00:
				state.add("up")
			elif dpad == 0x01:
				state.add("up")
				state.add("right")
			elif dpad == 0x02:
				state.add("right")
			elif dpad == 0x03:
				state.add("down")
				state.add("right")
			elif dpad == 0x04:
				state.add("down")
			elif dpad == 0x05:
				state.add("down")
				state.add("left")
			elif dpad == 0x06:
				state.add("left")
			elif dpad == 0x07:
				state.add("left")
				state.add("up")

			if payload[8] & 0x01:
				state.add('a')
			if payload[8] & 0x02:
				state.add('b')
			if payload[8] & 0x04:
				state.add('rpaddle')
			if payload[8] & 0x08:
				state.add('x')
			if payload[8] & 0x10:
				state.add('y')
			if payload[8] & 0x20:
				state.add('lpaddle')
			if payload[8] & 0x40:
				state.add('l')
			if payload[8] & 0x80:
				state.add('r')

			if payload[9] & 0x01:
				state.add('l2')
			if payload[9] & 0x02:
				state.add('r2')
			if payload[9] & 0x04:
				state.add('select')
			if payload[9] & 0x08:
				state.add('start')
			if payload[9] & 0x10:
				state.add('heart')
			if payload[9] & 0x20:
				state.add('lstick')
			if payload[9] & 0x40:
				state.add('rstick')

			#if self.ptt_state is not None:
			#	if self.ptt_state in state:
			#		self.ptt.set_value(True)
			#	else:
			#		self.ptt.set_value(False)

			#print(state)
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
			limits['y'][2] = stick_y

			limits = self.axis_limits['rstick']
			stick_x = payload[4]
			stick_y = payload[5]
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			pos = payload[6]
			if self.res.axes['r2'].value != pos:
				self.res.axes['r2'].set_value(pos)
				dirty = True

			pos = payload[7]
			if self.res.axes['l2'].value != pos:
				self.res.axes['l2'].set_value(pos)
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
			self.set_dirty()
