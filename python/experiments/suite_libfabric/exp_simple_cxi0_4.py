import yaml, sys, time, os
from defw_app_util import *
from defw import me
from util_data import *
from defw_exception import DEFwOperationFailure

def progress(fab, cq, requests, completed_reqs, once=False):
	num_reqs = len(requests)
	logging.debug(f"{os.getpid()}: waiting for operations {num_reqs} to complete")
	# wait for the send to complete
	start = time.time()
	while completed_reqs != num_reqs:
		if time.time() - start > 10:
			raise DEFwOperationFailure(f"Test did not finish. " \
					f"completed_requests {completed_reqs} " \
					f"num_reqs {num_reqs}")
		try:
			rc, events = cq.read()
		except Exception as e:
			if type(e) == ValueError:
				raise e
			if once:
				return completed_reqs
			continue
		logging.debug(f"{os.getpid()}: cq.read() return {rc}, num of events {len(events)}")
		for ev in events:
			req = fab.get_op_context(ev.op_context)
			logging.debug(f"op {req.req_id} for pid {req.pid} completed")
			for r in requests:
				logging.debug(f"Pending op {r.req_id} for pid {r.pid} completed")
				if r.req_id == req.req_id and r.pid == req.pid:
					completed_reqs += 1
		if once:
			return completed_reqs
	return completed_reqs

def send_data(ep, cq, num_snd, pid, request_id, requests, addrs, tag, completed_reqs):
	for i in range(0, num_snd):
		req = fab.ReqContext(pid, request_id)
		request_id += 1
		req_context = req.get_context()
		requests.append(req_context)
		buf = generate_data(1024, tag)
		if not 'send_buf' in addrs:
			addrs['send_buf'] = []
		addrs['send_buf'].append(buf)
		logging.debug(f"{os.getpid()}: sending to {pid}:{addrs['fi_addrs'][0]}:{tag}")
		start = time.time()
		while True:
			try:
				ep.tsenddata(buf, addrs['fi_addrs'][0], tag, req_context)
				break
			except Exception as e:
				if type(e) == ValueError:
					raise e
				# progress and then try again.
				completed_reqs = progress(fab, cq, requests, completed_reqs, once=True)
				if time.time() - start > 60:
					raise DEFwOperationFailure(f"{os.getpid()}: Couldn't send data")
	return request_id, completed_reqs

def post_recv(ep, num_rcv, pid, request_id, requests, addrs, tag):
	for i in range(0, num_rcv):
		req = fab.ReqContext(pid, request_id)
		request_id += 1
		req_context = req.get_context()
		requests.append(req_context)
		buf = bytearray(1024)
		if not 'recv_buf' in addrs:
			addrs['recv_buf'] = []
		addrs['recv_buf'].append(buf)
		logging.debug(f"{os.getpid()}: posting receive from {pid}:{addrs['fi_addrs'][0]}:{tag}")
		ep.post_trecv(buf, addrs['fi_addrs'][0], tag, 0, req_context)
	return request_id

def run():
	global fab

	# connect to the resource manager
	logging.debug(f"{os.getpid()}: Starting test with {sys.argv[1]}")
	rsmgr = defw_get_resource_mgr()

	logging.debug(f"{os.getpid()}: got resmgr {rsmgr}")

	# initialize libfabric
	fabric = services['libfabric'].get_service_class()
	fab = fabric()
	dom = fab.add_domain(sys.argv[1])
	ep = dom.add_ep()
	cq = dom.add_cq()
	av = dom.add_av()
	ep.bind_cq(cq)
	ep.bind_av(av)
	ep.enable()
	logging.debug(f"{os.getpid()}: libfabric configured")
	# get your endpoint address
	addr = ep.get_name()
	# publish it to the resource manager
	rsmgr.register_agent(me.my_endpoint(), addr)
	# Wait until all processes in the world has connected
	rsmgr.wait_agents()
	# get the addresses
	addrs = rsmgr.get_agents_context()
	logging.debug(f"{os.getpid()}: peers contexts {addrs}")
	if len(addrs) != 2:
		raise DEFwError("This test handles exactly 2 processes")

	peers = {}
	for pid, addr in addrs.items():
		fi_addr = av.insert_addr(addr)
		peers[pid] = {'fi_addrs': fi_addr}
	logging.debug(f"{os.getpid()}: peers table {peers}")

	logging.debug(f"{os.getpid()}: posting receives")
	request_id = 100
	tag = 1000
	requests = []
	completed_reqs = 0
	for pid, addrs in peers.items():
		if me.my_pid() != pid:
			request_id = post_recv(ep, 4, pid, request_id, requests, addrs, tag)

	logging.debug(f"{os.getpid()}: sending data")
	tag = 1000
	for pid, addrs in peers.items():
		if me.my_pid() != pid:
			request_id, completed_reqs = send_data(ep, cq, 4, pid, request_id,
							requests, addrs, tag, completed_reqs)

	completed_reqs = progress(fab, cq, requests, completed_reqs)
	logging.debug('Test Successful')

	fab.close()

if __name__ == '__main__':
	try:
		run()
	except Exception as e:
		logging.debug(e)
		logging.debug('Test Failure')
		raise e
