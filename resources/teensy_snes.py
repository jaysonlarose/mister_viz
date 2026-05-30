import mister_viz_openvizsla
import struct

NAME = "snes"
SVG_FILENAME = "snes.svg"


class Translator(mister_viz_openvizsla.OpenVizslaTranslator):
	def __init__(self, resources):
		mister_viz_openvizsla.OpenVizslaTranslator.__init__(self, resources)
		self.button_elements = dict([ [x.element, x] for x in self.res.buttons.values() ])
		self.last_event = None

		self.axis_limits = {
		}

	def event_handler(self, widget, event):
		self.last_event = event
		dirty = False
		payload = event.payload
		if len(payload) != 2:
			return
		state = set()
		if payload[0] & 0x10:
			state.add("up")
		if payload[0] & 0x20:
			state.add("down")
		if payload[0] & 0x40:
			state.add("left")
		if payload[0] & 0x80:
			state.add("right")
		if payload[0] & 0x08:
			state.add("start")
		if payload[0] & 0x04:
			state.add("select")
		if payload[1] & 0x01:
			state.add("a")
		if payload[0] & 0x01:
			state.add("b")
		if payload[1] & 0x02:
			state.add("x")
		if payload[0] & 0x02:
			state.add("y")
		if payload[1] & 0x04:
			state.add("l")
		if payload[1] & 0x08:
			state.add("r")


		for k, v in self.button_elements.items():
			if k in state:
				new_value = 1
			else:
				new_value = 0
			if new_value != v.value:
				v.set_value(new_value)
				dirty = True


		if dirty:
			#print(state)
			#print(self.res.axes['l'].value)
			#print(self.res.axes['r'].value)
			self.set_dirty()
