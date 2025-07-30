#include <stdlib.h>
#include "defw_sl.h"

int
main(int argc, char *argv[])
{
	defw_rc_t rc;

	rc = defw_start(argc, argv);

	switch (rc) {
	case EN_DEFW_RC_OK:
		exit(DEFW_EXIT_NORMAL);
	case EN_DEFW_RC_LOG_CREATION_FAILURE:
		exit(DEFW_EXIT_ERR_BAD_PARAM);
	default:
		exit(DEFW_EXIT_ERR_STARTUP);
	}

	return DEFW_EXIT_NORMAL;
}
