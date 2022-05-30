#!/usr/bin/env python3

ECODE_YAML_FILE = "_ecodes.yaml"

if __name__ == '__main__':
	import evdev, yaml, os, sys

	if os.path.exists(ECODE_YAML_FILE):
		print(f"{ECODE_YAML_FILE} exists, exiting!", file=sys.stderr)
		sys.exit(1)
	prefixes = 'KEY ABS REL SW MSC LED BTN REP SND ID EV BUS SYN FF_STATUS FF INPUT_PROP'.split()
	export_codes = {}
	for p in prefixes:
		export_codes[p] = getattr(evdev.ecodes, p)
	
	print(f"Writing {ECODE_YAML_FILE}...", file=sys.stderr)
	open(ECODE_YAML_FILE, "w").write(yaml.dump(export_codes))
	print("Done!", file=sys.stderr)
