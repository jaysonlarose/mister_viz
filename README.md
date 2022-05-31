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

# How do I use it?

## Configure MiSTer

This (currently) requires a specially patched version of the main MiSTer binary, You can get that [here](https://github.com/jaysonlarose/Main_MiSTer_inputsocket/releases). I hope to get this added to the official MiSTer procject, but I digresss. This replaces the MiSTer file on the root of your MiSTer SD card.

You'll also need to open up MiSTer.ini and add the following to it:

```
input_socket_enabled=1
input_socket_bindport=22101
input_socket_bindhost=
```

## Optional (but recommended): Create an SVG file for your controller

I've included a couple of .SVG files for reference, but half of the fun it rolling your own. MiSTer_viz uses regular run-of-the-mill SVG files. The bits that are meant to represent pressed buttons and movable analog sticks are placed in their own group/layer, and the "data-state" attribute is applied to them to tell MiSTer_viz what controls they represent. This can be done by hand, or you can use Inkscape's XML Editor feature to do this.

## Create a .yaml file to map your controller onto the SVG

This part is a little tricky, but I added a feature to help you out with this.

Fire up mister_viz, and you should be greeted with the main window. Enter the hostname or IP address of your MiSTer (you can find it in the Misc. Options section of the MiSTer OSD) and hit "Connect". It should connect nearly instantly.

Now, hit buttons and move things on your controller. You should see information about the controls you're pressing in the main window. Hit the "Seen" button to bring up the Seen Events window. Hit all of your controller's buttons, move all of the sticks through their full range of motion. When you're happy with this, hit the Seen Event's windows "Copy" button to copy the YAML file to your clipboard. Name it with a `.yaml` extension and place it in your mister_viz resources folder.

Modify the .yaml file. Everything inside &lt;angle brackets&gt; needs to be changed.

* name: to give your controller a name
* svg: this needs to point to your graphics .svg file.
* svg state: All of the &lt;svg state&gt; entries correspond to the `data-state` attributes in your .svg file. If you need to figure out what any particular control is called, just press it and observe what comes up on the main mister_viz window.

### Defining Axes

Axes (the plural of "axis". One axis, two axes.) are a little complicated, but only a little bit. You can define each axis as either `binary` or `stick`.

Binary axes are treated as one or more svg state elements, according to where they are in their travel.

#### Hat Switch Example

By default, the 8Bitdo M30 gamepad's D-pad presents itself as the analog X and Y axes. To turn this into the controller states "up", "down", "left", and "right", we do this:

```yaml
axes:
  ABS_X:
    binary:
      left: [0, 0]
      right: [255, 255] 
  ABS_Y:
    binary:
      up: [0, 0]
      down: [255, 255]
```

This is saying:

* when ABS_X is moved between 0 and 0, apply state "left"
* when ABS_X is moved between 255 and 255, apply state "right"
* when ABS_Y is moved between 0 and 0, apply state "up"
* when ABS_Y is moved between 255 and 255, apply state "down"

#### Analog trigger as button example

The R2 trigger on an 8Bitdo Pro 2 controller presents itself as the ABS_GAS axis, which reports a value betwen 0 (fully released) and 255 (fully pressed). We map this onto the digital "r2" state by defining a range between 1 and 255 (basically, everything aside from completely released):

```yaml
axes:
  ABS_GAS:
    binary:
      r2: [1, 255]
```
In the future, I'm thinking of adding support for maybe partially coloring a state or doing rotations, but this hasn't happend yet.

#### Sticks

Sticks are the most complicated thing. I'll just show you an example and we'll walk through it. The 8Bitdo Pro 2 has two analog sticks that also act as buttons when pressed. Let's look at the definitions for just the left thumb stick:

```yaml
buttons:
  BTN_THUMBL: lstick
axes:
  ABS_X:
    stick:
      lstick:
        x:
          - [0, -30]
          - [255, 30]
  ABS_Y:
    stick:
      lstick:
        y:
          - [0, -30]
          - [255, 30]
```

`ABS_X` and `ABS_Y` are the names of the two axes reported by MiSTer. The `stick` directive says that we want to display them as a stick, and `lstick` is the name of the stick (well, sort of. More on this in a bit). `x` and `y` defines which axis each of these is going to represent. The next pair of lists define:

* minimum reported value, minimum pixel offset
* maximum reported value, maximum pixel offset

So, looking at the definition for `lstick`, it's basically saying "This is the x axis. It has a range from 0 to 255. When its value is 0, draw the graphic for it 30 pixels to the left of neutral. When its value is 255, draw the graphic for it 30 pixels to the right of neutral." (These pixel values are for when the graphic is rendered at 100% size. They're scaled accordingly if the window is resized.)

##### A Special Case: Clicky Sticks

There's one piece we still haven't talked about. We've defined a stick named "lstick", but also a button named "lstick". This is treated as a special case in the code. When there's a stick that's been defined with the same name as a button, it doesn't look in the SVG for a group or layer with a data-state attribute of "blah", it looks for "blah idle" and "blah active", depending on whether the button is currently activated or not.

That's basically it!

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


