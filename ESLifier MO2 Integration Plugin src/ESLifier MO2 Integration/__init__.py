import os
import site
from typing import List

site.addsitedir(os.path.join(os.path.dirname(__file__), "lib"))

from mobase import IPlugin
from .ESLifier import ESLifier

def createPlugins() -> List["IPlugin"]:
    return [ESLifier()]