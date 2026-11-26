/* OSE-004 hello: prints a fixed line and returns the value given in PARM
 * (0 when none), so the batch test can check a planted step RC. */
#include <stdio.h>
#include <stdlib.h>

int
main(int argc, char **argv)
{
    int rc = (argc > 1) ? atoi(argv[1]) : 0;

    printf("OSE-004 HELLO RC=%d\n", rc);
    return rc;
}
