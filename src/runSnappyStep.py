import argparse
import gmsh
import xml.etree.ElementTree as ET
import os

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
tree = ET.parse(os.path.join(geoPath[0],'NamedGeometry.xml')) # Read XML file that defines volumes and Named Faces
root = tree.getroot()
for Volume in root.findall("Volume"): # loop through all Volume entries
    #print(Volume.get('name'))
    #print(Volume.find('Tag').text)
    gmsh.model.setEntityName(3,int(Volume.find("Tag").text),Volume.get('name')) # Adds names to gmsh entites
print('Volume names assigned')

# Loop through surfaces. Each surface may have more than one tag

# Find shared boundaries
print('Identifying contacts')
volumes = gmsh.model.getEntities(3)
geoBounds = gmsh.model.getBoundary(volumes)


gmsh.model.occ.synchronize()

# See results
gmsh.fltk.run()

# Last GMSH command
gmsh.finalize()