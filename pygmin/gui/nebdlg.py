import matplotlib
matplotlib.use("QT4Agg")

from collections import deque
import numpy as np
from PyQt4.QtGui import QDialog, QApplication
import sys

from pygmin.storage import Database
from pygmin.utils.events import Signal
import ui.nebbrowser

def no_event(*args, **kwargs):
    return


# the following lines implement the ability to follow the status of the
# NEB in real time.  the callback is passed to the NEB and plots the
# last several values of the energies of the path.  The implementation
# is quite simple and could easily be a lot faster.
# set follow_neb=False to turn this off
class NEBCallback(object):
    def __init__(self, plw, axes, frq=30, nplots=3):
        self.count = 0
        self.nplots = nplots
        self.data = deque()
        self.frq = frq
        self.process_events = Signal()
        self.plw = plw
        self.axes = axes
        
        
    def __call__(self, energies=None, distances=None, **kwargs):
        self.count += 1
        if self.count % self.frq == 1:
#            print "plotting NEB energies"
            S = np.zeros(energies.shape)
            S[1:] = np.cumsum(distances)
            self.data.append((S, energies.copy()))
            if len(self.data) > self.nplots:
                self.data.popleft()
            self.axes.clear()
            for S, E in self.data:
                line, = self.axes.plot(S, E, "o-")
                # note: if we save the line and use line.set_ydata(E)
                # this would be a lot faster, but we would have to keep
                # track of the y-axis limits manually
            self.axes.set_ylabel("NEB image energy")
            self.axes.set_xlabel("distance along the path")
            self.plw.draw()
            self.process_events()



class NEBDialog(QDialog):
    def __init__(self):
        super(NEBDialog, self).__init__()
                
        self.ui = ui.nebbrowser.Ui_Form()
        self.ui.setupUi(self)
        self.plw = self.ui.widget
        
#        self.plw.axes.set_ylabel("NEB image energy")
#        pl.xlabel("distance along the path")
        
#        self.system = system
#        self.min1 = min1
#        self.min2 = min2
        
#        self.minimum_selected = Signal()
        # self.minimum_selected(minim)
    
        #the function which tells the eventloop to continue processing events
        #if this is not set, the plots will stall and not show until the end of the NEB run.
        #ideally it is the function app.processEvents where app is returned by
        #app = QApplication(sys.argv)
        self.process_events = Signal()
            

    def attach_to_NEB(self, neb):
        neb_callback = NEBCallback(self.plw, self.plw.axes)
        neb_callback.process_events.connect(self.process_events)        
        neb.events.append(neb_callback)

def getNEB(coords1, coords2, system):
    """setup the NEB object"""
    throwaway_db = Database()
    min1 = throwaway_db.addMinimum(0., coords1)
    min2 = throwaway_db.addMinimum(1., coords2)
    #use the functions in DoubleEndedConnect to set up the NEB in the proper way
    double_ended = system.get_double_ended_connect(min1, min2, 
                                                        throwaway_db, 
                                                        fresh_connect=True)
    local_connect = double_ended._getLocalConnectObject()

    
    
    neb =  local_connect._getNEB(system.get_potential(),
                                      coords1, coords2,
                                      verbose=True,
                                      **local_connect.NEBparams)        
    
    return neb


def start():
    print "starting  neb"
    neb = getNEB(x1, x2, system)
#    wnd.do_NEB(min1.coords, min2.coords)
    wnd.attach_to_NEB(neb)
    neb.optimize()
    
if __name__ == "__main__":
    from pygmin.systems import LJCluster
    from pygmin.storage import Database
    import pylab as pl
    app = QApplication(sys.argv)
    
    def process_events():
        app.processEvents()
    
    #setup system
    natoms = 13
    system = LJCluster(natoms)
    x1, e1 = system.get_random_minimized_configuration()[:2]
    x2, e2 = system.get_random_minimized_configuration()[:2]
    db = Database()
    min1 = db.addMinimum(e1, x1)
    min2 = db.addMinimum(e2, x2)
    
    #setup neb dialog
    pl.ion()
#    pl.show()
    wnd = NEBDialog()   
    wnd.show()
    wnd.process_events.connect(process_events)

    #initilize the NEB and run it.
    #we have to do it through QTimer because the gui has to 
    #be intitialized first... I don't really understand it 
    from PyQt4.QtCore import QTimer
    QTimer.singleShot(10, start)
        
    sys.exit(app.exec_()) 
        