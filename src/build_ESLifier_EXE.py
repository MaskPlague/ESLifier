import subprocess
import os
from datetime import datetime

def luhn_checksum(data: bytes) -> int:
    total = 0
    for i, digit in enumerate(reversed(data)):
        if i % 2 == 0:
            digit *= 2
            if digit > 255:
                digit -= 256
        total += digit

    return (256 - (total % 256)) % 256

def append_luhn_checksum(filename):
    with open(filename, "rb") as f:
        data = f.read()

    checksum = luhn_checksum(data)

    with open(filename, "ab") as f:
        f.write(bytes([checksum]))

    print(f"Checksum {checksum} appended to {filename}")

def compile_exe(one_dir:bool):
    working_directory = os.getcwd()
    one_file_args = ["pyinstaller", "src/eslifier_app.py", "--onefile", "-n", "ESLifier", "--noconsole", "--icon", "src/images/ESLifier.ico"]
    one_dir_args = ["pyinstaller", "src/eslifier_app.py", "--onedir", "-y", "-n", "ESLifier", "--noconsole", "--icon", "src/images/ESLifier.ico"]
    with subprocess.Popen(
        one_dir_args if one_dir else one_file_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        cwd=working_directory
    ) as p:
        for line in p.stderr:
            print(line, end="")
    print('Done Building EXE')

compile_exe(one_dir=False)
print('Calculating Checksum (exe)')
append_luhn_checksum("dist\\ESLifier.exe")
print('')
print("Standalone EXE done\n")
#compile_exe(one_dir=True)
#print('')
#print('Calculating Checksum (one dir)')
#append_luhn_checksum("dist\\ESLifier\\ESLifier.exe")
#print("One Dir done\n")
formatted_datetime = datetime.now().isoformat(timespec='milliseconds')
print("Last Ran: " + formatted_datetime)