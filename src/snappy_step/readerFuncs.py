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
        print("commands for ", element)
        # write foamDictinary command strings here for each object.
    
    # write file
    fileName = "snappyStep.sh"