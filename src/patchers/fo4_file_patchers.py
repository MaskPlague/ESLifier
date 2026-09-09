import json
import json5
import os

import configparser
import io
from patchers.shared_file_patchers import shared_patchers
from log_stream import write_to_file, write_ineligible

class patchers(shared_patchers):    
    ...