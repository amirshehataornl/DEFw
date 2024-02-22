
# 1. Bring up the Resource Manager, Quantum Resource and the Client
# 2. Show the Client message log -> enable messaging only

import yaml

# Show the Active Resource on the client
AS()

# dump available Service APIs which is available. We should've been
# provided with the Quantum Resource API
service_apis.dump()

# Get available services from the Resource Manager
r = resmgr.get_services()

# print available resources
print(yaml.dump(r))

# reserve the Quantum Resource
ep = resmgr.reserve(me.my_endpoint(), r)

# print the endpoint
print(yaml.dump(ep))

# connect to the endpoint(s)
defw.connect_to_services(ep)

# Show the Active Resources, now we should see the Quantum Resource as
# well
AS()

#instantiate the Quantum Resource API so you can use it
class_obj = getattr(service_apis['Quantum HPC'], r['qhpc']['api'])
qhpc_api = class_obj(ep[0])

# ----NOTE:
# All the above can be abstracted away from the user

# Start of Quantum Resource usage

# Read a QASM circuit you want to execute
with open("/home/a2e/ORNL/Quantum/intersect/qhpc/python/experiments/suite_qhpc/dj.qasm", "r") as f:
    qasm_str = f.read()

# Create 3 circuits with the same QASM code
cid = qhpc_api.create_circuit(qasm_str, nbits=17)
cid2 = qhpc_api.create_circuit(qasm_str, nbits=17)
cid3 = qhpc_api.create_circuit(qasm_str, nbits=17)

# synchronous runs
result = qhpc_api.sync_run(cid)
result2 = qhpc_api.sync_run(cid2)
result3 = qhpc_api.sync_run(cid3)
# print synchronous run results
print(yaml.dump(result))
print(yaml.dump(result2))
print(yaml.dump(result3))

# a synchronous runs
aresult = qhpc_api.async_run(cid)
aresult2 = qhpc_api.async_run(cid2)
aresult3 = qhpc_api.async_run(cid3)

# check the status of the asynchronous runs
print(yaml.dump(qhpc_api.status()))

# peek the completion queue
print(yaml.dump(qhpc_api.peek_cq()))

# grab the results from the completion queue
while True:
    r = qhpc_api.read_cq()
    if r:
        print(yaml.dump(r))
    else:
        break

qhpc_api.delete_circuit(cid)
qhpc_api.delete_circuit(cid2)
qhpc_api.delete_circuit(cid3)
qhpc_api.delete_circuit(cid)

