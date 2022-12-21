# mister_viz for windows

## Disclaimer

I'm primarily a Linux user. I use Python and GTK+ to write GUI applications. So this is written in Python in GTK+. I realize that most people who play video games and stream do so using Windows. So this is my first application that I've ever tried porting to Windows. If it breaks, you get to keep both pieces.

## Differences between Windows and Linux

I couldn't figure out how to hook the output of `multiprocessing.Process` into something I could feed into GLib under Windows, so I had to use polling instead.

Under Linux, mister_viz looks for resources under `$HOME/.config/mister_viz`. Under Windows, it looks for resources under `%USERPROFILE%\mister_viz`.

The windows version of mister_viz will check to see if there are any other `mister_viz.exe` processes running on startup. If it finds any, it offers the choice of killing them and continuing startup, or leaving them alone and exiting. If mister_viz errors out or otherwise exits uncleanly, run it again, let it kill the old processes, and then close it out.

The windows version of mister_viz will store the last host it connected to in the registry when it exits, and auto-fill the connect hostname when it starts back up.

## Important Notes

Be sure to check [readme.md](readme.md).

The directory that mister_viz looks for resources in is "%USERPROFILE%\mister_viz. Or, to put it another way, open Windows Explorer. Click on the address bar, type `%USERPROFILE%`, and hit enter. You should create a folder inside this directory named "mister_viz". The installer will create this by default and put some example resources inside.

## How the Sausage is Made

### Development Environment

Development environment: [MSYS2](https://www.msys2.org/)

Nowadays, if you open up a command prompt under Windows and type `python`, the Microsoft Store pops up and tries to get you to install something. This isn't the version of python that I used (Does anyone know how to disable that Microsoft Store popup?). [This page](https://www.gtk.org/docs/installations/windows) pointed me at MSYS2 for running GTK apps under Windows, and it does what it says on the tin, for the most part.

These were the commands that I ran to bring the MSYS2 python environment up-to-snuff so it could run mister_viz:

```bash
pacman -S --needed base-devel mingw-w64-x86_64-toolchain
pacman -S mingw-w64-x86_64-python-pip
pacman -S mingw-w64-x86_64-python-pillow
python3 -m pip install wheel
python3 -m pip install cairosvg
pacman -S mingw-w64-x86_64-python-gobject
pacman -S mingw-w64-x86_64-python3-gobject
pacman -S mingw-w64-x86_64-gtk3
pacman -S mingw-w64-x86_64-python-yaml
pacman -S mingw-w64-x86_64-python-lxml
pacman -S mingw-w64-x86_64-python-psutil
```

(maybe add `pacman -S python-devel` to this list?)

I decided that numpy has a very large install footprint, and I'm actually using it for very little, so I rewrote the things that depended on it. Even so, here's how I installed it just in case it turns out to be necessary:

```bash
pacman -S mingw-w64-x86_64-python-numpy
```

These were the commands I ran to install the first python-exe-bundler method I tried, cx_Freeze. They shouldn't be necessary, but in case, here they are:

```bash
python3 -m pip install wheel
pacman -S cmake
pacman -S mingw-w64-x86_64-python-lief
pacman -S mingw-w64-x86_64-python-cx-freeze 
```

New stuff

### EXE Bundler

Exe bundler: [PyInstaller](https://pyinstaller.org/)

As you can tell from the Development Environment section, there's a lot of hoops you have to jump through to get this thing running on Windows. I can't expect everyone to do that shit! So I use PyInstaller to take all that junk and turn it into a single folder that has an .exe file in it, that you can run. Yeah, that folder is a couple hundred megs, but modern games clock in at tens of gigabytes. You'll deal.

### Installer

Installer: [Nullsoft Scriptable Install System](https://nsis.sourceforge.io/)

It really whips the llama's ass. Actually, it's a bit of a pain in the ass to figure out, but hey, you only have to figure it out once.
