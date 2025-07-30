#ifndef DEFW_MESSAGE_H
#define DEFW_MESSAGE_H

#include "defw_common.h"

typedef struct defw_agent_uuid_s {
	uuid_t remote_uuid;  /* uuid of the remote process/agent */
	uuid_t blk_uuid; /* assigned locally. unique to agent */
} defw_agent_uuid_t;

typedef enum {
	EN_MSG_TYPE_HB = 0,
	EN_MSG_TYPE_SESSION_INFO,
	EN_MSG_TYPE_GET_NUM_AGENTS,
	EN_MSG_TYPE_PY_REQUEST,
	EN_MSG_TYPE_PY_RESPONSE,
	EN_MSG_TYPE_PY_EVENT,
	EN_MSG_TYPE_MAX
} defw_msg_type_t;

typedef struct defw_message_hdr_s {
	defw_msg_type_t type;
	unsigned int len;
	struct in_addr ip;
	unsigned int version;
} defw_message_hdr_t;

/* add a uuid in the session message.
 * Active sends to passive as part of session creation
 * Passive sends to active in the heart beat
 */
typedef struct defw_msg_session_s {
	defw_agent_uuid_t agent_id;
	defw_type_t node_type;
	pid_t pid;
	int rpc_setup;
	int listen_port;
	char node_name[MAX_STR_LEN];
	char node_hostname[MAX_STR_LEN];
} defw_msg_session_t;

typedef struct defw_msg_num_agents_query_s {
	int num_agents;
} defw_msg_num_agents_query_t;

#endif /* DEFW_MESSAGE_H */
