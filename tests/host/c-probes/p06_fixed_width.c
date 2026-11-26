/* probe: <stdint.h> exact-width types and their sizes */
#include <stdint.h>
typedef char u8_ok[(sizeof(uint8_t) == 1) ? 1 : -1];
typedef char u16_ok[(sizeof(uint16_t) == 2) ? 1 : -1];
typedef char u32_ok[(sizeof(uint32_t) == 4) ? 1 : -1];
typedef char i32_ok[(sizeof(int32_t) == 4) ? 1 : -1];
typedef char ptr_ok[(sizeof(void *) == 4) ? 1 : -1];
