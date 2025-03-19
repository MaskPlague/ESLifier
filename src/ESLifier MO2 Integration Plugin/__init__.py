import os
import site
from typing import List

site.addsitedir(os.path.join(os.path.dirname(__file__), "lib"))

from mobase import IPlugin
from .ESLifier import ESLifier
from .ESLifier_notifier import ESLifier_Notifier

def createPlugins() -> List["IPlugin"]:
    return [ESLifier(), ESLifier_Notifier()]