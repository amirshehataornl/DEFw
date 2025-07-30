from defw_agent import *

class ServiceDescriptor:
	def __init__(self, name, uuid, service_type, capabilities):
		self.name = name
		self.service_type = service_type
		self.caps = capabilities
		self.uuid = uuid

class Service:
	def __init__(self, agent, service_descriptor):
		self.agent_descriptor = agent_descriptor
		self.service_descriptor = service_descriptor

# Resource Manager reservation API takes a ServiceDescriptor object and
# returns back a Service API object which the client can immediately call.
# The infrastructure takes care of all the object instantiation and
# handling of Agents, effectively abstracting away all communication
# information from the user.

class ServiceCollection:
class DataChannel(Endpoint):
class CntrlChannel(Endpoint):

class ExAgent():
	def __init__(self, ip, port,):
		self.__data_channel = DataChannel()
		
