# Fully hallucinated Touhou Koumakyou: New Classic - the Embodiment of Scarlet Devil modding toolkit
Sloppy Python scripts for both extracting and repacking PKGL (Zstandard) archives used in 2026 remake of Touhou 6 (and the 1.03 update to the original game that comes with it), complete with non-standard opus "decoder" and "encoder" (for New Classic) and batch scripts for one-click operation.

These are slow with bigger New Classic archives and are a temporary, albeit fully functional solution until thtk or some other tool implements proper PKGL support.
## Usage
1. Install Python https://www.python.org/downloads/
2. Run `pip install zstandard` in command line
3. Download/clone the repository
4. Merge th06nc and th06c folders with your New Classic and Classic installations respectively
5. Run `EXTRACT.bat` to extract everything to UNPACKED folder
6. Additionally run `DECODE_BGM.bat` for New Classic if you want to mess with it's BGM, it'll put OGGs into UNPACKED/bgm and UNPACKED/bgm2
7. Mod away! Now it's Yourhou! (sorry) It's all pretty much the same as with the original, except ANMs are mostly redirects to more convenient DDS textures
8. Run `REPACK.bat` to create new archives from files in UNPACKED folder ***(careful, this will overwrite archives currently in game folder)***
9. Run `ENCODE_BGM.bat` to turn OGGs back into OPUSes ***(same, this will overwrite current BGM files)***
