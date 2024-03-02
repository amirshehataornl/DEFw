#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <arpa/inet.h>
#include <sys/time.h>
#include <pthread.h>
#include <string.h>
#include <signal.h>
#include <uuid/uuid.h>
#include "defw.h"
#include "defw_python.h"
#include "defw_agent.h"
#include "defw_global.h"
#include "libdefw_agent.h"
#include "defw_message.h"
#include "defw_listener.h"

fd_set g_tAllSet;
int g_iMaxSelectFd = INVALID_TCP_SOCKET;
static int g_iListenFd = INVALID_TCP_SOCKET;
static bool g_bShutdown;
bool resmgr_connected;
bool resmgr_connect_in_progress;
pthread_mutex_t global_var_mutex;

typedef struct connection_info_s {
	int *iNReady;
	fd_set *tReadSet;
} connection_info_t;

typedef defw_rc_t (*msg_process_fn_t)(char *msg, defw_agent_blk_t *agent);

static defw_rc_t process_msg_hb(char *msg, defw_agent_blk_t *agent);
static defw_rc_t process_msg_get_num_agents(char *msg, defw_agent_blk_t *agent);
static defw_rc_t process_msg_py_request(char *msg, defw_agent_blk_t *agent);
static defw_rc_t process_msg_py_response(char *msg, defw_agent_blk_t *agent);
static defw_rc_t process_msg_session_info(char *msg, defw_agent_blk_t *agent);

static msg_process_fn_t msg_process_tbl[EN_MSG_TYPE_MAX] = {
	[EN_MSG_TYPE_HB] = process_msg_hb,
	[EN_MSG_TYPE_GET_NUM_AGENTS] = process_msg_get_num_agents,
	[EN_MSG_TYPE_PY_REQUEST] = process_msg_py_request,
	[EN_MSG_TYPE_PY_RESPONSE] = process_msg_py_response,
	[EN_MSG_TYPE_SESSION_INFO] = process_msg_session_info,
};

static void set_resmgr_connected(defw_rc_t status, uuid_t uuid)
{
	pthread_mutex_lock(&global_var_mutex);
	if (!status)
		resmgr_connected = true;
	else
		resmgr_connected = false;
	resmgr_connect_in_progress = false;
	pthread_mutex_unlock(&global_var_mutex);
}

void defw_listener_shutdown(void)
{
	g_bShutdown = true;
}

int defw_get_highest_fd(void)
{
	int iAgentFd = defw_agent_get_highest_fd();
	int iMaxFd;

	if (iAgentFd > g_iListenFd)
		iMaxFd = iAgentFd;
	else
		iMaxFd = g_iListenFd;
	PDEBUG("Current highest FD = %d", iMaxFd);

	return iMaxFd;
}

static defw_rc_t process_msg_py_request(char *msg, defw_agent_blk_t *agent)
{
	defw_rc_t rc;
	char *uuid = calloc(1, UUID_STR_LEN);
	uuid_unparse_lower(agent->id.blk_uuid, uuid);

	agent->state |= DEFW_AGENT_WORK_IN_PROGRESS;
	rc = python_handle_request(msg, uuid);
	agent->state &= ~DEFW_AGENT_WORK_IN_PROGRESS;

	return rc;
}

/* An RPC reponse means the agent that there a thread waiting on the
 * response to arrive. Signal the agent that a response has arrived.
 *
 * There could be one outstanding response per agent.
 */
static defw_rc_t process_msg_py_response(char *msg, defw_agent_blk_t *agent)
{
	defw_rc_t rc;
	char *uuid = calloc(1, UUID_STR_LEN);
	uuid_unparse_lower(agent->id.blk_uuid, uuid);

	agent->state |= DEFW_AGENT_WORK_IN_PROGRESS;
	rc = python_handle_response(msg, uuid);
	agent->state &= ~DEFW_AGENT_WORK_IN_PROGRESS;

	return rc;
}

static defw_rc_t process_msg_session_info(char *msg, defw_agent_blk_t *agent)
{
	defw_msg_session_t *ses = (defw_msg_session_t *)msg;
	defw_agent_blk_t *existing;
	defw_type_t agent_type = ntohl(ses->node_type);

	if (agent_type != EN_DEFW_AGENT &&
	    agent_type != EN_DEFW_SERVICE &&
	    agent_type != EN_DEFW_RESMGR)
		return EN_DEFW_RC_PROTO_ERROR;

	/* This is an agent on the new list. Let's see if there exists an
	 * agent that has the session information */
	existing = defw_find_agent_by_uuid_passive(ses->agent_id.remote_uuid);
	if (existing) {
		existing->iRpcFd = agent->iFileDesc;
		PDEBUG("existing = %p, agent = %p", existing, agent);
		PDEBUG("Second connection on an existing agent is the RPC connection: %d",
		       existing->iRpcFd);
		if (ses->rpc_setup)
			set_agent_state(existing, DEFW_AGENT_RPC_CHANNEL_CONNECTED);
		/* release ref count acquired when you found the agent */
		defw_release_agent_blk(existing, false);
		/* agent should never be the same as existing.
		 * existing looks at the client and service lists while
		 * the agent passed in here should always be from the new
		 * list
		 */
		assert(agent != existing);
		defw_release_agent_blk(agent, false);
		python_refresh_agent();
		return EN_DEFW_RC_OK;
	}

	if (ses->rpc_setup) {
		PERROR("Protocol Error. Setup of RPC before CNTRL");
		//defw_release_agent_blk(agent, true);
		return EN_DEFW_RC_PROTO_ERROR;
	}

	if (agent_type == EN_DEFW_AGENT)
		defw_move_to_client_list(agent);
	else
		defw_move_to_service_list(agent);

	PDEBUG("First connection on a new agent is the Cntrl connection: %d",
		agent->iFileDesc);
	/* update the agent with the information */
	uuid_copy(agent->id.remote_uuid, ses->agent_id.remote_uuid);
	agent->node_type = agent_type;
	agent->pid = ntohl(ses->pid);
	agent->listen_port = ntohl(ses->listen_port);
	strncpy(agent->hostname, ses->node_hostname, MAX_STR_LEN);
	agent->hostname[MAX_STR_LEN-1] = '\0';
	strncpy(agent->name, ses->node_name, MAX_STR_LEN);
	agent->name[MAX_STR_LEN-1] = '\0';
	set_agent_state(agent, DEFW_AGENT_CNTRL_CHANNEL_CONNECTED);
	set_agent_state(agent, DEFW_AGENT_STATE_ALIVE);
	unset_agent_state(agent, DEFW_AGENT_STATE_NEW);
	gettimeofday(&agent->time_stamp, NULL);

	return EN_DEFW_RC_OK;
}

static defw_rc_t process_msg_hb(char *msg, defw_agent_blk_t *agent)
{
	defw_msg_session_t *hb = (defw_msg_session_t *)msg;
	/*
	char uuid[UUID_STR_LEN];
	char uuid2[UUID_STR_LEN];
	*/
	/* update the agent with the information */
	/* TODO: Can check if the uuid has changed for security. If the
	 * uuid has been set before and the connection has not been dropped,
	 * but the uuid changed then this could be from an impostor.
	 */
	if (uuid_is_null(agent->id.remote_uuid)) {
		uuid_copy(agent->id.remote_uuid, hb->agent_id.remote_uuid);
		python_refresh_agent();
	} else if (uuid_compare(agent->id.remote_uuid,
				hb->agent_id.remote_uuid)) {
		PERROR("Agent %s has changed it's uuid. Has it restarted?",
		       agent->name);
	}
/*
	uuid_unparse_lower(agent->id.remote_uuid, uuid);
	uuid_unparse_lower(agent->id.blk_uuid, uuid2);
	PDEBUG("Received a heartbeat from %s-%s", uuid, uuid2);
*/
	agent->node_type = ntohl(hb->node_type);
	agent->pid = ntohl(hb->pid);
	strncpy(agent->hostname, hb->node_hostname, MAX_STR_LEN);
	agent->hostname[MAX_STR_LEN-1] = '\0';
	strncpy(agent->name, hb->node_name, MAX_STR_LEN);
	agent->name[MAX_STR_LEN-1] = '\0';
	gettimeofday(&agent->time_stamp, NULL);

	return EN_DEFW_RC_OK;
}

static defw_rc_t process_msg_get_num_agents(char *msg, defw_agent_blk_t *agent)
{
	defw_rc_t rc;
	defw_msg_num_agents_query_t query;

	query.num_agents = get_num_service_agents() + get_num_client_agents();
	rc = sendTcpMessage(agent->iFileDesc, (char *)&query, sizeof(query));
	if (rc) {
		PERROR("failed to send tcp message to get num agents query");
		return rc;
	}

	return EN_DEFW_RC_OK;
}

static defw_rc_t process_agent_message(defw_agent_blk_t *agent, int fd)
{
	defw_rc_t rc = EN_DEFW_RC_OK;
	defw_message_hdr_t hdr;
	char *buffer;
	msg_process_fn_t proc_fn;

	/* get the header first */
	rc = readTcpMessage(fd, (char *)&hdr, sizeof(hdr),
			    TCP_READ_TIMEOUT_SEC, false);

	if (rc)
		return rc;

	hdr.version = ntohl(hdr.version);
	if (hdr.version != DEFW_VERSION_NUMBER) {
		PERROR("version %d != %d", hdr.version,
		       DEFW_VERSION_NUMBER);
		return EN_DEFW_RC_BAD_VERSION;
	}

	/* if the ips don't match ignore the message */
	if (memcmp(&agent->addr.sin_addr, &hdr.ip, sizeof(hdr.ip))) {
		PERROR("IP addresses don't match");
		return rc;
	}

	hdr.type = ntohl(hdr.type);
	hdr.len = ntohl(hdr.len);

	if (hdr.type >= EN_MSG_TYPE_MAX) {
		PERROR("Received an unknown message: %d", hdr.type);
		return EN_DEFW_RC_UNKNOWN_MESSAGE;
	}

	buffer = calloc(hdr.len, 1);
	if (!buffer)
		return EN_DEFW_RC_OOM;

	/* get the rest of the message */
	rc = readTcpMessage(fd, buffer, hdr.len,
			    TCP_READ_TIMEOUT_SEC, false);

	if (rc) {
		free(buffer);
		return rc;
	}

	/* call the appropriate processing function */
	proc_fn = msg_process_tbl[hdr.type];
	if (proc_fn)
		rc = proc_fn(buffer, agent);

	if (rc != EN_DEFW_RC_KEEP_DATA)
		free(buffer);

	if (rc == EN_DEFW_RC_KEEP_DATA)
		return EN_DEFW_RC_OK;

	return rc;
}

int process_new_agents_helper(defw_agent_blk_t *agent, void *user_data)
{
	connection_info_t *info = user_data;
	int *iNReady = info->iNReady;
	fd_set *tReadSet = info->tReadSet;
	int hb_fd = INVALID_TCP_SOCKET, rpc_fd = INVALID_TCP_SOCKET, rc;

	if (*iNReady) {
		if (FD_ISSET(agent->iFileDesc, tReadSet))
			hb_fd = agent->iFileDesc;
		if (FD_ISSET(agent->iRpcFd, tReadSet))
			rpc_fd = agent->iRpcFd;

		/* need to release reference on the connection here,
		 * because by the time the message gets processed the
		 * agent might've moved over to another list
		 */
		defw_release_agent_conn(agent);

		if (rpc_fd != INVALID_TCP_SOCKET &&
		    hb_fd == INVALID_TCP_SOCKET) {
			PERROR("agent connection is unexpected (%p) hb_fd = %d, rpc_fd = %d",
			       agent, hb_fd, rpc_fd);
			goto out;
		}

		if (hb_fd != INVALID_TCP_SOCKET) {
			rc = process_agent_message(agent, hb_fd);
			FD_CLR(hb_fd, tReadSet);
			if (rc)
				PERROR("Error processing new agent: %s", defw_rc2str(rc));
			(*iNReady)--;
		}
	}

out:
	if (*iNReady)
		return 0;
	return 1;
}

static defw_rc_t process_new_agents(fd_set *tReadSet, int *iNReady)
{
	connection_info_t info;
	info.iNReady = iNReady;
	info.tReadSet = tReadSet;

	defw_new_agent_iter(process_new_agents_helper, &info);

	return EN_DEFW_RC_OK;
}

static int process_active_agents_helper(defw_agent_blk_t *agent, void *user_data)
{
	connection_info_t *info = user_data;
	int *iNReady = info->iNReady;
	fd_set *tReadSet = info->tReadSet;
	int hb_fd = INVALID_TCP_SOCKET, rpc_fd = INVALID_TCP_SOCKET, rc;
	bool dead = false;

	if (*iNReady) {
		if (FD_ISSET(agent->iFileDesc, tReadSet))
			hb_fd = agent->iFileDesc;
		if (FD_ISSET(agent->iRpcFd, tReadSet))
			rpc_fd = agent->iRpcFd;

		if (hb_fd == INVALID_TCP_SOCKET &&
		    rpc_fd == INVALID_TCP_SOCKET)
			goto out;

		/* process heart beat */
		if (hb_fd != INVALID_TCP_SOCKET) {
			/* process the message */
			rc = process_agent_message(agent, hb_fd);
			FD_CLR(hb_fd, tReadSet);
			(*iNReady)--;
			if (rc) {
				if (agent->node_type == EN_DEFW_RESMGR)
					set_resmgr_connected(rc, NULL);
				PERROR("CTRL msg failure: %s: %d", defw_rc2str(rc),
				       agent->node_type);
				dead = true;
				goto out;
			}
		}

		if (*iNReady <= 0)
			goto out;

		/* process rpc */
		if (rpc_fd != INVALID_TCP_SOCKET) {
			/* process the message */
			PDEBUG("Received a message on %p:%d\n", agent, rpc_fd);
			rc = process_agent_message(agent, rpc_fd);
			FD_CLR(rpc_fd, tReadSet);
			(*iNReady)--;
			if (rc && rc != EN_DEFW_RC_NO_DATA_ON_SOCKET) {
				if (agent->node_type == EN_DEFW_RESMGR)
					set_resmgr_connected(rc, NULL);
				dead = true;
				PERROR("RPC msg failure: %s: %d", defw_rc2str(rc),
				       agent->node_type);
				goto out;
			}
		}
	}

out:
	defw_release_agent_blk(agent, dead);

	if (*iNReady)
		return 0;
	return 1;
}

static defw_rc_t process_active_agents(fd_set *tReadSet, bool service, int *iNReady)
{
	connection_info_t info;
	info.iNReady = iNReady;
	info.tReadSet = tReadSet;

	if (service) {
		defw_active_service_agent_iter(process_active_agents_helper, &info);
		defw_service_agent_iter(process_active_agents_helper, &info);
	} else {
		defw_active_client_agent_iter(process_active_agents_helper, &info);
		defw_client_agent_iter(process_active_agents_helper, &info);
	}

	return EN_DEFW_RC_OK;
}

static defw_rc_t init_comm(struct sockaddr_in *listen_addr)
{
	int iFlags;
	struct sockaddr_in sServAddr;

	signal(SIGPIPE, SIG_IGN);

	/*  Create a socket to listen to.  */
	g_iListenFd = socket(AF_INET, SOCK_STREAM, 0);
	if (g_iListenFd < 0) {
		/*  Cannot create a listening socket.  */
		return EN_DEFW_RC_SOCKET_FAIL;
	}

	/* Set a socket option which will allow us to be quickly restarted
	 * if necessary.
	 */
	iFlags = 1;
	if (setsockopt(g_iListenFd, SOL_SOCKET, SO_REUSEADDR, (void *) &iFlags,
		       sizeof(iFlags)) < 0) {
		/*  Cannot change the socket options.  */
		closeTcpConnection(g_iListenFd);
		return EN_DEFW_RC_FAIL;
	}

	/*  Bind to our listening socket.  */
	bzero((char *) &sServAddr, sizeof(sServAddr));
	sServAddr.sin_family = AF_INET;
	sServAddr.sin_addr.s_addr = htonl(listen_addr->sin_addr.s_addr);
	sServAddr.sin_port = htons(listen_addr->sin_port);

	if (bind(g_iListenFd, (struct sockaddr *) &sServAddr,
		 sizeof(sServAddr)) < 0) {
		/*  Cannot bind our listening socket.  */
		closeTcpConnection(g_iListenFd);
		return EN_DEFW_RC_BIND_FAILED;
	}

	/* Let the system know we wish to listen to this port for
	 * connections.
	 */
	if (listen(g_iListenFd, 2) < 0) {
		/*  Cannot listen to socket, close and fail  */
		closeTcpConnection(g_iListenFd);
		return EN_DEFW_RC_LISTEN_FAILED;
	}

	/* We want this socket to be non-blocking even though it will be used
	 * in a blocking select call. This is to avoid a problem identified by
	 * Richard Stevens.
	 */
	iFlags = fcntl(g_iListenFd, F_GETFL, 0);
	fcntl(g_iListenFd, F_SETFL, iFlags | O_NONBLOCK);

	/*  Add the listening socket to our select() mask.  */
	FD_ZERO(&g_tAllSet);
	FD_SET(g_iListenFd, &g_tAllSet);

	return EN_DEFW_RC_OK;
}

void agent_hb_check(struct timeval *t, defw_type_t me)
{
	defw_agent_blk_t *agent = NULL;

	while (1) {
		agent = defw_get_next_client_agent(agent);
		if (!agent)
			break;
		if (t->tv_sec - agent->time_stamp.tv_sec >= HB_TO*100) {
			/* agent didn't send a HB move to dead list
			 */
			PERROR("agent %s presumed dead", agent->name);
			defw_release_agent_blk(agent, true);
			continue;
		}
		defw_release_agent_blk(agent, false);
	}
}

static int send_hb_to_agents(defw_agent_blk_t *agent, void *user_data)
{
	bool dead = false;
	defw_rc_t rc;

	rc = defw_send_hb(agent);
	if (rc != EN_DEFW_RC_OK)
		dead = true;
	defw_release_agent_blk(agent, dead);

	return 0;
}

/*
 * defw_listener_main
 *   main loop.  Listens for incoming agent connections, and for agent
 *   messages.  Every period of time it triggers a walk through the agent
 *   list to see if any of the HBs stopped
 *
 *   If I am an Agent, then attempt to connect to the resmgr and add an
 *   agent block on the list of agents. After successful connection send
 *   a regular heart beat.
 *
 *   Since the resmgr's agent block is on the list of agents and its FD is
 *   on the select FD set, then if the resmgr sends the agent a message
 *   the agent should be able to process it.
 */
static void *defw_listener_main(void *usr_data)
{
	int iConnFd;
	struct sockaddr_in sCliAddr;
	socklen_t  tCliLen;
	fd_set tReadSet;
	int iNReady;
	defw_rc_t rc;
	defw_agent_blk_t *agent = NULL;
	struct timeval time_1, time_2, select_to;
	defw_listener_info_t *info;
	bool send_hb_now = false;

	resmgr_connect_in_progress = false;
	resmgr_connected = false;

	info = (defw_listener_info_t *)usr_data;
	if ((!info) ||
	    ((info) && (info->listen_address.sin_port == 0))) {
		PERROR("No liston port provided");
		return NULL;
	}

	rc = init_comm(&info->listen_address);
	if (rc) {
		PERROR("init_comm failed: %s", defw_rc2str(rc));
		return NULL;
	}

	defw_agent_init();

	g_iMaxSelectFd = g_iListenFd;

	gettimeofday(&time_2, NULL);

	/*  Main Processing Loop: Keep going until we have reason
	 * to shutdown.
	 */
	while (!g_bShutdown) {
		/*  Wait on our select mask for an event to occur.  */
		select_to.tv_sec = HB_TO;
		select_to.tv_usec = 0;

		FD_ZERO(&tReadSet);
		tReadSet = g_tAllSet;
		iNReady = select(g_iMaxSelectFd + 1, &tReadSet, NULL, NULL,
				 &select_to);

		defw_release_dead_list_agents();

		/* Everyone registers with the resmgr, even the resmgr
		 * registers with itself
		 */
		if (!resmgr_connected && strlen(get_parent_name()) != 0 &&
		    !resmgr_connect_in_progress) {
			char *resmgr_name = get_parent_name();
			char *ip_addr = get_parent_address();
			int port = get_parent_port();

			PDEBUG("Attempting a connection on resmgr %s:%s:%d",
			       resmgr_name, ip_addr, port);
			rc = defw_connect_to_service(get_parent_address(), get_parent_port(),
						    get_parent_name(), get_parent_hostname(),
						    EN_DEFW_RESMGR, NULL, set_resmgr_connected);
			if (rc == EN_DEFW_RC_IN_PROGRESS) {
				pthread_mutex_lock(&global_var_mutex);
				resmgr_connect_in_progress = true;
				pthread_mutex_unlock(&global_var_mutex);
			}
		}

		/*  Determine if we failed the select call */
		if (iNReady < 0) {
			/*  Check to see if we were interrupted by a signal.  */
			if ((errno == EINTR) || (errno == EAGAIN)) {
				PERROR("Select failure: errno = %d", errno);
			} else if (errno != ECONNABORTED) {
				/* If this is an ECONNABORTED error, just
				 * ignore it. Raise a fatal alarm and shut
				 * down.
				 */
				PERROR("Shutting down Listener thread. errno: %d",
				       errno);
				defw_listener_shutdown();
			}

			/* store the current time */
			time_1 = time_2;

			/* Zero out the g_tAllSet */
			FD_ZERO(&g_tAllSet);

			continue;
		}

		if (FD_ISSET(g_iListenFd, &tReadSet)) {
			/* A new incoming connection */
			tCliLen = sizeof(sCliAddr);
			iConnFd = accept(g_iListenFd,
					 (struct sockaddr *) &sCliAddr,
					 &tCliLen);
			if (iConnFd < 0) {
				/*  Cannot accept new connection... just ignore.
				 */
				if (errno != EWOULDBLOCK)
					PERROR("Error on accept(), errno = %d", errno);
			} else {
				PDEBUG("Accepted a connection on %d from client port %d",
				       iConnFd, sCliAddr.sin_port);
				send_hb_now = true;
				/* For new connections we create an agent
				 * block, which goes on the new list. It
				 * stays there until the client sends
				 * session information we're able to
				 * figure out if it's a new agent or a new
				 * connection on an existing agent.
				 */
				agent = defw_find_create_agent_blk_by_addr(&sCliAddr);
				if (!agent) {
					/*  Cannot support more clients...just ignore.  */
					PERROR("Cannot accept more clients");
					closeTcpConnection(iConnFd);
				} else {
					int iOption, iFlags;

					PDEBUG("Received a connection (%p) from %s on FD %d",
					       agent, inet_ntoa(agent->addr.sin_addr), iConnFd);

					agent->iFileDesc = iConnFd;

					/*  Add new client to our select mask.  */
					FD_SET(iConnFd, &g_tAllSet);
					g_iMaxSelectFd = defw_get_highest_fd();

					/* Ok, it seems that the connected socket gains
					 * the same flags as the listen socket.  We want
					 * to make it blocking here.
					 */
					iFlags = fcntl(iConnFd, F_GETFL, 0);
					fcntl(iConnFd, F_SETFL, iFlags & (~O_NONBLOCK));

					/*  And, we want to turn off Nagle's algorithm to
					 *  reduce latency
					 */
					iOption = 1;
					setsockopt(iConnFd, IPPROTO_TCP, TCP_NODELAY,
						   (void *)&iOption,
						   sizeof(iOption));
				}
			}

			/*  See if there are other messages waiting.  */
			iNReady--;
		}

		/* Let's go over the agents we know about and see if any
		 * of them received a message. We first go over the new
		 * list to see if we can consolidate them to existing
		 * agents or move it to one of the other lists.
		 *
		 * Then we go over the service list and process messages
		 * sent from them.
		 *
		 * Finally we go over the client list and process messages
		 * sent from them
		 */
		if (iNReady)
			process_new_agents(&tReadSet, &iNReady);
		if (iNReady)
			process_active_agents(&tReadSet, true, &iNReady);
		if (iNReady)
			process_active_agents(&tReadSet, false, &iNReady);

		/*
		 * Each node can have a list of clients connected to it
		 * and a list of services connected to it. It can also be
		 * connected to other services.
		 *
		 * For all services we're connected to, we need to send
		 * a heart beat to tell them we're still around.
		 *
		 * For all clients connected to us, we expect a heart beat
		 * to tell us they are still alive. Otherwise we clean
		 * them up.
		 */
		gettimeofday(&time_2, NULL);
		if (agent_get_hb()) {
			/* check if HB_TO seconds has passed since the last
			 * time we collected the time
			 */
			if (time_2.tv_sec - time_1.tv_sec >= HB_TO * 100) {
				/* do the heartbeat check */
				agent_hb_check(&time_1, info->type);
			}
		}

		if (time_2.tv_sec - time_1.tv_sec >= HB_TO || send_hb_now) {
			defw_active_service_agent_iter(send_hb_to_agents, NULL);
			defw_service_agent_iter(send_hb_to_agents, NULL);
			defw_active_client_agent_iter(send_hb_to_agents, NULL);
			defw_client_agent_iter(send_hb_to_agents, NULL);
			send_hb_now = false;
		}

		/* store the current time */
		memcpy(&time_1, &time_2, sizeof(time_1));
	}

	/* Zero out the g_tAllSet */
	FD_ZERO(&g_tAllSet);

	return NULL;
}

defw_rc_t defw_spawn_listener(pthread_t *id)
{
	pthread_t tid;
	pthread_t *ptid;
	int trc;

	if (id)
		ptid = id;
	else
		ptid = &tid;

	/* initialize global mutex used for protecting global variables */
	pthread_mutex_init(&global_var_mutex, NULL);

	/*
	 * Spawn the listener thread if we are in resmgr Mode.
	 * The listener thread listens for Heart beats and deals
	 * with maintaining the health of the agents. If an agent
	 * dies and comes back again, then we know how to deal
	 * with it.
	 */
	trc = pthread_create(ptid, NULL,
			     defw_listener_main,
			     &g_defw_cfg.l_info);
	if (trc) {
		PERROR("Failed to start listener thread");
		return EN_DEFW_RC_ERR_THREAD_STARTUP;
	}

	return EN_DEFW_RC_OK;
}
