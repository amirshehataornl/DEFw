from defw_util import prformat, fg, bg
from .svc_qhpc import *
import sys

# This is used by the infrastructure to display information about
# the service module. The name is also used as a key through out the
# infrastructure. Without it the service module will not load.
svc_info = {'name': 'Quantum HPC',
			'description': 'Quantum HPC Service',
			'version': 1.0}

# This is used by the infrastructure to define all the service classes.
# Each class should be a separate service. Each class should implement the
# following methods:
#	query()
#	reserve()
#	release()
service_classes = [Qhpc]

def initialize():
	# Initialize the service. EX: start threads/processes, etc
	sys.path.append('/home/a2e/ORNL/Quantum/install/qCuda_July3_2023/xacc')
	prformat(fg.green+fg.bold, "registering the Quantum HPC")

def uninitialize():
	prformat(fg.green+fg.bold, "unregistering the Quantum HPC")
