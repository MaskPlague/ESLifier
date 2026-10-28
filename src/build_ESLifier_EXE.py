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

def compile_exe(game_mode: str):
    working_directory = os.getcwd()
    one_file_args = ["pyinstaller", f"src/run_{game_mode.lower()}_mode.py", "--onefile",
                    "-n", f"ESLifier-{game_mode}", "--noconsole", "--icon", f"src/images/{game_mode}/ESLifier.ico",
                    "--add-data", f"src/images/{game_mode}/;images/{game_mode}"]
    with subprocess.Popen(
        one_file_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        cwd=working_directory
    ) as p:
        for line in p.stderr:
            print(line, end="")
    print(f'Done Building {game_mode} EXE')

if __name__ == "__main__":
    choice = input("Enter a build mode (SSE|S, FO4|F, Both|B): ").strip()
    if choice.lower() in ("sse", "s"):
        game_modes = ["SSE"]
    elif choice.lower() in ("fo4", "f"):
        game_modes = ["FO4"]
    elif choice.lower() in ("both", "b"):
        game_modes = ["SSE", "FO4"]
    else:
        print(f"Invalid input: '{choice}', cancelling")
        exit()

    for game_mode in game_modes:
        compile_exe(game_mode)
        print('Calculating Checksum (exe)')
        append_luhn_checksum(f"dist\\ESLifier-{game_mode}.exe")
        print('')
        print(f"Standalone {game_mode} EXE done\n")
        formatted_datetime = datetime.now().isoformat(timespec='milliseconds')
        print("Last Ran: " + formatted_datetime)
