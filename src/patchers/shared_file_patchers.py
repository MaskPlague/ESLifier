import json
import json5
import os

import configparser
import io
from log_stream import write_to_file, write_ineligible

class shared_patchers():
    def pex_patcher_for_debug(basename: str, new_file: str, form_id_map: dict, endian = 'big'):
        DEBUG = True
        def var_data_reader(data, offset):
            variableType = data[offset]
            offset += 1
            if DEBUG:
                print(f"{variableType = }")
            variableData = None
            if variableType == 0: # Null
                return offset, 0, None
            elif variableType == 1: # identifier (string)
                variableData = strings[int.from_bytes(data[offset:offset+2], endian)]
                offset += 2
                return offset, 1, variableData
            elif variableType == 2: # string
                variableData = strings[int.from_bytes(data[offset:offset+2], endian)]
                offset += 2
                return offset, 2, variableData
            elif variableType == 3: # integer
                variableData = int.from_bytes(data[offset:offset+4], endian)
                offset += 4
                return offset, 3, variableData
            elif variableType == 4: # float
                variableData = data[offset:offset+4]
                offset += 4
                return offset, 4, variableData
            elif variableType == 5: # bool
                variableData == bool(data[offset])
                offset += 1
                return offset, 1, variableData
            else:
                print(f"Unknown variable type: {variableType}?")
            return offset, variableType, variableData
        
        def function_processor(data, offset):
            if DEBUG:
                returnType = strings[int.from_bytes(data[offset:offset+2], endian)]
                print(f"{returnType = }")
            offset += 2
            offset += 2
            offset += 4
            offset += 1
            numParams = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            if DEBUG:
                print(f"{numParams = }")
            for _ in range(numParams):
                if DEBUG:
                    paramName = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{paramName = }")
                offset += 2
                if DEBUG:
                    paramType = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{paramType = }")
                offset += 2
            numLocals = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            if DEBUG:
                print(f"{numLocals = }")
            for _ in range(numLocals):
                if DEBUG:
                    localName = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{localName = }")
                offset += 2
                if DEBUG:
                    localType = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{localType = }")
                offset += 2
            numInstructions = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            arrays = {}
            arrayTempId = None
            arraySize = None
            tempVars = {}
            for _ in range(numInstructions):
                opCode = data[offset:offset+1]
                if DEBUG:
                    print(f"{opCode.hex() = }")
                offset += 1
                #TODO: update additional FO4 op codes
                if opCode in (b'\x01', b'\x02', b'\x03', b'\x04', b'\x05', b'\x06', b'\x07', b'\x08', b'\x09', b'\x0F', b'\x10', b'\x11', b'\x12', b'\x13', b'\x1B', b'\x1C', b'\x1D'):
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode == b'\x1E': # Create Array
                    offset, vType, vData = var_data_reader(data, offset)
                    arrayTempId = bytes(vData)
                    offset, vType, arraySize = var_data_reader(data, offset)
                    if DEBUG:
                        print(f"\nCreating array: {arrayTempId}")
                        print(f"Array length: {arraySize}")
                elif opCode == b'\x0D': # Store variable
                    offset, vType, assignedTo = var_data_reader(data, offset)
                    prevOffset = offset
                    offset, vType, vData = var_data_reader(data, offset)
                    if DEBUG:
                        print(f"Assigning value to: {assignedTo}")
                        print(f"Value Type: {vType}")
                        print(f"Value being assigned: {vData}")
                    if bytes(vData) == arrayTempId:
                        arrays[bytes(assignedTo)] = { "integers": [(None, None) for _ in range(arraySize)],
                                                        "length": arraySize, 
                                                        "patch": False}
                    else:
                        if vType == 3:
                            tempVars[bytes(assignedTo)] = (prevOffset, vType, vData)
                        elif vType == 1:
                            tmp = tempVars.get(bytes(vData))
                            if tmp:
                                tempVars[bytes(assignedTo)] = tmp
                elif opCode == b'\x21': # Array set element
                    offset, vType, arrayId = var_data_reader(data, offset)
                    offset, vType, arrayIndex = var_data_reader(data, offset)
                    offset, vType, assignedValue = var_data_reader(data, offset)
                    if DEBUG:
                        print(f"Assigning to Array: {arrayId}")
                        print(f"Assigning to Index: {arrayIndex}")
                        print(f"Assigning Value: {assignedValue}")
                    tmp = tempVars.get(bytes(assignedValue))
                    if tmp and tmp[1] == 3: #if tmp value is integer
                        #set index for array to (offset, value)
                        arrays[bytes(arrayId)]["integers"][arrayIndex] = (tmp[0], tmp[2])
                elif opCode == b'\x20': # get element from array to var
                    offset, vType, assignToVar = var_data_reader(data, offset)
                    offset, vType, arrayId = var_data_reader(data, offset)
                    offset, vType, arrayIndex = var_data_reader(data, offset)
                    if DEBUG:
                        print(f"Putting element in var: {assignToVar}")
                        print(f"Getting element from array: {arrayId}")
                        print(f"Getting element from index: {arrayIndex}")
                    tempVars[bytes(assignToVar)] = (0, -1, bytes(arrayId))
                elif opCode == b'\x1F': # get array size
                    offset, vType, tmpVar = var_data_reader(data, offset)
                    offset, vType, arrayId = var_data_reader(data, offset)
                    tempVars[bytes(tmpVar)] = (0, 3, arrays.get(bytes(arrayId), {"length": 0})["length"], arrayId)
                elif opCode in (b'\x0A', b'\x0B', b'\x0C', b'\x0E', b'\x15', b'\x16'):
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode in (b'\x14', b'\x1A'):
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode in (b'\x17',b'\x19'):
                    offset, vType, methodName = var_data_reader(data, offset)
                    
                    offset, vType, s1 = var_data_reader(data, offset)
                    
                    offset, vType, vData = var_data_reader(data, offset)
                    
                    offset, vType, numArgs = var_data_reader(data, offset)
                    if DEBUG:
                        print(f"\nCalling method: {methodName}")
                        print(f"Method S1: {s1}")
                        print(f"Method S2: {vData}")
                        print(f"{numArgs = }")
                    args = []
                    for i in range(numArgs):
                        prevOffset = offset
                        offset, vType, vData = var_data_reader(data, offset)
                        args.append((prevOffset, vType, vData))
                        if DEBUG:
                            print(f"Method arg{i}: {vType}, {vData}")
                    if bytes(s1) == b'getformfromfile':
                        arg1 = args[0]
                        arg2 = args[1]
                        #if arg1 is int and arg2 is string
                        if arg1[1] == 3 and arg2[1] == 2:
                            if bytes(arg2[2]) == basename_bytes:
                                if DEBUG:
                                    print(f"should patch integer {arg1[2]} at {arg1[0]}" )
                                to_id_data = form_id_map.get(arg1[2])
                                if to_id_data:
                                    aOffset = arg1[0]
                                    if endian == 'big':
                                        data[aOffset+2:aOffset+5] = to_id_data["bytes"][::-1][1:]
                                    else: #TODO: perhaps remove? we'll see what I end up doing with the fid map for FO4
                                        data[aOffset+1:aOffset+4] = to_id_data["bytes"][:-1]
                        elif arg1[1] == 1 and arg2[1] == 2:
                            if bytes(arg2[2]) == basename_bytes:
                                if DEBUG:
                                    print(f"should patch integers in array: {tempVars[bytes(arg1[2])][2]}")
                                arrays[tempVars[bytes(arg1[2])][2]]["patch"] = True

                elif opCode == b'\x18':
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    
                    offset, vType, numArgs = var_data_reader(data, offset)
                    for _ in range(numArgs):
                        offset, vType, vData = var_data_reader(data, offset)

                elif opCode in (b'\x22', b'\x23'):
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode == b'\x00':
                    ...
                else:
                    print("Missing opcode?")
            if DEBUG:
                print(f"{arrays = }")
            for array in arrays.values():
                for aOffset, integer in array["integers"]:
                    #int.from_bytes(data[aOffset+1:aOffset+5], endian)
                    to_id_data = form_id_map.get(integer)
                    if to_id_data:
                        if endian == 'big':
                            data[aOffset+2:aOffset+5] = to_id_data["bytes"][::-1][1:]
                        else: #TODO: perhaps remove? we'll see what I end up doing with the fid map for FO4
                            data[aOffset+1:aOffset+4] = to_id_data["bytes"][:-1]
            return offset
        
        def state_processor(data, offset):
            if DEBUG:
                stateName = strings[int.from_bytes(data[offset:offset+2], endian)]
                print(f"{stateName = }")
            offset += 2
            numFunctions = int.from_bytes(data[offset:offset+2], endian)
            if DEBUG:
                print(f"{numFunctions = }")
            offset += 2
            for _ in range(numFunctions):
                if DEBUG:
                    functionName = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{functionName = }")
                offset += 2 
                offset = function_processor(data, offset)
            return offset
        
        basename_bytes = basename.encode(encoding='utf-8')
        with open(new_file,'rb+') as f:
            data = f.read()
            data = bytearray(data)
            src_name_length = int.from_bytes(data[16:18], endian)
            offset = 18 + src_name_length
            username_length = int.from_bytes(data[offset:offset+2], endian)
            offset += 2 + username_length
            machine_name_length = int.from_bytes(data[offset:offset+2], endian)
            offset += 2 + machine_name_length
            string_count = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            strings = []
            for _ in range(string_count):
                string_length = int.from_bytes(data[offset:offset+2], endian)
                strings.append(data[offset+2:offset+2+string_length].lower())
                offset += 2 + string_length
            if DEBUG:
                print(f"{strings = }")
            debug_info_exists = data[offset]
            offset += 1
            if DEBUG:
                print(f"{debug_info_exists = }")
            if debug_info_exists == 1:
                offset += 8
                func_count = int.from_bytes(data[offset:offset+2], endian)
                if DEBUG:
                    print(f"{func_count = }")
                offset += 2
                for _ in range(func_count):
                    if DEBUG:
                        objectName = strings[int.from_bytes(data[offset:offset+2])]
                        print(f"debugInfo {objectName = }")
                    #offset += 2
                    #stateNameIndex = int.from_bytes(data[offset:offset+2])
                    #stateName = strings[stateNameIndex]
                    #print(f"{stateName = }")
                    #offset += 2
                    #functionNameIndex =	int.from_bytes(data[offset:offset+2])
                    #functionName = strings[functionNameIndex]
                    #print(f"{functionName = }")
                    #offset += 2
                    #functionType = data[offset]
                    #print(f"{functionType = }")
                    #offset += 1
                    offset += 7
                    instructionCount = int.from_bytes(data[offset:offset+2], endian)
                    offset += 2
                    offset += 2*instructionCount
                if endian == 'little': # not skyrim (i.e. FO4)
                    groupCount = int.from_bytes(data[offset:offset+2], endian)
                    if DEBUG:
                        print(f"{groupCount = }")
                    offset += 2
                    for _ in range(groupCount):
                        offset += 2 + 2 + 2 + 4
                        nameCount = int.from_bytes(data[offset:offset+2], endian)
                        offset += 2
                        if DEBUG:
                            print(f"{nameCount = }")
                        offset += 2 * nameCount
                    orderCount = int.from_bytes(data[offset:offset+2], endian)
                    if DEBUG:
                        print(f"{orderCount = }")
                    offset += 2
                    for _ in range(orderCount):
                        offset += 2 + 2
                        nameCount = int.from_bytes(data[offset:offset+2], endian)
                        offset += 2
                        if DEBUG:
                            print(f"{nameCount = }")
                        offset += 2 * nameCount
            if DEBUG:
                print(f"offset after passing debug info: {offset}")
            userFlagCount = int.from_bytes(data[offset:offset+2], endian)
            if DEBUG:
                print(f"{userFlagCount = }")
            offset += 2
            offset += 3 * userFlagCount
            objectCount = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            if DEBUG:
                print(f"{objectCount = }")
            for _ in range(objectCount):
                #Object
                if DEBUG:
                    objectName = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{objectName = }")
                offset += 2
                #objectSize = int.from_bytes(data[offset:offset+4]) - 4
                offset += 4
                #Object Data
                if DEBUG:
                    parentClassName = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{parentClassName = }")
                offset += 2
                if DEBUG:
                    docString = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{docString = }")
                offset += 2
                if endian == 'little':
                    offset += 1
                if DEBUG:
                    userFlags = data[offset:offset+4]
                    print(f"{userFlags = }")
                offset += 4
                if DEBUG:
                    autoStateName = strings[int.from_bytes(data[offset:offset+2], endian)]
                    print(f"{autoStateName = }")
                offset += 2
                if endian == 'little':
                    structCount = int.from_bytes(data[offset:offset+2], endian)
                    if DEBUG:
                        print(f"{structCount = }")
                    offset += 2
                    for _ in range(structCount):
                        if DEBUG:
                            structName = strings[int.from_bytes(data[offset:offset+2], endian)]
                            print(f"{structName = }")
                        offset += 2
                        memberCount = int.from_bytes(data[offset:offset+2], endian)
                        offset += 2
                        for _ in range(memberCount):
                            if DEBUG:
                                memberName = strings[int.from_bytes(data[offset:offset+2], endian)]
                                print(f"{memberName = }")
                            offset += 2
                            offset += 2 + 4
                            offset, vType, vData = var_data_reader(data, offset)
                            offset += 1 + 2

                numVariables = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                if DEBUG:
                    print(f"{numVariables = }")
                for _ in range(numVariables):
                    #Variable
                    offset += 8
                    offset, vType, vData = var_data_reader(data, offset)
                numProperties = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                if DEBUG:
                    print(f"{numProperties = }")
                for _ in range(numProperties):
                    if DEBUG:
                        propertyName = strings[int.from_bytes(data[offset:offset+2], endian)]
                        print(f"{propertyName = }")
                    offset += 10
                    flags = data[offset]
                    offset += 1
                    if flags & 4 != 0:
                        offset += 2
                    if flags & 5 == 1:
                        if DEBUG:
                            print("readHandler")
                        offset = function_processor(data, offset)
                    if flags & 6 == 2:
                        if DEBUG:
                            print("writeHandler")
                        offset = function_processor(data, offset)

                numStates = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                if DEBUG:
                    print(f"{numStates = }")
                for _ in range(numStates):
                    offset = state_processor(data, offset)
            if not DEBUG:
                data = bytes(data)
                f.seek(0)
                f.truncate(0)
                f.write(data)  
            print(f"done processing {new_file}")
            return   

    #endian = 'big' for skyrim and 'little' for all others (i.e. FO4)
    def pex_patcher(basename: str, new_file: str, form_id_map: dict, endian = 'big'):
        def var_data_reader(data, offset):
            variableType = data[offset]
            offset += 1
            variableData = None
            if variableType == 0: # Null
                return offset, 0, None
            elif variableType == 1: # identifier (string)
                variableData = strings[int.from_bytes(data[offset:offset+2], endian)]
                offset += 2
                return offset, 1, variableData
            elif variableType == 2: # string
                variableData = strings[int.from_bytes(data[offset:offset+2], endian)]
                offset += 2
                return offset, 2, variableData
            elif variableType == 3: # integer
                variableData = int.from_bytes(data[offset:offset+4], endian)
                offset += 4
                return offset, 3, variableData
            elif variableType == 4: # float
                variableData = data[offset:offset+4]
                offset += 4
                return offset, 4, variableData
            elif variableType == 5: # bool
                variableData == bool(data[offset])
                offset += 1
                return offset, 1, variableData
            else:
                print(f"Unknown variable type: {variableType}?")
            return offset, variableType, variableData
        
        def function_processor(data, offset):
            offset += 9
            offset += 2 + (4 * int.from_bytes(data[offset:offset+2], endian)) #Num Params
            offset += 2 + (4 *int.from_bytes(data[offset:offset+2], endian)) #Num Locals
            numInstructions = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            arrays = {}
            arrayTempId = None
            arraySize = None
            tempVars = {}
            for _ in range(numInstructions):
                opCode = data[offset:offset+1]
                offset += 1
                #TODO: update additional FO4 op codes
                if opCode in (b'\x01', b'\x02', b'\x03', b'\x04', b'\x05', b'\x06', b'\x07', b'\x08', b'\x09', b'\x0F', b'\x10', b'\x11', b'\x12', b'\x13', b'\x1B', b'\x1C', b'\x1D'):
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode == b'\x1E': # Create Array
                    offset, vType, vData = var_data_reader(data, offset)
                    arrayTempId = bytes(vData)
                    offset, vType, arraySize = var_data_reader(data, offset)
                elif opCode == b'\x0D': # Store variable
                    offset, vType, assignedTo = var_data_reader(data, offset)
                    prevOffset = offset
                    offset, vType, vData = var_data_reader(data, offset)
                    if bytes(vData) == arrayTempId:
                        arrays[bytes(assignedTo)] = { "integers": [(None, None) for _ in range(arraySize)],
                                                        "length": arraySize, 
                                                        "patch": False}
                    else:
                        if vType == 3:
                            tempVars[bytes(assignedTo)] = (prevOffset, vType, vData)
                        elif vType == 1:
                            tmp = tempVars.get(bytes(vData))
                            if tmp:
                                tempVars[bytes(assignedTo)] = tmp
                elif opCode == b'\x21': # Array set element
                    offset, vType, arrayId = var_data_reader(data, offset)
                    offset, vType, arrayIndex = var_data_reader(data, offset)
                    offset, vType, assignedValue = var_data_reader(data, offset)
                    tmp = tempVars.get(bytes(assignedValue))
                    if tmp and tmp[1] == 3: #if tmp value is integer
                        #set index for array to (offset, value)
                        arrays[bytes(arrayId)]["integers"][arrayIndex] = (tmp[0], tmp[2])
                elif opCode == b'\x20': # get element from array to var
                    offset, vType, assignToVar = var_data_reader(data, offset)
                    offset, vType, arrayId = var_data_reader(data, offset)
                    offset, vType, arrayIndex = var_data_reader(data, offset)
                    tempVars[bytes(assignToVar)] = (0, -1, bytes(arrayId))
                elif opCode == b'\x1F': # get array size
                    offset, vType, tmpVar = var_data_reader(data, offset)
                    offset, vType, arrayId = var_data_reader(data, offset)
                    tempVars[bytes(tmpVar)] = (0, 3, arrays.get(bytes(arrayId), {"length": 0})["length"], arrayId)
                elif opCode in (b'\x0A', b'\x0B', b'\x0C', b'\x0E', b'\x15', b'\x16'):
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode in (b'\x14', b'\x1A'):
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode in (b'\x17',b'\x19'):
                    offset, vType, methodName = var_data_reader(data, offset)
                    offset, vType, s1 = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, numArgs = var_data_reader(data, offset)
                    args = []
                    for _ in range(numArgs):
                        prevOffset = offset
                        offset, vType, vData = var_data_reader(data, offset)
                        args.append((prevOffset, vType, vData))
                    if bytes(s1) == b'getformfromfile':
                        arg1 = args[0]
                        arg2 = args[1]
                        #if arg1 is int and arg2 is string and arg2 is basename
                        if arg1[1] == 3 and arg2[1] == 2 and bytes(arg2[2]) == basename_bytes:
                            to_id_data = form_id_map.get(arg1[2])
                            if to_id_data:
                                aOffset = arg1[0]
                                if endian == 'big':
                                    data[aOffset+2:aOffset+5] = to_id_data["bytes"][::-1][1:]
                                else: #TODO: perhaps remove? we'll see what I end up doing with the fid map for FO4
                                    data[aOffset+1:aOffset+4] = to_id_data["bytes"][:-1]
                        elif arg1[1] == 1 and arg2[1] == 2:
                            if bytes(arg2[2]) == basename_bytes:
                                arrays[tempVars[bytes(arg1[2])][2]]["patch"] = True

                elif opCode == b'\x18':
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    
                    offset, vType, numArgs = var_data_reader(data, offset)
                    for _ in range(numArgs):
                        offset, vType, vData = var_data_reader(data, offset)

                elif opCode in (b'\x22', b'\x23'):
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                    offset, vType, vData = var_data_reader(data, offset)
                elif opCode == b'\x00':
                    ... #do nothing
                else:
                    print(f"Missing opcode? {opCode.hex()}")

            for array in arrays.values():
                for aOffset, integer in array["integers"]:
                    #int.from_bytes(data[aOffset+1:aOffset+5], endian)
                    to_id_data = form_id_map.get(integer)
                    if to_id_data:
                        if endian == 'big':
                            data[aOffset+2:aOffset+5] = to_id_data["bytes"][::-1][1:]
                        else: #TODO: perhaps remove? we'll see what I end up doing with the fid map for FO4
                            data[aOffset+1:aOffset+4] = to_id_data["bytes"][:-1]
            return offset
        
        def state_processor(data, offset):
            offset += 2
            numFunctions = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            for _ in range(numFunctions):
                offset += 2 
                offset = function_processor(data, offset)
            return offset
        
        basename_bytes = basename.encode(encoding='utf-8')
        with open(new_file,'rb+') as f:
            data = f.read()
            data = bytearray(data)
            offset = 18 + int.from_bytes(data[16:18], endian)
            offset += 2 + int.from_bytes(data[offset:offset+2], endian)
            offset += 2 + int.from_bytes(data[offset:offset+2], endian)
            string_count = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            strings = []
            for _ in range(string_count):
                string_length = int.from_bytes(data[offset:offset+2], endian)
                strings.append(data[offset+2:offset+2+string_length].lower())
                offset += 2 + string_length
            debug_info_exists = data[offset]
            offset += 1
            if debug_info_exists == 1:
                offset += 8
                func_count = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                for _ in range(func_count):
                    offset += 7
                    offset += 2 + (2*int.from_bytes(data[offset:offset+2], endian))
                if endian == 'little': # not skyrim (i.e. FO4)
                    groupCount = int.from_bytes(data[offset:offset+2], endian)
                    offset += 2
                    for _ in range(groupCount):
                        offset += 10
                        offset += 2 + (2 * int.from_bytes(data[offset:offset+2], endian))
                    orderCount = int.from_bytes(data[offset:offset+2], endian)
                    offset += 2
                    for _ in range(orderCount):
                        offset += 4
                        offset += 2 + (2 * int.from_bytes(data[offset:offset+2], endian))
            offset += 2 + (3 * int.from_bytes(data[offset:offset+2], endian))
            objectCount = int.from_bytes(data[offset:offset+2], endian)
            offset += 2
            #Objects
            for _ in range(objectCount):
                #Object + Object Data
                offset += 16
                if endian == 'little':
                    offset += 1
                if endian == 'little':
                    structCount = int.from_bytes(data[offset:offset+2], endian)
                    offset += 2
                    for _ in range(structCount):
                        offset += 2
                        memberCount = int.from_bytes(data[offset:offset+2], endian)
                        offset += 2
                        for _ in range(memberCount):
                            offset += 8
                            offset, vType, vData = var_data_reader(data, offset)
                            offset += 3

                numVariables = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                for _ in range(numVariables):
                    #Variable
                    offset += 8
                    offset, vType, vData = var_data_reader(data, offset)
                numProperties = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                for _ in range(numProperties):
                    offset += 10
                    flags = data[offset]
                    offset += 1
                    if flags & 4 != 0:
                        offset += 2
                    if flags & 5 == 1:
                        offset = function_processor(data, offset)
                    if flags & 6 == 2:
                        offset = function_processor(data, offset)

                numStates = int.from_bytes(data[offset:offset+2], endian)
                offset += 2
                for _ in range(numStates):
                    offset = state_processor(data, offset)
            data = bytes(data)
            f.seek(0)
            f.truncate(0)
            f.write(data)  


    def find_prev_non_alphanumeric(text: str, start_index: int, tokens: set[str] = {}):
            """Use this with care, do not use this to find the start of a plugin name as plugins are files and can contain non-alphanumeric characters"""
            for i in range(start_index, -1, -1): #this was range(start_index, 0, -1) I have changed it to -1 as 0 was not 0 inclusive, I hope I didn't just break a bunch of stuff...
                if (not text[i].isalnum() and text[i] != ' ') or text[i] in tokens:
                    return i
            return -1
    
    def find_next_non_alphanumeric(text: str, start_index: int, tokens: set[str] = {}):
        for i in range(start_index, len(text)):
            if not text[i].isalnum() or text[i] in tokens:
                return i
        return len(text)

    def ini_formid_sep_plugin_patcher(basename: str, new_file: str, form_id_map: dict, 
                                      sep: str = '~', tkns: set[str] = {" "}, fid_start: str = '0x', to_id_key: str = "hex_no_0",
                                      encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if sep+basename in line.lower() and not line.startswith(';'):
                    count = line.lower().count(sep)
                    start = 0
                    final_index = line.index(';') if ';' in line else None
                    for _ in range(count):
                        line = lines[i]
                        middle_index = line.index(sep, start)
                        start_index = shared_patchers.find_prev_non_alphanumeric(line, middle_index-2, tokens=tkns)
                        if final_index is not None and start_index > final_index:
                            continue
                        end_index = line.index('.es', middle_index) + 4
                        plugin = line.lower()[middle_index+len(sep):end_index].strip()
                        start_of_line = line[:start_index+1]
                        end_of_line = line[middle_index:]
                        form_id = line[start_index+1:middle_index].strip()
                        start = middle_index+len(sep)
                        if not form_id.lower().startswith('0x'):
                            continue
                        if len(form_id) > 8: # 0x accounts for 2
                            if form_id[2:4] == 'FE':
                                form_id = form_id [-3:]
                            else:
                                form_id = form_id[-6:]
                        if basename == plugin: 
                            form_id_int = int(form_id, 16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + fid_start + to_id_data[to_id_key] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = start_of_line + fid_start + to_id_data[to_id_key] + sep + "ESLifier_Cell_Master.esm" + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))            

    def ini_plugin_sep_formid_patcher(basename: str, new_file: str, form_id_map: dict,
                                        sep: str = '~', tkns: set[str] = {" "}, fid_start: str = '0x', to_id_key: str = "hex_no_0",
                                        encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename+sep in line.lower() and not line.startswith(';'):
                    count = line.lower().count(basename+sep)
                    start = 0
                    final_index = line.index(';') if ';' in line else None
                    for _ in range(count):
                        line = lines[i]
                        start_index = line.lower().index(basename+sep, start)
                        if final_index is not None and start_index > final_index:
                            continue
                        middle_index = start_index + len(basename+sep)
                        end_index = shared_patchers.find_next_non_alphanumeric(line, middle_index+1, tokens=tkns)
                        plugin = line.lower()[start_index:middle_index-len(sep)].strip()
                        start_of_line = line[:start_index]
                        end_of_line = line[end_index:]
                        form_id = line[middle_index:end_index].strip()
                        start = middle_index+1
                        if not form_id.lower().startswith('0x'):
                            continue
                        if len(form_id) > 8: # 0x accounts for 2
                            if form_id[2:4] == 'FE':
                                form_id = form_id [-3:]
                            else:
                                form_id = form_id[-6:]
                        if basename == plugin: 
                            form_id_int = int(form_id, 16)
                            to_id_data = form_id_map.get(form_id_int)
                            if to_id_data is not None:
                                if not to_id_data["update_name"]:
                                    lines[i] = line[:middle_index] + fid_start + to_id_data[to_id_key] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = start_of_line + "ESLifier_Cell_Master.esm" + sep + fid_start + to_id_data[to_id_key] + line[end_index:]
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))

    def ini_eq_plugin_sep_formid_patcher(basename: str, new_file: str, form_id_map: dict, sep: str ='|', encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            lines = f.readlines()
            print_replace = True
            for i, line in enumerate(lines):
                if basename in line.lower() and sep in line and '=' in line and not line.strip().startswith(';'):
                    ox = False
                    middle_index = line.index(sep)
                    plugin_index = line.index('=') + 1
                    plugin = line[plugin_index:middle_index].lower().strip()
                    if plugin == basename:
                        end_index = shared_patchers.find_next_non_alphanumeric(line, middle_index+1)
                        start_of_line = line[:middle_index+1]
                        end_of_line = line[end_index:]
                        form_id = line[middle_index+1:end_index].lower().strip()
                        if form_id.startswith('0x'):
                            ox = True
                        form_id_int = int(form_id, 16)
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if ox:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '0x' + to_id_data["hex_no_0"] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False   
                                    lines[i] = line[:plugin_index+1] + "ESLifier_Cell_Master.esm" + sep + "0x" + to_id_data["hex_no_0"] + end_of_line
                            else:
                                if not to_id_data["update_name"]:
                                    lines[i] = start_of_line + '00' + to_id_data["hex"] + end_of_line
                                else:
                                    if print_replace:
                                        write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                        print_replace = False
                                    lines[i] = line[:plugin_index+1] + "ESLifier_Cell_Master.esm" + sep + "00" + to_id_data["hex"] + end_of_line
            f.seek(0)
            f.truncate(0)
            f.write(''.join(lines))


        #IDK why I read it into a string for json5, probably was part of debugging way back when I first started, not going to touch it though.
    def safe_load_json(file_handle) -> dict:
        try:
            data = json.load(file_handle)
        except:
            file_handle.seek(0)
            string = file_handle.read()
            data = json5.loads(string)
        return data 

    def extract_values_and_keys(json_data, path=[]):
        results = []
        if isinstance(json_data, dict):
            for key, value in json_data.items():
                if path:
                    new_path = path.copy()
                    new_path.append(key)
                else:
                    new_path = [key]
                results.extend(shared_patchers.extract_values_and_keys(value, new_path))
        elif isinstance(json_data, list):
            for index, item in enumerate(json_data):
                if path:
                    new_path = path.copy()
                    new_path.append(index)
                else:
                    new_path = [index]
                results.extend(shared_patchers.extract_values_and_keys(item, new_path))
        else:
            results.append((path, json_data))

        return results

    def change_json_element(data, path, new_value):
        if not path:
            return new_value
        
        key = path[0]
        if isinstance(data, dict):
            data[key] = shared_patchers.change_json_element(data[key], path[1:], new_value)
        elif isinstance(data, list):
            index = int(key)
            data[index] = shared_patchers.change_json_element(data[index], path[1:], new_value)
        return data

    def change_json_key(data, old_key, new_key):
        if isinstance(data, dict):
            if old_key in data:
                data[new_key] = data.pop(old_key)
            for key, value in data.items():
                shared_patchers.change_json_key(value, old_key, new_key)
        elif isinstance(data, list):
            for item in data:
                shared_patchers.change_json_key(item, old_key, new_key)
        return data
    
    def json_generic_plugin_sep_formid_patcher(basename: str, new_file: str, form_id_map: dict, sep: str = '|', encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            ox = False
            print_replace = True
            for path, value in json_dict:
                if isinstance(value, str) and sep in value:
                    index = value.index(sep)
                    plugin = value[:index]
                    if plugin.lower() == basename:
                        form_id = value[index+len(sep):]
                        form_id_int = int(form_id, 16)
                        if not ox and '0x' in form_id.lower():
                            ox = True
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                if not ox:
                                    data = shared_patchers.change_json_element(data, path, plugin + sep + to_id_data["hex_no_0"])
                                else:
                                    data = shared_patchers.change_json_element(data, path, plugin + sep + '0x' + to_id_data["hex_no_0"])
                            else:
                                if print_replace:
                                    write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if not ox:
                                    data = shared_patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + sep + to_id_data["hex_no_0"])
                                else:
                                    data = shared_patchers.change_json_element(data, path, "ESLifier_Cell_Master.esm" + sep + '0x' + to_id_data["hex_no_0"])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            

    def json_generic_formid_sep_plugin_patcher(basename: str, new_file: str, form_id_map: dict, int_type: bool = False, sep: str = '|', encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            print_replace = True
            for path, value in json_dict:
                if isinstance(value, str) and sep in value:
                    ox = False
                    int_type_actual = int_type
                    index = value.index(sep)
                    plugin = value[index+len(sep):]
                    if plugin.lower() == basename:
                        form_id = value[:index]
                        if '0x' in form_id.lower():
                            ox = True
                        if ox or not int_type:
                            form_id_int = int(form_id, 16)
                        else:
                            try:
                                form_id_int = int(form_id)
                            except:
                                form_id_int = int(form_id, 16)
                                int_type_actual = False
                        to_id_data = form_id_map.get(form_id_int)
                        if to_id_data is not None:
                            if not to_id_data["update_name"]:
                                if not ox and not int_type_actual:
                                    data = shared_patchers.change_json_element(data, path, to_id_data["hex_no_0"] + sep + plugin)
                                elif ox:
                                    data = shared_patchers.change_json_element(data, path, '0x' + to_id_data["hex_no_0"] + sep + plugin)
                                else: # not ox and int_type
                                    data = shared_patchers.change_json_element(data, path, str(to_id_data["int"]) + sep + plugin)
                            else:
                                if print_replace:
                                    write_to_file(f'Plugin Name Replaced: {basename} | {new_file}')
                                    print_replace = False  
                                if not ox and not int_type_actual:
                                    data = shared_patchers.change_json_element(data, path, to_id_data["hex_no_0"] + sep + "ESLifier_Cell_Master.esm")
                                elif ox:
                                    data = shared_patchers.change_json_element(data, path, '0x' + to_id_data["hex_no_0"] + sep + "ESLifier_Cell_Master.esm")
                                else: # not ox and int_type
                                    data = shared_patchers.change_json_element(data, path, str(to_id_data["int"]) + sep + "ESLifier_Cell_Master.esm")
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
            
    
    def json_generic_key_fid_sep_plugin_patcher(basename: str, new_file: str, form_id_map: dict, int_type: bool = False, sep: str = ":", encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            patched_keys = []
            for path, value in json_dict:
                for i, part in enumerate(path):
                    if isinstance(part, str) and part.lower().endswith(sep + basename) and path[:i+1] not in patched_keys:
                        index = part.find(sep)
                        to_id_data = form_id_map.get(int(part[:index])) if int_type else form_id_map.get(int(part[:index],16))
                        if to_id_data is not None:
                            new_id = '0x' + to_id_data['hex'] if part.startswith('0x') else str(to_id_data['int']) if int_type else to_id_data['hex']
                            plugin = sep + 'ESLifier_Cell_Master.esm' if to_id_data['update_name'] else part[index:]
                            data = shared_patchers.change_json_key(data, part, new_id + plugin)
                            patched_keys.append(path[:i+1])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)

    def json_generic_key_plugin_sep_fid_patcher(basename: str, new_file: str, form_id_map: dict, int_type: bool = False, sep: str = ":", encoding_method: str ='utf-8'):
        with open(new_file, 'r+', encoding=encoding_method) as f:
            data = shared_patchers.safe_load_json(f)
            json_dict = shared_patchers.extract_values_and_keys(data)
            patched_keys = []
            for path, value in json_dict:
                for i, part in enumerate(path):
                    if isinstance(part, str) and part.lower().startswith(basename+sep) and not path[:i+1] in patched_keys:
                        index = part.find(sep)
                        id_part = part[index+len(sep):]
                        to_id_data = form_id_map.get(int(id_part)) if int_type else form_id_map.get(int(id_part ,16))
                        if to_id_data is not None:
                            new_id = '0x' + to_id_data['hex'] if id_part.startswith('0x') else str(to_id_data['int']) if int_type else to_id_data['hex']
                            plugin = 'ESLifier_Cell_Master.esm' + sep if to_id_data['update_name'] else part[:index+len(sep)]
                            data = shared_patchers.change_json_key(data, part, plugin + new_id)
                            patched_keys.append(path[:i+1])
            f.seek(0)
            f.truncate(0)
            json.dump(data, f, ensure_ascii=False, indent=3)
