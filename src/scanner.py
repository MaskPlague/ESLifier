import os
import re
import threading

class scanner():
    def __init__(self, path):
        self.path = path
        self.path = 'fakemodsfolder/'
        self.getFileMasters()

    def getFileMasters(self):
        pattern = re.compile(r'(?:~|: *|\||")([^\n\r~|"]+\.es[pml])"?\s*\|?')
        pattern2 = re.compile(rb'GetFormFromFile[^\n\r]*?([A-Za-z0-9_]+\.esp)')
        matchers = ['.pex', '.psc', '.ini', '_conditions.txt', '.json', '_srd.', '.seq', 'facegeom', 'voice', 'facetint']
        self.fileDict = dict()
        threads =[]
        seqFiles = []
        for file in self.getAllFiles():
            if any(match in file.lower() for match in matchers):
                if not 'meta.ini' in file.lower() and ('.ini' in file.lower() or '.json' in file.lower() or '_conditions.txt' in file.lower() or '_srd.' in file.lower() or '.psc' in file.lower()):
                    thread = threading.Thread(target=self.fileReader,args=(pattern, file, 'r'))
                    threads.append(thread)
                    thread.start()
                if '.pex' in file.lower():
                    thread = threading.Thread(target=self.fileReader,args=(pattern2, file, 'rb'))
                    threads.append(thread)
                    thread.start()
                if '.seq' in file.lower():
                    plugin, _ = os.path.splitext(os.path.basename(file))
                    seqFiles.append([plugin, file])
                if ('facegeom' in file.lower() and '.nif' in file.lower()) or ('facetint' in file.lower() and '.dds' in file.lower()):
                    head, _ = os.path.split(file)
                    _, plugin = os.path.split(head)
                    with threading.Lock():
                        if plugin not in self.fileDict.keys():
                            self.fileDict.update({plugin: []})
                        fl = self.fileDict[plugin]
                        if file not in fl:
                            fl.append(file)
                            self.fileDict[plugin] = fl
                if 'sound' in file.lower() and 'voice' in file.lower():
                    head, _ = os.path.split(file)
                    head, _ = os.path.split(head)
                    _, plugin = os.path.split(head)
                    with threading.Lock():
                        if plugin not in self.fileDict.keys():
                            self.fileDict.update({plugin: []})
                        fl = self.fileDict[plugin]
                        if file not in fl:
                            fl.append(file)
                            self.fileDict[plugin] = fl
                
        self.fileNameWithoutExtProcessor(seqFiles)

        for thread in threads:
            thread.join()

        print(self.fileDict.keys())

    def fileNameWithoutExtProcessor(self, files):
        for file in files:
            esp = file[0] + '.esp'
            esl = file[0] + '.esl'
            esm = file[0] + '.esm'
            if esp in self.fileDict.keys():
                fl = self.fileDict[esp]
                if file not in fl:
                    fl.append(file[1])
                    self.fileDict[esp] = fl
            elif esl in self.fileDict.keys():
                fl = self.fileDict[esl]
                if file not in fl:
                    fl.append(file[1])
                    self.fileDict[esl] = fl
            elif esm in self.fileDict.keys():
                fl = self.fileDict[esm]
                if file not in fl:
                    fl.append(file[1])
                    self.fileDict[esm] = fl

    def fileReader(self, pattern, file, readerType):
        if readerType == 'r':
            with open(file, 'r', errors='ignore') as f:
                r = re.findall(pattern,f.read())
                if r != []:
                    for plugin in r:
                        with threading.Lock():
                            if plugin not in self.fileDict.keys():
                                self.fileDict.update({plugin: []})
                            fl = self.fileDict[plugin]
                            if file not in fl:
                                fl.append(file)
                                self.fileDict[plugin] = fl
        if readerType == 'rb':
            with open(file, 'rb') as f:
                data = f.read()
                r = re.findall(pattern,data)
                if r == [] and b'GetFormFromFile' in data: #catches when a file may have GetFormFromFile but with variables instead of string of the plugin name.
                    r = re.findall(b'([A-Za-z0-9_\'\\- ]+\\.es[pml])\x00', data)
                if r != []:
                    for plugin in r:
                        plugin = plugin.decode('utf-8')
                        with threading.Lock():
                            if plugin not in self.fileDict.keys():
                                self.fileDict.update({plugin: []})
                            fl = self.fileDict[plugin]
                            if file not in fl:
                                fl.append(file)
                                self.fileDict[plugin] = fl

    def getAllFiles(self):
        for root, dirs, files in os.walk(self.path):
            for file in files:
                yield os.path.join(root,file)

s = scanner('')
