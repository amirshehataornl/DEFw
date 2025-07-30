from defw_remote import BaseRemote
from enum import IntFlag

class ResMgrType(IntFlag):
	RESMGR_TYPE_DEFW = 1 << 0

class ResMgrCapability(IntFlag):
	RESMGR_CAP_DEFW = 1 << 0

"""
Interface module for the Resource Manager
"""

class DEFwResMgr(BaseRemote):
	def __init__(self, si):
		super().__init__(service_info = si)

	"""
	Register a client with the Resource Manager

	Args:
		client_ep (endpoint): Client endpoint

	Returns:
		None

	Raises:
		DEFwCommError: If Resource Manager is not reachable
	"""
	def register_agent(self, client_ep):
		pass

	"""
	return true only when all of the expected agents are connected

	Args:
		None

	Return:
		None

	Raises:
		DEFwInProgress: If the number of indicated processes hadn't connected yet
		DEFwInternalError: If the number of expected agents is not configured
	"""
	def ready_agents(self):
		pass

	"""
	Wait for all the expected agents to connect

	Args:
		timeout [optional]: timeout to wait for agents to connect

	Return:
		None

	Raises:
		DEFwCommError: if timeout expires
		DEFwInProgress: If the number of indicated processes hadn't connected yet
		DEFwInternalError: If the number of expected agents is not configured
	"""
	def wait_agents(self, timeout=10):
		pass

	"""
	Retrieve the context information the agents registered

	Args:
		None

	Return:
		None

	Raises:
		DEFwNotFound: If the number of contexts doesn't match number of registered agents
	"""
	def get_agents_context(self):
		pass

	def deregister_agent(self, ep):
		pass

	def wait_agents_deregistration(self, timeout = 10):
		pass

	"""
	Register a service with the Resource Manager

	Args:
		client_ep (endpoint): service endpoint

	Returns:
		agent: An agent class instance which references the service

	Raises:
		DEFwCommError: If Resource Manager is not reachable
	"""
	def register_service(self, service_ep):
		pass

	"""
	De-register an agent

	Args:
		agent (Agent): Agent instance to deregister

	Returns:
		None

	Raises:
		DEFwCommError: If Resource Manager is not reachable
		DEFwAgentNotFound: If agent is not registered
	"""
	def deregister(self, agent_ep):
		pass

	"""
	List all available Agents in the DEFw Network

	Args:
		service_filter: a string to filter services on

	Returns:
		dict: dictionary of services available on each agent

	Raises:
		DEFwCommError: If Resource Manager is not reachable
	"""
	def get_services(self, service_filter=None):
		pass

	"""
	Reserve an Agent which exists on the DEFw Network

	Args:
		servics (dict): Dictionary of services to reserve

	Returns:
		None

	Raises:
		DEFwCommError: If Resource Manager is not reachable
		DEFwReserveError: If there is an error in the reservation process
	"""
	def reserve(self, services):
		pass

	"""
	Release a reserved Agent

	Args:
		servics (dict): Dictionary of services to release

	Returns:
		None

	Raises:
		DEFwCommError: If Resource Manager is not reachable
		DEFwReserveError: If there is an error in the release process
	"""
	def release(self, agents):
		pass



