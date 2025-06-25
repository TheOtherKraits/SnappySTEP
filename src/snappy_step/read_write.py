import re
import os
from foamlib import FoamFile, FoamCase
import math

def get_geometry_path(): 
    geometry_path = "./constant/geometry"
    if not os.path.exists(geometry_path):
        geometry_path = "./constant/triSurface"
        if not os.path.exists(geometry_path):
            geometry_path = None
    if geometry_path is None:
        print("Please run from OpenFOAM case root directory.")
        exit(1)
    return geometry_path

def read_config()->dict:
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
    return config

def read_snappy_step_dict()->dict:
    file_path = "./system/snappyStepDict"
    file = FoamFile(file_path)
    return file.as_dict()

def find_geometry_file(file_name:str, geometry_path:str)->str:
    # Find geometry files
    extension = [".stp", ".step", ".STP", ".STEP"]
    files = []
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
    return step_file

def write_snappy_step_dict_template():
    file_path = "./system/snappyStepDict"
    file = FoamFile(file_path)
    if os.path.isfile(file_path):
        try:
            os.remove(file_path)
        except PermissionError:
            print(f"Error: Permission denied to delete '{file_path}'.")
        except OSError as e:
            print(f"Error: Could not delete '{file_path}'. Reason: {e}")
    file["gmsh"] = {"meshSizeMax": 1000, "meshSizeMin": 0,"meshSizeFactor": 1,"meshSizeFromCurvature": 90,"meshAlgorithm": 6, "scaling": 1}
    file["snappyHexMeshSetup"] = {"edgeMesh": True, "multiRegionFeatureSnap": True, "generateBlockMeshDict": True, "backgroundMeshSize": [0.01, 0.01, 0.01], "defaultSurfaceRefinement": [2, 2],"defaultEdgeRefinement": 1, "overwriteRefinements": False}
    file["locationInMesh"] = {}

def write_block_mesh_dict(bouding_box:list,dx:list[float]):
    x_len = bouding_box[3]-bouding_box[0]
    y_len = bouding_box[4]-bouding_box[1]
    z_len = bouding_box[5]-bouding_box[2]
    x_cells = math.ceil(x_len/dx[0])
    y_cells = math.ceil(y_len/dx[1])
    z_cells = math.ceil(z_len/dx[2])
    x_buffer = ((x_cells*dx[0])-x_len)/2.0
    y_buffer = ((y_cells*dx[1])-y_len)/2.0
    z_buffer = ((z_cells*dx[2])-z_len)/2.0
    vertices = [
            ["$xMin", "$yMin", "$zMin"],
            ["$xMax", "$yMin", "$zMin"],
            ["$xMax", "$yMax", "$zMin"],
            ["$xMin", "$yMax", "$zMin"],
            ["$xMin", "$yMin", "$zMax"],
            ["$xMax", "$yMin", "$zMax"],
            ["$xMax", "$yMax", "$zMax"],
            ["$xMin", "$yMax", "$zMax"]
            ]
    blocks = ["hex", [0, 1, 2, 3, 4, 5, 6, 7], ["$xCells", "$yCells", "$zCells"], "simpleGrading", [1, 1, 1]]
    fn = "./system/blockMeshDict"
    if os.path.isfile(fn):
        os.remove(fn)
    case = FoamCase(".")
    with case.block_mesh_dict as file: # Load Dict
        file["defaultPatch"]={"name":  "background", "type": "patch"}
        file["xMin"] = bouding_box[0] - x_buffer
        file["xMax"] = bouding_box[3] + x_buffer
        file["yMin"] = bouding_box[1] - y_buffer
        file["yMax"] = bouding_box[4] + y_buffer
        file["zMin"] = bouding_box[2] - z_buffer
        file["zMax"] = bouding_box[5] + z_buffer
        file["xCells"] = x_cells
        file["yCells"] = y_cells
        file["zCells"] = z_cells
        file["scale"] = 1

        if "vertices" not in file.as_dict():
            file["vertices"] = vertices
        elif file["vertices"] != vertices:
            file["vertices"] = vertices
        file["blocks"] = blocks
        if "edges" not in file.as_dict():
            file["edges"] = []
            
        if "mergePatchPairs" not in file.as_dict():
            file["mergePatchPairs"] = []

def retrive_old_dict_user_entries(old_dict, new_dict):
    for key, value in old_dict:
        if key == "geometry":
            continue
        elif key == "refinementSurfaces":
            continue
        elif key == "refinementRegions":
            continue
        elif isinstance(value, dict) and key in new_dict:
            retrive_old_dict_user_entries(old_dict[key], new_dict[key])
        elif key not in new_dict and (isinstance(value, str) or isinstance(value, int) or isinstance(value, float)):
            new_dict[key] = value
        else:
            continue

def write_mesh_quality_dict():
    file_path = "./system/meshQualityDict"
    file = FoamFile(file_path)
    file["#includeEtc"] = "\"caseDicts/mesh/generation/meshQualityDict.cfg\""

def write_sHMD(new_dict):
    fn = "./system/snappyHexMeshDict"
    if os.path.isfile(fn):
        os.remove(fn)
    file = FoamFile("./system/snappyHexMeshDict") # Load snappyHexMeshDict
    for key in new_dict:
        file[key] = new_dict[key]

def ask_yes_no(question):
    while True:
        response = input(f"{question} (yes or no): ").lower()
        if response in ["yes", "y"]:
            return True
        elif response in ["no", "n"]:
            return False
        else:
            print("Invalid input. Please enter 'yes' or 'no' (y/n).")
def initialize_sHMD():
    file = FoamFile("./system/snappyHexMeshDict")
    try:
        old_sHMD = file.as_dict()
    except:
        old_sHMD = None
    new_dict = {}
    new_dict["#includeEtc"] = "\"caseDicts/mesh/generation/snappyHexMeshDict.cfg\""
    new_dict["castellatedMesh"] = check_old_dict(old_sHMD,"castellatedMesh", "on")
    new_dict["snap"] = check_old_dict(old_sHMD,"snap", "on")
    new_dict["addLayers"] = check_old_dict(old_sHMD,"addLayers", "off")
    new_dict["geometry"] = {}
    new_dict["castellatedMeshControls"] = {}
    new_dict["castellatedMeshControls"]["features"] = []
    new_dict["castellatedMeshControls"]["refinementSurfaces"] = {}
    new_dict["snapControls"] = {}
    new_dict["mergeToleance"] = check_old_dict(old_sHMD,"mergeTolerance", 1e-6)
    return old_sHMD, new_dict

def check_old_dict(old_dict, key, default_value):
    if old_dict is not None and key in old_dict:
        return old_dict[key]
    else:
        return default_value
    
def write_split_command(default_zone: str):
    commands = []
    commands.append("splitMeshRegions -cellZones -defaultRegionName " + default_zone + " -useFaceZones -overwrite")
    file_name = "snappyStepSplitMeshRegions.sh"
    write_commands(file_name,commands)
    os.chmod("./snappyStepSplitMeshRegions.sh",0o755)

def write_commands(file_name: str, commands: list):
    with open(file_name, 'w') as script:
        script.write("\n".join(commands))
    