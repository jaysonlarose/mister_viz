import teensy_n64

NAME = "n64"
SVG_FILENAME = "8bitdo_64.svg"
RESOURCE_REMAP = {
	'button': {
		'zl': 'z',
		'zr': 'z',
	}
}

class Translator(teensy_n64.Translator):
	remapping = {
		'button': {
			'zl': 'z',
			'zr': 'z',
		}
	}
