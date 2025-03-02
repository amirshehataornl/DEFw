export DEFW_PATH=/sw/crusher/ums/ompix/DEVELOP/source/DEFw
export DEFW_CONFIG_PATH=$DEFW_PATH/python/config/defw_generic.yaml
export LD_LIBRARY_PATH=$DEFW_PATH/src/:$LD_LIBRARY_PATH
export DEFW_AGENT_NAME=resmgr
export DEFW_LISTEN_PORT=8090
export DEFW_AGENT_TYPE=resmgr
export DEFW_PARENT_HOSTNAME=$(hostname)
export DEFW_PARENT_PORT=8090
export DEFW_TELNET_PORT=8091
export DEFW_PARENT_NAME=resmgr
export DEFW_SHELL_TYPE=interative
export DEFW_LOG_LEVEL=all
export DEFW_LOG_DIR=/tmp/${DEFW_AGENT_NAME}
export DEFW_ONLY_LOAD_MODULE=svc_resmgr,svc_libfabric
export DEFW_EXTERNAL_SERVICES_PATH=/sw/crusher/ums/ompix/DEVELOP/source/libfabric-amir/python/
