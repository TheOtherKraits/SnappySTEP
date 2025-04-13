import argparse
import gmsh
import os
from .readerFuncs import *
from collections import Counter
from itertools import count
import tomllib


def mainFunc():
    parser = argparse.ArgumentParser(description='Prepare STEP geometry for SnappyHexMesh using GMSH')
    parser.add_argument('-v', action='store_true',help='Display generated surface mesh after genration') # view generated mesh in gmsh
    parser.add_argument('-vf', action='store_true',help='Display faces and labels. Exits without generating mesh') # view faces after coherence and don't generate mesh

    args = parser.parse_args()
    
    ext = [".stp", ".step", ".STP", ".STEP"]
    geoPath = "./constant/geometry"
    files = []
    

    # Check for OpenFOAM case structure

    if not os.path.exists(geoPath):
        print("Please run from OpenFOAM case root directory.")
        exit(1)

    # Read Config
    with open("./system/snappyStep.toml", "rb") as f:
        config = tomllib.load(f)

    if "insidePoint" in config:  
        print("Using insidePoints defined in config")
    else:
        config["insidePoint"] = []
    commands = []
    if "sHM" in config:
        mRFS = str(config["sHM"]["multiRegionFeatureSnap"])
        commands.append("foamDictionary system/snappyHexMeshDict -entry snapControls/multiRegionFeatureSnap -set " + str(config["sHM"]["multiRegionFeatureSnap"]).lower()+";")


    # Find geometry files
    for file in os.listdir(geoPath):
        if file.endswith(tuple(ext)):
            files.append(file)
    
    if len(files) == 0:
        print("No step file found in constant/geometry directory")
        exit(1)
    elif len(files) > 1:
        print("More than one step file found. Please remove or rename other files.")
        exit(1)
    else:
        print(files[0]+" found")

    makeGroups = False
    # # Get manual face groups
    # if os.path.isfile("./constant/snappyStepGroups.toml"):
    #     print ("Reading geometry names from snappyStepGroups.toml")
    #     with open("./constant/snappyStepGroups.toml", "rb") as f:
    #         snappyStepGroups = tomllib.load(f)
    #         if "surfaces" in snappyStepGroups:
    #             print("Getting surface groups")
    #             patch_tags = flatten(list(snappyStepGroups["surfaces"].values()))
    #             makeGroups = True

    # else:
    #     snappyStepGroups = []
    #     patch_tags = []
    patch_tags = []    

    # if makeGroups:
    #     if len(set(patch_tags))<len(patch_tags):
    #         print(" Overlapping selected surfaces detected. Exiting")
    #         exit(1)

    # Begin gmsh operations
    gmsh.initialize()
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit

    # retrive geometry
    print('Reading geometry')
    stepFile = os.path.join(geoPath, files[0])
    gmsh.model.occ.importShapes(stepFile,False) # Optional argument allows for lower dimension entities to be imported
    gmsh.model.occ.synchronize()

    # How many volumes before coherence
    nVol = len(gmsh.model.getEntities(3))

    # Get surfaces
    print("Reading Surface Names")
    # print(surfaces)
    snappyStepGroups, surfaceGroupLenghts = getStepSurfaces(stepFile)
    print("Found Surfaces:")
    print(*snappyStepGroups)
    if len(snappyStepGroups)>0:
        makeGroups = True
        surfaces = gmsh.model.occ.getEntities(2)
        # print(surfaces)
        # surfTags = []
        surfTagPairs = []
        # volSurfTagPairs = []
        for element in surfaces:
            adj = gmsh.model.get_adjacencies(element[0],element[1])
            # print(adj)
            if adj[0] == []:
                # surfTags.append(element[1])
                surfTagPairs.append(element) # For surface coherence
            # else:
                # volSurfTagPairs.append(element) # For surface coherence
        groupTags = [[] for i in range(len(surfaceGroupLenghts))]# empty list of lists
        count = 0
        for iter, element in enumerate(surfaceGroupLenghts):
            for i in range(element):
                # groupTags[iter].append(surfTags[count])
                groupTags[iter].append(surfTagPairs[count][1])
                count += 1 # increment counter
    snappyStepGroupsDict = dict(zip(snappyStepGroups, groupTags)) # Combine into dictionary for easy acces

    # Apply coherence to remove duplicate surfaces, edges, and points
    print('Imprinting features and removing duplicate faces')
    gmsh.model.occ.fragment([],[])
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    newTags, outDimTagsMap = gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),surfTagPairs)
    gmsh.model.occ.synchronize()

    # print(len(outDimTagsMap[:][:]))
    if any(len(sublist) > 1 for sublist in outDimTagsMap):
        print("geometry tags of face groups changed. Support for this to be added later. Please fully imprint surfaces in CAD. Exiting")
        exit(1)
    # print(len(outDimTagsMap[1]))
    # Get Geometry Names
    print('Getting Names of Bodies')
    volumes = gmsh.model.getEntities(3)
    if len(volumes) != nVol:
        print("Coherence changed number of volumes. Check geometry. Exiting")
        exit(1)
    volNames = regexStepBodyNames(stepFile)
    print("Found Volumes:")
    print(*volNames)
    for i, element in enumerate(volNames): # loop through all Volume entries
        gmsh.model.setEntityName(3,volumes[i][1],element) # Adds names to gmsh entites
    print('Volume names assigned')

    print("Getting locationInMesh coordinates")
    # get inside points for each volume
    insidePoints = []
    volTags = [] # For quick access to tags without dims. Used in writeFoamDictionarySurf
    for i, element in enumerate(volumes):
        print(volNames[i]+":")
        if volNames[i] in config["insidePoint"]:
            insidePoints.append(config["insidePoint"][volNames[i]])
            print("Using coordinates in config file.")
        else:
            volTags.append(element[1])
            insidePoints.append(getLocationInMesh(gmsh,element[1]))
    

    print('Identifying contacts')

    geoBounds = gmsh.model.getBoundary(volumes,False,False,False)
    interfaces = {x for x in geoBounds if geoBounds.count(x) > 1} # Checks each index for more than one item the list, if so added to the set
    print(len(interfaces), "contacting face(s) found.")
    # get volumes of interfaces
    interfaceVolPair = [] # List of dim, tag pairs of volume pairs of each interface
    interfaceNames = []
    interfaceList = []
    for element in interfaces:
        adj = gmsh.model.getAdjacencies(element[0],element[1])
        interfaceVolPair.append([adj[0][0],adj[0][1]])
        namePair = [gmsh.model.getEntityName(3,adj[0][0]), gmsh.model.getEntityName(3,adj[0][1])] # Gets names of both volumes
        namePair.sort # sorts names for consistency
        interfaceNames.append(namePair[0] + "_to_" + namePair[1]) #Adds name to list
        interfaceList.append(element) # List rather than set for use later

    # Setting for viewing mesh
    gmsh.option.set_number("Geometry.VolumeLabels",1)
    gmsh.model.occ.synchronize()

# optionally view faces and volumes and exit before mesh
    if args.vf:
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.model.occ.synchronize()
        gmsh.fltk.run()
        exit(1)

    # Set Physical Surfaces
    # Start with exterior surfaces

    external_regions = [] # This will be used in the foamDict script
    external_tag = [] # This will be used in the foamDict script
    external_patches = []
    for i, element in enumerate(volumes):
        anyExternal = False # Don't need to make entry in dictionary if there are no external surfaces for this volume
        bounds = gmsh.model.getBoundary([element],True,False,False)
        isExternal = []
        for j, face in enumerate(bounds):
            # Find surfaces that bound more than one volume
            if face in interfaces:
                isExternal.append(False)
            else:
                isExternal.append(True)
        if any(isExternal):
            externalList = []
            for k, face in enumerate(bounds):
                # if face[1] in surfTags and isExternal[k]:
                if face[1] in [surfTag[1] for surfTag in surfTagPairs] and isExternal[k]:
                    external_patches.append(face[1])
                elif isExternal[k]:
                    externalList.append(face[1]) # Gets face tag
                    external_tag.append([2, face[1]]) # May not need. Leave for now
                    if not anyExternal:
                        anyExternal = True
                    # counter = counter + 1        
        
        if anyExternal: # Don't need to make entry in dictionary if there are no external surfaces for this volume
            external_regions.append(volNames[i]+"_wall") # This will be used in the foamDict script
            gmsh.model.addPhysicalGroup(2,externalList,-1,volNames[i]+"_wall")

    # Check that all patches are either internal or external
    if makeGroups:
        for key in snappyStepGroupsDict:
            res = set(snappyStepGroupsDict[key]).issubset(external_patches)
            if res:
                continue
            else:
                if any(x in snappyStepGroupsDict[key] for x in external_patches):
                    print("Mismatched patch groups found. Exiting")
                    exit(1)

        # Add external patches to physical groups
        setPatchList = []
        for key in snappyStepGroups:
            if snappyStepGroupsDict[key][0] in external_patches:
                gmsh.model.addPhysicalGroup(2,snappyStepGroupsDict[key],-1,key)
                external_regions.append(key)
                setPatchList.append(key)
            else:
                continue

    # Mesh
    # Use commands below to set mesh sizes
    print("Generating Surface Mesh")
    gmsh.option.setNumber("Mesh.Algorithm",config["MESH"]["MeshAlgorithm"])
    gmsh.option.setNumber("Mesh.MeshSizeFactor",config["MESH"]["MeshSizeFactor"])
    gmsh.option.setNumber("Mesh.MeshSizeMin",config["MESH"]["MeshSizeMin"])
    gmsh.option.setNumber("Mesh.MeshSizeMax",config["MESH"]["MeshSizeMax"])
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature",config["MESH"]["MeshSizeFromCurvature"])
    gmsh.model.mesh.generate(2)

    # export settings
    gmsh.option.set_number("Mesh.StlOneSolidPerSurface",2)

    # export stl
    print("Writing ." + stepFile.split('.')[1]+".stl")
    gmsh.write(os.path.relpath(stepFile).split('.')[0]+".stl")
    print("Done.")
    #Clear all phsical groups
    gmsh.model.removePhysicalGroups([])
    #Create physical group for each interface volume pair
    uniqueInterfaceNames = set(interfaceNames)
    
    # interfaces not in snappy step surfaces
    volPair = [] # This will be used in the foamDict script
    uniqueInterfaceNamesList = []
    for element in uniqueInterfaceNames:
        patches = []
        for j, name in enumerate(interfaceNames):
            if interfaceList[j][1] in patch_tags:
                continue
            elif name == element:
                patches.append(interfaceList[j][1]) # This will be used in the foamDict script
            else:
               continue
        if not patches: # skip adding to physical group and lists if patch list is empty
            continue
        volPair.append(interfaceVolPair[j])
        uniqueInterfaceNamesList.append(element)
        gmsh.model.addPhysicalGroup(2,patches,-1,element)
        print("Writing " + os.path.join(geoPath,element+".stl"))
        gmsh.write(os.path.join(geoPath,element+".stl"))
        print("Done.")
        gmsh.model.removePhysicalGroups([])
    

    # interfaces in snappy step surfaces
    if makeGroups:
        for key in snappyStepGroupsDict:
            if snappyStepGroupsDict[key][0] not in external_patches:
                gmsh.model.addPhysicalGroup(2,snappyStepGroups["surfaces"][key],-1,key)
            else:
                continue
            uniqueInterfaceNamesList.append(key)
            adj = gmsh.model.getAdjacencies(2,snappyStepGroups["surfaces"][key][0])
            volPair.append([adj[0][0],adj[0][1]])
            setAdj = set([adj[0][0],adj[0][1]])
            for iter, tag in enumerate(snappyStepGroups["surfaces"][key]):
                if iter != 0:
                    compAdj = gmsh.model.getAdjacencies(2,snappyStepGroups["surfaces"][key][0])
                    # if not setAdj == set([compAdj[iter][0],compAdj[iter][1]]):
                    if not setAdj == set([compAdj[0][0],compAdj[0][1]]):
                        print("interface group " + key + " contains surfaces between multiple volume pairs. Please split into groups of single volume pairs. Exiting.")
                        exit(1)

                    
            # gmsh.model.addPhysicalGroup(2,snappyStepGroups["surfaces"][key],-1,key)
            print("Writing " + os.path.join(geoPath,key+".stl"))
            gmsh.write(os.path.join(geoPath,key+".stl"))
            print("Done.")
            gmsh.model.removePhysicalGroups([])

    # Write shell scripts
    # External walls
    print("Writing foamDictionary commands.")
    commands.extend(writeFoamDictionaryGeo(os.path.splitext(os.path.basename(stepFile))[0],external_regions))
    commands.extend(writeRefinementRegions(os.path.splitext(os.path.basename(stepFile))[0],external_regions))
    # Interfaces
    # for i, element in enumerate(uniqueInterfaceNamesList):
    for element in uniqueInterfaceNamesList:
        commands.extend(writeFoamDictionaryGeo(element,[])) # pass empty region list since each interface only has the single region
        commands.extend(writeRefinementRegions(element,[]))
        #writeRefinementRegions(element, interface_patches[i])

    # Refinement Surfaces commands and get name default zone
    surfReturn = writeFoamDictionarySurf(uniqueInterfaceNamesList.copy(),volPair.copy(),volNames,volTags,insidePoints)
    defaultZone = surfReturn[1]
    commands.extend(surfReturn[0])

    # Set external groups as type patch
    if makeGroups:
        commands.extend(setExternalPatch(setPatchList, os.path.splitext(os.path.basename(stepFile))[0]))
    print("Done.")
    # Write mesh generation commands
    writeMeshCommands()
    writeSplitCommand(defaultZone)
    writeCommands('snappystep.sh',commands)

    os.chmod("./snappyStep.sh",0o755) # Make shell script executable
    os.chmod("./snappyStepGenerateMesh.sh",0o755)
    os.chmod("./snappyStepSplitMeshRegions.sh",0o755)

    # See results
    if args.v:
        gmsh.fltk.run()
    print("All geometry files and scripts generated. Done.")
    # Last GMSH command
    gmsh.finalize()

    

