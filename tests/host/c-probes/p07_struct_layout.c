/* probe: struct layout with explicit padding, and packed behaviour */
#include <stddef.h>
struct hdr { unsigned char ver; unsigned char flags; unsigned short op; unsigned int len; unsigned int corr; };
typedef char hdr_size[(sizeof(struct hdr) == 12) ? 1 : -1];
typedef char op_off[(offsetof(struct hdr, op) == 2) ? 1 : -1];
typedef char len_off[(offsetof(struct hdr, len) == 4) ? 1 : -1];
struct pk { unsigned char a; unsigned int b; } __attribute__((packed));
typedef char pk_size[(sizeof(struct pk) == 5) ? 1 : -1];
