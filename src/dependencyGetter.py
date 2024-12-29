import os
import re

class dependecyGetter():    
    def __init__(self, path):
        plugins = self.getListOfPlugins(path)
        self.createDependecyDictionary(plugins)
        self.addDependantFiles(path)

    def getListOfPlugins(path):
        plugins = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if re.search(r'\.es[pml]', file):
                    plugins.append(os.path.join(root,file))
        return plugins
    
    def createDependecyDictionary(plugins):
        pluginNames = []
        for plugin in plugins:
            pluginNames.append(os.path.basename(plugin))
            pluginNames.append(os.path.basename(plugin) + '_path')

        dictionary = dict.fromkeys(pluginNames, [])
        for plugin in plugins:
            dictionary[os.path.basename(plugin) + '_path'] = plugin
            masters = dependecyGetter.getMasters(plugin)
            if len(masters) > 0:
                for master in masters:
                    dependencyList = dictionary[master]
                    if plugin not in dependencyList:
                        dependencyList.append(plugin)
                        dictionary[master] = dependencyList
        dependecyGetter.dependencyDictionary = dictionary
        return dictionary

    def getMasters(file):
        masterList = []
        with open(file, 'rb') as f:
            f.seek(4)
            size = int.from_bytes(f.read(4)[::-1])
            f.seek(0)
            tes4Header = f.read(size + 24)
            dataList = re.split(b'MAST..',tes4Header)
            dataList.remove(dataList[0])
            for master in dataList:
                masterList.append(re.sub(b'.DATA.*', b'', master, flags=re.DOTALL).decode('utf-8'))

        return masterList
