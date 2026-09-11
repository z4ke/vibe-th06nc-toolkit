# Fully hallucinated Touhou Koumakyou: New Classic - the Embodiment of Scarlet Devil modding toolkit
Sloppy Python scripts for both extracting and repacking PKGL archives used in 2026 remake of Touhou 6 (and the 1.03 update to the original game that comes with it), complete with non-standard opus "decoder" and "recoder" (for New Classic) and batch scripts for one-click operation.

These are slow with bigger New Classic archives and are a temporary, albeit fully functional solution until thtk or some other tool implements proper PKGL support.
# Usage
* Install Python https://www.python.org/downloads/
* Run `pip install zstandard` in command line
* Download/clone the repository
* Merge th06nc and th06c folders with your New Classic and Classic installations respectively
* Run `EXTRACT.bat` to extract everything to UNPACKED folder
* Additionally run `DECODE_BGM.bat` for New Classic if you want to mess with it's BGM, it'll put OGGs into UNPACKED/bgm and UNPACKED/bgm2
* Mod away! Now it's Yourhou! (sorry) It's all pretty much the same as with the original, except ANMs are mostly redirects to more convenient DDS textures
* Run `REPACK.bat` to create new archives from files in UNPACKED folder ***(careful, this will overwrite archives currently in game folder)***
* Run `ENCODE_BGM.bat` to turn OGGs back into OPUSes ***(same, this will overwrite current BGM files)***
