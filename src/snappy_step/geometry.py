import gmsh
import re
import math

class Volume:
    """ TODO """
    def __init__(self, tag: int):
        self._tag: int = tag
        self.exterior_tags: list[int] = []
        self.interface_tags: list[int] = []
        self.exterior_patches: dict = {}
        self.exterior_patch_edges: dict = {}
        self.interface_patches: list[int] = []
        self.name = gmsh.model.getEntityName(3,tag)
        self.face_dim_tags: list[tuple[int,int]] = gmsh.model.getBoundary([(3,tag)], False, False, False)
        self.inside_point: list[float] = []
        for dim_tag in self.face_dim_tags:
            if len(gmsh.model.getAdjacencies(2,dim_tag[1])[0]) == 1:
                self.exterior_tags.append(dim_tag[1])
            else:
                self.interface_tags.append(dim_tag[1])
        
        for tag in self.exterior_tags:
            name = gmsh.model.getEntityName(2, tag)
            if not name:
                if self.name+"_default" in self.exterior_patches:
                    self.exterior_patches[self.name+"_default"].append(tag)
                    self.exterior_patch_edges[self.name+"_default"].update(gmsh.model.get_adjacencies(2,tag)[1])
                else:
                    self.exterior_patches[self.name+"_default"] = [tag]
                    self.exterior_patch_edges[self.name+"_default"] = set(gmsh.model.get_adjacencies(2,tag)[1])

            elif name in self.exterior_patches:
                self.exterior_patches[name].append(tag)
                self.exterior_patch_edges[name].update(gmsh.model.get_adjacencies(2,tag)[1])
            else:
                self.exterior_patches[name] = [tag]
                self.exterior_patch_edges[name] = set(gmsh.model.get_adjacencies(2,tag)[1])

    def get_inside_point(self, config: dict):
        """ TODO """
        if "locationInMesh" in config and self.name in config["locationInMesh"]:
            self.inside_point =  config["locationInMesh"][self.name]
            print(f"Using coordiantes in config file for {self.name}.")
        else:
            self.inside_point = get_location_in_mesh(self)
        
class Interface:
    """ TODO """
    def __init__(self, volume_1: Volume, volume_2: Volume, name:str, face_tags: list[int], edge_tags: set[int]):
        self.volume_pair: set[Volume] = {volume_1, volume_2}
        self.face_tags: list[int] = face_tags
        self.name: str = name
        self.edge_tags: set[int] = edge_tags
        self.cell_zone_volume: Volume|None = None
        

def process_geometry(config: dict):
    """ TODO """
    volumes: list[Volume] = []
    interfaces: list[Interface] = []
    volume_dim_tags = gmsh.model.getEntities(3)
    for dim_tag in volume_dim_tags:
        volumes.append(Volume(dim_tag[1]))
    for element in volumes:
        element.get_inside_point(config)
    for index_a, volume_a in enumerate(volumes):
        for index_b, volume_b in enumerate(volumes):
            if index_b <= index_a:
                continue
            overlap = list(set(volume_a.interface_tags) & set(volume_b.interface_tags))
            if len(overlap)>0:
                volume_name_pair = [volume_a.name, volume_b.name]
                volume_name_pair.sort()
                default_interface_name = volume_name_pair[0]+"_"+volume_name_pair[1]+"_interface"
                groups = {}
                for tag in overlap:
                    name = gmsh.model.getEntityName(2, tag)
                    if not name:
                        if default_interface_name not in groups:
                            groups[default_interface_name] = [tag]
                        else:
                            groups[default_interface_name].append(tag)
                    else:
                        if name not in groups:
                            groups[name] = [tag]
                        else:
                            groups[name].append(tag)
                for interface_name in groups:
                    edges = set()
                    for face in groups[interface_name]:
                        edges.update(set(gmsh.model.getAdjacencies(2, face)[1]))
                    interfaces.append(Interface(volume_a,volume_b,interface_name,groups[interface_name],edges))
                    volume_a.interface_patches.append(interfaces[-1])
                    volume_b.interface_patches.append(interfaces[-1])
    return volumes, interfaces


def get_location_in_mesh(entity: Volume):
    """ TODO """
    coordinates = []
    # First try center of mass
    coordinates = list(gmsh.model.occ.getCenterOfMass(3,entity._tag))
    if check_coordinate(entity, coordinates):
        print("Found by center of mass")
        print(coordinates)
        return coordinates
    # try center of bounding box
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(3,entity._tag)
    coordinates = [(xmax+xmin)/2,(ymax+ymin)/2,(zmax+zmin)/2]

    if check_coordinate(entity, coordinates):
        print("Found by bounding box center")
        print(coordinates)
        return coordinates
    # sweep through grids, increasingly fine. Choosing plane in cernter, sweeping though 2d locations on grid
    orders = [0, 1, 2]
    for order in orders: # coarse grid to fine grid
        points, spacing = generate_search_grid(entity, order)
        print(f'Grid search order {order+1}')
        for xi in points[0]:
            for yi in points[1]:
                for zi in points[2]:
                    coordinates = [xi, yi, zi]
                    if check_coordinate(entity, coordinates):
                        coordinates = local_grid_search(entity, coordinates, spacing)
                        print("Found by grid search")
                        print(coordinates)
                        return coordinates
    print("Point not found.")
    exit(1)

def check_coordinate(entity: Volume, coordinates: list[float]) -> bool | float:
    if gmsh.model.isInside(3,entity._tag,coordinates):
        distances = []
        for face in entity.exterior_tags + entity.interface_tags:
            closest_point = gmsh.model.getClosestPoint(2,face,coordinates)[0]
            distances.append(math.sqrt((closest_point[0] - coordinates[0])**2 + (closest_point[1] - coordinates[1])**2 + (closest_point[2] - coordinates[2])**2))
            if distances[-1] < 1e-6:
                return False
        return min(distances)
    else:
        return False

def local_grid_search(entity: Volume, coordinates: list[float], spacing:float) -> list[float]:
    print('Intial coordinate found. Looking for optimized point.')
    x = linspace(coordinates[0] - spacing, coordinates[0]+ spacing, 11)
    y = linspace(coordinates[1] - spacing, coordinates[1]+ spacing, 11)
    z = linspace(coordinates[2] - spacing, coordinates[2]+ spacing, 11)
    max_distance = 0
    percent = 0
    for xi in x:
        for yi in y:
            for zi in z:
                distance = check_coordinate(entity, [xi, yi, zi])
                if distance > max_distance:
                    max_distance = distance
                    new_coordinates = [xi, yi, zi]
        percent = percent+10
        print(f'{percent}%')
    print ("done.")
    return new_coordinates

def validate_name(name: str):
    """ TODO """
    if name.startswith("."):
        name = name.lstrip(".")
    name = name.split("/")[-1]
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    return name

def linspace(a, b, n):
    """ TODO """
    diff = (float(b) - a)/(n - 1)
    return [diff * i + a  for i in range(1, n-1)] # Skips first and last

def generate_search_grid(entity: Volume, order: int):
    """ TODO """
    x_min, y_min, z_min, x_max, y_max, z_max = gmsh.model.getBoundingBox(3,entity._tag)
    n_divisons = [9, 99, 999]
    mins = [x_min, y_min, z_min]
    deltas = [x_max - x_min, y_max - y_min, z_max - z_min]
    spacing = min(deltas)/n_divisons[order]
    points = [[],[],[]]
    for dim in [0, 1, 2]:
        points[dim] = [deltas[dim]/2 + mins[dim], deltas[dim]/2 + mins[dim] + spacing, deltas[dim]/2 + mins[dim] - spacing]
        new_points = [points[dim][-2] + spacing, points[dim][-1] - spacing]
        while new_points[-1] > mins[dim]:
            points[dim].extend(new_points)
            new_points = [points[dim][-2] + spacing, points[dim][-1] - spacing]
    return points, spacing

def validate_gmsh_names():
    """ TODO """
    dim_tags = gmsh.model.getEntities(-1)
    for dim_tag in dim_tags:
        name = gmsh.model.getEntityName(dim_tag[0], dim_tag[1])
        if name:
            name = validate_name(name)
            gmsh.model.setEntityName(dim_tag[0], dim_tag[1], name)

def load_step_file(file_path, config):
    """ TODO """
    gmsh.option.setString('Geometry.OCCTargetUnit', 'M') # Set meters as working unit
    # Set Import Scaling
    if "gmsh" in config:
        if "scaling" in config["gmsh"]:
            gmsh.option.setNumber("Geometry.OCCScaling",config["gmsh"]["scaling"])
    print('Reading geometry')
    gmsh.model.occ.importShapes(file_path,False)
    gmsh.model.occ.synchronize()

def imprint_geometry():
    """ TODO """
    # How many volumes before coherence
    number_volumes = len(gmsh.model.getEntities(3))

    # Remove extra names face names. Prevent issues when tags change.
    remove_face_labels_on_volumes()

    # Apply coherence to remove duplicate surfaces, edges, and points
    print('Imprinting features and removing duplicate faces')
    if number_volumes > 1:
        gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(3))
        gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.fragment(gmsh.model.occ.getEntities(3),gmsh.model.occ.getEntities(2))
    gmsh.model.occ.removeAllDuplicates()
    gmsh.model.occ.synchronize()

    # Check coherence results
    volumes = gmsh.model.getEntities(3)
    if len(volumes) != number_volumes:
        print("Coherence changed number of volumes. Check geometry. Exiting")
        gmsh.finalize()
        exit(1)

def remove_face_labels_on_volumes():
    """ TODO """
    faces = gmsh.model.getEntities(2)
    for face in faces:
        adjacent = gmsh.model.getAdjacencies(face[0],face[1])
        if adjacent[0].size > 0:
            name = gmsh.model.getEntityName(face[0],face[1])
            if name is not None:
                gmsh.model.removeEntityName(name)
                print("removed "+ name)

def assign_cell_zones_to_interfaces(volumes:list[Volume]) -> Volume:
    """ TODO """
    volumes.sort(key=lambda x: len(x.interface_patches), reverse=False)
    for element in volumes:
        if element == volumes[-1]:
            return element
        for surface in element.interface_patches:
            if surface.cell_zone_volume is None:
                surface.cell_zone_volume = element
                break
            else:
                continue
                
def generate_surface_mesh(config: dict):
    """ TODO """
    print("Generating Surface Mesh")
    gmsh.option.setNumber("Mesh.Algorithm",config["gmsh"]["meshAlgorithm"])
    gmsh.option.setNumber("Mesh.MeshSizeFactor",config["gmsh"]["meshSizeFactor"])
    gmsh.option.setNumber("Mesh.MeshSizeMin",config["gmsh"]["meshSizeMin"])
    gmsh.option.setNumber("Mesh.MeshSizeMax",config["gmsh"]["meshSizeMax"])
    gmsh.option.setNumber("Mesh.MeshSizeFromCurvature",config["gmsh"]["meshSizeFromCurvature"])
    gmsh.model.mesh.generate(2)

    # export settings
    gmsh.option.set_number("Mesh.StlOneSolidPerSurface",2)

        
