call conda create -n eslifier_env python=3.14 -y

call conda activate eslifier_env

call conda install -y leveldb

call conda install -y --file requirements.txt --channel conda-forge

rem call pip install PySide6

call pip install PyQt6-stubs

call set PYINSTALLER_COMPILE_BOOTLOADER=1
call pip install --verbose --no-binary=PyInstaller PyInstaller