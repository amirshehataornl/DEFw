import cdefw_global
from cdefw_agent import *
from defw_common_def import *
from defw_exception import *
import yaml, logging, sys, ctypes, uuid
import ipaddress, traceback

class Endpoint:
	def __init__(self, addr, port, listen_port, pid, name, hostname,
				 node_type, remote_uuid, blk_uuid=str(uuid.UUID(int=0))):
		if not (node_type == EN_DEFW_RESMGR or \
				node_type == EN_DEFW_SERVICE or \
				node_type == EN_DEFW_AGENT):
			raise IFWError("Unknown node type provided: ", node_type)
		self.addr = addr
		self.port = port
		self.listen_port = listen_port
		self.pid = pid
		self.name = name
		self.hostname = hostname
		self.node_type = node_type
		self.remote_uuid = remote_uuid
		self.blk_uuid = blk_uuid

	def __repr__(self):
		return yaml.dump(self.get())

	def __eq__(self, other):
		if not isinstance(other, Endpoint):
			return False
		return defw_agent_uuid_compare(self.remote_uuid, other.remote_uuid)

	def is_service(self):
		return self.node_type == EN_DEFW_SERVICE

	def is_resmgr(self):
		return self.node_type == EN_DEFW_RESMGR

	def get(self):
		info = {self.name: {'remote uuid': self.remote_uuid,
					'block uuid': self.blk_uuid,
					'hostname': self.hostname,
					'addr': self.addr,
					'listen port': self.listen_port,
					'connection port': self.port,
					'pid': self.pid,
					'node-type': self.node_type2str()}
				}
		return info

	def node_type2str(self):
		if self.node_type == EN_DEFW_RESMGR:
			nt = 'RESMGR'
		elif self.node_type == EN_DEFW_AGENT:
			nt = 'AGENT'
		elif self.node_type == EN_DEFW_SERVICE:
			nt = 'SERVICE'
		else:
			raise IFWError("Unknown node type provided: ", self.node_type)

		return nt

	def dump(self):
		print(yaml.dump(self.get(), sort_keys=False))

class Agent:
	def __init__(self, endpoint):
		self.__endpoint = endpoint
		self.name = endpoint.name
		pref = load_pref()
		self.timeout = pref['RPC timeout']

	def get_ep(self):
		return self.__endpoint

	def get_remote_uuid(self):
		return self.__endpoint.remote_uuid

	def get_blk_uuid(self):
		return self.__endpoint.blk_uuid

	def is_resmgr(self):
		return self.__endpoint.is_resmgr()

	def dump(self):
		self.__endpoint.dump()

	def get(self):
		return self.__endpoint.get()

	def get_name(self):
		return self.name

	def get_node_type(self):
		return self.__endpoint.node_type

	def get_addr(self):
		return self.__endpoint.addr

	def get_hostname(self):
		return self.__endpoint.hostname

	def get_pid(self):
		return self.__endpoint.pid

	def get_port(self):
		return self.__endpoint.port

	def set_rpc_timeout(self, timeout):
		self.timeout = timeout

	def send_req(self, rpc_type, src, module, cname,
				 mname, class_id, blocking, *args, **kwargs):
		import defw_workers

		if not mname:
			raise IFWError("A method or a function name need to be specified")

		rpc = populate_rpc_req(src, self.__endpoint, rpc_type, module, cname,
				       mname, class_id, *args, **kwargs)
		wr = defw_workers.WorkerRequest(defw_workers.WorkerRequest.WR_SEND_MSG,
									   remote_uuid=self.__endpoint.remote_uuid,
									   blk_uuid=self.__endpoint.blk_uuid,
									   msg=rpc,
									   blocking=blocking)
		y = defw_workers.send_req(wr)

		if not blocking:
			return 0

		target = y['rpc']['dst']
		if not target == src:
			raise IFWError("MSG intended to %s but I am %s" % (target, src))

		source = y['rpc']['src']
		if not source == self.__endpoint:
			raise IFWError("MSG originated from %s but expected from %s" %
					 (source, self.name))

		if y['rpc']['type'] == 'failure':
			raise IFWRemoteError('RPC failure')

		if y['rpc']['type'] == 'exception':
			if type(y['rpc']['exception']) == str:
				raise IFWRemoteError(nname=source, msg=y['rpc']['exception'])
			else:
				raise y['rpc']['exception']

		return y['rpc']['rc']

class IfwAgents:
	"""
	A class to access all agents. This is useful to get a view of all agents currently connected
	"""
	def __init__(self, agent_dict, get_agent_cb):
		self.agent_dict = agent_dict
		self.get_agent_cb = get_agent_cb
		self.max = 0
		self.n = 0
		self.reload()

	def __iter__(self):
		self.n = 0
		return self

	def __contains__(self, item):
		return item in self.agent_dict

	# needed for python 3.x
	def __next__(self):
		if self.n < self.max:
			key = list(self.agent_dict.keys())[self.n]
			agent = self.agent_dict[key]
			self.n += 1
			return key, agent
		else:
			raise StopIteration

	def __getitem__(self, key):
		try:
			rc = self.agent_dict[key]
		except:
			raise IFWError('no entry for', key)
		return rc

	def __setitem__(self, endpoint):
		if endpoint.name not in self.agent_dict.keys():
			self.connect(endpoint)

	def items(self):
		return [(key, self.agent_dict[key]) for key in self.agent_dict]

	def keys(self):
		self.reload()
		return list(self.agent_dict.keys())

	def values(self):
		self.reload()
		return list(self.agent_dict.values())

	def connect(self, endpoint):
		import defw_workers
		wr = defw_workers.WorkerRequest(defw_workers.WorkerRequest.WR_CONNECT,
									   remote_uuid=endpoint.remote_uuid,
									   ep=endpoint)
		defw_workers.connect_to_agent(wr)
		self.reload()

	def reload(self):
		self.agent_dict = {}
		self.max = 0
		agent = None
		defw_lock_agent_lists()
		try:
			while True:
				agent = self.get_agent_cb(agent)
				if not agent:
					break
				if agent:
					remote_uuid, blk_uuid = defw_get_agent_uuid(agent)
					ep = Endpoint(defw_agent_ip2str(agent),
							defw_agent_get_port(agent),
							defw_agent_get_listen_port(agent),
							defw_agent_get_pid(agent),
							agent.name,
							agent.hostname,
							agent.node_type,
							remote_uuid,
							blk_uuid = blk_uuid)
					if agent.name not in self.agent_dict:
						self.max += 1
					self.agent_dict[agent.name] = Agent(ep)
					defw_release_agent_blk_unlocked(agent, False)
		except:
			pass
		defw_release_agent_lists()

	def get_resmgr(self):
		self.reload()
		for name, agent in self.agent_dict.items():
			if agent.is_resmgr():
				return agent.get_ep()

	# always update the dictionary for the following two operations
	def dump(self):
		self.reload()
		for k, v in self.agent_dict.items():
			v.dump()

	def enable_hb_check(self):
		defw_agent_enable_hb()

	def disable_hb_check(self):
		defw_agent_disable_hb()

class IfwServiceAgents(IfwAgents):
	def __init__(self):
		self.__agent_dict = {}
		super().__init__(self.__agent_dict, defw_get_next_service_agent)

class IfwClientAgents(IfwAgents):
	def __init__(self):
		self.__agent_dict = {}
		super().__init__(self.__agent_dict, defw_get_next_client_agent)

class IfwActiveServiceAgents(IfwAgents):
	def __init__(self):
		self.__agent_dict = {}
		super().__init__(self.__agent_dict, defw_get_next_active_service_agent)

class IfwActiveClientAgents(IfwAgents):
	def __init__(self):
		self.__agent_dict = {}
		super().__init__(self.__agent_dict, defw_get_next_active_client_agent)

