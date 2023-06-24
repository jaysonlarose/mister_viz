#!/usr/bin/env python3

import os, sys, lxml.etree, copy
from mister_viz import set_xmlsubattrib

if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("infile")
	parser.add_argument("outfile")
	args = parser.parse_args()

	svg_bytes = open(args.infile, "rb").read()
	tree = lxml.etree.fromstring(svg_bytes)

	key_layer = None
	state_layer = None
	for element in list(tree):
		if element.tag == '{http://www.w3.org/2000/svg}g':
			if element.attrib['{http://www.inkscape.org/namespaces/inkscape}label'] == "key_layer":
				key_layer = element
			if element.attrib['{http://www.inkscape.org/namespaces/inkscape}label'] == "state_layer":
				state_layer = element
	

	for element in list(state_layer):
		state_layer.remove(element)
	
	for element in list(key_layer):
		ec = copy.deepcopy(element)
		print(ec.attrib)
		#ec.attrib['style'] = "display:none"
		ec.attrib['data-state'] = f"KEY_{ec.attrib['data-key']}"
		ec_rect = ec.find("{http://www.w3.org/2000/svg}rect")
		if ec_rect is None:
			for sub in ec.findall("{http://www.w3.org/2000/svg}g"):
				ec_rect = sub.find("{http://www.w3.org/2000/svg}rect")
				if ec_rect is not None:
					break

		set_xmlsubattrib(ec_rect, "style", "fill", "#ff0000")
		state_layer.append(ec)
	

	open(args.outfile, "wb").write(lxml.etree.tostring(tree))
