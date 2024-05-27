import argparse
import gmsh
import os
from .readerFuncs import *
from collections import Counter
from itertools import count
import tomllib


def mainFunc():
    parser = argparse.ArgumentParser(description='Prepare STEP geometry for SnappyHexMesh using GMSH')
    parser.add_argument('-v', action='store_true')

    args = parser.parse_args()
    
    ext = [".stp", ".step", ".STP", ".STEP"]
    relPath = "./constant/geometry"
    files = []
    

    # Check for OpenFOAM case structure

    if not os.path.exists(relPath):
        print("Please run from OpenFOAM case root directory.")
        exit(1)

    # Read Config
    with open("./system/snappyStep.toml", "rb") as f:
        config = tomllib.load(f)

    for file in os.listdir(relPath):
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

    # Begin gmsh operations
    gmsh.initialize()
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit

    # retrive geometry
    print('Reading geometry')
    stepFile = os.path.join(relPath, files[0])
    gmsh.model.occ.importShapes(stepFile)
    # geoPath = os.path.split(os.path.join(relPath, files[0]))
    geoPath = relPath # Fix the need for this later ...


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
    c = Counter(interfaceNames)
    iters = {k: count(1) for k, v in c.items() if v > 1}
    interfacePatchNames = [x+"_"+str(next(iters[x])) if x in iters else x for x in interfaceNames]
    # Renaming might need to changed or done after other operations. Not sure how I need to handle multiple interfaces. Seperate patches in single  STL, seperate STL and overlap with named surfaces



    gmsh.option.set_number("Geometry.VolumeLabels",1)
    gmsh.model.occ.synchronize()

    # Mesh
    #gmsh.model.mesh.set_size
    gmsh.model.mesh.generate(2)

    # Set Physical Surfaces and Export STLs
    # export settings
    gmsh.option.set_number("Mesh.StlOneSolidPerSurface",2)
    # Start with exterior surfaces

    external_regions = [] # This will be used in the foamDict script
    for i, element in enumerate(volumes):
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
                if isExternal[k]:
                    externalList.append(bounds[k][1]) # Gets face tag


        gmsh.model.addPhysicalGroup(2,externalList,-1,VolNames[i]+"_wall")
        external_regions.append(VolNames[i]+"_wall") # This will be used in the foamDict script
    # export stl
    gmsh.write(os.path.abspath(stepFile).split('.')[0]+".stl")
    #Clear all phsical groups
    gmsh.model.removePhysicalGroups([])
    #Create physical group for each interface volume pair
    uniqueInterfaceNames = set(interfaceNames)
    interface_regions = [] # This will be used in the foamDict script
    interface_patches = [] # This will be used in the foamDict script
    volPair = [] # This will be used in the foamDict script
    for i, element in enumerate(uniqueInterfaceNames):
        patches = []
        for j, name in enumerate(interfaceNames):
            if name == element:
                # add to physical group
                gmsh.model.addPhysicalGroup(2,[interfaceList[j][1]],-1,interfacePatchNames[j])
                interface_regions.append(interfacePatchNames[j]) # This will be used in the foamDict script
                volPair.append(interfaceVolPair[j]) # This will be used in the foamDict script
                patches.append(interfacePatchNames[j]) # This will be used in the foamDict script
            else:
               continue
        gmsh.write(os.path.join(geoPath,element+".stl"))
        gmsh.model.removePhysicalGroups([])
        interface_patches.append(patches) # This will be used in the foamDict script

    # Write shell scripts
    open("snappyStep.sh", 'w').close() # Create empty file. overwrites if exists
    open("snappyStepGenerateMesh.sh", 'w').close()
    # maybe split into one fucntion for geometry section, and nother for the points and interfaces
    # External walls
    writeFoamDictionaryGeo(os.path.splitext(os.path.basename(stepFile))[0],external_regions)
    # Interfaces
    for i, element in enumerate(interface_regions):
        writeFoamDictionaryGeo(element,interface_patches[i])

    # Refinement Surfaces commands and get name default zone
    defaultZone = writeFoamDictionarySurf(interface_regions,volPair,VolNames,volTags,insidePoints)

    # Write mesh generation commands
    writeMeshCommands(defaultZone)

    os.chmod("./snappyStep.sh",0o755) # Make shell script executable
    os.chmod("./snappyStepGenerateMesh.sh",0o755)

    # See results
    if args.v:
        gmsh.fltk.run()

    # Last GMSH command
    gmsh.finalize()

#if __name__ == '__main__':
#    mainFunc()
# mainFunc()