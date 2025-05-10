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
        try:
            config = tomllib.load(f)
        except:
            print("There seems to be a problem with snappyStep.toml. Please check for format errors. Exiting.")
            exit(1)

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
    patch_tags = []    

    # Begin gmsh operations
    gmsh.initialize()
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit

    # retrive geometry
    print('Reading geometry')
    stepFile = os.path.join(geoPath, files[0])
    gmsh.model.occ.importShapes(stepFile,False)
    gmsh.model.occ.synchronize()

    # How many volumes before coherence
    nVol = len(gmsh.model.getEntities(3))

    # Remove extra names face names. Prevent issues when tags change.
    removeFaceLabelsOnVolumes(gmsh)

    # Apply coherence to remove duplicate surfaces, edges, and points
    print('Imprinting features and removing duplicate faces')
    if nVol > 1:
        gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(3))
        gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(2))
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    # Check coherence results
    volumes = gmsh.model.getEntities(3)
    if len(volumes) != nVol:
        print("Coherence changed number of volumes. Check geometry. Exiting")
        exit(1)

    # Get Geometry Names
    print('Getting Names of Bodies')
    volNames, volTags = getVolumeNames(gmsh)
    print("Found Volumes:")
    print(*volNames)


    # Get surfaces
    print("Getting Surface Names")
    surfNames, surfTags, patch_tags = getSurfaceNames(gmsh)

    if len(surfNames)>0:
        print("Found Surfaces:")
        print(*surfNames)
        makeGroups = True
        snappyStepGroupsDict = dict(zip(surfNames, surfTags)) # Combine into dictionary for easy acces
  
    # print(len(outDimTagsMap[:][:]))
    # if any(len(sublist) > 1 for sublist in outDimTagsMap):
    #     print("geometry tags of face groups changed. Support for this to be added later. Please fully imprint surfaces in CAD. Exiting")
    #     exit(1)

    # Assign surface names
    for iter, group in enumerate(surfTags):
        for surf in group:
            gmsh.model.setEntityName(2,surf[1],surfNames[iter])

    for i, element in enumerate(volNames): # loop through all Volume entries
        gmsh.model.setEntityName(3,volTags[i][1],element) # Adds names to gmsh entites
    print('Volume names assigned')

    print("Getting locationInMesh coordinates")
    # get inside points for each volume
    insidePoints = []
    for i, element in enumerate(volumes):
        print(volNames[i]+":")
        if volNames[i] in config["insidePoint"]:
            insidePoints.append(config["insidePoint"][volNames[i]])
            print("Using coordinates in config file.")
        else:
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

# optionally view faces and volumes and exit before mesh
    if args.vf:
        gmsh.option.set_number("Geometry.VolumeLabels",1)
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.option.set_number("Geometry.LabelType",3)
        print("gmsh window open.")
        gmsh.fltk.run()
        exit(1)

    # Set Physical Surfaces
    # Start with exterior surfaces

    external_regions = [] # This will be used in the foamDict script
    external_patches = []
    patches_for_edge_mesh = []
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
                # print([surfTag for surfTag in surfTags])
                # print([item for sublist in surfTags for item in sublist])
                if (2,face[1]) in [item for sublist in surfTags for item in sublist] and isExternal[k]:
                # if face[1] in surfTags and isExternal[k]:
                # if face[1] in [surfTag[1] for surfTag in surfTagPairs] and isExternal[k]:
                    external_patches.append(face[1])
                elif isExternal[k]:
                    externalList.append(face[1]) # Gets face tag
                    if not anyExternal:
                        anyExternal = True
                    # counter = counter + 1        
        
        if anyExternal: # Don't need to make entry in dictionary if there are no external surfaces for this volume
            external_regions.append(volNames[i]+"_default") # This will be used in the foamDict script
            gmsh.model.addPhysicalGroup(2,externalList,-1,volNames[i]+"_default")
            patches_for_edge_mesh.extend(externalList)

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
        for key in snappyStepGroupsDict:
            if snappyStepGroupsDict[key][0][1] in external_patches:
                gmsh.model.addPhysicalGroup(2,[el[1] for el in snappyStepGroupsDict[key]],-1,key)
                external_regions.append(key)
                setPatchList.append(key)
                patches_for_edge_mesh.extend([el[1] for el in snappyStepGroupsDict[key]])
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
    # Write corresponding edge mesh
    writeEdgeMesh(gmsh,patches_for_edge_mesh,os.path.basename(stepFile).split('.')[0],geoPath)
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
                idx = j
            else:
               continue
        if not patches: # skip adding to physical group and lists if patch list is empty
            continue
        volPair.append(interfaceVolPair[idx])
        uniqueInterfaceNamesList.append(element)
        gmsh.model.addPhysicalGroup(2,patches,-1,element)
        print("Writing " + os.path.join(geoPath,element+".stl"))
        gmsh.write(os.path.join(geoPath,element+".stl"))
        print("Done.")
        gmsh.model.removePhysicalGroups([])
        writeEdgeMesh(gmsh, patches, element, geoPath)
    

    # interfaces in snappy step surfaces
    if makeGroups:
        for key in snappyStepGroupsDict:
            if snappyStepGroupsDict[key][0][1] not in external_patches:
                gmsh.model.addPhysicalGroup(2,[el[1] for el in snappyStepGroupsDict[key]],-1,key)
                patches_for_edge_mesh = [el[1] for el in snappyStepGroupsDict[key]]
            else:
                continue
            uniqueInterfaceNamesList.append(key)
            adj = gmsh.model.getAdjacencies(2,snappyStepGroupsDict[key][0][1])
            volPair.append([adj[0][0],adj[0][1]])
            setAdj = set([adj[0][0],adj[0][1]])
            for iter, tag in enumerate(snappyStepGroupsDict[key]):
                if iter != 0:
                    compAdj = gmsh.model.getAdjacencies(2,snappyStepGroupsDict[key][iter][1])
                    # if not setAdj == set([compAdj[iter][0],compAdj[iter][1]]):
                    if not setAdj == set([compAdj[0][0],compAdj[0][1]]):
                        print("interface group " + key + " contains surfaces between multiple volume pairs. Please split into groups of single volume pairs. Exiting.")
                        exit(1)

            print("Writing " + os.path.join(geoPath,key+".stl"))
            gmsh.write(os.path.join(geoPath,key+".stl"))
            print("Done.")
            gmsh.model.removePhysicalGroups([])
            # Write corresponding edge mesh
            writeEdgeMesh(gmsh, patches_for_edge_mesh, key, geoPath)

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
    surfReturn = writeFoamDictionarySurf(uniqueInterfaceNamesList.copy(),volPair.copy(),volNames,[el[1] for el in volTags],insidePoints)
    defaultZone = surfReturn[1]
    commands.extend(surfReturn[0])

    # Set external groups as type patch
    if makeGroups:
        commands.extend(setExternalPatch(setPatchList, os.path.splitext(os.path.basename(stepFile))[0]))
    print("Done.")

    commands.extend(writeFoamDictionaryEdge([os.path.splitext(os.path.basename(stepFile))[0]] + uniqueInterfaceNamesList))
    # Write mesh generation commands
    writeMeshCommands()
    writeSplitCommand(defaultZone)
    writeCommands('snappystep.sh',commands)

    os.chmod("./snappyStep.sh",0o755) # Make shell script executable
    os.chmod("./snappyStepGenerateMesh.sh",0o755)
    os.chmod("./snappyStepSplitMeshRegions.sh",0o755)

    # See results
    if args.v:
        gmsh.option.set_number("Geometry.VolumeLabels",1)
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.option.set_number("Geometry.LabelType",3)
        print("gmsh window open.")
        gmsh.fltk.run()
    print("All geometry files and scripts generated. Done.")
    # Last GMSH command
    gmsh.finalize()

    

