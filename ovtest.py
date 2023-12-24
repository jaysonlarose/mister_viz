#!/usr/bin/env python3
import os, sys, time, binascii
import mister_viz_openvizsla

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, GObject





class Winder(Gtk.Window):
	def __init__(self):
		super().__init__()
		self.resize(640, 480)
		self.label = Gtk.Label()
		self.add(self.label)
		self.show_all()
		self.count = 0
		self.rq = 0
		self.last_packet = None

		#GLib.timeout_add(int(1000 / 60), self.periodic_handler)

	def input_handler(self, widget, packet):
		self.last_packet = packet
		self.count += 1
		#self.label.set_text(f"{self.count} {repr(args)}")
		self.label.set_text(f"{self.count} {self.rq} {repr(self.last_packet)}")

	def periodic_handler(self):
		self.rq += 1
		self.label.set_text(f"{self.count} {self.rq} {repr(self.last_packet)}")
		return True

def pwint(ts, pkt, flags):
	#pass
	if len(pkt) > 10:
		print(f"pwint: {ts} {binascii.hexlify(pkt).decode()} {flags}")

def printer(*args):
	print(f"printer: {args}")

def packet_printer(widget, packet):
	print(packet.to_dict())

if __name__ == '__main__':

	#loop = GLib.MainLoop()

	w = Winder()

	obj = mister_viz_openvizsla.OpenVizslaReader()
	obj.connect("packet", w.input_handler)
	obj.connect("packet", packet_printer)
	obj.startup()

	try:
		Gtk.main()
	except KeyboardInterrupt:
		pass

	obj.shutdown()


	#fw_zipfile = zipfile.ZipFile(os.path.join(ov_dir, "ov3.fwpkg"), "r")
	#dev = LibOV.OVDevice(mapfile=fw_zipfile.open("map.txt", "r"))
	#err = dev.open(bitstream=fw_zipfile.open("ov3.bit", "r"))
	#if err:
	#	print("USB: Unable to find device")
	#	sys.exit(1)

	#speed = "fs"
	#timeout = None

	#dev.regs.LEDS_MUX_2.wr(0)
	#dev.regs.LEDS_OUT.wr(0)
	#												 
	## LEDS 0/1 to FTDI TX/RX
	#dev.regs.LEDS_MUX_0.wr(2)
	#dev.regs.LEDS_MUX_1.wr(2)
	#												 
	## enable SDRAM buffering
	#ring_base = 0
	#ring_size = 16 * 1024 * 1024
	#ring_end = ring_base + ring_size
	#dev.regs.SDRAM_SINK_GO.wr(0)
	#dev.regs.SDRAM_HOST_READ_GO.wr(0)
	#dev.regs.SDRAM_SINK_RING_BASE.wr(ring_base)
	#dev.regs.SDRAM_SINK_RING_END.wr(ring_end)
	#dev.regs.SDRAM_HOST_READ_RING_BASE.wr(ring_base)
	#dev.regs.SDRAM_HOST_READ_RING_END.wr(ring_end)
	#dev.regs.SDRAM_SINK_GO.wr(1)
	#dev.regs.SDRAM_HOST_READ_GO.wr(1)
	#												 
	## clear perfcounters
	#dev.regs.OVF_INSERT_CTL.wr(1)
	#dev.regs.OVF_INSERT_CTL.wr(0)

	#if not dev.regs.ucfg_stat.rd():
	#	print("ULPI clock not started")
	#	sys.exit(1)
	#

	## set to non-drive; set FS or HS as requested
	#if speed == "hs":
	#	dev.ulpiregs.func_ctl.wr(0x48)
	#	dev.rxcsniff.service.highspeed = True
	#elif speed == "fs":
	#	dev.ulpiregs.func_ctl.wr(0x49)
	#	dev.rxcsniff.service.highspeed = False
	#elif speed == "ls":
	#	dev.ulpiregs.func_ctl.wr(0x4a)
	#	dev.rxcsniff.service.highspeed = False
	#else:
	#	assert 0,"Invalid Speed"

	#dev.rxcsniff.service.handlers = [pwint]

	#elapsed_time = 0
	#try:
	#	dev.regs.CSTREAM_CFG.wr(1)
	#	while True:
	#		time.sleep(1)
	#		#print('loop')

	#		##print("dev.regs.SDRAM_SINK_PTR_READ.wr(0)")
	#		##dev.regs.SDRAM_SINK_PTR_READ.wr(0)
	#		##print("done")
	#		##print("dev.regs.OVF_INSERT_CTL.wr(0)")
	#		##dev.regs.OVF_INSERT_CTL.wr(0)
	#		##print("done")

	#		###print("rptr = dev.regs.SDRAM_SINK_RPTR.rd()")
	#		###rptr = dev.regs.SDRAM_SINK_RPTR.rd()
	#		###print("done")
	#		###print("wptr = dev.regs.SDRAM_SINK_WPTR.rd()")
	#		###wptr = dev.regs.SDRAM_SINK_WPTR.rd()
	#		###print("done")
	#		###print("wrap_count = dev.regs.SDRAM_SINK_WRAP_COUNT.rd()")
	#		###wrap_count = dev.regs.SDRAM_SINK_WRAP_COUNT.rd()
	#		###print("done")

	#		###rptr -= ring_base
	#		###wptr -= ring_base

	#		###assert 0 <= rptr <= ring_size
	#		###assert 0 <= wptr <= ring_size

	#		###delta = wptr - rptr
	#		###if delta < 0:
	#		###	delta += ring_size

	#		###total = wrap_count * ring_size + wptr
	#		###utilization = delta * 100 / ring_size

	#		###print("%d / %d (%3.2f %% utilization) %d kB | %d overflow, %08x total | R%08x W%08x" %
	#		###	(delta, ring_size, utilization, total / 1024,
	#		###	dev.regs.OVF_INSERT_NUM_OVF.rd(), dev.regs.OVF_INSERT_NUM_TOTAL.rd(),
	#		###	rptr, wptr
	#		###	), file = sys.stderr)

	#		##print("dev.regs.OVF_INSERT_CTL.wr(0)")
	#		##dev.regs.OVF_INSERT_CTL.wr(0)
	#		##print("done")
	#		##print("%d overflow, %08x total" % (dev.regs.OVF_INSERT_NUM_OVF.rd(), dev.regs.OVF_INSERT_NUM_TOTAL.rd()), file = sys.stderr)

	#		#if False:
	#		#	dev.regs.SDRAM_SINK_DEBUG_CTL.wr(0)
	#		#	print("rptr = %08x i_stb=%08x i_ack=%08x d_stb=%08x d_term=%08x s0=%08x s1=%08x s2=%08x | wptr = %08x i_stb=%08x i_ack=%08x d_stb=%08x d_term=%08x s0=%08x s1=%08x s2=%08x wrap=%x" % (
	#		#		dev.regs.SDRAM_HOST_READ_RPTR_STATUS.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_I_STB.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_I_ACK.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_D_STB.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_D_TERM.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_S0.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_S1.rd(),
	#		#		dev.regs.SDRAM_HOST_READ_DEBUG_S2.rd(),
	#		#		dev.regs.SDRAM_SINK_WPTR.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_I_STB.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_I_ACK.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_D_STB.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_D_TERM.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_S0.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_S1.rd(),
	#		#		dev.regs.SDRAM_SINK_DEBUG_S2.rd(),
	#		#		dev.regs.SDRAM_SINK_WRAP_COUNT.rd(),
	#		#		), file = sys.stderr)
	#		#if timeout and elapsed_time > timeout:
	#		#	break
	#		##time.sleep(1)
	#		#elapsed_time = elapsed_time + 1
	#except KeyboardInterrupt:
	#	pass
	#finally:
	#	dev.regs.SDRAM_SINK_GO.wr(0)
	#	dev.regs.SDRAM_HOST_READ_GO.wr(0)
	#	dev.regs.CSTREAM_CFG.wr(0)

