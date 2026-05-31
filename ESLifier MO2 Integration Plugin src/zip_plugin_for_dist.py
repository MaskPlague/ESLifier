import os
import build_mo2_plugin_translation_template
def zip_files():
    build_mo2_plugin_translation_template.create_template()
    os.system('"ESLifier MO2 Integration Plugin src/zip_plugin_for_dist.bat"')

if __name__ == "__main__":
    zip_files()