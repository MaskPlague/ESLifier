import subprocess
import os

def create_template():
    working_directory = os.getcwd()
    with subprocess.Popen(
        ["pylupdate6", r"D:\GitHub\ESLifier\src", "-ts", "eslifier_translation.ts"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        shell=False,
        cwd=working_directory
    ) as p:
        for line in p.stderr:
            print(line, end="")
    print('Done Creating template')

if __name__ == "__main__":
    create_template()