import argparse
import os
from .readerFuncs import *
from .geometry import *

def run_snappy_step(file_name,v,vf):
    
    extension = [".stp", ".step", ".STP", ".STEP"]
    geometry_path = get_geometry_path()
    files = []

    # Check for OpenFOAM case structure

    if geometry_path is None:
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
            new_key = validate_names([key])
            config["locationInMesh"][new_key[0]] = config["locationInMesh"].pop(key)

    else:
        config["locationInMesh"] = []

    if "edgeMesh" in config["snappyHexMeshSetup"]:
        edge_mesh = config["snappyHexMeshSetup"]["edgeMesh"]
        if edge_mesh:
            print("Edge mesh files will be generated")
    else:
        edge_mesh = False
    
    # Find geometry files
    if file_name is None:
        for file in os.listdir(geometry_path):
            if file.endswith(tuple(extension)):
                files.append(file)
    
        if len(files) == 0:
            print("No step file found in constant/(geometry||triSurface) directory. Exiting.")
            exit(1)
        elif len(files) > 1:
            print("More than one step file found. Please remove or rename other files, or specify the filepath to read with the -file arguemnt. Exiting.")
            exit(1)   
        else:
            print(files[0]+" found")
            step_file = os.path.join(geometry_path, files[0])
    else:
        if os.path.isabs(file_name):
            if os.path.isfile(file_name):
                step_file = file_name
            else:
                print(file_name + " is not a file. Exiting.")
                exit(1)
        else:
            if os.path.isfile(file_name):
                 step_file = file_name
            else:
                print(file_name + " is not a file. Exiting.")
                exit(1)
           

    # Begin gmsh operations
    gmsh.initialize()
    load_step_file(gmsh, step_file, config)
    imprint_geometry(gmsh)
    validate_gmsh_names(gmsh)
    volumes, interfaces = process_geometry(gmsh, config)
    default_volume = assign_cell_zones_to_interfaces(volumes,interfaces)
    print(volumes)
    print(interfaces)



    




def snappy_step_cleanup():
    gmsh.finalize()
    return

def main_func():
    parser = argparse.ArgumentParser(description='Process STEP geometry to generate STL files for SnappyHexMesh using GMSH')
    parser.add_argument('-v', action='store_true',help='Display generated surface mesh after genration') # view generated mesh in gmsh
    parser.add_argument('-vf', action='store_true',help='Display faces and labels. User can choose to continue or stop after inspecting output') # view faces after coherence and don't generate mesh
    parser.add_argument('-file',help='Specify filename if not in constant/(geometry||triSurface) directory or multiple step files are present')

    args = parser.parse_args()
    run_snappy_step(args.file, args.v,args.vf)

def snappy_step(file_name = None):
    run_snappy_step(file_name,False,False)

if __name__ == "__main__":
    main_func()