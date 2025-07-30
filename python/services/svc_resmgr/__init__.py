from defw_util import prformat, fg, bg
from .svc_resmgr import DEFwResMgr

SERVICE_NAME = 'DEFwResMgr'
SERVICE_DESC = 'DEFw Service Resource Manager'

# This is used by the infrastructure to display information about
# the service module
svc_info = {'name': 'Resource Manager',
			'module': __name__,
			'description': SERVICE_DESC,
			'version': 1.0}

# This is used by the infrastructure to define all the service classes.
# Each class should be a separate service. Each class should implement the
# following methods:
#	query()
#	reserve()
#	release()
service_classes = [DEFwResMgr]

def initialize():
	# Initialize the service. EX: start threads/processes, etc
	prformat(fg.green+fg.bold, "registering the Resource Manager")

def uninitialize():
	prformat(fg.green+fg.bold, "unregistering the Resource Manager")
