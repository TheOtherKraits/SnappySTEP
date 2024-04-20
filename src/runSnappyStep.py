import argparse
import gmsh
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

# Apply coherence to remove duplicate surfaces, edges, and points
print('Imprinting features and removing duplicate faces')
gmsh.model.occ.fragment([],[])
gmsh.model.occ.removeAllDuplicates()
gmsh.model.occ.synchronize()
# Find shared boundaries
print('Identifying contacts')
volumes = gmsh.model.getEntities(3)
geoBounds = gmsh.model.getBoundary(volumes)


gmsh.model.occ.synchronize()

# See results
#gmsh.fltk.run()

# Last GMSH command
gmsh.finalize()