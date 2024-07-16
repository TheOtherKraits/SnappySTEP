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
        print(files[0]+" found.")

    makeGroups = False
    # Get manual face groups
    if os.path.isfile("./constant/snappyStepGroups.toml"):
        makeGroups = True
        print ("Reading geometry names from snappyStepGroups.toml")
        with open("./constant/snappyStepGroups.toml", "rb") as f:
            snappyStepGroups = tomllib.load(f)
            patch_tags = flatten(list(snappyStepGroups["surfaces"].values()))

    else:
        snappyStepGroups = []
    # add check for repeated tags in surface groups

    # Begin gmsh operations
    gmsh.initialize()
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit

    # retrive geometry
    print('Reading geometry')
    stepFile = os.path.join(geoPath, files[0])
    gmsh.model.occ.importShapes(stepFile)

    # Apply coherence to remove duplicate surfaces, edges, and points
    print('Imprinting features and removing duplicate faces')
    gmsh.model.occ.fragment([],[])
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    # Get Geometry Names
    print('Getting Names of Bodies and Surfaces')
    volumes = gmsh.model.getEntities(3)
    VolNames = regexStepBodyNames(stepFile)
    print("Found Volumes: ",VolNames)
    for i, element in enumerate(VolNames): # loop through all Volume entries
        gmsh.model.setEntityName(3,volumes[i][1],element) # Adds names to gmsh entites
    print('Volume names assigned')

    print("Getting pointInside")
    # get inside points for each volume
    insidePoints = []
    volTags = []
    for i, element in enumerate(volumes):

        if VolNames[i] in config["insidePoint"]:
            insidePoints.append(config["insidePoint"][VolNames[i]])
        else:
            insidePoints.append(gmsh.model.occ.getCenterOfMass(3,element[1])) # This gets center of mass. will not work for objects where COM is not inside
        volTags.append(element[1])
        # see if isInside can do check on points
        # Below was attempt to use first face and offset to get point inside. Could not figure out how to get a point on the center of a face
        # faces = gmsh.model.get_adjacencies(2,element[1])
        # coord = gmsh.model.get
        # param = gmsh.model.getParametrization(2,faces[1][0],coord)# first element of downard adjacency
        # normal = gmsh.model.getNormal()
    

    print('Identifying contacts')

    geoBounds = gmsh.model.getBoundary(volumes,False,False,False)
    Interfaces = {x for x in geoBounds if geoBounds.count(x) > 1} # Checks each index for more than one item the list, if so added to the set
    print(len(Interfaces), "contacting face(s) found.")
    # get volumes of interfaces
    interfaceVolPair = [] # List of dim, tag pairs of volume pairs of each interface
    interfaceNames = []
    interfaceList = []
    for i, element in enumerate(Interfaces):
        adj = gmsh.model.getAdjacencies(element[0],element[1])
        interfaceVolPair.append([adj[0][0],adj[0][1]])
        namePair = [gmsh.model.getEntityName(3,adj[0][0]), gmsh.model.getEntityName(3,adj[0][1])] # Gets names of both volumes
        namePair.sort # sorts names for consistency
        interfaceNames.append(namePair[0] + "_to_" + namePair[1]) #Adds name to list
        interfaceList.append(element) # List rather than set for use later

    # Rename repeated interface names    
    # c = Counter(interfaceNames)
    # iters = {k: count(1) for k, v in c.items() if v > 1}
    # interfacePatchNames = [x+"_"+str(next(iters[x])).zfill(4) if x in iters else x for x in interfaceNames]
    # Renaming might need to changed or done after other operations.

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
            if face in Interfaces:
                isExternal.append(False)
            else:
                isExternal.append(True)
        if any(isExternal):
            externalList = []
            for k, face in enumerate(bounds):
                if face[1] in patch_tags and isExternal[k]:
                    external_patches.append(face[1])
                elif isExternal[k]:
                    externalList.append(face[1]) # Gets face tag
                    # gmsh.model.addPhysicalGroup(2,externalList,-1,VolNames[i]+"_"+str(counter).zfill(4))
                    # gmsh.model.addPhysicalGroup(2,[face[1]],-1,VolNames[i]+"_"+str(counter).zfill(4))
                    # external_regions.append(VolNames[i]+"_"+str(counter).zfill(4)) # This will be used in the foamDict script
                    external_tag.append([2, face[1]]) # May not need. Leave for now
                    if not anyExternal:
                        anyExternal = True
                    # counter = counter + 1        
        
        if anyExternal: # Don't need to make entry in dictionary if there are no external surfaces for this volume
            external_regions.append(VolNames[i]+"_wall") # This will be used in the foamDict script
            gmsh.model.addPhysicalGroup(2,externalList,-1,VolNames[i]+"_wall")

    # Check that all patches are either internal or external

    for key in snappyStepGroups["surfaces"]:
        res = set(snappyStepGroups["surfaces"][key]).issubset(external_patches)
        if res:
            continue
        else:
            if any(x in snappyStepGroups["surfaces"][key] for x in external_patches):
                print("Mismatched patch groups found. Exiting")
                exit(1)


    # Add external patches to physical groups
    setPatchList = []
    for key in snappyStepGroups["surfaces"]:
        if snappyStepGroups["surfaces"][key][0] in external_patches:
            gmsh.model.addPhysicalGroup(2,snappyStepGroups["surfaces"][key],-1,key)
            external_regions.append(key)
            setPatchList.append(key)
        else:
            continue


    # Mesh
    # Use commands below to set mesh sizes
    gmsh.option.setNumber("Mesh.Algorithm",config["MESH"]["MeshAlgorithm"])
    gmsh.option.setNumber("Mesh.MeshSizeFactor",config["MESH"]["MeshSizeFactor"])
    gmsh.option.setNumber("Mesh.MeshSizeMin",config["MESH"]["MeshSizeMin"])
    gmsh.option.setNumber("Mesh.MeshSizeMax",config["MESH"]["MeshSizeMax"])
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature",config["MESH"]["MeshSizeFromCurvature"])
    gmsh.model.mesh.generate(2)

    # export settings
    gmsh.option.set_number("Mesh.StlOneSolidPerSurface",2)

    # export stl
    gmsh.write(os.path.abspath(stepFile).split('.')[0]+".stl")
    #Clear all phsical groups
    gmsh.model.removePhysicalGroups([])
    #Create physical group for each interface volume pair
    uniqueInterfaceNames = set(interfaceNames)
    # interface_regions = [] # This will be used in the foamDict script
    # interface_patches = [] # This will be used in the foamDict script
    # interface_fn = [] # This will be used in the foamDict script
    
    
    # interfaces not in snappy step surfaces
    volPair = [] # This will be used in the foamDict script
    uniqueInterfaceNamesList = []
    for i, element in enumerate(uniqueInterfaceNames):
        patches = []
        for j, name in enumerate(interfaceNames):
            if interfaceList[j][1] in patch_tags:
                continue
            elif name == element:
                # add to physical group
                # gmsh.model.addPhysicalGroup(2,[interfaceList[j][1]],-1,interfaceNames[j])
                # interface_regions.append(interfacePatchNames[j]) # This will be used in the foamDict script
                # interface_fn.append(element) # This will be used in the foamDict script
                # volPair.append(interfaceVolPair[j]) # This will be used in the foamDict script
                patches.append(interfaceList[j][1]) # This will be used in the foamDict script
            else:
               continue
        if not patches: # skip adding to physical group and lists if patch list is empty
            continue
        volPair.append(interfaceVolPair[j])
        uniqueInterfaceNamesList.append(element)
        gmsh.model.addPhysicalGroup(2,patches,-1,element)
        gmsh.write(os.path.join(geoPath,element+".stl"))
        gmsh.model.removePhysicalGroups([])
        # interface_patches.append(patches) # This will be used in the foamDict script

    # interfaces in snappy step surfaces
    
    for key in snappyStepGroups["surfaces"]:
        if snappyStepGroups["surfaces"][key][0] not in external_patches:
            gmsh.model.addPhysicalGroup(2,snappyStepGroups["surfaces"][key],-1,key)
        else:
            continue
        uniqueInterfaceNamesList.append(key)
        adj = gmsh.model.getAdjacencies(2,snappyStepGroups["surfaces"][key][0])
        volPair.append([adj[0][0],adj[0][1]])
        # gmsh.model.addPhysicalGroup(2,snappyStepGroups["surfaces"][key],-1,key)
        gmsh.write(os.path.join(geoPath,key+".stl"))
        gmsh.model.removePhysicalGroups([])

    # Write shell scripts
    open("snappyStep.sh", 'w').close() # Create empty file. overwrites if exists
    open("snappyStepGenerateMesh.sh", 'w').close()
    open("snappyStepSplitMeshRegions.sh", 'w').close()
    # maybe split into one fucntion for geometry section, and nother for the points and interfaces
    # External walls
    writeFoamDictionaryGeo(os.path.splitext(os.path.basename(stepFile))[0],external_regions)
    writeRefinementRegions(os.path.splitext(os.path.basename(stepFile))[0],external_regions)
    # Interfaces
    #for i, element in enumerate(interface_regions):
    #    writeFoamDictionaryGeo(element,interface_patches[i])
    for i, element in enumerate(uniqueInterfaceNamesList):
        writeFoamDictionaryGeo(element,[]) # pass empty region list since each interface only has the single region
        writeRefinementRegions(element,[])
        #writeRefinementRegions(element, interface_patches[i])

    # Refinement Surfaces commands and get name default zone
    defaultZone = writeFoamDictionarySurf(uniqueInterfaceNamesList.copy(),volPair.copy(),VolNames,volTags,insidePoints)

    # Set external groups as type patch
    setExternalPatch(setPatchList, os.path.splitext(os.path.basename(stepFile))[0])

    # Write groups

    # if makeGroups:
    #     writeFoamDictionaryInterfaceGroups(interfacePatchNames, interfaceList, snappyStepGroups['surfaces'])
    #     writeFoamDictionaryExternalGroups(external_regions, external_tag, snappyStepGroups['surfaces'],os.path.splitext(os.path.basename(stepFile))[0])
            # This does not work due to cell zone splitting. Try using changeDictionary
    # Write mesh generation commands
    writeMeshCommands()
    writeSplitCommand(defaultZone)

    os.chmod("./snappyStep.sh",0o755) # Make shell script executable
    os.chmod("./snappyStepGenerateMesh.sh",0o755)
    os.chmod("./snappyStepSplitMeshRegions.sh",0o755)

    # See results
    if args.v:
        gmsh.fltk.run()

    # Last GMSH command
    gmsh.finalize()

#if __name__ == '__main__':
#    mainFunc()
# mainFunc()