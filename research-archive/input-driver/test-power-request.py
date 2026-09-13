#!/usr/bin/env python3
"""Compile the actual patched function against a recording transport stub."""
from pathlib import Path
import subprocess
import tempfile

source = (Path(__file__).parent / "dockchannel-hid.c").read_text()
start = source.index("static int dchid_reset_interface(")
end = source.index("\nstatic int dchid_send_firmware(", start)
function = source[start:end]
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
typedef uint8_t u8;
#define CMD_RESET_INTERFACE 0x40
#define dev_info(...) ((void)0)
struct dockchannel_hid { void *dev; };
struct dchid_iface { int index; struct dockchannel_hid *dchid; };
static int board, count, fail_at;
static u8 packets[2][9];
static unsigned lengths[2];
static int of_machine_is_compatible(const char *s) {
    assert(!strcmp(s, "apple,j714s")); return board;
}
static int dchid_comm_cmd(struct dockchannel_hid *d, void *p, unsigned n) {
    assert(count < 2 && n <= 9);
    memcpy(packets[count], p, n); lengths[count] = n;
    count++; return count == fail_at ? -5 : 0;
}
'''
test = r'''
int main(void) {
    struct dockchannel_hid d = {0};
    struct dchid_iface i = { .index=1, .dchid=&d };
    for (int state=0; state<=2; state+=2) {
        board=1; count=0; fail_at=0;
        assert(dchid_reset_interface(&i,state)==0 && count==2);
        for (int phase=0; phase<2; phase++) {
            u8 expected[9]={0x40,2,1,state,phase,0,0,0,0};
            assert(lengths[phase]==9 && !memcmp(packets[phase],expected,9));
        }
    }
    for (int failure=1; failure<=2; failure++) {
        board=1; count=0; fail_at=failure;
        assert(dchid_reset_interface(&i,2)==-5 && count==failure);
    }
    board=0; count=0; fail_at=0;
    assert(dchid_reset_interface(&i,2)==0 && count==1);
    u8 old[4]={0x40,1,1,2};
    assert(lengths[0]==4 && !memcmp(packets[0],old,4));
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="azahi-power-test-") as temporary:
    c = Path(temporary) / "test.c"
    binary = Path(temporary) / "test"
    c.write_text(stub + function + test)
    subprocess.run(["clang", "-Wall", "-Wextra", "-Wno-unused-parameter", str(c), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: OFF/ON v2 bytes, will/has ordering, both error paths, unchanged old-board request")
