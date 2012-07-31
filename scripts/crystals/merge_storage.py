'''
Created on Jul 27, 2012

@author: vr274
'''
from pygmin.utils.rbtools import *
from pygmin.storage import savenlowest
from pygmin.utils import crystals
import pickle

save = savenlowest.SaveN(nsave=1000, accuracy=1e-3)
save.compareMinima = compareMinima

import sys
for i in sys.argv[1:]:
    print i
    save2 = pickle.load(open(i, "r"))
    for m in save2.data:
        save.insert(m.E, m.coords)

pickle.dump(save, open("storage", "w"))
