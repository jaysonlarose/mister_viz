import mister_viz, mister_viz_openvizsla, jlib, binascii, time, random, math, collections
import os, sys

svg_filename = "dualshock3.svg"

class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	"""
	Sony DualShock 3 controller.
	"""
	def __init__(self, resources, **kwargs):
		#print("Translator __init__()")
		self.output_pressures = False
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources, **kwargs)
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
		self.res.has_rumble = True
		self.res.rumbling = False
		self.res.last_rumble = 0
	def event_handler(self, widget, event):
		nao = time.time()
		self.last_event = event
		dirty = False
		if event.direction == "IN" and event.payload is not None and len(event.payload) == 51:
			payload = event.payload

			state = set()

			
			if self.output_pressures:
				pressures = collections.OrderedDict()
				for idx, key in [
					[14, 'up'],
					[15, 'right'],
					[16, 'down'],
					[17, 'left'],
					[18, 'l2'],
					[19, 'r2'],
					[20, 'l1'],
					[21, 'r1'],
					[22, 'triangle'],
					[23, 'circle'],
					[24, 'cross/'],
					[25, 'square'],
				]:
					pressures[key] = payload[idx]
				output_frags = []
				for k, v in pressures.items():
					output_frags.append(f"{v}")
				print(" ".join(output_frags), file=sys.stderr)

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

			if payload[2] & 0x01:
				state.add('select')
			if payload[2] & 0x02:
				state.add('lstick')
			if payload[2] & 0x04:
				state.add('rstick')
			if payload[2] & 0x08:
				state.add('start')
			if payload[2] & 0x10:
				state.add('up')
			if payload[2] & 0x20:
				state.add('right')
			if payload[2] & 0x40:
				state.add('down')
			if payload[2] & 0x80:
				state.add('left')

			if payload[3] & 0x80:
				state.add('square')
			if payload[3] & 0x10:
				state.add('triangle')
			if payload[3] & 0x20:
				state.add('circle')
			if payload[3] & 0x40:
				state.add('cross')
			if payload[3] & 0x01:
				state.add('l2')
			if payload[3] & 0x02:
				state.add('r2')
			if payload[3] & 0x04:
				state.add('l1')
			if payload[3] & 0x08:
				state.add('r1')

			if payload[4] & 0x01:
				state.add('playstation')



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
			stick_x = payload[6]
			stick_y = payload[7]
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			limits = self.axis_limits['rstick']
			stick_x = payload[8]
			stick_y = payload[9]
			limits['x'][2] = stick_x
			limits['y'][2] = stick_y

			pos = payload[19]
			if self.res.axes['r2'].value != pos:
				self.res.axes['r2'].set_value(pos)
				dirty = True

			pos = payload[18]
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
						dest_axis = self.res.sticks[stick].x_axis
					elif axis == 'y':
						dest_axis = self.res.sticks[stick].y_axis
					if abs(dest_axis.value - pos) > 1:
						#print(f"stick {stick} axis {axis} value went from {dest_axis.value} to {pos}", file=sys.stderr)
						dest_axis.set_value(pos)
						dirty = True
		#elif event.direction == "OUT" and event.payload is not None and len(event.payload) == 37:
		#	print(f"len({len(event.payload)}) {' '.join(jlib.splitlen(binascii.hexlify(event.payload).decode(), 2))}", file=sys.stderr)
		#	rumble = False
		#	if event.payload[-2:] == bytes([0x87, 0x4c]):
		#		rumble = True
		#	elif event.payload[-2:] == bytes([0xea, 0x8c]):
		#		rumble = True
		#	if rumble:
		#		if nao - self.res.last_rumble > (1 / 30):
		#			print(f"Setting rumbling", file=sys.stderr)
		#			self.res.rumbling = True
		#			self.set_dirty()

			#print(f"len({len(event.payload)}) {' '.join(jlib.splitlen(binascii.hexlify(event.payload).decode(), 2))}", file=sys.stderr)
		if dirty:
			#print("Setting dirty")
			self.set_dirty()
