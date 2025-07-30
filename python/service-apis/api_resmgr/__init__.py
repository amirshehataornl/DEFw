from defw_util import prformat, fg, bg
from .api_resmgr import *

# This is used by the infrastructure to display information about
# the service module
svc_info = {'name': 'Resource Manager',
			'description': 'DEFw Framework Resource Manager',
			'version': 1.0}

# This is used by the infrastructure to define all the service classes.
# Each class should be a separate service. Each class should implement the
# following methods:
#	query()
#	reserve()
#	release()
service_classes = [DEFwResMgr]

def initialize():
	pass

def uninitialize():
	pass
