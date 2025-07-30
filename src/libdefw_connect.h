/*---------------------------------------------------------------------------
 * 
 * libdefw_connect.h 
 *
 *     03/26/2024 - 
 *
 *     <shehataa@crusher.olcf.ornl.gov>
 *
 *     Copyright (c) 2024 RedBack Networks, Inc.
 *     All rights reserved.
 *
 *---------------------------------------------------------------------------
 */

#ifndef LIBDEFW_CONNECT_H
#define LIBDEFW_CONNECT_H

#include "defw_message.h"

int establishTCPConnection(unsigned long uiAddress,
			   int iPort,
			   bool b_non_block,
			   bool endian);


defw_rc_t sendTcpMessage(int iTcpSocket, char *pcBody, int iBodySize);

defw_rc_t defw_send_msg(int fd, char *msg, size_t msg_size,
			defw_msg_type_t type);

defw_rc_t populateMsgHdr(int rsocket, char *msg_hdr,
			 int msg_type, int msg_size,
			 int defw_version_number);

defw_rc_t readTcpMessage(int iFd, char *pcBuffer,
			int iBufferSize, int iTimeout,
			bool force_wait);

defw_rc_t closeTcpConnection(int iTcpSocket);

#endif /* LIBDEFW_CONNECT_H */
