import os
from lists.list_parent import list_parent_class

class ListObjBase():
    name:str
    mod_list:list_parent_class
    skip_key:str
    title:str

    def __init__(self, name, alist:list_parent_class, skip_key:str, title:str, confirm_text, confirmed):
        self.name = name
        self.mod_list = alist
        self.skip_key = skip_key
        self.title = title
        self.confirm_text = confirm_text
        self.confirmed = confirmed

    def confirmed(self):
        ...

    def confirm_text(self, size:int, free_space:int)->str:
        ...


def estimate_output_size(mods:list[str], dependency_dictionary:dict, file_masters:dict, 
                         game_archive_masters:dict=None, has_others:set=None) -> int:
    size = 0
    counted = set()

    def add(path):
        nonlocal size
        lower = path.lower()
        if lower in counted or not os.path.exists(path):
            return
        try:
            size += os.path.getsize(path)
        except OSError:
            return
        counted.add(lower)

    for mod in mods:
        add(mod)
        if has_others is not None and mod not in has_others:
            continue
        basename = os.path.basename(mod.lower())
        for dependent in dependency_dictionary.get(basename, ()):
            add(dependent)
        for file in file_masters.get(basename, ()):
            add(file)
        if game_archive_masters:
            for file in game_archive_masters.get(basename, ()):
                add(file)
    return size

def size_in_units(size: int):
    if size > 1024 ** 3:
        return round(size / (1024 ** 3), 3), 'GBs'
    if size > 1048576:
        return round(size / 1048576, 2), 'MBs'
    return round(size / 1024, 2), 'KBs'
