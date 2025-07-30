from .api_events import *

# This is used by the infrastructure to display information about
# the service module. The name is also used as a key through out the
# infrastructure. Without it the service module will not load.
svc_info = {'name': 'EventHandler',
			'description': 'Event Handling API',
			'version': 1.0}

service_classes = [BaseEventAPI]

def initialize():
	pass

def uninitialize():
	pass
