import re


def regexStepBodyNames(fullPath): # Just regex all text?
    with open(fullPath, 'r') as StepFile:
        bodyNames = re.findall(r"MANIFOLD_SOLID_BREP\(\'(.*?)\'\,\#", StepFile.read())
        bodyNames = validateNames(bodyNames)
        return bodyNames

def regexStepShellNames(fullPath): # Just regex all text?
    with open(fullPath, 'r') as StepFile:
        shellNames = re.findall(r"SHELL_BASED_SURFACE_MODEL\(\'(.*?)\'\,\(#", StepFile.read())
        shellNames = validateNames(shellNames)
        print(shellNames)
        return shellNames

def writeCommands(fileName: str, commands: list):
    with open(fileName, 'w') as script:
        script.write("\n".join(commands))

def writeFoamDictionaryGeo(name: str, regions: list[str]) -> None:
    commands = [] # use append to add to list
    commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions -remove") # clear any existing regions
    if regions != []: # Check if empty
        commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions -add \"{}\"") # re add regions
        for i, element in enumerate(regions):
            commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions/" + element +" -add {}")
            commands.append("foamDictionary system/snappyHexMeshDict -entry geometry/" + name + "/regions/" + element +"/name -add "+ element +";")
          
    commands.append("\n") # add new line to end
    return commands
    

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
            commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/insidePoint -set \"(" + " ".join(str(x) for x in coordinate[i]) + ")\";")
            break
        k = volumeTags[i] # Tag of volume
        for j, tag in enumerate(pairs): # Find first insance of volume in pairs
            if k in tag:
                break
            else:
                continue

        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/cellZone -add " + element + ";")
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/mode -add insidePoint;")
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + names[j] + "/insidePoint -add \"(" + " ".join(str(x) for x in coordinate[i]) + ")\";")
        # print("Generated commands for ", element)
        # remove used interface from list
        names.pop(j)
        pairs.pop(j)
    
    # write file
    commands.append("\n") # add new line to end
    return commands, element


def writeRefinementRegions(name: str, regions: list[str]) -> None:
    commands = [] # use append to add to list
    
    commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions -remove") # remove any existing regions
    if regions != []: # Check if empty
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions -add \"{}\"") # add regions sub dict
        for i, element in enumerate(regions):
            commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + element +" -add {}")
            commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + element +"/level -add \"(2 2)\";")
            commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + element +"/patchInfo -add \"{}\";")
            commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + element +"/patchInfo/type -add wall;")
    else:
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/faceZone -add " + name + ";")
    commands.append("\n") # add new line to end
    return commands



def writeMeshCommands():
    commands = []
    commands.append("snappyHexMeshConfig -explicitFeatures")
    commands.append("blockMesh")
    commands.append("./snappyStep.sh")
    commands.append("surfaceFeatures")
    commands.append("snappyHexMesh -overwrite")
    commands.append("./snappyStepSplitMeshRegions.sh")
    commands.append("checkMesh")
    fileName = "snappyStepGenerateMesh.sh"
    writeCommands(fileName,commands)
  

def writeSplitCommand(defaultZone: str):
    commands = []
    commands.append("splitMeshRegions -cellZones -defaultRegionName " + defaultZone + " -useFaceZones -overwrite")
    fileName = "snappyStepSplitMeshRegions.sh"
    writeCommands(fileName,commands)
 

def writeFoamDictionaryInterfaceGroups(interfacePatchNames: list, interfaceList: list, faceSets: dict):
    # This does not work due to cell zone splitting. Try using changeDictionary
    commands = []
    for iter, patch in enumerate(interfacePatchNames):
        for key in faceSets:
            if interfaceList[iter][1] in faceSets[key]:
                commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + patch + "/patchInfo/inGroups -add \"(" + key +")\";")
                continue
    return commands


def writeFoamDictionaryExternalGroups(external_regions: list, external_tag: list, faceSets: dict, name):
    commands = []
    for iter, patch in enumerate(external_regions):
        for key in faceSets:
            if external_tag[iter][1] in faceSets[key]:
                commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + patch +"/patchInfo/inGroups -add \"(" + key +")\";")
                commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + patch +"/patchInfo/type -set patch;")
                continue
    return commands


def flatten(arg):
    if not isinstance(arg, list): # if not list
        return [arg]
    return [x for sub in arg for x in flatten(sub)]

def setExternalPatch(regionList: list, name: str):
    commands = []
    for region in regionList:
        commands.append("foamDictionary system/snappyHexMeshDict -entry castellatedMeshControls/refinementSurfaces/" + name + "/regions/" + region +"/patchInfo/type -set patch;")
    return commands


def getStepSurfaces(fullPath):
    with open(fullPath, 'r') as StepFile:
        StepText = StepFile.read()
    # print(StepText)
    Names = re.findall(r"SHELL_BASED_SURFACE_MODEL\(\'(.*?)\'\,\(#", StepText)
    surfaceLines = re.findall(r"SHELL_BASED_SURFACE_MODEL\(\'.*?\'\,\((#\d+)", StepText)
    nSurfaces = [0] * len(Names)
    for iter, line in enumerate(surfaceLines):
        exp = re.compile(line + r"=OPEN_SHELL\(\'.*?\'\,\(([#\d+\,?]+)\)")
        tempList = re.findall(exp,StepText)
        # print(tempList[0])
        nSurfaces[iter] = tempList[0].count(",") +1 
    Names = validateNames(Names)
    return Names, nSurfaces

def validateNames(names):
    names = [name.strip().replace(" ", "_") for name in names]
    names = [name.replace("(", "") for name in names]
    names = [name.replace(")", "") for name in names]
    return names

def getLocationInMesh(gmsh, volTag: int):
    coords = []
    # First try center of mass
    coords = gmsh.model.occ.getCenterOfMass(3,volTag)
    
    if gmsh.model.isInside(3,volTag,coords):
        print("Found by center of mass")
        print(coords)
        return coords
    
    # try center of bounding box
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(3,volTag)
    coords = ((xmax+xmin)/2,(ymax+ymin)/2,(zmax+zmin)/2)

    if gmsh.model.isInside(3,volTag,coords):
        print("Found by bounding box center")
        print(coords)
        return coords

    # sweep through grids, increasingly fine. Choosing plane in cernter, sweeping though 2d locations on grid
    z = (zmax+zmin)/2
    grids = [10, 100, 1000]
    for element in grids: # coarse grid to fine grid
        x = linspace(xmin, xmax, element)
        y = linspace(ymin, ymax, element)
        print("Grid Search: "+str(element)+"x"+str(element))
        for xi in x:
            for yi in y:
                coords = (xi, yi, z)
                if gmsh.model.isInside(3,volTag,coords):
                    print("Found by grid search")
                    print(coords)
                    return coords




    print("Point not found.")
    exit(1)

def linspace(a, b, n):
    diff = (float(b) - a)/(n - 1)
    return [diff * i + a  for i in range(1, n-1)] # Skips first and last
    
