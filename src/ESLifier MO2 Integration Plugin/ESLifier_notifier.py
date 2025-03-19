import mobase
import os
import json
import threading

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
        self.needs_flag_list = []
        self.needs_compacting_list = []
        self.needs_flag_new_cell_list = []
        self.needs_compacting_new_cell_list = []
        self.needs_flag_interior_cell_list = []
        self.needs_compacting_interior_cell_list = []
        self._problems = [0]
        self._finished = False
        self.any_esl = False
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
            if len(self.needs_flag_list) > 0:
                output_string += "The following plugins can be flagged as esl:\n"
                output_string += "NC = New Cell Flag, IC = New Interior Cell Flag\n"
                for plugin in self.needs_flag_list:
                    line = " ‣ "
                    if plugin in self.needs_flag_new_cell_list:
                        line += " | NC"
                    else:
                        line += " |      "
                    if plugin in self.needs_flag_interior_cell_list:
                        line += " | IC"
                    else:
                        line += " |    "
                    line += " | " + os.path.basename(plugin) + '\n'
                    output_string += line
                output_string += '\n'

            if len(self.needs_compacting_list) > 0:
                output_string += "The following plugins can be flagged as esl after compacting:\n"
                output_string += "NC = New Cell Flag, IC = New Interior Cell Flag\n"
                for plugin in self.needs_compacting_list:
                    line = " ‣ "
                    if plugin in self.needs_compacting_new_cell_list:
                        line += " | NC"
                    else:
                        line += " |      "
                    if plugin in self.needs_compacting_interior_cell_list:
                        line += " | IC"
                    else:
                        line += " |    "
                    line += " | " + os.path.basename(plugin) + '\n'
                    output_string += line
                
                output_string += '\n'
                
            output_string += self.tr(
                "You can launch ESLifier via the tool button.\n"
                "Plugins with new cells may have the cell be inaccessable after marking as light.\n"
                "Light plugins' new interior cells may not properly reload if the game is not restarted before load.\n"
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
    
    def scan_for_eslable(self):
        self.needs_flag_list.clear()
        self.needs_compacting_list.clear()
        self.needs_flag_new_cell_list.clear()
        self.needs_compacting_new_cell_list.clear()
        self.needs_flag_interior_cell_list.clear()
        self.any_esl = False
        show_cells = self._organizer.pluginSetting("ESLifier", "Display Plugins With Cells")
        scan_esms = self._organizer.pluginSetting("ESLifier", "Scans ESMs")
        eslifier_folder = self._organizer.pluginSetting("ESLifier", "ESLifier Folder")
        blacklist_path = os.path.join(eslifier_folder, 'ESLifier_Data/blacklist.json')
        if os.path.exists(blacklist_path):
            with open(blacklist_path, 'r', encoding='utf-8') as f:
                ignore_list = json.load(f)
        else:
            ignore_list = []
        new_header = self._organizer.pluginSetting("ESLifier", "Use 1.71 Header Range")
        
        plugin_files_list = [plugin for plugin in self._organizer.findFiles("", "*.es[pm]") if os.path.basename(plugin) not in ignore_list]

        if len(plugin_files_list) > 1000:
            split = 5
        elif len(plugin_files_list) > 500:
            split = 2
        else:
            split = 1

        chunk_size = len(plugin_files_list) // split
        chunks = [plugin_files_list[i * chunk_size:(i + 1) * chunk_size] for i in range(split)]
        chunks.append(plugin_files_list[(split) * chunk_size:])

        threads = []
        for chunk in chunks:
            thread = threading.Thread(target=self.plugin_scanner, args=(chunk, new_header, show_cells, scan_esms))
            threads.append(thread)
            thread.start()
            
        for thread in threads:
            thread.join()

        return self.any_esl
    
    def plugin_scanner(self, plugins, new_header, show_cells, scan_esms):
        for plugin in plugins:
            esl_allowed, needs_compacting, new_cell, new_interior_cell = self.qualification_check(plugin, new_header, show_cells, scan_esms)
            if esl_allowed == True:
                self.any_esl = True
                basename = os.path.basename(plugin)
                with self.lock:
                    if esl_allowed:
                        if not needs_compacting:
                            self.needs_flag_list.append(basename)
                            if new_cell:
                                self.needs_flag_new_cell_list.append(basename)
                                if new_interior_cell:
                                    self.needs_flag_interior_cell_list.append(basename)
                        else:
                            self.needs_compacting_list.append(basename)
                            if new_cell:
                                self.needs_compacting_new_cell_list.append(basename)
                                if new_interior_cell:
                                    self.needs_compacting_interior_cell_list.append(basename)
    def return_eslable(self):
        return (self.needs_flag_list, self.needs_flag_new_cell_list, self.needs_flag_interior_cell_list,
                self.needs_compacting_list, self.needs_compacting_new_cell_list, self.needs_compacting_interior_cell_list)
    
    @staticmethod
    def qualification_check(plugin, new_header, show_cells, scan_esms):
        return light_check().qualification_check(plugin, new_header, show_cells, scan_esms)
