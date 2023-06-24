#!/usr/bin/env python3

import os, sys, lxml.etree

def xmlwalk(tree):
	yield tree
	for item in tree:
		yield from xmlwalk(item)


if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("files", nargs="+")
	args = parser.parse_args()

	for svg_file in args.files:
		print(f"Processing {svg_file}")
		data = open(svg_file, "rb").read()
		tree = lxml.etree.fromstring(data)
		dirty = False
		for element in xmlwalk(tree):
			if 'data-state' in element.attrib:
				if not 'data-type' in element.attrib:
					print(f"Adding data-type to {element}")
					element.attrib['data-type'] = 'button'
					dirty = True
		if dirty:
			print(f"Writing {svg_file}")
			open(svg_file, "wb").write(lxml.etree.tostring(tree))
		
		
