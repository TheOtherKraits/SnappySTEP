import argparse
from .geometry import *
from .read_write import *

def run_snappy_step(file_name,v,vf):
    
    # Determine if in openfoam case structure and if it is .org or .com version
    geometry_path = get_geometry_path()

    # Read Config
    config = read_config()
    
    # Find geometry files
    step_file = find_geometry_file(file_name, geometry_path)
    step_name = os.path.split(step_file)[-1].split('.')[0]

    # Begin gmsh operations
    gmsh.initialize()
    load_step_file(gmsh, step_file, config)
    imprint_geometry(gmsh)
    validate_gmsh_names(gmsh)
    volumes, interfaces = process_geometry(gmsh, config)
    default_volume = assign_cell_zones_to_interfaces(volumes)
    model_bounding_box = gmsh.model.get_bounding_box(-1,-1)

    # Generate Mesh
    generate_surface_mesh(gmsh,config)

    # Write Mesh
    write_surface_meshes(gmsh, volumes, interfaces, step_name, geometry_path)
    if config["snappyHexMeshSetup"]["edgeMesh"]:
        write_edge_meshes(gmsh, volumes, interfaces, geometry_path)

    # Write Dictionaries
    old_dict, new_dict = initialize_sHMD()
    if config["snappyHexMeshSetup"]["generateBlockMeshDict"]:
        write_block_mesh_dict(model_bounding_box,config["snappyHexMeshSetup"]["backgroundMeshSize"])
    if not os.path.isfile("./system/meshQualityDict"): # Write base meshMeshQualityDict if one does not exits
        write_mesh_quality_dict()
    configure_sHMD_geometry(new_dict, volumes, interfaces, step_name)

    # Write mesh split command
    write_split_command(default_volume.name)
    



    




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