import numpy as np
from pygmin.utils import rotations
from pygmin.utils import vec3

__all__ = ["uniform_displace", "rotate", "reduced_coordinates_displace"]

def uniform_displace(stepsize, coords, indices=None):
    '''uniform random displacement
    
    Parameters
    ----------
    coords : array like x(:,3)
       coordinates
    indices : list, optional
       list of coordinates to displace, None for all coordinates in array
    '''
    if(indices):
        for i in indices:
            coords[i] += stepsize * rotations.vector_random_uniform_hypersphere(3)
        return
    
    for x in coords:
        x += stepsize * rotations.vector_random_uniform_hypersphere(3)
        
def rotate(stepsize, coords, indices=None):
    '''uniform random rotation of angle axis vector
    
    Parameters
    ----------
    coords : array like x(:,3)
       coordinates
    indices : list, optional
       list of coordinates to displace, None for all coordinates in array
    
    '''
    if(indices):
        for i in indices:
            rotations.takestep_aa( coords[i], stepsize )
        return
    
    for x in coords:
        rotations.takestep_aa( x, stepsize )
        
def reduced_coordinates_displace(stepsize, lattice_matrix, coords, indices=None):
    '''uniform random displacement of reduced coordinates
    
    Parameters
    ----------
    coords : array like x(:,3)
       coordinates
    indices : list, optional
       list of coordinates to displace, None for all coordinates in array
    
    '''
    ilattice = vec3.invert3x3(lattice_matrix) # inverse_lattice
    if(indices):
        for i in indices:
            coords[i] += np.dot(ilattice, stepsize * rotations.vector_random_uniform_hypersphere(3))
        return
            
    for x in coords:
        x += np.dot(ilattice, stepsize * rotations.vector_random_uniform_hypersphere(3))
   
    