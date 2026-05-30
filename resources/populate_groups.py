#!/usr/bin/env python3

"""
This is a script to help prepare an SVG file fresh out of Inkscape
for use by mister_viz.

It does this by retrieving the list of button and axis names from the supplied
YAML file, and then it searches the supplied SVG file for Inkscape layers
that have the same name. It then adds appropriate data-type and data-state
attributes to those groups.

It runs this modified SVG through HTML Tidy and then outputs it on stdout.
"""

import yaml
import lxml.etree
import subprocess
import sys

SVG_PREFIX = '{http://www.w3.org/2000/svg}'
INKSCAPE_PREFIX = '{http://www.inkscape.org/namespaces/inkscape}'


if __name__ == '__main__':
	import argparse
	parser = argparse.ArgumentParser()
	parser.add_argument("yaml_file")
	parser.add_argument("svg_file")
	args = parser.parse_args()

	y = yaml.load(open(args.yaml_file, "r").read(), Loader=yaml.SafeLoader)
	buttons = set()
	sticks = set()
	buttons |= set(y['buttons'].values())
	if 'axes' in y:
		for axis_event in y['axes']:
			if 'binary' in y['axes'][axis_event]:
				buttons |= set(y['axes'][axis_event]['binary'].keys())
			if 'stick'  in y['axes'][axis_event]:
				sticks  |= set(y['axes'][axis_event]['stick'].keys())

	print(f"identified buttons: {buttons}", file=sys.stderr)
	print(f"identified sticks:  {sticks}", file=sys.stderr)



	tree = lxml.etree.fromstring(open(args.svg_file, "rb").read())
	if 'name' in y:
		tree.attrib['data-name'] = y['name']
	groups = tree.findall(f".//{SVG_PREFIX}g")
	for g in groups:
		if f"{INKSCAPE_PREFIX}label" not in g.attrib:
			continue
		label = g.attrib[f"{INKSCAPE_PREFIX}label"]
		print(f"{label}", file=sys.stderr)
		for s in sticks:
			if s in buttons:
				if label == f"{s} active":
					g.attrib["data-state"] = s
					g.attrib["data-type"]  = "button"
				elif label == f"{s} idle":
					g.attrib["data-state"] = s
					g.attrib["data-type"]  = "stick"
					g.attrib["data-extents-x"] = "-30 30"
					g.attrib["data-extents-y"] = "-30 30"
		if "data-state" in g.attrib:
			continue
		for b in buttons:
			if label == b:
				g.attrib["data-state"] = b
				g.attrib["data-type"]  = "button"

	modified_xml = lxml.etree.tostring(tree)
	proc = subprocess.run(['tidy', '-config', 'tidy.config', '-'], input=modified_xml, stdout=subprocess.PIPE)
	print(proc.stdout.decode())
