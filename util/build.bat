cd c:\users\jayson\desktop\mister_viz
c:\msys64\mingw64\bin\pyinstaller.exe --name=mister_viz --noconsole --icon=viz.ico mister_viz_stub.py
copy _ecodes.yaml dist\mister_viz
c:\msys64\usr\bin\tar.exe cvf dist.tar dist
c:\msys64\usr\bin\gzip.exe dist.tar
