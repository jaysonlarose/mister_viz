# How mister_viz processes SVG files

## The tl;dr

mister_viz inspects the .svg file and looks for layers and groups that have the `data-state` attribute. It isolates each of those layers and uses them for the active or pressed state for the button, value, or stick that has the same name as the value of the `data-state` attribute. Everything else (that wasn't set as hidden) is used to draw the background.

## The gory details

### Pass 1: Data-state attribute discovery.

Function: `svg_state_split()`

First the SVG is iterated through, looking to find `g` tags that have a `data-state` attribute set. Each of these attribute values is added to the list of states. That `g` tag is also set as hidden (`style` attrib set to `display:none`) if it isn't already. The value `None` is also added to the list of states, which is used to represent the background.

For each state in the state list, a new copy of the SVG XML tree is made, which gets processed further from here.

### Pass 2: 
