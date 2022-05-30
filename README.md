# What is mister_viz?

mister_viz is a controller visualization client, written to be the counterpart to my [Main_MiSTer_inputsocket](https://github.com/jaysonlarose/Main_MiSTer_inputsocket) modification for MiSTer. It reads input events from MiSTer_inputsocket and applies them to graphics rendered from SVG files. It's intended to be used by streamers, speedrunners, and anyone else who might want to show what physical inputs are taking place. It's capable of tracking multiple input devices, and is designed with configurability in mind.

# What does it run on?

It runs on Linux and Windows.

For Linux users, the following dependencies need to be installed:

* Python GObject Introspection
* GTK+ 3.0
* cairosvg
* cairo
* PIL
* yaml
* lxml

For windows, an installation program is provided. If you *really* want to try building it, see [here](README.windows.md).

# How do I 

# How mister_viz processes SVG files

## The tl;dr

mister_viz inspects the .svg file and looks for layers and groups that have the `data-state` attribute. It isolates each of those layers and uses them for the active or pressed state for the button, value, or stick that has the same name as the value of the `data-state` attribute. Everything else (that wasn't set as hidden) is used to draw the background.

## The gory details

### Pass 1: Data-state attribute discovery.

Function: `svg_state_split()`

First the SVG is iterated through, looking to find `g` tags that have a `data-state` attribute set. Each of these attribute values is added to the list of states. That `g` tag is also set as hidden (`style` attrib set to `display:none`) if it isn't already. The value `None` is also added to the list of states, which is used to represent the background.

For each state in the state list, a new copy of the SVG XML tree is made, which gets processed further from here.

### Pass 2: 

Function: `mangle()`

All of the `g` tags in the SVG are inspected.

If the `g` tag has a `data-state` attribute, and it matches the state that this SVG XML tree belongs to, it will be given a `style=display:inline` attribute, in other words, making it visible. In addition to this, each of its parent elements will be checked, and any which have a `style` of `display:none` will be changed to `style="display:inline"`.

If the `data-state` attribute doesn't match, the group and all of its children will be deleted.

If neither of the above conditions apply, and it's not the `None` state's SVG XML being processed:

* The group and all of its children will be deleted if the `style` tag contains `display:none`.
* Otherwise, the group will have a `style` tag of `display:none` applied to it.

The end result of this logic is that the SVG XML trees for the state tags will only show the graphics with that tag applied to them, and the `None` SVG XML tree will look like however the unmodified SVG would look like, with the exception of any of the state tag graphics, which will be hiddn or removed.

### Pass 3:

Function: `devastate()`

This is a final cleanup pass, it finds any `g` tags which may still be remaining that are set as hidden, and removes them.


