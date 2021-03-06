import networkx as nx
import numpy as np
import logging

from pygmin.landscape import Graph

__all__ = []

logger = logging.getLogger("pygmin.connect")

class _DistanceGraph(object):
    """
    This graph is used by DoubleEndedConnect to make educated guesses for connecting two minima
    
    Parameters
    ----------
    database : 
        the database in which to store newly found minima and transition states.
        If database contains contains previously found minima and transition states,
        those will be used to help with the connection.
    graph :
        the graph build from the database which contains the minima and transition states
    mindist : callable
        the routine which calculates the optimized distance between two structures
    verbosity :
        how much info to print (not very thoroughly implemented)
    defer_database_update : bool
        if true, save new distances and only update the database when enough new
        distances have been accumulated
    db_update_min : int
        only update the database when at least this many new distances have been found.
    
    Description
    -----------
    This graph has a vertex for every minimum and an edge
    between every minima pair. The edge weight between vertices u and v
    is
                       
        if u and v are connected by transition states:
            weight(u, v) = 0. 
        elif we have already tried local_connect on (u,v):
            weight(u, v) = Infinity
        else:
            weight(u, v) = dist(u, v)**2

    Edge weights are set to Infinity to ensure that we don't try to connect
    them again.  The minimum weight path between min1 and min2 in this graph gives a
    good guess for the best way to try connect min1 and min2.  

    """
    def __init__(self, database, graph, mindist, verbosity=0,
                 defer_database_update=True, db_update_min=300):
        self.database = database
        self.graph = graph
        self.mindist = mindist
        self.verbosity = verbosity
        
        self.Gdist = nx.Graph()
        self.distance_map = dict() #place to store distances locally for faster lookup
        nx.set_edge_attributes(self.Gdist, "weight", dict())
        self.debug = False
        
        self.defer_database_update = defer_database_update
        
        self.new_distances = dict() #keep track of newly calculated distances
        self.db_update_min = db_update_min
        
        self.infinite_weight = 1e20

    def distToWeight(self, dist):
        """
        this function defines how the edge weight is calculated.
        
        good options might be:
        
        weight = dist
        
        weight = dist**2
            this favors paths with many short edges over
            paths with fewer but longer edges.
        """
        return dist**2

    def updateDatabase(self, force=False):
        """update databases with new distances"""
        nnewdist = len(self.new_distances.items())
        if nnewdist == 0:
            return
        if not force:
            if nnewdist < self.db_update_min:
                return
        logger.info("updating database with %s %s", nnewdist, "new distances")
        self.database.setDistanceBulk(self.new_distances.iteritems())
        self.new_distances = dict()

    def _setDist(self, min1, min2, dist):
        """
        this function saves newly calculated distances both to the local
        distance map and ultimately to the database
        """
        #add the distance to the database and the distance map
        if self.defer_database_update:
            self.new_distances[(min1, min2)] = dist
        else:
            self.database.setDistance(dist, min1, min2)
        self.distance_map[(min1, min2)] = dist
        
        #make sure a zeroed edge weight is not overwritten
        #if not self.edge_weight.has_key((min1, min2)):
        #    if not self.edge_weight.has_key((min2, min1)):
        #        self.edge_weight[(min1, min2)] = weight
    
    def _getDistNoCalc(self, min1, min2):
        """
        get distance from local memory.  if it doesn't exist, return None,
        don't calculate it.
        """
        #first try to get the distance from the dictionary 
        dist = self.distance_map.get((min1,min2))
        if dist is not None: return dist
        dist = self.distance_map.get((min2,min1))
        if dist is not None: return dist

        if False:
            #this is extremely slow for large databases (> 50% of time spent here)
            #also, it's not necessary if we load all the distances in initialize()
            #if that fails, try to get it from the database
            dist = self.database.getDistance(min1, min2)
            if dist is not None: 
                logger.warning("distance in database but not in distance_map")
                return dist
        return None

    def getDist(self, min1, min2):
        """
        return the distance between two minima.  Calculate it and store it if
        not already known
        """
        dist = self._getDistNoCalc(min1, min2)
        if dist is not None: return dist
        
        #if it's not already known we must calculate it
        dist, coords1, coords2 = self.mindist(min1.coords, min2.coords)
        if self.verbosity > 1:
            logger.debug("calculated distance between %s %s %s", min1._id, min2._id, dist)
        self._setDist(min1, min2, dist)
        return dist
    
#    def _addEdge(self, min1, min2):
#        """
#        add a new edge to the graph.  Calculate the distance
#        between the minima and set the edge weight
#        """
#        if min1 == min2: return
#        dist = self.getDist(min1, min2)
#        weight = self.distToWeight(dist)
#        self.Gdist.add_edge(min1, min2, {"weight":weight})
#        if self.graph.areConnected(min1, min2):
#            self.setTransitionStateConnection(min1, min2)
#            #note: this is incomplete.  if a new edge between
#            #min1 and min2 connects
#            #two clusters that were previously unconnected
#            #then the edge weight should be set to zero 
#            #with self.setTransitionStateConnection() for all minima
#            #in the two clusters.  Currently this is being fixed
#            #by calling checkGraph() from time to time.  I'm not sure
#            #which is better.
    
    def _addMinimum(self, m):
        """
        add a new minimum to the graph
        
        must add an edge with the appropriate weight to every other 
        node in the graph.
        
        this can take a long time if there are many minima or if the
        distance calculation is slow.
        """
        self.Gdist.add_node(m)
        #for noded that are connected set the edge weight using setTransitionStateConnection
        cc = nx.node_connected_component(self.graph.graph, m)
        for m2 in cc:
            if m2 in self.Gdist:
                #self.Gdist.add_edge(m, m2, weight=0.)
                self.setTransitionStateConnection(m, m2)
        
        #for all other nodes set the weight to be the distance
        for m2 in self.Gdist.nodes():
            if not self.Gdist.has_edge(m, m2):
                dist = self.getDist(m, m2)
                weight = self.distToWeight(dist)
                self.Gdist.add_edge(m, m2, {"weight":weight})


        
        
    
    def addMinimum(self, m):
        """
        add a new minima to the graph and add an edge to all the other
        minima in the graph.  
        
        Note: this can take a very long time if there are lots of minima
        in the graph.  mindist need to be run many many times.
        """
        trans = self.database.connection.begin()
        try:
            if not m in self.Gdist:
                self._addMinimum(m)
#                self.Gdist.add_node(m)
#                #add an edge to all other minima
#                for m2 in self.Gdist.nodes():
#                    self._addEdge(m, m2)
        except:
            trans.rollback()
            raise
        trans.commit()
                               

    def removeEdge(self, min1, min2):
        """set the edge weight to near infinity
                
        used to indicate that the routine should not try to connect
        these minima again.
        
        don't overwrite zero edge weight
        """
        if self.Gdist.has_edge(min1, min2):
            w = self.Gdist[min1][min2]["weight"]
            if not w < 1e-6:
                self.Gdist.add_edge(min1, min2, weight=self.infinite_weight)
        return True
#        try:
#            self.Gdist.remove_edge(min1, min2)
#        except nx.NetworkXError:
#            pass
#        return True

    def _initializeDistances(self):
        """put all distances in the database into distance_map for faster access"""
#        from pygmin.storage.database import Distance
#        from sqlalchemy.sql import select
#        conn = self.database.engine.connect()
#        sql = select([Distance.__table__])
#        for tmp, dist, id1, id2 in conn.execute(sql):
#            #m1 = self.database.getMinimum(id1)
#            #m2 = self.database.getMinimum(id2)
#            self.distance_map[id1, id2] = dist
        if False:
            for d in self.database.distances():
                self.distance_map[(d.minimum1, d.minimum2)] = d.dist
        else:
            for d in self.database.distances():
                self.distance_map[(d._minimum1_id, d._minimum2_id)] = d.dist

    def replaceTransitionStateGraph(self, graph):
        self.graph = graph

    def _addRelevantMinima(self, minstart, minend):
        """
        add all the relevant minima from the database to the distance graph
        
        a minima is considered relevant if distance(min1, minstart) and
        distance(min1, minend) are both less than distance(minstart, minend)
        
        also, don't calculate any new distances, only add a minima if all distances
        are already known. 
        """
        start_end_distance = self.getDist(minstart, minend)
        count = 0
        naccept = 0
        for m in self.graph.graph.nodes():
            count += 1
            d1 = self._getDistNoCalc(m, minstart)
            if d1 is None: continue
            if d1 > start_end_distance: continue
            
            d2 = self._getDistNoCalc(m, minend)
            if d2 is None: continue
            if d2 > start_end_distance: continue
            
            logger.debug("    accepting minimum %s %s %s", d1, d2, start_end_distance)
            
            naccept += 1
            self.addMinimum(m)
        logger.info("    found %s %s %s", naccept, "relevant minima out of", count)


    def initialize(self, minstart, minend, use_all_min=False, use_limited_min=True, load_no_distances=False):
        """
        set up the distance graph
        
        initialize distance_map, add the start and end minima and load any other
        minima that should be used in the connect routine.
        """
        #raw_input("Press Enter to continue:")
        if not load_no_distances:
            logger.info("loading distances from database")
            self._initializeDistances()
        #raw_input("Press Enter to continue:")
        dist = self.getDist(minstart, minend)
        self.addMinimum(minstart)
        self.addMinimum(minend)
        if not load_no_distances:
            if use_all_min:
                # add all minima in self.graph to self.Gdist
                logger.info("adding all minima to distance graph (Gdist).")
                logger.info( "    This might take a while.")
                for m in self.graph.graph.nodes():
                    self.addMinimum(m)
            elif use_limited_min:
                logger.info( "adding relevant minima to distance graph (Gdist).")
                logger.info( "    This might take a while.")
                self._addRelevantMinima(minstart, minend)
        #raw_input("Press Enter to continue:")

    def setTransitionStateConnection(self, min1, min2):
        """use this function to tell _DistanceGraph that
        there exists a known transition state connection between min1 and min2
        
        The edge weight will be set to zero
        """
        weight = 0.
        self.Gdist.add_edge(min1, min2, {"weight":weight})

    def shortestPath(self, min1, min2):
        """return the minimum weight path path between min1 and min2""" 
        try:
            path = nx.shortest_path(
                    self.Gdist, min1, min2, weight="weight")
        except nx.NetworkXNoPath:
            return None, None
        
        #get_edge attributes is really slow:
        #weights = nx.get_edge_attributes(self.Gdist, "weight") #this takes order number_of_edges
        weights = [ self.Gdist[path[i]][path[i+1]]["weight"] for i in range(len(path)-1) ]
        
        return path, weights
        
    def mergeMinima(self, min1, min2):
        """
        rebuild the graph with min2 deleted and 
        everything pointing to min1 pointing to min2 instead
        """
#        print "    rebuilding Gdist"
        for m, data in self.Gdist[min2].iteritems():
            if m == min1:
                continue
            if not self.Gdist.has_edge(min1, m):
                self.add_edge(min1, m, **data)
            
            #the edge already exists, keep the edge with the lower weight
            w2 = data["weight"]
            w1 = self.Gdist[min1][m]["weight"]
            wnew = min(w1, w2)
            #note: this will override any previous call to self.setTransitionStateConnection
            self.Gdist.add_edge(min1, m, weight=wnew)
            
        self.Gdist.remove_node(min2)
            

    def checkGraph(self):
        """
        make sure graph is up to date.
        and make any corrections
        """
        logger.info( "checking Gdist")
        allok = True
        #check that all edges that are connected in self.graph
        #have zero edge weight
        #note: this could be done a lot more efficiently
        weights = nx.get_edge_attributes(self.Gdist, "weight")
        count = 0
        for e in self.Gdist.edges():
            are_connected = self.graph.areConnected(e[0], e[1])
            zero_weight = weights[e] < 1e-10

            #if they are connected they should have zero_weight
            if are_connected and not zero_weight:
                #print "    problem: are_connected", are_connected, "but weight", weights[e], "dist", dist
                if True:
                    #note: this is an inconsistency, but it's only a problem if
                    #there is no zero weight path from e[0] to e[1]
                    path, path_weight = self.shortestPath(e[0], e[1])
                    weight_sum = sum(path_weight)
                    if weight_sum > 10e-6:
                        #now there is definitely a problem.
                        allok = False
                        count += 1
                        dist = self.getDist(e[0], e[1])
                        logger.warning("    problem: are_connected %s %s %s %s %s %s %s %s %s", 
                                        are_connected, "but weight", weights[e], "dist", dist, 
                                        "path_weight", weight_sum, e[0]._id, e[1]._id)
                self.setTransitionStateConnection(e[0], e[1])
                            
                     
            if not are_connected and zero_weight:
                allok = False
                dist = self.getDist(e[0], e[1])
                logger.warning("    problem: are_connected %s %s %s %s %s %s %s", 
                                are_connected, "but weight", weights[e], "dist", dist, e[0]._id, e[1]._id)
                w = self.distToWeight(dist)
                self.Gdist.add_edge(e[0], e[1], {"weight":w})
        if count > 0:
            logger.info("    found %s %s", count, "inconsistencies in Gdist")
        
        return allok



#
#
# below here only stuff for testing
#
#

import unittest
class TestDistanceGraph(unittest.TestCase):
    def setUp(self):
        from pygmin.landscape import DoubleEndedConnect
        from pygmin.landscape._graph import create_random_database
        from pygmin.systems import LJCluster
#        from pygmin.mindist import minPermDistStochastic, MinDistWrapper
#        from pygmin.potentials import LJ
        
        nmin = 10
        natoms=13
        
        sys = LJCluster(natoms)
        
        pot = sys.get_potential()
        mindist = sys.get_mindist()
        
        db = create_random_database(nmin=nmin, natoms=natoms, nts=nmin/2)
        min1, min2 = list(db.minima())[:2] 
        
        
        connect = DoubleEndedConnect(min1, min2, pot, mindist, db, use_all_min=True, 
                                     merge_minima=True, max_dist_merge=1e100)

        self.connect = connect
        self.db = db
        self.natoms = natoms
    
    def make_result(self, coords, energy):
        from pygmin.optimize import Result
        res = Result()
        res.coords = coords
        res.energy = energy
        return res

    
    def test_merge_minima(self):
        """merge two minima and make sure the distance graph is still ok"""
        min3, min4 = list(self.db.minima())[2:4]
        allok = self.connect.dist_graph.checkGraph()
        self.assertTrue(allok, "the distance graph is broken at the start")

        print min3._id, min4._id, "are connected", self.connect.graph.areConnected(min3, min4)
        print min3._id, "number of edges", self.connect.graph.graph.degree(min3)
        print min4._id, "number of edges", self.connect.graph.graph.degree(min4)
        self.connect.mergeMinima(min3, min4)
        
        self.assertNotIn(min4, self.connect.graph.graph)
        self.assertNotIn(min4, self.connect.dist_graph.Gdist)
        self.assertNotIn(min4, self.db.minima())
        
        allok = self.connect.dist_graph.checkGraph()
        
        
        self.assertTrue(allok, "merging broke the distance graph")
        
    def test_add_TS_existing_minima(self):
        from pygmin.optimize import Result
        min3, min4 = list(self.db.minima())[4:6]
        allok = self.connect.dist_graph.checkGraph()
        self.assertTrue(allok, "the distance graph is broken at the start")

        print min3._id, min4._id, "are connected", self.connect.graph.areConnected(min3, min4)
        print min3._id, "number of edges", self.connect.graph.graph.degree(min3)
        print min4._id, "number of edges", self.connect.graph.graph.degree(min4)
        
        coords = np.random.uniform(-1,1,self.natoms*3)
        E = float(min3.energy + min4.energy)
        min_ret1 = self.make_result(min3.coords, min3.energy)
        min_ret2 = self.make_result(min4.coords, min4.energy)
        
        eigenvec = coords.copy()
        eigenval = -1.
        
        self.connect._addTransitionState(E, coords, min_ret1, min_ret2, eigenvec, eigenval)

        allok = self.connect.dist_graph.checkGraph()
        self.assertTrue(allok, "adding a transition state broke the distance graph")
        

    def test_add_TS_new_minima(self):
        min3 = list(self.db.minima())[6]
        allok = self.connect.dist_graph.checkGraph()
        self.assertTrue(allok, "the distance graph is broken at the start")

#        print min3._id, min4._id, "are connected", self.connect.graph.areConnected(min3, min4)
        print min3._id, "number of edges", self.connect.graph.graph.degree(min3)

        #create new minimum from thin air
        coords = np.random.uniform(-1,1,self.natoms*3)
        E = np.random.rand()*10.
        min_ret1 = self.make_result(min3.coords, min3.energy)
        min_ret2 = self.make_result(coords, E)

#        min_ret2 = [coords, E]
#        min_ret1 = [min3.coords, min3.energy]


        #create new TS from thin air        
        coords = np.random.uniform(-1,1,self.natoms*3)
        E = float(min3.energy + min_ret2.energy)
        
        eigenvec = coords.copy()
        eigenval = -1.
        
        self.connect._addTransitionState(E, coords, min_ret1, min_ret2, eigenvec, eigenval)

        allok = self.connect.dist_graph.checkGraph()
        self.assertTrue(allok, "adding a transition state broke the distance graph")

    def run_add_TS(self, min3, min4, nocheck=False):
        if not nocheck:
            allok = self.connect.dist_graph.checkGraph()
            self.assertTrue(allok, "the distance graph is broken at the start")

        print min3._id, min4._id, "are connected", self.connect.graph.areConnected(min3, min4)
        print min3._id, "number of edges", self.connect.graph.graph.degree(min3)
        print min4._id, "number of edges", self.connect.graph.graph.degree(min4)
        
        coords = np.random.uniform(-1,1,self.natoms*3)
        E = float(min3.energy + min4.energy)
        min_ret1 = self.make_result(min3.coords, min3.energy)
        min_ret2 = self.make_result(min4.coords, min4.energy)

#        min_ret1 = [min3.coords, min3.energy]
#        min_ret2 = [min4.coords, min4.energy]
        
        eigenvec = coords.copy()
        eigenval = -1.
        
        self.connect._addTransitionState(E, coords, min_ret1, min_ret2, eigenvec, eigenval)

        if not nocheck:
            allok = self.connect.dist_graph.checkGraph()
            self.assertTrue(allok, "adding a transition state broke the distance graph")


    def test_add_TS_existing_not_connected(self):
        minima = list(self.db.minima())
        min3 = minima[2]
        for min4 in minima[3:]:
            if not self.connect.graph.areConnected(min3, min4):
                break
        self.run_add_TS(min3, min4)
        
    def test_add_TS_existing_already_connected(self):
        minima = list(self.db.minima())
        min3 = minima[2]
        for min4 in minima[3:]:
            if self.connect.graph.areConnected(min3, min4):
                break
        self.run_add_TS(min3, min4)
    
    def test_add_TS_multiple(self):
        minima = list(self.db.minima())
        min3 = minima[2]
        nnew = 4
        for min4 in minima[3:3+nnew]:
            self.run_add_TS(min3, min4, nocheck=True)

        allok = self.connect.dist_graph.checkGraph()
        self.assertTrue(allok, "adding multiple transition states broke the distance graph")




def mytest(nmin=40, natoms=13):
    from pygmin.landscape import DoubleEndedConnect
    from pygmin.landscape._graph import create_random_database
    from pygmin.mindist import minPermDistStochastic, MinDistWrapper
    from pygmin.potentials import LJ
    
    pot = LJ()
    mindist = MinDistWrapper(minPermDistStochastic, permlist=[range(natoms)], niter=10)
    
    db = create_random_database(nmin=nmin, natoms=natoms)
    min1, min2 = list(db.minima())[:2] 
    
    
    graph = Graph(db)
    connect = DoubleEndedConnect(min1, min2, pot, mindist, db, use_all_min=True, 
                                 merge_minima=True, max_dist_merge=.1)

if __name__ == "__main__":
    #mytest()
    unittest.main()
