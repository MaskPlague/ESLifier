"""
Stand-in for the ``scanner`` class that the mod-manager back ends (MO2, NoManager, Vortex) talk to.
It records what they hand to the BSA extractor and can drop files into ``bsa_extracted/`` the way a real
extraction would.
"""
import os


class FakeScanner:
    def __init__(self, output_file_name="ESLifier Output"):
        self.file_count = 0
        self.all_files = []
        self.ignored_files = set()
        self.game_archive_blacklist = {"skyrim - misc.bsa"}
        self.output_file_name = output_file_name
        self.winning_files_dict = {}
        self.bsa_calls = []                      # [(bsa_list, plugins_list), ...]
        self.files_to_extract = []               # relative paths created under bsa_extracted/ on extraction
        self.plugins_list = []                   # what get_plugins_list() returns
        self.plugins_list_paths = []             # paths get_plugins_list() was asked to read

    def get_plugins_list(self, path):
        self.plugins_list_paths.append(path)
        return self.plugins_list

    def extract_scripts_and_seq_from_game_archive(self, bsa_list, plugins_list):
        self.bsa_calls.append((bsa_list, plugins_list))
        for rel in self.files_to_extract:
            path = os.path.join("bsa_extracted", rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(b"extracted")


def touch(path, data=b"x"):
    """Create a file (and its folders). ``path`` may be a pathlib.Path or str."""
    path = os.fspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path
