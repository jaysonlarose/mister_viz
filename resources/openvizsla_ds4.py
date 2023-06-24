
import mister_viz, mister_viz_openvizsla

import os, sys, binascii, jlib, time, random, math

svg_filename = "dualshock3.svg"

class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	"""
	Sony DualShock 4 controller.
	"""
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
		self.res.has_rumble = True
		self.res.rumble_vect = None
	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		nao = time.time()
		if event.direction == "IN" and event.payload is not None and len(event.payload) == 66:
			payload = event.payload

			state = set()

			# payload[14] - up
			# payload[15] - right
			# payload[16] - down
			# payload[17] - left
			# payload[18] - l2
			# payload[19] - r2
			# payload[20] - l1
			# payload[21] - r1
			# payload[22] - triangle
			# payload[23] - circle
			# payload[24] - cross/
			# payload[25] - square

			if payload[5] & 0x0f != 0x08:
				state.update([
					['up'],
					['up', 'right'],
					['right'],
					['down', 'right'],
					['down'],
					['down', 'left'],
					['left'],
					['left', 'up'],
				][payload[5] & 0x0f])

			if payload[5] & 0x10:
				state.add('square')
			if payload[5] & 0x20:
				state.add('cross')
			if payload[5] & 0x40:
				state.add('circle')
			if payload[5] & 0x80:
				state.add('triangle')

			if payload[6] & 0x01:
				state.add('l1')
			if payload[6] & 0x02:
				state.add('r1')
			if payload[6] & 0x10:
				state.add('share')
				state.add('select')
			if payload[6] & 0x20:
				state.add('options')
				state.add('start')
			if payload[6] & 0x40:
				state.add('lstick')
			if payload[6] & 0x80:
				state.add('rstick')

			if payload[7] & 0x01:
				state.add('playstation')
			if payload[7] & 0x02:
				state.add('touchpad')

			#34 - goes brr
			#34-38 - touchpad slot 1
			#35 - 
			#	bit 7 - event type:
			#		0 - finger up
			#		1 - finger down
			#	bits 0-6: event serial
			#36 - x pos bits 0:7
			#37 - bits 0:3: x pos bits 8:11
			#37 - bits 4-7: y pos bits 0:3
			#38 - y pos bits 4-11



			#39-42 - touchpad slot 2
			#39 -
			#    bit 7: event type:
			#		0 - finger up
			#		1 - finger down
			#	bits 0-6: event serial

			#note: event serial increments, is shared between both touchpad slots






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
			stick_x = payload[1]
			stick_y = payload[2]
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			limits = self.axis_limits['rstick']
			stick_x = payload[3]
			stick_y = payload[4]
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			pos = payload[9]
			if self.res.axes['r2'].value != pos:
				self.res.axes['r2'].set_value(pos)
				dirty = True

			pos = payload[8]
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
