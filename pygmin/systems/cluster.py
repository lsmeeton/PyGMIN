import numpy as np

from pygmin.systems import BaseSystem
from pygmin.potentials import LJ
from pygmin.transition_states import orthogopt
from pygmin.mindist import MinPermDistAtomicCluster, ExactMatchAtomicCluster, \
    PointGroupOrderCluster
from pygmin.landscape import smoothPath
from pygmin.transition_states import create_NEB


__all__ = ["AtomicCluster"]

class AtomicCluster(BaseSystem):
    """
    Define an atomic cluster.  
    
    This is a system of point particles with global rotational 
    and translational symmetry and some form of permutational 
    symmetry.
    """
    def get_potential(self):
        return LJ(self.natoms)
    
    def get_random_configuration(self):
        coords = np.random.uniform(-1, 1, [3*self.natoms]) * 0.7 * float(self.natoms)**(1./3)
        return coords
    
    def get_permlist(self):
        raise NotImplementedError
    
    def get_compare_exact(self, **kwargs):
        """this function quickly determines whether two clusters are identical
        given translational, rotational and permutational symmeties
        """
        permlist = self.get_permlist()
        return ExactMatchAtomicCluster(permlist=permlist, **kwargs)
    
    def get_mindist(self, **kwargs):
        """return a function which puts two structures in best alignment.
        
        take into account global rotational symmetry, global translational
        symmetry and permutational symmetry
        """
        permlist = self.get_permlist()
        return MinPermDistAtomicCluster(permlist=permlist, **kwargs)
        
    def get_orthogonalize_to_zero_eigenvectors(self):
        """the zero eigenvectors correspond to 3 global translational
        degrees of freedom and 3 global rotational degrees of freedom"""
        return orthogopt

    def get_metric_tensor(self, coords):
        """ metric tensor for all masses m_i=1.0 """
        return np.identity(coords.size)
    
    def get_pgorder(self, coords):
        calculator = PointGroupOrderCluster(self.get_compare_exact())
        return calculator(coords)

    
    #
    #below here only stuff for the gui
    #

    def smooth_path(self, path, **kwargs):
        mindist = self.get_mindist()
        return smoothPath(path, mindist, **kwargs)
        
    def createNEB(self, coords1, coords2, **kwargs):
        pot = self.get_potential()
        NEBparams = self.params.double_ended_connect.local_connect_params.NEBparams.copy()
        NEBparams.update(kwargs)
        return create_NEB(pot, coords1, coords2, verbose=True, **NEBparams)

