#ifndef LIBIFW_AGENT_H
#define LIBIFW_AGENT_H

#include <stdbool.h>
#include "defw_agent.h"

typedef int (*process_agent)(defw_agent_blk_t *agent, void *user_data);

/*
 * agent_init
 *	Initialize the agent module
 */
void defw_agent_init(void);

/* defw_agent_get_highest_fd
 *	Find the highest connected FD in all connected agents.
 */
int defw_agent_get_highest_fd(void);

/*
 * defw_find_create_agent_blk_by_addr
 *	return an agent block with this address or create a new one
 */
defw_agent_blk_t *defw_find_create_agent_blk_by_addr(struct sockaddr_in *addr);

/*
 * defw_alloc_agent_blk
 *	allocate an agent block
 */
defw_agent_blk_t *defw_alloc_agent_blk(struct sockaddr_in *addr, bool add);

/*
 * acquire_agent_blk
 *	acquire the agent for work
 */
void acquire_agent_blk(defw_agent_blk_t *agent);

/*
 * agent_get_hb
 *	Get current HB state
 */
int agent_get_hb(void);

/*
 * get the number of registered agents
 */
int get_num_service_agents(void);
int get_num_client_agents(void);

/*
 * set_agent_state
 *
 * convenience function to set the agent state
 */
void set_agent_state(defw_agent_blk_t *agent, unsigned int state);

/*
 * unset_agent_state
 *
 * unset the state and check if the agent is a zombie and
 * it has not pending work. If so then free it
 */
void unset_agent_state(defw_agent_blk_t *agent, unsigned int state);


/*
 * defw_release_agent_conn
 *	release an agent connection
 */
void defw_release_agent_conn(defw_agent_blk_t *agent);

/*
 * defw_get_next_new_agent_conn
 *	Iterate over the agent blocks on the new list
 */
defw_agent_blk_t *defw_get_next_new_agent_conn(defw_agent_blk_t *agent);

defw_rc_t defw_send_hb(defw_agent_blk_t *agent);
defw_rc_t defw_send_session_info(defw_agent_blk_t *agent, bool rpc_setup);
defw_agent_blk_t *defw_find_agent_by_uuid_global(defw_agent_uuid_t *id);
defw_agent_blk_t *defw_find_agent_by_uuid_passive(uuid_t uuid);
void defw_move_to_client_list(defw_agent_blk_t *agent);
void defw_move_to_service_list(defw_agent_blk_t *agent);
void defw_release_dead_list_agents(void);
void defw_service_agent_iter(process_agent cb, void *user_data);
void defw_client_agent_iter(process_agent cb, void *user_data);
void defw_active_service_agent_iter(process_agent cb, void *user_data);
void defw_active_client_agent_iter(process_agent cb, void *user_data);
void defw_new_agent_iter(process_agent cb, void *user_data);

#endif /* LIBIFW_AGENT_H */
