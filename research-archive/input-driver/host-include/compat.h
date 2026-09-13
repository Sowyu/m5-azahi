/* Include Darwin's uuid typedef before renaming the kernel-tools typedef. */
#include <sys/types.h>
#include <sys/stat.h>
#include <unistd.h>
#define uuid_t linux_modpost_uuid_t
