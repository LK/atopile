#%%
import hashlib
import uuid
from typing import List, Optional

import igraph as ig

#%%
def add_to_graph(g: ig.Graph, what_to_add: ig.Graph, new_reference: str, part_of: Optional[str] = None, defined_by: Optional[str] = None) -> ig.Graph:
    block_start_index = len(g.vs)
    block_root_index = find_root_vertex(what_to_add).index + block_start_index
    g += what_to_add
    g.vs[block_root_index]['ref'] = new_reference

    if part_of:
        g.add_edge(block_root_index, find_vertex_at_path(g, part_of).index, type='part_of')
    if defined_by:
        g.add_edge(block_root_index, find_vertex_at_path(g, defined_by).index, type='defined_by')
    return g


def create_instance(g: ig.Graph, instance_of_what: str, instance_ref: str, part_of_what: Optional[str] = None):
    copy_root = find_vertex_at_path(g, part_of_what)


    block_start_index = len(g.vs)
    block_root_index = find_root_vertex(instance_of_what).index + block_start_index
    g += instance_of_what
    g.vs[block_root_index]['ref'] = instance_ref

    g.add_edge(block_root_index, find_vertex_at_path(g, part_of_what).index, type='part_of')

    if part_of_what:
        g.add_edge(block_root_index, find_vertex_at_path(g, part_of_what).index, type='part_of')

    return g


def generate_uid_from_path(path: str) -> str:
    path_as_bytes = path.encode('utf-8')
    hashed_path = hashlib.blake2b(path_as_bytes, digest_size=16).digest()
    return uuid.UUID(bytes=hashed_path)

# Deprecated
# def get_vertex_path(g: ig.Graph, vid: int):
#     return ".".join(g.vs[ancestory_dot_com(g, vid)[::-1]]['ref'])

def get_vertex_index(vertices: ig.VertexSeq) -> list:
    return vertices.indices

def get_vertex_ref(g: ig.Graph, vid: int):
    return g.vs[vid]['ref']

def get_vertex_path(g: ig.Graph, vid: int):
    return g.vs[vid]['path']

def find_vertex_at_path(g: ig.Graph, path: str):
    path_parts = path.split('.')
    candidates = g.vs.select(ref_eq=path_parts.pop(0))
    if len(candidates) > 1:
        raise ValueError(f"Multiple verticies found at path {path_parts}. Graph is invalid")
    for ref in path_parts:
        candidates = ig.VertexSeq(g, {i.index for c in candidates for i in c.neighbors(mode='in')})
        candidates = candidates.select(ref_eq=ref)
    return candidates[0]

def find_root_vertex(g: ig.Graph):
    candidates = g.vs.select(type_eq='block', _outdegree_eq=0)
    if len(candidates) > 1:
        raise ValueError("Multiple root verticies found. Graph is invalid")
    return candidates[0]

def ancestory_dot_com(g: ig.Graph, v: int) -> List[int]:
    """
    Get a list of all the logical parents above this
    """
    connectedness = g.subgraph_edges(g.es.select(type_eq='part_of'), delete_vertices=False)
    return connectedness.dfs(v, mode='out')[0]

def who_are_you_part_of(g: ig.Graph, v: int):
    """
    Get logical parent of a node
    """
    connectedness = g.subgraph_edges(g.es.select(type_eq='part_of'), delete_vertices=False)
    parent = connectedness.vs[v].neighbors(mode='out')
    if len(parent) > 1:
        raise ValueError("Multiple logical parents found. Graph is invalid")
    elif len(parent) == 0:
        return None
    return parent[0]

def find_blocks_associated_to_package(g: ig.Graph):
    """
    Get all blocks associated to package
    """
    return g.vs.select(type_in='block', _degree_gt=0, type_ne="package")
#%%
import hashlib
import uuid
from typing import List, Optional

import igraph as ig
from enum import Enum
from typing import Union, Optional, List

class VertexType(Enum):
    block = "block"
    package = "package"
    pin = "pin"
    ethereal_pin = "ethereal_pin"

class EdgeType(Enum):
    connects_to = "connects_to"
    part_of = "part_of"
    defined_by = "defined_by"
    instance_of = "instance_of"

#%%

class Graph:
    def __init__(self) -> None:
        self.graph = ig.Graph(directed=True)

    def get_children(self, path: str) -> List[int]:
        sg = self.graph.subgraph_edges(self.graph.es.select(type_in=[EdgeType.part_of.name, EdgeType.defined_by.name]), delete_vertices=False)
        children = sg.subcomponent(self.graph.vs.find(path_eq=path).index, mode="in")
        return children

    def add_vertex(self, ref: str, vertex_type: Union[VertexType, str], defined_by: Optional[str] = None, part_of: Optional[str] = None, **kwargs):
        if defined_by and part_of:
            raise ValueError("Vertex cannot be both defined_by and part_of")
        parent = defined_by or part_of  # will result in None if both are None

        vertex_params = {
            "path": parent + "/" + ref if parent else ref,
            "ref": ref,
            "type": VertexType(vertex_type).name,
        }

        vertex_params.update(kwargs)
        vertex = self.graph.add_vertex(**vertex_params)

        if part_of:
            self.graph.add_edge(vertex.index, self.graph.vs.find(path_eq=part_of).index, type='part_of')
        elif defined_by:
            self.graph.add_edge(vertex.index, self.graph.vs.find(path_eq=defined_by).index, type='defined_by')

        return g

    def add_connection(self, from_path: str, to_path: str):
        self.graph.add_edge(self.graph.vs.find(path_eq=from_path).index, self.graph.vs.find(path_eq=to_path).index, type='connects_to')

    def create_instance(self, class_path: str, ref: str, defined_by: Optional[str] = None, part_of: Optional[str] = None):
        if defined_by and part_of:
            raise ValueError("instantiation cannot be both defined_by and part_of")
        
        sg = self.graph.subgraph(self.get_children(class_path))
        if part_of:
            new_path = part_of + "/" + ref or part_of
        elif defined_by:
            new_path = defined_by + "/" + ref or defined_by

        sg.vs["path"] = [p.replace(class_path, new_path) for p in sg.vs["path"]]
        sg.vs.find(path_eq=new_path)["ref"] = ref

        self.graph: ig.Graph = self.graph.disjoint_union(sg)

        self.graph.add_edge(
            self.graph.vs.find(path_eq=new_path).index,
            self.graph.vs.find(path_eq=class_path).index,
            type='instance_of'
        )

        if part_of:
            self.graph.add_edge(
                self.graph.vs.find(path_eq=new_path).index,
                self.graph.vs.find(path_eq=part_of).index,
                type='part_of'
            )
        elif defined_by:
            self.graph.add_edge(
                self.graph.vs.find(path_eq=new_path).index,
                self.graph.vs.find(path_eq=defined_by).index,
                type='defined_by'
            )
    def plot(self, *args, debug=False, **kwargs):
        color_dict = {
            None: "grey",
            "block": "red",
            "package": "green",
            "pin": "cyan",
            "ethereal_pin": "magenta",
            "connects_to": "blue",
            "part_of": "black",
            "defined_by": "green",
            "instance_of": "red",
        }
        assert all(t is not None for t in self.graph.vs["type"])

        kwargs["vertex_color"] = [color_dict.get(type_name, "grey") for type_name in self.graph.vs["type"]]
        kwargs["edge_color"] = [color_dict[type_name] for type_name in self.graph.es["type"]]
        kwargs["vertex_label_size"] = 8
        kwargs["edge_label_size"] = 8
        if debug:
            kwargs["vertex_label"] = [f"{i}: {vs['path']}" for i, vs in enumerate(self.graph.vs)]
            kwargs["edge_label"] = self.graph.es["type"]
        else:
            kwargs["vertex_label"] = self.graph.vs["ref"]
        return ig.plot(self.graph, *args, **kwargs)

#%%
"""
The code below is equivalent to:

resistor.ato

def seed:
    symbol = None
    def package:
        package = None
        def pin:
            pass
    def ethereal_pin:
        pass

def resistor:
    symbol = resistor
    resistor_package = package()

    1 = ethereal_pin()
    2 = ethereal_pin()

    1 = resistor_package.pin() #maybe need to clean this
    2 = resistor_package.pin()

def vdiv:
    vdiv_res_1 = resistor()
    vdiv_res_2 = resistor()

    INPUT = ethereal_pin()
    OUTPUT = ethereal_pin()
    GROUND = ethereal_pin()

    INPUT ~ vdiv_res_1[0]
    OUTPUT ~ vdiv_res_1[1]
    GROUND ~ vdiv_res_2[1]
    vdiv_res_1[1] ~ vdiv_res_2[0]

a_voltage_divider = vdiv()
"""

g = Graph()
g.add_vertex("resistor.ato", VertexType.block)
g.add_vertex("seed", VertexType.block, defined_by="resistor.ato")
# g.add_vertex("block", VertexType.block, defined_by="resistor.ato/seed")
g.add_vertex("package", VertexType.package, defined_by="resistor.ato/seed")
g.add_vertex("ethereal_pin", VertexType.ethereal_pin, defined_by="resistor.ato/seed")
g.add_vertex("pin", VertexType.pin, defined_by="resistor.ato/seed/package")

g.create_instance("resistor.ato/seed", "resistor", defined_by="resistor.ato")
g.create_instance("resistor.ato/resistor/package", "resistor_package", part_of="resistor.ato/resistor")
g.create_instance("resistor.ato/resistor/ethereal_pin", "1", part_of="resistor.ato/resistor")
g.create_instance("resistor.ato/resistor/ethereal_pin", "2", part_of="resistor.ato/resistor")
g.create_instance("resistor.ato/resistor/resistor_package/pin", "1", part_of="resistor.ato/resistor/resistor_package")
g.create_instance("resistor.ato/resistor/resistor_package/pin", "2", part_of="resistor.ato/resistor/resistor_package")
g.add_connection("resistor.ato/resistor/1", "resistor.ato/resistor/resistor_package/1")
g.add_connection("resistor.ato/resistor/2", "resistor.ato/resistor/resistor_package/2")

g.create_instance("resistor.ato/seed", "vdiv", defined_by="resistor.ato")
g.create_instance("resistor.ato/resistor", "vdiv_res_1", part_of="resistor.ato/vdiv")
g.create_instance("resistor.ato/resistor", "vdiv_res_2", part_of="resistor.ato/vdiv")
g.create_instance("resistor.ato/vdiv/ethereal_pin", "INPUT", part_of="resistor.ato/vdiv")
g.create_instance("resistor.ato/vdiv/ethereal_pin", "OUTPUT", part_of="resistor.ato/vdiv")
g.create_instance("resistor.ato/vdiv/ethereal_pin", "GROUND", part_of="resistor.ato/vdiv")
# Creating a random pin just to see if it shows up in the netlist (it should)
# Note that pins are always dependent on packages, so connecting a pin as part_of a block should usually not be allowed
g.create_instance("resistor.ato/vdiv/package/pin", "1", part_of="resistor.ato/vdiv")

g.add_connection("resistor.ato/vdiv/INPUT", "resistor.ato/vdiv/vdiv_res_1/1")
g.add_connection("resistor.ato/vdiv/OUTPUT", "resistor.ato/vdiv/vdiv_res_1/2")
g.add_connection("resistor.ato/vdiv/GROUND", "resistor.ato/vdiv/vdiv_res_2/2")
g.add_connection("resistor.ato/vdiv/vdiv_res_1/2", "resistor.ato/vdiv/vdiv_res_2/1")

g.create_instance("resistor.ato/vdiv", "a_voltage_divider", part_of="resistor.ato")

g.plot(debug=True)

#%%
def generate_nets_dict_from_graph(g: Graph, root_index: int) -> dict:
    entry = g.graph
    # Generate the part_of connectedness graph without removing other vertices
    part_of_g = g.graph.subgraph_edges(entry.es.select(type_eq='part_of'), delete_vertices=False)
    # The delete vertices is required because the subgraph built below depends on the vertex indices

    # Select only the subgraph that contains the root
    instance_graph = part_of_g.subcomponent(root_index)
    
    # This subgraph contain the part_of connectedness tree that contains the root vertex
    # and that also has electical connections within that tree
    subgraph = entry.induced_subgraph(instance_graph)
    
    # Intersect the entry graph with the subgraph
    #graphs = [subgraph, entry]
    # The union graph contains 
    #union_graph = entry.intersection(graphs, byname=True)
    
    electrical_g = subgraph.subgraph_edges(subgraph.es.select(type_eq='connects_to'), delete_vertices=False)
    
    # Find all the vertex indices in the main graph that are associated to a pin
    pins = electrical_g.vs.select(type_in='pin').indices
    pin_set = set(pins)
    
    clusters = electrical_g.connected_components(mode='weak')
    print('pin_set', pin_set)
    print('cluster_set', clusters)
    print('node 0 of the graph', electrical_g.vs[4]['path'], ',', electrical_g.vs[4]['ref'])
    # Instantiate the net dictionary and net names
    nets = {}
    net_index = 0
    
    for cluster in clusters:
        cluster_set = set(cluster)
        print('cluster_set:', cluster_set)

        # Intersect the pins from the main graph with the vertices in that cluster
        union_set = pin_set.intersection(cluster_set)

        if len(union_set) > 0:# If pins are found in that net
            print('intersection found:', union_set)
            nets[net_index] = {}

            for pin in union_set:
                uid = get_vertex_path(electrical_g, pin)
                nets[net_index][uid] = pin
                # pin_associated_package = who_are_you_part_of(entry, pin)
                # if pin_associated_package:
                #     pin_associated_block = who_are_you_part_of(entry, pin_associated_package.index)
                #     block_path = get_vertex_path(entry, pin_associated_block.index)
                #     uid = generate_uid_from_path(block_path)
                #     uid = pin_associated_block['ref']
                #     # TODO: place uid into stamp
                #     nets[net_index][uid] = pin

            net_index += 1
            #TODO: find a better way to name nets
    
    return nets
    #g.graph = subgraph
    return electrical_g

    # Generate the graph of electrical connectedness without removing other vertices
    electrial_g = graph.subgraph_edges(graph.es.select(type_eq='connects_to'), delete_vertices=False)

    # Find all the vertex indices in the main graph that are associated to a pin
    pins = graph.vs.select(type_in='pin').indices
    pin_set = set(pins)

    # Cluster the electrical graph into multiple nets
    clusters = electrial_g.connected_components(mode='weak')

    # Instantiate the net dictionary and net names
    nets = {}
    net_index = 0

    for cluster in clusters:
        cluster_set = set(cluster)

        # Intersect the pins from the main graph with the vertices in that cluster
        union_set = pin_set.intersection(cluster_set)

        if len(union_set) > 0:# If pins are found in that net
            nets[net_index] = {}

            for pin in union_set:
                pin_associated_package = model.whos_your_daddy(graph, pin)
                pin_associated_block = model.whos_your_daddy(graph, pin_associated_package.index)
                block_path = model.get_vertex_path(graph, pin_associated_block.index)
                uid = model.generate_uid_from_path(block_path)
                # TODO: place uid into stamp
                nets[net_index][uid] = pin

            net_index += 1
            #TODO: find a better way to name nets
    
    return nets

dict = Graph()
#dict.graph = generate_nets_dict_from_graph(g, 0)
#dict.plot(debug=False)
print(generate_nets_dict_from_graph(g, 0))
# %%
