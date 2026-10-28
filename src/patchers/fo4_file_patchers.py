import json
import json5
import os

import configparser
import io
import struct
try:
    from patchers.shared_file_patchers import shared_patchers
    from log_stream import write_to_file, write_ineligible
except:
    from shared_file_patchers import shared_patchers
    def write_to_file(txt):
        print(str(f"write_to_file: {str(txt)}"))
    def write_ineligible(txt):
        print(str(f"write_ineligible: {str(txt)}"))

class patchers(shared_patchers):    
    ...