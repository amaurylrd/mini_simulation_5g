import networkx as nx
import pandas as pd
import numpy.random as random

class Graph():
    def __init__(self, filepath: str):
        """ Constructs a directed graph with the specified edges.
        
        Args:
            filepath (str): the path of the csv containing the data.
        """
        df = pd.read_csv(filepath) # dataframe retrieving graph edges from the csv
        self._graph = nx.from_pandas_edgelist(df, edge_attr=['average_throughput'], create_using=nx.DiGraph(directed=True))
        
        nx.set_edge_attributes(self._graph, values=None, name='current_throughput') # sets for each edge None as the current throughput
        
        self._emitters = set()
        for column in df.iloc():
            dst = column['destination']
            src = column['source']
            if dst == dst and src != dst and self._graph.has_node(dst):
                self._emitters.add((src, dst))
                
    def render(self, pltax):
        total_throughput = sum(weight for _, _, weight in self.get_weighted_edges()) // 10
        weights = [ weight / total_throughput for _, _, weight in self.get_weighted_edges() ]
        nx.draw_shell(self._graph, ax=pltax, width=weights, with_labels=True, node_size=550, font_size=15, font_weight='bold', font_color='whitesmoke')
        
    def get_weighted_edges(self):
        """ Returns all the edges of the graph formated like so (source, target, weight).

        Returns:
            out (list): all the edges of the graph.
        """
        return self._graph.edges(data="average_throughput")
    
    def get_edges(self):
        """ Returns all the edges of the graph formated like so (source, target).

        Returns:
            out (list): all the edges of the graph.
        """
        return self._graph.edges()
    
    def get_vertices(self):
        """ Returns all the vertices of the graph.

        Returns:
            out (NodeView): the nodes from the graph.
        """
        return nx.nodes(self._graph)
    
    def get_adjacency_list(self):
        """ Returns all the edges as an adjacency list.

        Returns:
            out (list): lines of data in adjlist format.
        """
        return nx.generate_adjlist(self._graph)
    
class Network(Graph):
    class Node():
        def __init__(self, node_name):
            self.name = str(node_name)
            self.packages_in = [] # packages that have just been received
            self.packages_out = [] # packages that will be sent
        
        def __eq__(self, other):
            if isinstance(other, type(self)):
                return self.name == other.name
            return False
        
        def update(self):
            """ Moves the packages from 'packages_in' to 'packages_out' buffer.
            """
            self.packages_out.extend(self.packages_in)
            self.packages_in = []
            
        def get_packages_from_out(self, n: int):
            """ Returns the packages to be sent. Those packages are removed from the buffer.

            Args:
                destination (str): The number of packages to pop.
                
            Returns:
                out (list): The list of packages to send from this node.
            """
            return [ self.packages_out.pop(0) for _ in range(min(len(self.packages_out), n)) ]
        
        def set_packages_in(self, packages: list):
            """ Adds the specified packages at the end of the buffer.

            Args:
                packages (list): The list of received packages.
            """
            self.packages_in.extend(packages)
        
        def set_packages_out(self, packages: list):
            """ Sets the specified packages ready for send.

            Args:
                packages (list): The list of new packages to send from this node.
            """
            self.packages_out.extend(packages)
        
        def get_buffer_size(self):
            """ Returns the size of the buffer.

            Returns:
                out (int): The length of the buffer.
            """
            return len(self.packages_out)
        
        def is_buffer_empty(self):
            """ Tells if the buffer is empty.

            Returns:
                out (bool): True if the buffer is empty, otherwise False.
            """
            return not self.packages_out
        
    def __init__(self, filename: str):
        super().__init__("ressources/dataframes/" + filename + ".csv")
        
        self._nodes = {}
        for vertex in self.get_vertices():
            self._nodes[vertex] = self.Node(vertex)
            
    def update(self, tick, congestion):  #TODO: coeff congestion pour sigma throughputs et sigma packages
        # current throughput is randomized around its average_throughput
        for (u, v, w) in self.get_weighted_edges():
            nx.set_edge_attributes(self._graph, {(u, v): { 'current_throughput': int(random.normal(w, 1.0)) }})
        
        # moves the packages from 'reception' to 'ready_to_send' queue
        for _, node in self._nodes.items():
            node.update()
        
        # generates n packages for each node source
        for (source, destination) in self._emitters:
            packages = [ p | { "from": source, "to": destination, "sent": tick } for p in self.generate_packages(100, 10, 2) ]
            self._nodes[source].set_packages_out(packages)
        
        
        # prend le meilleur débit entre voisins directs
        # for (node_name, node) in self._nodes.items():
        #     for destination in set([ package["to"] for package in node.packages_out ]):
        #         nx.all_simple_paths(self._graph, node_name,)
        
        # OLSR meilleur débit moyen 
        #https://networkx.org/documentation/networkx-1.10/reference/generated/networkx.algorithms.simple_paths.all_simple_paths.html
        #https://networkx.guide/algorithms/shortest-path/
        
        # la plus petite latence
        for (node_name, node) in self._nodes.items():
            nexts = {}
                
            for destination in set([ package["to"] for package in node.packages_out ]):
                next = nx.shortest_path(self._graph, source=node_name, target=destination, weight='average_thourhput', method='dijkstra')[1]
                nexts[destination] = next
            
            debit_nexts = { next: self._graph[node_name][next]['current_throughput'] for next in set(nexts.values()) }
            
            print("nexts et debits_nexts", nexts, debit_nexts)
            
            # while node.package_out:
            #     package = node.packages_out[-1]
                
            #     if debit_nexts[nexts[package["to"]]] > 0:
            #         package = node.packages_out.pop(0)
            #         nexts[package["to"]].set_packages_in([package])
            #         debit_nexts[nexts[package['to']]] -= 1
            #     else:
            #         break
            
            while node.packages_out and debit_nexts[nexts[node.packages_out[-1]['to']]] > 0:
                package = node.packages_out.pop(0)
                self._nodes[nexts[package['to']]].set_packages_in([package])
                debit_nexts[nexts[package['to']]] -= 1

        for (node_name, node) in self._nodes.items():
            print("node", node.name, node.packages_in, node.packages_out)
            input()
            
        print("tick + 1")
        
    
    def generate_packages(self, package_size: int, normal_loc=0.0, normal_scale=1.0):
        """ Generates randomized packages from the specified parameters.

        Args:
            package_size (int): the specified fixed size (in bits) for all packages. Must be non-negative.
            package_loc (float, optional): the mean of the gaussian distribution. Must be non-negative. Defaults to 0.0.
            package_spread (float, optional): the standard deviation of the gaussian distribution. Defaults to 1.0.

        Returns:
            out (ndarray): samples of packages from the parameterized generation.
        """
        packages = []
        normal_distribution = random.normal(normal_loc, normal_scale)
        samples = int(normal_distribution)
        
        for _ in range(samples):
            package = { "data": random.randint(0, 2, size=(package_size)) } # generate an n-dimensional array of random bits
            packages.append(package)
        
        return packages
    