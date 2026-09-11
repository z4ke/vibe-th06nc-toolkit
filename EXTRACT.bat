@echo off
cd data
python pkgl_extract.py th06CM.dat th06CM ../UNPACKED/CM
python pkgl_extract.py th06ED.dat th06ED ../UNPACKED/ED
python pkgl_extract.py th06FN.dat th06FN ../UNPACKED/FN
python pkgl_extract.py th06IN.dat th06IN ../UNPACKED/IN
python pkgl_extract.py th06MD.dat th06MD ../UNPACKED/MD
python pkgl_extract.py th06ST.dat th06ST ../UNPACKED/ST
python pkgl_extract.py th06TL.dat th06TL ../UNPACKED/TL
