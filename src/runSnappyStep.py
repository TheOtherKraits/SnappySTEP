import argparse
import gmsh
import xml.etree.ElementTree as ET
import os
from readerFuncs import *

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
for i, element in enumerate(Interfaces):
    adj = gmsh.model.getAdjacencies(element[0],element[1])
    interfaceVolPair.append([[2,adj[0][0]],[2,adj[0][1]]])

gmsh.option.set_number("Geometry.VolumeLabels",1)
gmsh.model.occ.synchronize()

# See results
gmsh.fltk.run()

# Last GMSH command
gmsh.finalize()