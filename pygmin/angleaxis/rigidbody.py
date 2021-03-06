import numpy as np
import aatopology
from pygmin.potentials.potential import potential
from pygmin.mindist import StandardClusterAlignment, optimize_permutations

class RigidFragment(aatopology.AASiteType):
    ''' defines a single rigid fragment 
    
    In the most simple case, this is just a whole molecule
    '''
    
    def __init__(self):
        aatopology.AASiteType.__init__(self)
        self.atom_positions = []
        self.atom_types = []
        self.atom_masses = []
        
    def add_atom(self, atomtype, pos, mass=1.0):
        '''Add a new atom to the rigid fragment
        
        Parameters
        ----------
        type: string
            type identifier
        pos: np.array
            position of the atom
        mass: mass of the atom
        '''
        self.atom_types.append(atomtype)
        self.atom_positions.append(pos.copy())
        self.atom_masses.append(mass)
        
    def finalize_setup(self, shift_com=True):
        '''finalize setup after all sites have been added
        
        This will shift the center of mass to the origin and calculate
        the total mass and weighted tensor of gyration
        '''
        
        # first correct for the center of mass
        com = np.average(self.atom_positions, axis=0, weights=self.atom_masses)
        if shift_com:
            for x in self.atom_positions:
                x[:] -= com

        self.cog = np.average(self.atom_positions, axis=0)
        self.W = float(len(self.atom_masses))
        
        # calculate total mass
        self.M = np.sum(self.atom_masses)
        
        # now calculate the weighted moment of inertia tensor
        self.S[:] = 0.
        for x in self.atom_positions:
            self.S[:] += np.outer(x, x)
        self.Sm = np.zeros([3,3])
        for x, m in zip(self.atom_positions, self.atom_masses):
            self.Sm[:] += m*np.outer(x, x)
        self._determine_symmetries()
            
    def to_atomistic(self, com, p):
        R, R1, R2, R3 = aatopology.rotMatDeriv(p, False)
        return com + np.dot(R, np.transpose(self.atom_positions)).transpose()
            
    def transform_grad(self, p, g):
        g_com = np.sum(g, axis=0)
        R, R1, R2, R3 = aatopology.rotMatDeriv(p, True)
        g_p = np.zeros_like(g_com)
        for ga, x in zip(g, self.atom_positions):
            g_p[0] += np.dot(ga, np.dot(R1, x))
            g_p[1] += np.dot(ga, np.dot(R2, x))
            g_p[2] += np.dot(ga, np.dot(R3, x))
#                        

#        g_p[0] = -np.sum(
#                        np.dot(g, np.dot(R1, np.transpose(self.atom_positions)).transpose())
#                        )
#        g_p[1] = np.sum(
#                        np.dot(g, np.dot(R2, np.transpose(self.atom_positions)).transpose())
#                        )
#        g_p[2] = np.sum(
#                        np.dot(g, np.dot(R3, np.transpose(self.atom_positions)).transpose())
#                        )
        return g_com, g_p

    def redistribute_forces(self, p, grad_com, grad_p):
        R, R1, R2, R3 = aatopology.rotMatDeriv(p, True)
        grad = np.dot(R1, np.transpose(self.atom_positions)).transpose()*grad_p[0]
        grad += np.dot(R2, np.transpose(self.atom_positions)).transpose()*grad_p[1]
        grad += np.dot(R3, np.transpose(self.atom_positions)).transpose()*grad_p[2]
        grad += grad_com
        
        grad = (self.atom_masses * grad.transpose()).transpose()/self.M
        
        return grad


    def _determine_inversion(self, permlist):
        x = np.array(self.atom_positions)
        xi = -x
        for rot, invert in StandardClusterAlignment(-x, x, can_invert=False):
            xn = np.dot(rot, x.transpose()).transpose()
            if np.linalg.norm(xn-xi) < 1e-6:
                self.inversion = rot
                return

    def _determine_rotational_symmetry(self, permlist):
        x = np.array(self.atom_positions)
        for rot, invert in StandardClusterAlignment(x, x, can_invert=False):
            xn = np.dot(rot, x.transpose()).transpose()
            dist, tmp, xn = optimize_permutations(x, xn, permlist=permlist)
            if np.linalg.norm(xn.flatten()-x.flatten()) < 1e-6:
                self.symmetries.append(rot)
                
        
    def _determine_symmetries(self):
        perm_dict = dict()
        for t in self.atom_types:
            perm_dict[t] = []
            
        for i, t in zip(xrange(len(self.atom_types)), self.atom_types):
            perm_dict[t].append(i)
            
        permlist = []
        for i in perm_dict.itervalues():
            if len(i) > 1:
                permlist.append(i)
        
        self._determine_inversion(permlist)
        self._determine_rotational_symmetry(permlist)
                    
class RBTopology(aatopology.AATopology):
    def __init__(self):
        aatopology.AATopology.__init__(self)
        self.natoms=0
        
    def get_atomtypes(self):
        atom_types = [None for i in xrange(self.natoms)]
        for site in self.sites:
            for i, atype in zip(site.atom_indices, site.atom_types):
                atom_types[i]=atype
        return atom_types

    def get_atommasses(self):
        masses = [None for i in xrange(self.natoms)]
        for site in self.sites:
            for i, mass in zip(site.atom_indices, site.atom_masses):
                masses[i]=mass
        return masses
        
    def add_sites(self, sites):
        aatopology.AATopology.add_sites(self, sites)
        for site in sites:
            nsite_atoms = len(site.atom_positions)
            if not hasattr(site, "atom_indices"):
                site.atom_indices = range(self.natoms, self.natoms+nsite_atoms)
            self.natoms += nsite_atoms
            
    def get_atom_labels(self):
        labels=[]
        for s in self.sites:
            for t in s.atom_types:
                labels.append(str(t))
        return labels
    
    def to_atomistic(self, rbcoords):
        ca = self.coords_adapter(rbcoords)
        atomistic = np.zeros([self.natoms,3])
        for site, com, p in zip(self.sites, ca.posRigid, ca.rotRigid):
            atoms = site.to_atomistic(com, p)
            for i,x in zip(site.atom_indices, atoms):
                atomistic[i]=x
        return atomistic

    def transform_gradient(self, rbcoords, grad):
        ca = self.coords_adapter(rbcoords)
        rbgrad = self.coords_adapter(np.zeros_like(rbcoords))
        for site, p, g_com, g_p in zip(self.sites, ca.rotRigid,
                                       rbgrad.posRigid,rbgrad.rotRigid):
            g_com[:], g_p[:] = site.transform_grad(p, grad.reshape(-1,3)[site.atom_indices])
        return rbgrad.coords
                
    def redistribute_gradient(self, rbcoords, rbgrad):
        ca = self.coords_adapter(rbcoords)
        cg = self.coords_adapter(rbgrad)
        grad = np.zeros([self.natoms,3])
        for site, p, g_com, g_p in zip(self.sites, ca.rotRigid, cg.posRigid, cg.rotRigid):
            gatom = site.redistribute_forces(p, g_com, g_p)
            for i,x in zip(site.atom_indices, gatom):
                grad[i]=x
        return grad
    
class RBPotentialWrapper(potential):
    def __init__(self, rbsystem, pot):
        self.pot = pot
        self.rbsystem = rbsystem
        
    def getEnergy(self, rbcoords):
        coords = self.rbsystem.to_atomistic(rbcoords)
        return self.pot.getEnergy(coords.flatten())
    
    def getEnergyGradient(self, rbcoords):
        coords = self.rbsystem.to_atomistic(rbcoords)
        E, g = self.pot.getEnergyGradient(coords.flatten())
        return E, self.rbsystem.transform_gradient(rbcoords, g)
    
    
if __name__ == "__main__":
    from math import sin, cos, pi
    from copy import deepcopy
    water = RigidFragment()
    rho   = 0.9572
    theta = 104.52/180.0*pi      
    water.add_atom("O", np.array([0., -1., 0.]), 1.)
    water.add_atom("O", np.array([0., 1., 0.]), 1.)
    #water.add_atom("H", rho*np.array([0.0, sin(0.5*theta), cos(0.5*theta)]), 1.)
    #water.add_atom("H", rho*np.array([0.0, -sin(0.5*theta), cos(0.5*theta)]), 1.)
    water.finalize_setup()
    # define the whole water system
    system = RBTopology()
    nrigid = 1
    system.add_sites([deepcopy(water) for i in xrange(nrigid)])
    from pygmin.utils import rotations
    rbcoords=np.zeros(6)
    rbcoords[3:]= rotations.random_aa()
    
    coords = system.to_atomistic(rbcoords)
    
    print "rb coords\n", rbcoords
    print "coords\n", coords
    grad = (np.random.random(coords.shape) -0.5)
    
    v = coords[1] - coords[0]
    v/=np.linalg.norm(v)
    
    grad[0] -= np.dot(grad[0], v)*v
    grad[1] -= np.dot(grad[1], v)*v
    
    grad -= np.average(grad, axis=0)
    grad /= np.linalg.norm(grad)
    
    print "torque", np.linalg.norm(np.cross(grad, v))
    rbgrad = system.transform_gradient(rbcoords, grad)
    p = rbcoords[3:]
    x = rbcoords[0:3]
    gp = rbgrad[3:]
    gx = rbgrad[:3]
    
    from pygmin.potentials.fortran.rmdrvt import rmdrvt as rotMatDeriv
    R, R1, R2, R3 = rotMatDeriv(p, True)        
    
    print "test1", np.linalg.norm(R1*gp[0])     
    print "test2", np.linalg.norm(R2*gp[1])     
    print "test3", np.linalg.norm(R3*gp[2])
    print "test4", np.linalg.norm(R1*gp[0]) + np.linalg.norm(R2*gp[1]) + np.linalg.norm(R3*gp[2])
         
    dR = R1*gp[0] + R2*gp[1] + R3*gp[2]
    print "test", np.linalg.norm(R1*gp[0] + R2*gp[1] + R3*gp[2])
    print np.trace(np.dot(dR, dR.transpose()))
    G = water.metric_tensor_aa(p)
    print np.dot(p, np.dot(G, p))     
    exit()
    
    
    gnew = system.redistribute_forces(rbcoords, rbgrad)
    print gnew
    print system.transform_grad(rbcoords, gnew)
    
    
