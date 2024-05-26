import re


def regexStepBodyNames(fullPath): # Just regex all text?
    with open(fullPath, 'r') as StepFile:
        bodyNames = re.findall(r"MANIFOLD_SOLID_BREP\(\'(.*?)\'\,\#", StepFile.read())
        return bodyNames

def writeFoamDictionaryGeo(name: str, regions: list[str]) -> None:
    commands = [] # use append to add to list
    commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions -remove") # clear any existing regions
    commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions -add \"{}\"") # re add regions
    for i, element in enumerate(regions):
        commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions/" + element +" -add {}")
        commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions/" + element +"/name -add "+ element +";")
    
          
    commands.append("\n") # add new line to end
    # write file
    fileName = "snappyStep.sh"
    with open(fileName, 'a') as script:
        script.write("\n".join(commands))
    

def writeFoamDictionarySurf(names: list[str],pairs: list[int, int],volumeNames: list[str],volumeTags: list[int],coordinate: list[float,float,float]) -> None:
    commands = [] # use append to add to list
    nContacts = []
    flatPairs = sum(pairs, []) # flattens pairs list into single list
    for i, element in enumerate(volumeTags):
        nContacts.append(flatPairs.count(element)) # counts number of interfaces for each volume
    # Sort volumes by number of contacts
    nContacts, volumeTags, volumeNames, coordinate = zip(*sorted(zip(nContacts, volumeTags, volumeNames,coordinate)))
    for i, element in enumerate(volumeNames):
        if element == volumeNames[-1]:
            break
        k = volumeTags[i] # Tag of volume
        for j, tag in enumerate(pairs): # Find first insance of volume in pairs
            if k in tag:
                break
            else:
                continue
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/faceZone -add " + names[j] + ";")
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/cellZone -add " + element + ";")
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/mode -add insidePoint;")
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/insidePoint -add \"(" + " ".join(str(x) for x in coordinate[i]) + ")\";")
        print("commands for ", element)
        # remove used interface from list
        names.pop(j)
        pairs.pop(j)

        # write foamDictinary command strings here for each object.
    
    # write file
    commands.append("\n") # add new line to end
    fileName = "snappyStep.sh"
    with open(fileName, 'a') as script:
        script.write("\n".join(commands))
    return element

def writeMeshCommands(defaultZone: str):
    commands = []
    commands.append("snappyHexMeshConfig")
    commands.append("blockMesh")
    commands.append("./snappyStep.sh")
    commands.append("snappyHexMesh -overwrite")
    commands.append("splitMeshRegions -cellZones -defaultRegionName " + defaultZone + " -overwrite")
    commands.append("checkMesh")
    fileName = "snappyStepGenerateMesh.sh"
    with open(fileName, 'a') as script:
        script.write("\n".join(commands))