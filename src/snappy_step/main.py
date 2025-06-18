import argparse
import gmsh
import os
from .readerFuncs import *
import tomllib


def run_snappy_step(file_name,v,vf):
    
    
    ext = [".stp", ".step", ".STP", ".STEP"]
    geo_path = getGeoPath()
    files = []

    # Check for OpenFOAM case structure

    if geo_path is None:
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
        edge_mesh = config["snappyHexMeshSetup"]["edgeMesh"]
        if edge_mesh:
            print("Edge mesh files will be generated")
    else:
        edge_mesh = False
    
    # Find geometry files
    if file_name is None:
        for file in os.listdir(geo_path):
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
            step_file = os.path.join(geo_path, files[0])
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
        
    make_groups = False
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
    gmsh.model.occ.importShapes(step_file,False)
    gmsh.model.occ.synchronize()

    # How many volumes before coherence
    n_vol = len(gmsh.model.getEntities(3))

    # Remove extra names face names. Prevent issues when tags change.
    removeFaceLabelsOnVolumes(gmsh)

    # Apply coherence to remove duplicate surfaces, edges, and points
    print('Imprinting features and removing duplicate faces')
    if n_vol > 1:
        gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(3))
        gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(2))
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    # Check coherence results
    volumes = gmsh.model.getEntities(3)
    if len(volumes) != n_vol:
        print("Coherence changed number of volumes. Check geometry. Exiting")
        gmsh.finalize()
        exit(1)

    # Get geometric bounds for blockMesh
    model_bounding_box = gmsh.model.get_bounding_box(-1,-1)

    # Get Geometry Names
    print('Getting Names of Bodies')
    vol_names, vol_tags = getVolumeNames(gmsh)
    print("Found Volumes:")
    print(*vol_names)


    # Get surfaces
    print("Getting Surface Names")
    surf_names, surf_tags, patch_tags = getSurfaceNames(gmsh)

    if len(surf_names)>0:
        print("Found Surfaces:")
        print(*surf_names)
        make_groups = True
        snappy_step_groups_dict = dict(zip(surf_names, surf_tags)) # Combine into dictionary for easy acces
  
    # print(len(outDimTagsMap[:][:]))
    # if any(len(sub_list) > 1 for sub_list in outDimTagsMap):
    #     print("geometry tags of face groups changed. Support for this to be added later. Please fully imprint surfaces in CAD. Exiting")
    #     exit(1)

    # Assign surface names
    for iter, group in enumerate(surf_tags):
        for surf in group:
            gmsh.model.setEntityName(2,surf[1],surf_names[iter])

    for i, element in enumerate(vol_names): # loop through all Volume entries
        gmsh.model.setEntityName(3,vol_tags[i][1],element) # Adds names to gmsh entites
    print('Volume names assigned')

    print("Getting locationInMesh coordinates")
    # get inside points for each volume
    point_inside = []
    for i, element in enumerate(volumes):
        print(vol_names[i]+":")
        if "locationInMesh" in config and vol_names[i] in config["locationInMesh"]:
            point_inside.append(config["locationInMesh"][vol_names[i]])
            print("Using coordinates in config file.")
        else:
            point_inside.append(getLocationInMesh(gmsh,element[1]))
    
    print('Identifying contacts')

    geo_bounds = gmsh.model.getBoundary(volumes,False,False,False)
    interfaces = {x for x in geo_bounds if geo_bounds.count(x) > 1} # Checks each index for more than one item the list, if so added to the set
    print(len(interfaces), "contacting face(s) found.")
    # get volumes of interfaces
    interface_vol_pair = [] # List of dim, tag pairs of volume pairs of each interface
    interface_names = []
    interface_list = []
    for element in interfaces:
        adj = gmsh.model.getAdjacencies(element[0],element[1])
        interface_vol_pair.append([adj[0][0],adj[0][1]])
        name_pair = [gmsh.model.getEntityName(3,adj[0][0]), gmsh.model.getEntityName(3,adj[0][1])] # Gets names of both volumes
        name_pair.sort # sorts names for consistency
        interface_names.append(name_pair[0] + "_to_" + name_pair[1]) #Adds name to list
        interface_list.append(element) # List rather than set for use later

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
        any_external = False # Don't need to make entry in dictionary if there are no external surfaces for this volume
        bounds = gmsh.model.getBoundary([element],True,False,False)
        is_external = []
        for j, face in enumerate(bounds):
            # Find surfaces that bound more than one volume
            if face in interfaces:
                is_external.append(False)
            else:
                is_external.append(True)
        if any(is_external):
            external_list = []
            for k, face in enumerate(bounds):
                # print([surfTag for surfTag in surf_tags])
                # print([item for sub_list in surf_tags for item in sub_list])
                if (2,face[1]) in [item for sub_list in surf_tags for item in sub_list] and is_external[k]:
                # if face[1] in surf_tags and is_external[k]:
                # if face[1] in [surfTag[1] for surfTag in surfTagPairs] and is_external[k]:
                    external_patches.append(face[1])
                elif is_external[k]:
                    external_list.append(face[1]) # Gets face tag
                    if not any_external:
                        any_external = True
                    # counter = counter + 1        
        
        if any_external: # Don't need to make entry in dictionary if there are no external surfaces for this volume
            external_regions.append(vol_names[i]+"_default") # This will be used in the foamDict script
            gmsh.model.addPhysicalGroup(2,external_list,-1,vol_names[i]+"_default")
            patches_for_edge_mesh.extend(external_list)

    # Check that all patches are either internal or external
    if make_groups:
        for key in snappy_step_groups_dict:
            res = set(snappy_step_groups_dict[key]).issubset(external_patches)
            if res:
                continue
            else:
                if any(x in snappy_step_groups_dict[key] for x in external_patches):
                    print("Mismatched patch groups found. Exiting")
                    gmsh.finalize()
                    exit(1)

        # Add external patches to physical groups
        set_patch_list = []
        for key in snappy_step_groups_dict:
            if snappy_step_groups_dict[key][0][1] in external_patches:
                gmsh.model.addPhysicalGroup(2,[el[1] for el in snappy_step_groups_dict[key]],-1,key)
                external_regions.append(key)
                set_patch_list.append(key)
                patches_for_edge_mesh.extend([el[1] for el in snappy_step_groups_dict[key]])
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
    print("Writing ." + step_file.split('.')[1]+".stl")
    gmsh.write(os.path.relpath(step_file).split('.')[0]+".stl")
    print("Done.")
    #Clear all phsical groups
    gmsh.model.removePhysicalGroups([])
    # Write corresponding edge mesh
    if edge_mesh:
        writeEdgeMesh(gmsh,patches_for_edge_mesh,os.path.basename(step_file).split('.')[0],geo_path)
    #Create physical group for each interface volume pair
    unique_interface_names_set = set(interface_names)
    
    # interfaces not in snappy step surfaces
    vol_pair = [] # This will be used in the foamDict script
    unique_interface_names_list = []
    for element in unique_interface_names_set:
        patches = []
        for j, name in enumerate(interface_names):
            if interface_list[j][1] in patch_tags:
                continue
            elif name == element:
                patches.append(interface_list[j][1]) # This will be used in the foamDict script
                idx = j
            else:
               continue
        if not patches: # skip adding to physical group and lists if patch list is empty
            continue
        vol_pair.append(interface_vol_pair[idx])
        unique_interface_names_list.append(element)
        gmsh.model.addPhysicalGroup(2,patches,-1,element)
        print("Writing " + os.path.join(geo_path,element+".stl"))
        gmsh.write(os.path.join(geo_path,element+".stl"))
        print("Done.")
        gmsh.model.removePhysicalGroups([])
        if edge_mesh:
            writeEdgeMesh(gmsh, patches, element, geo_path)
    

    # interfaces in snappy step surfaces
    if make_groups:
        for key in snappy_step_groups_dict:
            if snappy_step_groups_dict[key][0][1] not in external_patches:
                gmsh.model.addPhysicalGroup(2,[el[1] for el in snappy_step_groups_dict[key]],-1,key)
                patches_for_edge_mesh = [el[1] for el in snappy_step_groups_dict[key]]
            else:
                continue
            unique_interface_names_list.append(key)
            adj = gmsh.model.getAdjacencies(2,snappy_step_groups_dict[key][0][1])
            vol_pair.append([adj[0][0],adj[0][1]])
            setAdj = set([adj[0][0],adj[0][1]])
            for iter, tag in enumerate(snappy_step_groups_dict[key]):
                if iter != 0:
                    compAdj = gmsh.model.getAdjacencies(2,snappy_step_groups_dict[key][iter][1])
                    # if not setAdj == set([compAdj[iter][0],compAdj[iter][1]]):
                    if not setAdj == set([compAdj[0][0],compAdj[0][1]]):
                        print("interface group " + key + " contains surfaces between multiple volume pairs. Please split into groups of single volume pairs. Exiting.")
                        gmsh.finalize()
                        exit(1)

            print("Writing " + os.path.join(geo_path,key+".stl"))
            gmsh.write(os.path.join(geo_path,key+".stl"))
            print("Done.")
            gmsh.model.removePhysicalGroups([])
            # Write corresponding edge mesh
            if edge_mesh:
                writeEdgeMesh(gmsh, patches_for_edge_mesh, key, geo_path)

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
    write_sHMD_Geo(new_sHMD,os.path.splitext(os.path.basename(step_file))[0],external_regions)
    write_sHMD_refinement_surfaces(new_sHMD,os.path.splitext(os.path.basename(step_file))[0],external_regions, old_sHMD, config["snappyHexMeshSetup"]["defaultSurfaceRefinement"])
    # Interfaces
    # for i, element in enumerate(unique_interface_names_list):
    for element in unique_interface_names_list:
        # pass empty region list since each interface only has the single region
        write_sHMD_Geo(new_sHMD,element,[])
        write_sHMD_refinement_surfaces(new_sHMD,element,[], old_sHMD, config["snappyHexMeshSetup"]["defaultSurfaceRefinement"])

    # Refinement Surfaces commands and get name default zone
    # surfReturn = writeFoamDictionarySurf(unique_interface_names_list.copy(),vol_pair.copy(),vol_names,[el[1] for el in vol_tags],point_inside)
    default_zone = write_sHMD_refinement_surfaces_cellZone(new_sHMD,unique_interface_names_list.copy(),vol_pair.copy(),vol_names,[el[1] for el in vol_tags],point_inside)

    # Set external groups as type patch
    if make_groups:
        set_sHMD_external_patch(new_sHMD,set_patch_list, os.path.splitext(os.path.basename(step_file))[0])
    print("Done.")
    if edge_mesh:
        # commands.extend(writeFoamDictionaryEdge([os.path.splitext(os.path.basename(step_file))[0]] + unique_interface_names_list))
        write_sHMD_feature_edges(new_sHMD,[os.path.splitext(os.path.basename(step_file))[0]] + unique_interface_names_list, old_sHMD, config["snappyHexMeshSetup"]["defaultEdgeRefinement"])
    # Write dictionaries
    write_sHMD(new_sHMD)
    if config["snappyHexMeshSetup"]["generateBlockMeshDict"]:
        write_block_mesh_dict(model_bounding_box,config["snappyHexMeshSetup"]["backgroundMeshSize"])
    if not os.path.isfile("./system/meshQualityDict"): # Write base meshMeshQualityDict if one does not exits
        write_mesh_quality_dict()
    
    # Write mesh split command
    writeSplitCommand(default_zone)
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
    run_snappy_step(args.file, args.v,args.vf)

def snappystep(file_name = None):
    run_snappy_step(file_name,False,False)

if __name__ == "__main__":
    mainFunc()