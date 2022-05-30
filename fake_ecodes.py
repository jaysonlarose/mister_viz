"""
This module aims to look, smell, act, and taste just like the `evdev.ecodes`
module, with the notable exception that this gets its values from a yaml file,
so non-linux OSes can use it.
"""

import os, sys, yaml

if sys.platform == "win32":
	if getattr(sys, "frozen", False):
		BASE_DIR = os.path.dirname(sys.executable)
	else:
		BASE_DIR = os.path.dirname(__file__)
else:
	BASE_DIR = os.path.dirname(__file__)

g = globals()

yaml_ecodes = yaml.load(open(os.path.join(BASE_DIR, "_ecodes.yaml"), "r").read(), Loader=yaml.Loader)

ecodes = {}

for prefix, members in yaml_ecodes.items():
	g.setdefault(prefix, members)
	for value, keyspec in members.items():
		if not isinstance(keyspec, list):
			keyspec = [keyspec]
		for key in keyspec:
			if key not in ecodes:
				ecodes[key] = value
			if key not in g:
				g[key] = value
			else:
				print(f"Key duplication: {key}")
				sys.exit(1)

keys = {}
keys.update(BTN)
keys.update(KEY)

del keys[KEY_MAX]
del keys[KEY_CNT]

bytype = {
	EV_KEY:       keys,
	EV_ABS:       ABS,
	EV_REL:       REL,
	EV_SW:        SW,
	EV_MSC:       MSC,
	EV_LED:       LED,
	EV_REP:       REP,
	EV_SND:       SND,
	EV_SYN:       SYN,
	EV_FF:        FF,
	EV_FF_STATUS: FF_STATUS,
}

del yaml_ecodes, BASE_DIR, g, prefix, members, value, keyspec, key, os, sys, yaml
