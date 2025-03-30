import subprocess
import os

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

def compile_exe():
    working_directory = os.getcwd()
    with subprocess.Popen(
        ["pyinstaller", "src/eslifier_app.py", "--onefile", "-n", "ESLifier", "--noconsole", "--icon", "src/images/ESLifier.ico"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        cwd=working_directory
    ) as p:
        for line in p.stderr:
            print(line, end="")
    print('Done Building EXE')

compile_exe()
append_luhn_checksum("dist\\ESLifier.exe")