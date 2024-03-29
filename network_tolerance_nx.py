import numpy as np
import random
import pandas as pd
import networkx as nx
from itertools import zip_longest
""" Tutorial:
1. Import necessary packages above
2. Place this script in the same folder as your workspace
3. Import this script:

from network_tolerance_nx import *

4. After import, instantiate needed class with the required parameters:

tolerance = GraphTolerance(graph)

5. Using a GraphTolerance function:
#Defining Parmaeters
graph_measures = ['average_shortest_path_length']
measure_params = [{'weight': None}]
custom_funcs = {'diameter': max_diameter, 'maxdegree': max_degree}
centrality = 'degree' #nx function
centrality_params = {'weight':None}

#Executing Node Deletion
target_attack = tolerance.target_attack(f=0.05, centrality=centrality, 
                                   centrality_params = centrality_params,
                                    steps= 5, 
                         graph_measures=graph_measures,
                         measure_params=measure_params,
                         custom_measures=custom_funcs)
"""

class CreateGraph:
    def __init__(self):
        pass
        
    def preprocess_df(self, df):
        # Drop rows with null values
        df.dropna(inplace=True)
        edge = df[['started_at', 'ended_at',
        'start_station_id', 'start_station_name',
       'end_station_id', 'end_station_name', 'member_casual']].copy()

        edge['start_time'] = pd.to_datetime(edge['started_at'])
        edge['end_time'] = pd.to_datetime(edge['ended_at'])

        # Extract month and year from start_time and end_time columns
        edge['start_year'] = edge['start_time'].dt.year
        edge['end_year'] = edge['end_time'].dt.year

        # Calculate travel time in seconds
        edge['travel_time_in_sec'] = (pd.to_datetime(edge['ended_at'])\
                                          - pd.to_datetime(edge['started_at'])).dt.total_seconds()
        
        edge.drop(columns=['start_time', 'end_time'], inplace=True)

        #Converts station id numbers to string
        edge['start_station_id'] = edge['start_station_id'].astype(int).astype('string')
        edge['end_station_id'] = edge['end_station_id'].astype(int).astype('string')

        #concat START and END ids to create edge pair ID column
        edge['edge_pairs'] = edge['start_station_id'] + '-' + edge['end_station_id']
        #clean up member_casual columns
        edge['member_casual'] = edge['member_casual'].str.lower()
        edge = pd.get_dummies(edge, columns =['member_casual'])


        #Groupby edge_pairs with count as method
        edge_grouped = edge.groupby(['edge_pairs'], as_index=False)\
            .agg({'start_station_id':'first',
                'end_station_id':'first',
                'edge_pairs': 'count' ,
                'started_at': 'first',
                'ended_at':'first',
                'start_station_name':'first',	
                'end_station_name':'first',
                'member_casual_casual': 'sum',
                'member_casual_member': 'sum',	
                'start_year': 'first',	
                'end_year': 'first',
                'travel_time_in_sec': 'sum'})


        #Concat start and end ID column again to be used as edge name
        #Rearrange columns for igraph ingest
        edge_grouped['name'] = edge_grouped['start_station_id'] + '-' \
            + edge_grouped['end_station_id']
        edge_grouped.rename(columns={'edge_pairs':'weight',
                                    'member_casual_casual': 'casual_count',
                                    'member_casual_member': 'member_count'
                                    }, inplace=True)

        edge_grouped = edge_grouped[['start_station_id', 'end_station_id', 
                                    'weight', 'name',
                                    'started_at',
                                    'ended_at',
                                    'start_station_name',	
                                    'end_station_name',
                                    'casual_count',
                                    'member_count',	
                                    'start_year',
                                    'end_year',
                                    'travel_time_in_sec']]


        #Create tuplelist from edge_grouped df, read tuplelist in igraph

        return edge_grouped

    def create_network(self, df):
        G = nx.from_pandas_edgelist(df, 
                            source=df.columns[0], target=df.columns[1], 
                            edge_attr=True,
                            create_using= nx.DiGraph)
        return G

class GraphTolerance:
    """Includes functions for error and attack tolerance"""
    def __init__(self, graph):
        self.G = graph
    
    def measure_calc(self, graph_measures, kwargs={}, custom_measures=None):
        measures = []
        for measure, kwarg in zip_longest(graph_measures, kwargs, fillvalue={}):
                method = getattr(nx, measure)
                result = method(self.G, **kwarg)
                measures.append(result)
        
        if custom_measures:
            for measure in custom_measures:
                custom_func = custom_measures.get(measure)
                custom_result = custom_func(self.G)
                measures.append(custom_result)
                    
        return measures

    def random_fail(self, f=0.05, steps=5, graph_measures=['diameter'],\
                     measure_params={}, custom_measures=None):
        """Error Tolerance Method

        Function: Randomly removes f percentage of nodes in a graph
        and ouputs a dataframe on graph-level measures after removal

        Parameters:
        f = percentage of nodes in graph to be removed
        steps = minimum number of datapoints generated from 0 to f
        graph_measures = MUST be a list or tuple of graph level methods
        custom_measures = Dictionary of customfunctions that calculate graph-level
        attriutes using NetworkX. Mostly for error-handling NetworkX methods
        or if there is no built-in method

        Note: High f values might lead to errors due to lack of error-handling
        of NetworkX methods

        Returns: dataframe
        """
      
        array = []
        sample_count = 0
        node_count = self.G.number_of_nodes()
        f_nodecount = round((f*node_count))
        node_delete = random.sample(list(self.G.nodes()),f_nodecount)
        sample = int(f_nodecount/steps)

        if sample <1:
            raise ValueError("Steps greater than nodes to be removed")

        if type(graph_measures) != list and type(graph_measures) != tuple:
            raise ValueError("Measures must be a string list or tuple")

        while sample_count != f_nodecount:                            
            if sample < len(node_delete):
                results = []
                to_delete = node_delete[:sample]
                self.G.remove_nodes_from(to_delete)
                sample_count += sample
                results.extend([sample_count/node_count, sample_count])
                results.extend(self.measure_calc(graph_measures, \
                        measure_params, custom_measures))
                array.append(results)
                if len(node_delete) == 0:
                    break
                else:
                    for node in to_delete:
                        node_delete.remove(node)
            else:
                if len(node_delete) == 0:
                    break
                else:
                    results = []
                    to_delete = node_delete
                    self.G.remove_nodes_from(to_delete)
                    sample_count += len(to_delete)
                    results.extend([sample_count/node_count, sample_count])
                    results.extend(self.measure_calc(graph_measures, \
                        measure_params, custom_measures))
                    array.append(results)
                    if len(node_delete) == 0:
                        break
                    else:
                        for node in to_delete:
                            node_delete.remove(node)

        column_names = ['f','f_count']
        column_names.extend(graph_measures)
        if custom_measures:
            column_names.extend(list(custom_measures.keys()))
        else:
            pass
        results_df = pd.DataFrame(array, columns = column_names)

        return results_df

    def target_attack(self, f=0.05, centrality='degree', centrality_params={},\
                      steps=5, graph_measures=['diameter'], measure_params={},\
                        custom_measures=None):
        """Targeted Attack Method

        Function: Removes top-f percent of nodes with highest degree
        and ouputs a dataframe on graph-level measures after removal

        Parameters:
        f = max percentage of nodes in graph to be removed
        steps = minimum number of datapoints generated from 0 to f
        graph_measures = MUST be a list or tuple of graph level methods
        custom_measures = Dictionary of custom functions that calculate graph-level
        attriutes using NetworkX. Mostly for error-handling NetworkX methods
        or if there is no built-in method.

        Note: High f values might lead to errors due to lack of error-handling
        of NetworkX methods

        Returns: dataframe
        """

        array = []
        sample_count = 0
        node_count = self.G.number_of_nodes()
        f_nodecount = round((f*node_count))

        bench = getattr(nx, centrality)
        bench_compute = bench(self.G, **centrality_params)
        bench_np = np.array([(n, d) for n, d in bench_compute])
        bench_int = bench_np[:, 1].astype(np.int16)
        sorted_indices = np.argsort(-bench_int)
        top_vertices = bench_np[sorted_indices[:f_nodecount], 0]
        node_delete = list(top_vertices)
        sample = int(f_nodecount/steps)
    
        if sample <1:
            raise ValueError("Steps greater than nodes to be removed")

        if type(graph_measures) != list and type(graph_measures) != tuple:
            raise ValueError("Measures must be a string list or tuple")

        while sample_count != f_nodecount:                            
            if sample < len(node_delete):
                results = []
                to_delete = node_delete[:sample]
                self.G.remove_nodes_from(to_delete)
                sample_count += sample
                results.extend([sample_count/node_count, sample_count])
                results.extend(self.measure_calc(graph_measures, \
                    measure_params, custom_measures))
                array.append(results)
                if len(node_delete) == 0:
                    break
                else:
                    for node in to_delete:
                        node_delete.remove(node)
            else:
                if len(node_delete) == 0:
                    break
                else:
                    results = []
                    to_delete = node_delete
                    self.G.remove_nodes_from(to_delete)
                    sample_count += len(to_delete)
                    results.extend([sample_count/node_count, sample_count])
                    results.extend(self.measure_calc(graph_measures, \
                    measure_params, custom_measures))
                    array.append(results)
                    if len(node_delete) == 0:
                        break
                    else:
                        for node in to_delete:
                            node_delete.remove(node)

        column_names = ['f','f_count']
        column_names.extend(graph_measures)
        if custom_measures:
            column_names.extend(list(custom_measures.keys()))
        else:
            pass
        results_df = pd.DataFrame(array, columns = column_names)

        return results_df