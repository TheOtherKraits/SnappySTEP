import argparse
import gmsh
import os
from .readerFuncs import *
import tomllib


def runSnappyStep(file_name,v,vf):
    
    
    ext = [".stp", ".step", ".STP", ".STEP"]
    geoPath = getGeoPath()
    files = []

    # Check for OpenFOAM case structure

    if geoPath is None:
        print("Please run from OpenFOAM case root directory.")
        exit(1)

    # Read Config

    try:
        config = read_snappy_step_dict()
    except:
        print("There seems to be a problem with snappyStepDict. Please check for format errors. Exiting.")
        exit(1)

    if "locationInMesh" in config:  
        print("Using locationInMesh coordinates defined in config")
        for key in config["locationInMesh"]:
            new_key = validateNames([key])
            config["locationInMesh"][new_key[0]] = config["locationInMesh"].pop(key)

    else:
        config["locationInMesh"] = []

    if "edgeMesh" in config["snappyHexMeshSetup"]:
        edgeMesh = config["snappyHexMeshSetup"]["edgeMesh"]
        if edgeMesh:
            print("Edge mesh files will be generated")
    else:
        edgeMesh = False
    
    # Find geometry files
    if file_name is None:
        for file in os.listdir(geoPath):
            if file.endswith(tuple(ext)):
                files.append(file)
    
        if len(files) == 0:
            print("No step file found in constant/(geometry||triSurface) directory. Exiting.")
            exit(1)
        elif len(files) > 1:
            print("More than one step file found. Please remove or rename other files, or specify the filepath to read with the -file arguemnt. Exiting.")
            exit(1)   
        else:
            print(files[0]+" found")
            stepFile = os.path.join(geoPath, files[0])
    else:
        if os.path.isabs(file_name):
            if os.path.isfile(file_name):
                stepFile = file_name
            else:
                print(file_name + " is not a file. Exiting.")
                exit(1)
        else:
            if os.path.isfile(file_name):
                 stepFile = file_name
            else:
                print(file_name + " is not a file. Exiting.")
                exit(1)
        
    makeGroups = False
    patch_tags = []    

    # Begin gmsh operations
    gmsh.initialize()
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit
    
    # Set Import Scaling
    if "gmsh" in config:
        if "scaling" in config["gmsh"]:
            gmsh.option.setNumber("Geometry.OCCScaling",config["gmsh"]["scaling"])


    # retrive geometry
    print('Reading geometry')
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
        gmsh.finalize()
        exit(1)

    # Get geometric bounds for blockMesh
    model_bounding_box = gmsh.model.get_bounding_box(-1,-1)

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
    locationInMesh = []
    for i, element in enumerate(volumes):
        print(volNames[i]+":")
        if "locationInMesh" in config and volNames[i] in config["locationInMesh"]:
            locationInMesh.append(config["locationInMesh"][volNames[i]])
            print("Using coordinates in config file.")
        else:
            locationInMesh.append(getLocationInMesh(gmsh,element[1]))
    
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
    if vf:
        gmsh.option.set_number("Geometry.VolumeLabels",1)
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.option.set_number("Geometry.LabelType",3)
        print("gmsh window open. Close gmsh window to continue.")
        gmsh.fltk.run()
        ans = ask_yes_no("Would you like to continue?")
        gmsh.fltk.finalize()
        if not ans:
            gmsh.finalize()
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
                    gmsh.finalize()
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
    gmsh.option.setNumber("Mesh.Algorithm",config["gmsh"]["meshAlgorithm"])
    gmsh.option.setNumber("Mesh.MeshSizeFactor",config["gmsh"]["meshSizeFactor"])
    gmsh.option.setNumber("Mesh.MeshSizeMin",config["gmsh"]["meshSizeMin"])
    gmsh.option.setNumber("Mesh.MeshSizeMax",config["gmsh"]["meshSizeMax"])
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature",config["gmsh"]["meshSizeFromCurvature"])
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
    if edgeMesh:
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
        if edgeMesh:
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
                        gmsh.finalize()
                        exit(1)

            print("Writing " + os.path.join(geoPath,key+".stl"))
            gmsh.write(os.path.join(geoPath,key+".stl"))
            print("Done.")
            gmsh.model.removePhysicalGroups([])
            # Write corresponding edge mesh
            if edgeMesh:
                writeEdgeMesh(gmsh, patches_for_edge_mesh, key, geoPath)

    # Write snappyHexMeshDic
    
    print("Configuring snappyHexMeshDict")
    old_sHMD , new_sHMD = initialize_sHMD()
    if "multiRegionFeatureSnap" in config["snappyHexMeshSetup"]:
        new_sHMD["snapControls"]["multiRegionFeatureSnap"] = config["snappyHexMeshSetup"]["multiRegionFeatureSnap"]
    else:
        try:
            new_sHMD["snapControls"]["multiRegionFeatureSnap"] = old_sHMD["snapControls"]["multiRegionFeatureSnap"]
        except:
            new_sHMD["snapControls"]["multiRegionFeatureSnap"] = False

    # External walls
    write_sHMD_Geo(new_sHMD,os.path.splitext(os.path.basename(stepFile))[0],external_regions)
    write_sHMD_refinement_surfaces(new_sHMD,os.path.splitext(os.path.basename(stepFile))[0],external_regions, old_sHMD, config["snappyHexMeshSetup"]["defaultSurfaceRefinement"])
    # Interfaces
    # for i, element in enumerate(uniqueInterfaceNamesList):
    for element in uniqueInterfaceNamesList:
        # pass empty region list since each interface only has the single region
        write_sHMD_Geo(new_sHMD,element,[])
        write_sHMD_refinement_surfaces(new_sHMD,element,[], old_sHMD, config["snappyHexMeshSetup"]["defaultSurfaceRefinement"])

    # Refinement Surfaces commands and get name default zone
    # surfReturn = writeFoamDictionarySurf(uniqueInterfaceNamesList.copy(),volPair.copy(),volNames,[el[1] for el in volTags],locationInMesh)
    defaultZone = write_sHMD_refinement_surfaces_cellZone(new_sHMD,uniqueInterfaceNamesList.copy(),volPair.copy(),volNames,[el[1] for el in volTags],locationInMesh)

    # Set external groups as type patch
    if makeGroups:
        set_sHMD_external_patch(new_sHMD,setExternalPatch(setPatchList, os.path.splitext(os.path.basename(stepFile))[0]))
    print("Done.")
    if edgeMesh:
        # commands.extend(writeFoamDictionaryEdge([os.path.splitext(os.path.basename(stepFile))[0]] + uniqueInterfaceNamesList))
        write_sHMD_feature_edges(new_sHMD,[os.path.splitext(os.path.basename(stepFile))[0]] + uniqueInterfaceNamesList, old_sHMD, config["snappyHexMeshSetup"]["defaultEdgeRefinement"])
    # Write dictionaries
    write_sHMD(new_sHMD)
    if config["snappyHexMeshSetup"]["generateBlockMeshDict"]:
        write_block_mesh_dict(model_bounding_box,config["snappyHexMeshSetup"]["backgroundMeshSize"])
    if not os.path.isfile("./system/meshQualityDict"): # Write base meshMeshQualityDict if one does not exits
        write_mesh_quality_dict()
    
    # Write mesh split command
    writeSplitCommand(defaultZone)
    os.chmod("./snappyStepSplitMeshRegions.sh",0o755)

    # See results
    if v:
        gmsh.option.set_number("Geometry.VolumeLabels",1)
        gmsh.option.set_number("Geometry.Surfaces",1)
        gmsh.option.set_number("Geometry.SurfaceLabels",1)
        gmsh.option.set_number("Geometry.LabelType",3)
        print("gmsh window open. Close gmsh window to continue.")
        gmsh.fltk.run()
        gmsh.fltk.finalize()
    print("All geometry files and scripts generated. Done.")
    # Last GMSH command
    gmsh.finalize()
    return

def snappyStepCleanup():
    gmsh.finalize()
    return

def mainFunc():
    parser = argparse.ArgumentParser(description='Process STEP geometry to generate STL files for SnappyHexMesh using GMSH')
    parser.add_argument('-v', action='store_true',help='Display generated surface mesh after genration') # view generated mesh in gmsh
    parser.add_argument('-vf', action='store_true',help='Display faces and labels. User can choose to continue or stop after inspecting output') # view faces after coherence and don't generate mesh
    parser.add_argument('-file',help='Specify filename if not in constant/(geometry||triSurface) directory or multiple step files are present')

    args = parser.parse_args()
    runSnappyStep(args.file, args.v,args.vf)

def snappystep(file_name = None):
    runSnappyStep(file_name,False,False)

if __name__ == "__main__":
    mainFunc()