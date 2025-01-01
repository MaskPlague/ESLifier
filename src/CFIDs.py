import os
import re
import binascii
import shutil
import fileinput
import zlib

class CFIDs():
    allInOneSetting = True
    
    #TODO: Consider adding an new warning to ESLifierWarn that detects if a master has no _ESLifierBackup/_FormIdMap.txt but its dependents do then they may be the wrong version.
    def main(file, dependents):
        modsFolder = CFIDs.compactFile(file)
        CFIDs.correctDependents(file, dependents, modsFolder)
        toPatch, toRename = CFIDs.getFilesToCorrect(file, CFIDs.getModFolders(file, dependents)) #function to get files that need to be edited in some way to function correctly.
        formIdMap = CFIDs.getFormIdMap(file)
        CFIDs.patchFiles(file, toPatch, formIdMap, modsFolder, True)
        CFIDs.renameFiles(file, toRename, formIdMap, modsFolder)
        #TODO: Change this file to format of scanner.py
        #TODO: update next object in TES4 header?
        #TODO: SkyPatcher, MCM Helper, possible others to check
        #TODO: add regex to certain replacements in patch files for safety
        #TODO: make 1.71 header change optional + setting for starting from 0 or 0x800 (I think it is 0x800)
        #TODO: Start front end probably in a separate file.\
            #TODO: probably change file path via ui
        #TODO: When compacting multiple masters, there is a chance that a file (an ini for example) may need to be patched twice for two different masters
            # and I need to make sure that the file is NOT overwritten by the original from the SSE folder as that would diregard prior changes.
            # this means that the output folder will need to be emptied and patched every time or an option...
        #TODO: Far in the future, consider actively scanning files for previous compacted files. Maybe a UI option to do a scan or directly select relevant folder/files.
        return

    #Create a copy of the mod plugin we're compacting
    def copyFileToNewMod(file, modsFolder):
        endPath = file[len(modsFolder) + 1:]
        if CFIDs.allInOneSetting:
            newFile = os.path.join(os.path.join(modsFolder,'ESLifier Compactor Output'), re.sub(r'(.*?)(/|\\)', '', endPath, 1))
        else:
            newModName = re.findall(r'(.*?)(/|\\)', endPath)[0][0] + ' - ESLifier Compacted'
            newFile = os.path.join(os.path.join(modsFolder, newModName), re.sub(r'(.*?)(/|\\)', '', endPath, 1))
        if not os.path.exists(os.path.dirname(newFile)):
            os.makedirs(os.path.dirname(newFile))
        shutil.copy(file, newFile)
        return newFile

    #get the list of folders for both the master and dependents
    def getModFolders(file, dependents):
        modFolders = []
        modFolders.append(os.path.dirname(file))
        for dependent in dependents:
            if os.path.dirname(dependent) not in modFolders:
                modFolders.append(os.path.dirname(dependent))
        return modFolders

    #Yield every file in every directory and subdirectory in every mod folder
    def getAllFiles(modFolders):
        for directory in modFolders:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    yield os.path.join(root,file)
    
    #Get files (not including plugins) that may/will need old Form IDs replaced with the new Form IDs
    def getFilesToCorrect(master, modFolders):
        #hexaPattern = re.compile(r'([0-9a-fA-F]+){6,}[.](?!p)')
        filesToPatch = []
        filesToRename = []
        matchers = ['.pex', '.psc', '.ini', '_conditions.txt', '.json', '_srd.', os.path.splitext(os.path.basename(master))[0].lower() + '.seq']
        for file in CFIDs.getAllFiles(modFolders):
            if any(match in file.lower() for match in matchers):
                if CFIDs.scanFile(master, file):
                    filesToPatch.append(file)
            elif os.path.basename(master).lower() in file.lower() and ('facegeom' in file.lower() or 'voice' in file.lower() or 'facetint' in file.lower()):
                filesToRename.append(file)
        return filesToPatch, filesToRename
    
    #Check any given file for certain specific features that would mean it does need patching
    def scanFile(master, file):
        formIdPattern0x = re.compile(r'0x([0-9a-fA-F]+){1,}')
        formIdPatternPipe = re.compile((r'\|([0-9a-fA-F]+){1,}'))
        if '.seq' in file:
            return True
        if not '.pex' in file.lower():
            with open(file, 'r', encoding='utf-8') as f:
                data = f.readlines()
                #if 'config.json' in file.lower():
                #    for line in data:
                #        if 'formid' in line.lower():
                #            return True
                #    return False
                if '.ini' in file.lower() or '_conditions.txt' in file.lower() or '.json' in file.lower(): #PO3's mods, DAR, OAR, MCM helper
                    for line in data:
                        s = re.search(formIdPattern0x, line.lower()) #for 0x form ids
                        s2 = re.search(formIdPatternPipe, line.lower()) #for some_mod.esp|form ids
                        if s and os.path.basename(master).lower() in line.lower(): #PO3's mods, 
                            return True
                        elif 'formid' in line.lower() or ('form_id' in line.lower() and os.path.basename(master).lower() in line.lower()): #OAR and 
                            return True
                        elif s2 and os.path.basename(master).lower() in line.lower(): #MCM helper
                            return True
                    return False
                if  '_srd.' in file.lower(): #Sound Record Distributor
                    for line in data:
                        s = re.search(formIdPatternPipe, line.lower())
                        if s and os.path.basename(master).lower() in line.lower():
                            return True
                    return False
                if '.psc' in file.lower(): #Papyrus Script Sources
                    for line in data:
                        if 'getformfromfile(0x' in line.lower():
                            return True
                f.close()
        elif '.pex' in file.lower(): #Papyrus Script compiled
            with open(file, 'rb') as f:
                data = f.read()
                if b'getformfromfile(0x' in data.lower():
                    data_list = re.split(b'getformfromfile',data.lower())
                    for dataChunk in data_list:
                        if os.path.basename(master.lower()) in str(re.findall(b'..(.*?)\x00', dataChunk)[0].lower()):
                            return True
                f.close()
        return False

    #Rename each file in the list of files from the old Form IDs to the new Form IDs
    def renameFiles(master, files, formIdMap, modsFolder):
        faceGeomMeshes = []
        for file in files:
            for formIds in formIdMap:
                if formIds[1].upper() in file.upper():
                    newFile = CFIDs.copyFileToNewMod(file, modsFolder)
                    os.replace(newFile, newFile.replace(formIds[1].upper(), formIds[3].upper()))
                    if 'facegeom' in newFile.lower() and os.path.basename(master).lower() in newFile.lower():
                        faceGeomMeshes.append(newFile.replace(formIds[1].upper(), formIds[3].upper()))
        if faceGeomMeshes != []:
            CFIDs.patchFiles(master, faceGeomMeshes, formIdMap, modsFolder, False)
        print('Files Renamed')
        return

    #Create the Form ID map which is a list of tuples that holds four Form Ids that are in \xMASTER\x00\x00\x00 order:
    #original Form ID w/o leading 0s, original Form ID w/ leading 0s, new Form ID w/o 0s, new Form ID w/ 0s, 
    #the orginal Form ID in \x00\x00\x00\xMASTER order, and the new Form ID in the same order.
    def getFormIdMap(file):
        formIDFileName = os.path.basename(file) + "_FormIdMap.txt"
        fidfData = ''
        formIdMap = []
        with open(formIDFileName, 'r') as fidf:
            fidfData = fidf.readlines()
        for fidHistory in fidfData:
            fidConversion = fidHistory.split('|')
            fromId = bytes.fromhex(fidConversion[0])[::-1].hex()[2:].removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').upper()
            fromId0 = bytes.fromhex(fidConversion[0])[::-1].hex()[2:].upper()
            toId = bytes.fromhex(fidConversion[1])[::-1].hex()[2:].removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').removeprefix('0').upper()
            toId0 = bytes.fromhex(fidConversion[1])[::-1].hex()[2:].upper()
            fromIdLE = bytes.fromhex(fidConversion[0])
            toIdLE = bytes.fromhex(fidConversion[1])
            formIdMap.append([fromId, fromId0, toId, toId0, fromIdLE, toIdLE])
        return formIdMap

    #Patches each file type in a different way as each has Form IDs present in a different format
    def patchFiles(master, files, formIdMap, modsFolder, flag):
        for file in files:
            if flag:
                newFile = CFIDs.copyFileToNewMod(file, modsFolder)
            else:
                newFile = file
            if '.ini' in newFile.lower() or '.json' in newFile.lower() or '_conditions.txt' in newFile.lower() or '_srd.' in newFile.lower() or '.psc' in newFile.lower():
                with fileinput.input(newFile, inplace=True, encoding="utf-8") as f:
                    if '.ini' in newFile.lower(): #All of PO3's various distributors patching and whatever else uses ini files with form ids.
                        #TODO: probably need to add more conditions to this and search for | or ~ before/after plugin name, consider SkyPatcher Format
                        for line in f:
                            if os.path.basename(master).lower() in line.lower():
                                for formIds in formIdMap:
                                    #this is faster than re.sub by a lot ;_;
                                    line = line.replace('0x' + formIds[0], '0x' + formIds[2]).replace('0x' + formIds[1], '0x' + formIds[3]).replace('0x' + formIds[0].lower(), '0x' + formIds[2].lower()).replace('0x' + formIds[1].lower(), '0x' + formIds[3].lower()).replace('0X' + formIds[0], '0X' + formIds[2]).replace('0X' + formIds[1], '0X' + formIds[3]).replace('0X' + formIds[0].lower(), '0X' + formIds[2].lower()).replace('0X' + formIds[1].lower(), '0X' + formIds[3].lower())
                            print(line.strip('\n'))
                    elif 'config.json' in newFile.lower(): #Open Animation Replacer Patching and MCM helper
                        #TODO: Redo this to look for plugin name on preceeding line (use for i in range()) for OAR
                        # Also add MCM helper structure, use regex so that if a mod somehow has form id "F" or "D" that
                        # gets compacted to something else, it won't break the json formatting i.e. "formid" -> "3ormi2" or "form:" -> "3orm"
                        for line in f:
                            if 'formid' in line.lower():
                                for formIds in formIdMap:
                                    line = line.replace(formIds[0], formIds[2]).replace(formIds[1], formIds[3]).replace(formIds[0].lower(), formIds[2].lower()).replace(formIds[1].lower(), formIds[3].lower())
                            print(line.strip('\n'))
                    elif '_conditions.txt' in newFile.lower(): #Dynamic Animation Replacer Patching
                        for line in f:
                            for formIds in formIdMap:
                                line = line.replace('0x00' + formIds[1], '0x00' + formIds[3]).replace('0x' + formIds[1], '0x' + formIds[3]).replace('0x00' + formIds[1].lower(), '0x00' + formIds[3].lower()).replace('0x' + formIds[1].lower(), '0x' + formIds[3].lower()).replace('0X00' + formIds[1], '0X00' + formIds[3]).replace('0X' + formIds[1], '0X' + formIds[3]).replace('0X00' + formIds[1].lower(), '0X00' + formIds[3].lower()).replace('0X' + formIds[1].lower(), '0X' + formIds[3].lower())
                            print(line.strip('\n'))
                    elif '_SRD.' in newFile.lower(): #Sound record distributor patching
                        #TODO: check if regex is necessary
                        for line in f:
                            if os.path.basename(master).lower() in line.lower():
                                for formIds in formIdMap:
                                    line = line.replace(formIds[0], formIds[2]).replace(formIds[1], formIds[3]).replace(formIds[0].lower(), formIds[2].lower()).replace(formIds[1].lower(), formIds[3].lower())
                            print(line.strip('\n'))
                    elif '.psc' in newFile.lower(): #Script source file patching
                        for line in f:
                            if os.path.basename(master).lower() in line.lower() and 'getformfromfile' in line.lower():
                                for formIds in formIdMap:
                                    line = line.replace('0x' + formIds[0], '0x' + formIds[2]).replace('0x' + formIds[1], '0x' + formIds[3]).replace('0x' + formIds[0].lower(), '0x' + formIds[2].lower()).replace('0x' + formIds[1].lower(), '0x' + formIds[3].lower()).replace('0X' + formIds[0], '0X' + formIds[2]).replace('0X' + formIds[1], '0X' + formIds[3]).replace('0X' + formIds[0].lower(), '0X' + formIds[2].lower()).replace('0X' + formIds[1].lower(), '0X' + formIds[3].lower())
                            print(line.strip('\n'))
                    elif '.json' in newFile.lower(): #Dynamic Key Activation Framework NG, and whatever else may be using .json?
                        #TODO: check for other json mods
                        for line in f:
                            if os.path.basename(master).lower() in line.lower():
                                for formIds in formIdMap:
                                    line = line.replace(formIds[0], formIds[2]).replace(formIds[1], formIds[3]).replace(formIds[0].lower(), formIds[2].lower()).replace(formIds[1].lower(), formIds[3].lower())
                            print(line.strip('\n'))
                    fileinput.close()
            
            elif 'facegeom' in newFile.lower():
                if '.nif' in newFile.lower(): #FaceGeom mesh patching
                    #TODO: check byte structure via hex editor to see what may go wrong here
                    with open(newFile, 'rb+') as f:
                        data = f.readlines()
                        for i in range(len(data)):
                            if bytes(os.path.basename(master).upper(), 'utf-8') in data[i].upper(): #check for plugin name, in file path, in line of nif file.
                                for formIds in formIdMap:
                                    data[i] = data[i].replace(formIds[1].encode(), formIds[3].encode()).replace(formIds[1].encode().lower(), formIds[3].encode().lower())
                        f.seek(0)
                        f.writelines(data)

            elif '.seq' in newFile or '.pex' in newFile.lower():
                with open(newFile,'rb+') as f:
                    data = f.read()
                    if '.seq' in newFile: #SEQ file patching
                        for formIds in formIdMap:
                            data = data.replace(formIds[4], formIds[5])
                        f.seek(0)
                        f.write(data)
                    elif '.pex' in newFile: #Compiled script patching
                        #TODO: replace with regex, check for b'\x03\x00\x ?? \xFORM ID
                        #      03 should be saying that this is an integer 00 is spacing since it is a form id without master byte and following bytes are big endian form id i.e 0x800 without 0x
                        for formIds in formIdMap:
                            data = data.replace(formIds[4][::-1][1:], formIds[5][::-1][1:])
                        f.seek(0)
                        f.write(data)
                    f.close()

        print("Files Patched")

    #Compacts master file and returns the new mod folder
    def compactFile(file):
        formIDFileName = os.path.basename(file) + "_FormIdMap.txt"
        modsFolder = os.path.dirname(os.path.dirname(file))
        newFile = CFIDs.copyFileToNewMod(file, modsFolder)

        #Set ESL flag, update to header 1.71 for new Form IDs, and get data from mod plugin
        data = b''
        with open(newFile, 'rb+') as f:
            f.seek(9)
            f.write(b'\x02')
            f.seek(0)
            f.seek(30)
            f.write(b'\x48\xE1\xDA\x3F')
            f.seek(0)
            data = f.read()
            f.close()

        print('initial data size:           ' + str(len(data)))
        data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................\x2c\x00.\x00)|(?=GRUP....................)', data, flags=re.DOTALL) if x]

        masterCount = data_list[0].count(b'MAST')
        formIdList = []

        if masterCount <= 15:
            mC = '0' + str(masterCount)
        else:
            mC = str(masterCount)

        newId = binascii.unhexlify(mC + '000000')
        newIdL = len(newId)
        counter = int.from_bytes(newId, 'big')
        sizesList = [[]] * len(data_list)

        #Decompress any compressed form ids in the plugin
        for i in range(len(data_list)):
            #flag for compressed forms is at byte 10 and is b'04'
            if len(data_list[i]) > 16 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= masterCount):
                size = int.from_bytes(data_list[i][4:8][::-1])
                #Decompress the compressed form
                decompressed = zlib.decompress(data_list[i][28:size + 24]) #24 is the size of the form header in every kind except GRUP
                sizesList[i] = [len(data_list[i]), len(decompressed), size]
                newForm = data_list[i].replace(data_list[i][28:size+24], decompressed)

                #get the form ids that were hiding in compressed data
                newForms = re.split(b'(?=....................\x2c\x00.\x00)', newForm, flags=re.DOTALL)
                if len(newForms) > 0:
                    for nF in newForms:
                        if nF != b'' and nF[15] == masterCount and nF[12:16] not in formIdList:
                            formIdList.append(nF[12:16])
                '''else:
                    #Untested, should work in theory
                    print('newForm length == 1')
                    if newForms[0] != b'' and newForms[0][15] == masterCount and newForms[0][12:16] not in formIdList:
                        formIdList.append(newForms[0][12:16])#'''

                data_list[i] = newForm
        
        #recreate data from data that has been altered when decompressed, but with an identifier of the previous split
        data = b'-||+||-'.join(data_list)

        #Get all other form ids in plugin
        for form in data_list:
            if len(form) > 16 and form[15] == masterCount and form[12:16] not in formIdList:
                formIdList.append(form[12:16])
        

        formIdList.sort()

        #Replace current Form IDs with the new Form IDs
        with open(formIDFileName, 'w') as fidf:
            print('decompacted size before:     ' + str(len(data)))
            for formId in formIdList:
                newId = counter.to_bytes(newIdL, 'little')
                #print("From: " + str(formId.hex()) + " to -> " + str(newId.hex()))
                counter += 1
                fidf.write(str(formId.hex()) + '|' + str(newId.hex()) + '\n')

                if formId[:2] != b'\xFF\xFF':
                    data = data.replace(formId, newId)
                else: #Prevent issues with replacing VMAD info with its \xFF\xFF structure
                    data = re.sub(re.escape(formId) + b'(?!.' + int.to_bytes(masterCount) + b')', newId, data, flags=re.DOTALL)

                '''#Extemely slow and missing \xFF\xFF that is above
                newIdReplacement1 = newId + bytes(r"\g<2>", 'utf-8')
                newIdReplacement2 = bytes(r"\g<1>", 'utf-8') + newId + bytes(r"\g<3>", 'utf-8')
                newIdReplacement3 = bytes(r"\g<1>", 'utf-8') + newId
                pattern1 = re.compile(b'(' + re.escape(formId) + b')(....\x2c[\x00-\x7F]{4})') #form id in non grup, form header replacement
                pattern2 = re.compile(b'(\x04\x00)(' + re.escape(formId) + b')([\x00-\x7F]{4}\x2c)') #form id in
                pattern3 = re.compile(b'(GRUP....)(' + re.escape(formId) + b')') #change form ids in grup header
                pattern4 = re.compile(b'(' + re.escape(formId) + b')([A-Z]{4})')
                pattern5 = re.compile(b'([A-Z]{4}..............)(' + re.escape(formId) + b')(...\x00)')
                #print(re.search(pattern3, data))
                data = re.sub(pattern1, newIdReplacement1, data)
                data = re.sub(pattern2, newIdReplacement2, data)
                data = re.sub(pattern3, newIdReplacement3, data)
                data = re.sub(pattern4, newIdReplacement1, data)
                data = re.sub(pattern5, newIdReplacement2, data)'''

            print('decompacted size after:      ' + str(len(data)))


        data_list = data.split(b'-||+||-')

        for i in range(len(data_list)):
            if len(data_list[i]) > 16 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= masterCount): #and data_list[i][15] == masterCount and data_list[i][10] == 0x4:
                #compressed = zlib.compress(data_list[i][28:sizesList[i][2] + 24])
                compressed = zlib.compress(data_list[i][28:len(data_list[i])-1], 9)
                formatted = [0] * (sizesList[i][0] - 28)
                formatted[:28] = data_list[i][:28]
                formatted[28:len(compressed)] = compressed
                data_list[i] = bytes(formatted)

        data = b''.join(data_list)
        print('final data size:             ' + str(len(data)))

        with open(newFile, 'wb') as f:
            f.write(data)
            f.close()
        print('file compacted')
        return modsFolder
        

    #replaced the old form ids with the new ones in all files that have the comapacted file as a master
    def correctDependents(file, dependents, modsFolder):
        formIDFileName = os.path.basename(file) + "_FormIdMap.txt"
        fidfData = ''
        with open(formIDFileName, 'r') as fidf:
            fidfData = fidf.readlines()

        for dependent in dependents:
            #TODO: consider if a dependent has compressed forms... please no
            newFile = CFIDs.copyFileToNewMod(dependent, modsFolder)
            dependentData = b''
            with open(newFile, 'rb+') as df:
                #Update header to 1.71 to fit new records
                df.seek(0)
                df.seek(30)
                df.write(b'\x48\xE1\xDA\x3F')
                df.seek(0)

                dependentData = df.read()
                print('initial data size:           ' + str(len(dependentData)))
                data_list = [x for x in re.split(b'(?=[A-Z]{3}[A-Z|_]................\x2c\x00.\x00)|(?=GRUP....................)', dependentData, flags=re.DOTALL) if x]
                
                masterCount = data_list[0].count(b'MAST')
                sizesList = [[]] * len(data_list)
                for i in range(len(data_list)):
                    #flag for compressed forms is at byte 10 and is b'04'
                    if len(data_list[i]) > 16 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= masterCount):
                        size = int.from_bytes(data_list[i][4:8][::-1])
                        #Decompress the compressed form
                        decompressed = zlib.decompress(data_list[i][28:size + 24]) #24 is the size of the form header in every kind except GRUP
                        sizesList[i] = [len(data_list[i]), len(decompressed), size]
                        newForm = data_list[i].replace(data_list[i][28:size+24], decompressed)
                        data_list[i] = newForm
                
                dependentData = b'-||+||-'.join(data_list)

                mL = CFIDs.getMasterIndex(file, dependentData)
                if mL <= 15:
                    mC = '0' + str(mL)
                else:
                    mC = str(mL)
                for fidHistory in fidfData:
                    fidConversion = fidHistory.split('|')
                    fromId = bytes.fromhex(fidConversion[0])[:3] + bytes.fromhex(mC)
                    toId = bytes.fromhex(fidConversion[1])[:3] + bytes.fromhex(mC)
                    if fromId[:2] != b'\xFF\xFF':
                        dependentData = dependentData.replace(fromId, toId)
                    else: #Prevent issues with replacing VMAD info with its \xFF\xFF structure
                        dependentData = re.sub(re.escape(fromId) + b'(?!.' + int.to_bytes(mL) + b')', toId, dependentData, flags=re.DOTALL)

                data_list = dependentData.split(b'-||+||-')

                for i in range(len(data_list)):
                    if len(data_list[i]) > 16 and data_list[i][10] == 0x4 and (0 <= data_list[i][15] <= mL): #and data_list[i][15] == masterCount and data_list[i][10] == 0x4:
                        #compressed = zlib.compress(data_list[i][28:sizesList[i][2] + 24])
                        compressed = zlib.compress(data_list[i][28:len(data_list[i])-1], 9)
                        formatted = [0] * (sizesList[i][0] - 28)
                        formatted[:28] = data_list[i][:28]
                        formatted[28:len(compressed)] = compressed
                        data_list[i] = bytes(formatted)

                dependentData = b''.join(data_list)
                print('final data size:             ' + str(len(dependentData)))
                df.seek(0)
                df.write(dependentData)
                df.close()
        
        print('Dependents patched')
        return

    #gets what master index the file is in inside of the dependent's data
    def getMasterIndex(file, data):
        masterPattern = re.compile(b'MAST..(.*?).DATA')
        matches = re.findall(masterPattern, data)
        masterIndex = 0
        for match in matches:
            if os.path.basename(file) in str(match):
                return masterIndex
            else:
                masterIndex += 1

#file = 'fakemodsfolder/Kangmina SE/Kangmina.esp'
#dependents = []
#CFIDs.main(file, dependents)
file = 'fakemodsfolder/EAS/TaberuAnimation.esp'
dependents = ['fakemodsfolder/EAS Patches/Taberu Animation - BSBruma Patch.esp','fakemodsfolder/EAS Patches/Taberu Animation - CACO Patch.esp', 'fakemodsfolder/EAS Patches/Taberu Animation - Dawn of Skyrim Patch.esp', 'fakemodsfolder/EAS Patches/Taberu Animation - LotD Patch.esp', 'fakemodsfolder/EAS Patches/Taberu Animation - USSEP Patch.esp', 'fakemodsfolder/EAS Patches/Taberu Animation - Wyrmstooth Patch.esp']
CFIDs.main(file, dependents)
#file = 'fakemodsfolder/AOS/Audio Overhaul Skyrim.esp'
#dependents = []
#CFIDs.main(file, dependents)