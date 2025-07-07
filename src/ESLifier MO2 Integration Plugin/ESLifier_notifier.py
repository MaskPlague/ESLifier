import mobase
import os
import json
import threading
import hashlib

from .ESLifier_qualification_checker import qualification_checker as light_check

try:
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtGui import QIcon
except ImportError:
    from PyQt5.QtCore import QCoreApplication
    from PyQt5.QtGui import QIcon

class ESLifier_Notifier(mobase.IPluginDiagnose):
    def __init__(self):
        super(ESLifier_Notifier, self).__init__()
    
    def init(self, organiser = mobase.IOrganizer):
        self._organizer = organiser
        self.flag_dict = {}
        self.hash_mismatches = []
        self._problems = [0]
        self._finished = False
        self.any_esl = False
        self.show_cells = True
        self.lock = threading.Lock()
        return True

    def name(self) -> str:
        return "ESLifierWarn"
    
    def localizedName(self) -> str:
        return self.tr("ESLifierWarn")
    
    def author(self) -> str:
        return "MaskPlague"

    def description(self):
        return self.tr("Checks if plugins can be ESLified.")
    
    def version(self) -> mobase.VersionInfo:
        return mobase.VersionInfo(2, 0, 0, mobase.ReleaseType.BETA)
    
    def requirements(self):
        return[]
    
    def settings(self):
        return [
        ]
    
    def activeProblems(self):
        self._organizer.onNextRefresh(self._resetProblems, False)
        if self.scan_for_eslable():
            return self._problems
        else:
            return []
    
    def _resetProblems(self):
        self._problems = [0]
    
    def shortDescription(self, key):
        return self.tr("ESLifiable plugin detected")

    def finish(self, boolean):
        self.finished = boolean

    def fullDescription(self, key):
        if self._problems == [0]:
            output_string = ""
            if len(self.hash_mismatches) > 0:
                output_string += self.tr(f"The following plugin files have been altered or\n")
                output_string += self.tr("removed since ESLifier last ran:\n")
                for file in self.hash_mismatches:
                    if len(file) > 50:
                        output_string += self.tr(f" ‣ ...{file[-50:]}\n")
                    else:
                        output_string += self.tr(f" ‣ {file}\n")
                output_string += self.tr("\nPlease open ESLifier and rebuild the output.\n\n")
                output_string += '\n'

            if len(self.needs_flag_dict) > 0:
                output_string += self.tr("The following plugins can be flagged as esl:\n")
                output_string += self.tr("NC = New Cell Flag, IC = New Interior Cell Flag, NW = New Worldspace\n")
                for plugin, flags in self.needs_flag_dict.items():
                    line = " ‣ "
                    if 'new_cell' in flags:
                        if not self.show_cells:
                            continue
                        line += " | NC"
                    else:
                        line += " |      "
                    if 'new_interior_cell' in flags:
                        line += " | IC"
                    else:
                        line += " |    "
                    if 'new_wrld' in flags:
                        line += " | NW"
                    else:
                        line += " |       "

                    line += " | " + os.path.basename(plugin) + '\n'
                    output_string += line
                output_string += '\n'

            if len(self.needs_compacting_flag_dict) > 0:
                output_string += self.tr("The following plugins can be flagged as esl after compacting:\n")
                output_string += self.tr("NC = New Cell Flag, IC = New Interior Cell Flag, NW = New Worldspace\n")
                for plugin, flags in self.needs_compacting_flag_dict.items():
                    line = " ‣ "
                    if 'new_cell' in flags:
                        if not self.show_cells:
                            continue
                        line += " | NC"
                    else:
                        line += " |      "
                    if 'new_interior_cell' in flags:
                        line += " | IC"
                    else:
                        line += " |    "
                    if 'new_wrld' in flags:
                        line += " | NW"
                    else:
                        line += " |       "
                    line += " | " + os.path.basename(plugin) + '\n'
                    output_string += line
                
                output_string += '\n'
                
            output_string += self.tr(
                "Notes/Warnings:\n"
                "You can launch ESLifier via the tool button.\n"
                "Compacting plugins may break things in on-going saves.\n"
                "Plugins with new cells may have the cell be break after marking as light if another mod changes it.\n"
                "Light plugins' new interior cells may not properly reload if the game is not restarted before loading.\n"
                "Plugins with new worldspaces will have them lose landscape data (no ground) when flagged ESL."
                "You can ignore a game plugin via this MO2 plugin's dropdown or via ESLifier's blacklist.\n"
            )
            return output_string
        
    def displayName(self):
        return self.tr("ESLifierWarn")
    
    def tooltip(self):
        return self.tr("")
    
    def icon(self):
        return QIcon()
    
    def display(self):
        return

    def getFiles(self):
        return

    def tr(self, str):
        return QCoreApplication.translate("ESLifierWarn", str)
    
    def hasGuidedFix(self, key):
        return False
    
    def startGuidedFix(self, key):
        pass
    
    def scan_for_eslable(self) -> bool:
        self.flag_dict.clear()
        self.hash_mismatches.clear()
        self.any_esl = False
        self.show_cells = self._organizer.pluginSetting("ESLifier", "Display Plugins With Cells")
        scan_esms = self._organizer.pluginSetting("ESLifier", "Scan ESMs")
        eslifier_folder = self._organizer.pluginSetting("ESLifier", "ESLifier Folder")
        blacklist_path = os.path.join(eslifier_folder, 'ESLifier_Data/blacklist.json')
        if os.path.exists(blacklist_path):
            with open(blacklist_path, 'r', encoding='utf-8') as f:
                ignore_list = json.load(f)
                ignore_list.append("ESLifier_Cell_Master.esm")
        else:
            ignore_list = ["ESLifier_Cell_Master.esm"]
        new_header = self._organizer.pluginSetting("ESLifier", "Use 1.71 Header Range")
        if scan_esms:
            filter = "*.es[pm]"
        else:
            filter = "*.esp"
        plugin_files_list = [plugin for plugin in self._organizer.findFiles("", filter) if os.path.basename(plugin) not in ignore_list]

        if len(plugin_files_list) > 1000:
            split = 5
        elif len(plugin_files_list) > 500:
            split = 2
        else:
            split = 1

        chunk_size = len(plugin_files_list) // split
        chunks = [plugin_files_list[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(plugin_files_list[(split) * chunk_size:])

        threads: list[threading.Thread] = []
        for chunk in chunks:
            thread = threading.Thread(target=self.plugin_scanner, args=(chunk, new_header, scan_esms))
            threads.append(thread)
            thread.start()
        
        original_plugins_path = os.path.join(eslifier_folder, 'ESLifier_Data/original_plugins.json')
        if os.path.exists(original_plugins_path):
            with open(original_plugins_path, 'r', encoding='utf-8') as f:
                original_plugins_dict = json.load(f)
                original_plugins_hash_map = [values for key, values in original_plugins_dict.items()]
                print(original_plugins_hash_map)

        for thread in threads:
            thread.join()

        threads.clear()

        if os.path.exists(original_plugins_path):
            for plugin, original_hash in original_plugins_hash_map:
                thread = threading.Thread(target=self.compare_previous_hash_to_current, args=(plugin, original_hash))
                threads.append(thread)
                thread.start()

        for thread in threads:
            thread.join()

        self.needs_flag_dict = {p: f for p, f in self.flag_dict.items() if 'need_compacting' not in f}
        self.needs_compacting_flag_dict = {p: f for p, f in self.flag_dict.items() if 'need_compacting' in f}
        return self.any_esl or len(self.hash_mismatches) > 0
    
    def compare_previous_hash_to_current(self, file, original_hash):
        if os.path.exists(file):
            with open(file, 'rb') as f:
                if hashlib.sha256(f.read()).hexdigest() != original_hash:
                    self.hash_mismatches.append(file)
        else:
            self.hash_mismatches.append(file)

    def plugin_scanner(self, plugins, new_header, scan_esms):
        flag_dict = {}
        for plugin in plugins:
            esl_allowed, need_compacting, new_cell, interior_cell, new_wrld = self.qualification_check(plugin, new_header, scan_esms)
            if esl_allowed == True:
                self.any_esl = True
                basename = os.path.basename(plugin)
                with self.lock:
                    if esl_allowed:
                        flag_dict[basename] = []
                        if need_compacting:
                            flag_dict[basename].append('need_compacting')
                        if new_cell:
                            flag_dict[basename].append('new_cell')
                            if interior_cell:
                                flag_dict[basename].append('new_interior_cell')
                        if new_wrld:
                            flag_dict[basename].append('new_wrld')
        with self.lock:
            for key, value in flag_dict.items():
                if key not in self.flag_dict:
                    self.flag_dict[key] = value

    def return_eslable(self):
        return self.flag_dict
    
    @staticmethod
    def qualification_check(plugin, new_header, scan_esms):
        return light_check().qualification_check(plugin, new_header, scan_esms)
