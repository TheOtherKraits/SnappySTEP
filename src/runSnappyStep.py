import argparse
import gmsh
import xml.etree.ElementTree as ET
import os
from readerFuncs import *
from collections import Counter
from itertools import count

parser = argparse.ArgumentParser(description='Prepare STEP geometry for SnappyHexMesh using GMSH')
parser.add_argument('filename', metavar='*.stp', type=str, nargs=1,help='STEP file to be processed')

args = parser.parse_args()
print(args.filename)

# Begin gmsh operations
gmsh.initialize()
gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit

# retrive geometry
print('Reading geometry')
gmsh.model.occ.importShapes(args.filename[0])
geoPath = os.path.split(args.filename[0])

# Apply coherence to remove duplicate surfaces, edges, and points
print('Imprinting features and removing duplicate faces')
gmsh.model.occ.fragment([],[])
gmsh.model.occ.removeAllDuplicates()
gmsh.model.occ.synchronize()

# Get Geometry Names
print('Getting Names of Bodies and Surfaces')
volumes = gmsh.model.getEntities(3)
VolNames = regexStepBodyNames(args.filename[0])
print("Found Volumes: ",VolNames)
for i, element in enumerate(VolNames): # loop through all Volume entries
    gmsh.model.setEntityName(3,volumes[i][1],element) # Adds names to gmsh entites
print('Volume names assigned')
# tree = ET.parse(os.path.join(geoPath[0],'NamedGeometry.xml')) # Read XML file that defines volumes and Named Faces
# root = tree.getroot()
# for Volume in root.findall("Volume"): # loop through all Volume entries
#     #print(Volume.get('name'))
#     #print(Volume.find('Tag').text)
#     gmsh.model.setEntityName(3,int(Volume.find("Tag").text),Volume.get('name')) # Adds names to gmsh entites


# Loop through surfaces. Each surface may have more than one tag

# Find shared boundaries
print('Identifying contacts')

geoBounds = gmsh.model.getBoundary(volumes,False,False,False)
Interfaces = {x for x in geoBounds if geoBounds.count(x) > 1} # Checks each index for more than one item the list, if so added to the set
print(len(Interfaces), "contacting face(s) found.")
# get volumes of interfaces
interfaceVolPair = [] # List of dim, tag pairs of volume pairs of each interface
interfaceNames = []
for i, element in enumerate(Interfaces):
    adj = gmsh.model.getAdjacencies(element[0],element[1])
    interfaceVolPair.append([[3,adj[0][0]],[3,adj[0][1]]])
    namePair = [gmsh.model.getEntityName(3,adj[0][0]), gmsh.model.getEntityName(3,adj[0][1])] # Gets names of both volumes
    namePair.sort # sorts names for consistency
    interfaceNames.append(namePair[0] + "_to_" + namePair[1]) #Adds name to list

# Rename repeated interface names    
c = Counter(interfaceNames)
iters = {k: count(1) for k, v in c.items() if v > 1}
interfaceNames = [x+"_"+str(next(iters[x])) if x in iters else x for x in interfaceNames]
# Renaming might need to changed or done after other operations. Not sure how I need to handle multiple interfaces. Seperate patches in single STL, seperate STL and overlap with named surfaces



gmsh.option.set_number("Geometry.VolumeLabels",1)
gmsh.model.occ.synchronize()

# Mesh
#gmsh.model.mesh.set_size
gmsh.model.mesh.generate(2)

# Set Physical Surfaces and Export STLs
# Start with exterior surfaces

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


# See results
gmsh.fltk.run()

# Last GMSH command
gmsh.finalize()