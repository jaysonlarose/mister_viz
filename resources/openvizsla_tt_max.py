import mister_viz
import mister_viz_openvizsla
import time
import struct

svg_filename = "tt_max.svg"

class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	"""
	GuliKit TT Max controller in XBox 360 mode.
	"""
	remapping = {}
	def __init__(self, resources):
		#print("Translator __init__()")
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None
		self.last_out_timestamp = None
		#self.ptt_state = ptt_state
		#if self.ptt_state is not None:
		#	self.ptt = mister_viz.JackPushToTalk()
		self.axis_limits = {
			'lstick': {
				'x': [-128, 127, None],
				'y': [-128, 127, None],
			},
			'rstick': {
				'x': [-128, 127, None],
				'y': [-128, 127, None],
			},
		}


		self.res.sticks['lstick'].x_axis.min_value = -128
		self.res.sticks['lstick'].x_axis.max_value = 127
		self.res.sticks['lstick'].x_axis.default_value = 0 
		self.res.sticks['lstick'].y_axis.min_value = -128
		self.res.sticks['lstick'].y_axis.max_value = 127
		self.res.sticks['lstick'].y_axis.default_value = 0

		self.res.sticks['rstick'].x_axis.min_value = -128
		self.res.sticks['rstick'].x_axis.max_value = 127
		self.res.sticks['rstick'].x_axis.default_value = 0
		self.res.sticks['rstick'].y_axis.min_value = -128 
		self.res.sticks['rstick'].y_axis.max_value = 127
		self.res.sticks['rstick'].y_axis.default_value = 0
		self.res.axes['zl'].is_analog = True
		self.res.axes['zl'].mapped_to = "zl"
		self.res.axes['zl'].min_value = 0
		self.res.axes['zl'].max_value = 255

		self.res.axes['zr'].is_analog = True
		self.res.axes['zr'].mapped_to = "zr"
		self.res.axes['zr'].min_value = 0
		self.res.axes['zr'].max_value = 255
		self.res.has_rumble = True
		self.res.rumble_vect = None
	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		nao = time.time()
		if event.direction == "IN" and event.payload is not None and len(event.payload) == 22:
			payload = event.payload

			state = set()


			# LSB of byte 2 is the d-pad
			if payload[2] & 0x01:
				state.add('up')
			if payload[2] & 0x02:
				state.add('down')
			if payload[2] & 0x04:
				state.add('left')
			if payload[2] & 0x08:
				state.add('right')

			if payload[3] & 0x10:
				state.add('b')
			if payload[3] & 0x20:
				state.add('a')
			if payload[3] & 0x40:
				state.add('y')
			if payload[3] & 0x80:
				state.add('x')


			if payload[3] & 0x01:
				state.add('l')
			if payload[3] & 0x02:
				state.add('r')
			if payload[2] & 0x20:
				state.add('minus')
			if payload[2] & 0x10:
				state.add('plus')
			if payload[2] & 0x40:
				state.add('lstick')
			if payload[2] & 0x80:
				state.add('rstick')
			if payload[3] & 0x04:
				state.add('home')



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
			stick_x = struct.unpack("b", bytes([payload[7]]))[0]
			stick_y = struct.unpack("b", bytes([payload[9]]))[0] * -1
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y
			#print(stick_x, stick_y)

			limits = self.axis_limits['rstick']
			stick_x = struct.unpack("b", bytes([payload[11]]))[0]
			stick_y = struct.unpack("b", bytes([payload[13]]))[0] * -1
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			pos = payload[5]
			if self.res.axes['zr'].value != pos:
				self.res.axes['zr'].set_value(pos)
				dirty = True

			pos = payload[4]
			if self.res.axes['zl'].value != pos:
				self.res.axes['zl'].set_value(pos)
				dirty = True

			for stick in self.axis_limits:
				for axis in ['x', 'y']:
					lim = self.axis_limits[stick][axis]
					mid = ((lim[1] - lim[0]) / 2) + lim[0]
					axrange = lim[1] - mid
					offset = lim[2] - mid
					#pos = (int((offset / axrange) * 127))
					pos = lim[2]
					#if axis == 'y':
					#	pos *= -1
					#pos += 127
					#print(f"{stick} {axis} {lim[0]}, {lim[1]}, {axrange} {pos} {lim[2]}")
					if axis == 'x':
						if self.res.sticks[stick].x_axis.value != pos:
							self.res.sticks[stick].x_axis.set_value(pos)
							dirty = True
					elif axis == 'y':
						if self.res.sticks[stick].y_axis.value != pos:
							self.res.sticks[stick].y_axis.set_value(pos)
							dirty = True
		elif event.direction == "OUT" and event.payload is not None and len(event.payload) == 34:
			#print(binascii.hexlify(event.payload[-2:]).decode(), file=sys.stderr)
			if event.payload[-2:] == bytes([0x41, 0xa2]):
				self.res.rumble_vect = random.random() * (math.pi * 2)
				self.set_dirty()
			elif event.payload[-2:] == bytes([0x3e, 0xe3]):
				self.res.rumble_vect = None
				self.set_dirty()
			#if self.last_out_timestamp is not None:
			#	ts_delta = nao - self.last_out_timestamp
			#else:
			#	ts_delta = 0
			#print(f"{ts_delta:10.3f} {len(event.payload)} {' '.join(jlib.splitlen(binascii.hexlify(event.payload).decode(), 2))}", file=sys.stderr)
			self.last_out_timestamp = nao
		if dirty:
			self.set_dirty()

