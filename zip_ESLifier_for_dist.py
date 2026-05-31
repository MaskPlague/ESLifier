import os
from src import build_translation_template

def zip_files():
    build_translation_template.create_template()
    os.system("zip_ESLifier_for_dist.bat")

if __name__ == "__main__":
    zip_files()