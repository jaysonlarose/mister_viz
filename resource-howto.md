# Resources Overview

mister_viz resources are made up of two types of files:

* (SVG)[https://en.wikipedia.org/wiki/Scalable_Vector_Graphics] files, which define the graphics for a controller
* (YAML)[https://en.wikipedia.org/wiki/YAML] files, which define a specific controller, which SVG file should be used to represent it, and how the various controls should be mapped onto the SVG file's features.


# The SVG files

These are, for the most part, perfectly normal SVG files. I recommend using Inkscape to create them, but technically, you should be able to use anything to do so, so long as it is capable of working with Inkscape layers and `data-*` properties.

Build your controller out, as complicated or as simple as you like. For each element that you'd like to change due to button presses or stick movements or whatnot, put it in its activated form on its own layer. Make sure it is marked as "hidden" (attribute "style" value "display:none"). Use the Inkscape XML Editor to apply a custom attribute to each of these layers. The name of this attribute is "data-state", and its value will be the name of the individual control in question (such as "l", "r", "up", "down", "lstick"). For analog sticks that also have button functionality (think: thumb sticks on most modern gamepads), there's a special case: assign values of "x idle" and "x active", where "x" is the original control name, to the layers that represent the stick in its button-released and button-pressed states.

# The YAML files

These are the files that define an actual controller or joystick, assign an .svg file to represent it, and map out controls to layers.

They contain the following sections:

* name
* vid
* pid
* svg
* scale
* buttons
* axes

## name

A friendly name to describe the controller.

## vid

The USB/Bluetooth VendorID for this controller. This will be printed out in the main mister_viz window every time a control is actuated.

## pid

The USB/Bluetooth ProductID for this controller. This will be printed out in the main mister_viz window every time a control is actuated.

## svg

The name of the .svg file that represents this controller.

## scale

Can be used to change the initial size of the viz graphic created. `1.0` is regular size, `0.5` is half size, `2.0` is double size, et cetera.

## buttons

This maps the button names (as reported by mister_viz) to graphics layers in the .svg file.

## axes

This is the most complicated one. It's how controller axis are turned into stuff.
