import os
import argparse
import sys

def cellZoneRefinement():
    parser = argparse.ArgumentParser(description='Modify snappyHexMeshDict refinement based on cellzone.  Run from OpenFOAM case root directory.')
    parser.add_argument('-all' ,help='Modify all CellZones with the same refinement value, e.g. -all \'(3 3)\'') # view generated mesh in gmsh
    if "-all" not in sys.argv:
        parser.add_argument('name_value', nargs='+', help='Enter cellZone and refinement in pairs, e.g. ZoneA \'(3 3)\'')
    args = parser.parse_args()

    if not os.path.exists('./system/snappyHexMeshDict'):
        print("Could not find snappyHexMeshDict. Make sure file exists and please run from OpenFOAM case root directory.")
        exit(1)

    nargs = len(args.name_value)
    if nargs % 2 != 0:
        print("invalid number of inputs. Exiting.")
        exit(1)
    for iter in range(0, nargs, 2):
        setRefinement(args.name_value[iter], args.name_value[iter+1])

def setRefinement(cellZone: str, value: str):
    with open('./system/snappyHexMeshDict', 'r') as sHMD:
        dict_text = sHMD.read()
    print(dict_text)
    print()

if __name__ == "__main__":
    cellZoneRefinement()       
        