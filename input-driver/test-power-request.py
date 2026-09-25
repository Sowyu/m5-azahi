#!/usr/bin/env python3
"""Compile the actual patched function against a recording transport stub."""
from pathlib import Path
import os
import shlex
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
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) + ["-Wall", "-Wextra", "-Wno-unused-parameter", str(c), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: OFF/ON v2 bytes, will/has ordering, both error paths, unchanged old-board request")

# Audit kernel-c C1/M4: execute the actual receiver with every byte-valued
# interface and with allocation failure. No device or kernel access.
start = source.index("static void dchid_handle_packet(void *cookie, size_t avail)\n{")
end = source.index("\nstatic int dockchannel_hid_probe", start)
receiver = source[start:end]
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define MAX_INTERFACES 16
#define DCHID_CHANNEL_CMD 0
#define DCHID_CHANNEL_REPORT 1
#define GFP_KERNEL 0
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define INIT_WORK(...) ((void)0)
struct dchid_hdr { u8 hdr_len, iface, channel; uint16_t length; };
struct dchid_subhdr { u8 flags, unk; uint16_t length; u32 retcode; };
struct dchid_iface { void *wq; };
struct dockchannel_hid { void *dev, *dc; struct dchid_iface *ifaces[16]; u8 pkt_buf[64]; };
struct dchid_work { struct dchid_hdr hdr; struct dchid_iface *iface; int work; u8 data[]; };
static struct dchid_hdr incoming;
static int receives, rearms, acks, queued, allocations, fail_alloc;
static int dockchannel_recv(void *dc, void *dest, size_t n) {
 if (!receives++) { assert(n==sizeof(incoming)); memcpy(dest,&incoming,n); }
 else { assert(n<=64); memset(dest,0,n); }
 return (int)n;
}
static u32 dchid_checksum(void *p, size_t n) { return receives==2 && n==sizeof(incoming) ? 0xffffffffu : 0; }
static void dchid_handle_ack(struct dchid_iface *i, struct dchid_hdr *h, void *p) { assert(i); acks++; }
static void *kzalloc(size_t n, int flags) { allocations++; return fail_alloc ? NULL : calloc(1,n); }
static void queue_work(void *wq, int *w) {
 struct dchid_work *item=(void *)((char *)w - __builtin_offsetof(struct dchid_work,work));
 queued++; free(item);
}
static void dockchannel_await(void *dc, void (*fn)(void *,size_t), void *cookie, size_t n) { rearms++; }
'''
test = r'''
int main(void) {
 struct dockchannel_hid d={0}; struct dchid_iface i={0};
 for (int n=0;n<16;n++) d.ifaces[n]=&i;
 incoming.hdr_len=sizeof(incoming); incoming.length=sizeof(struct dchid_subhdr);
 for (int n=0;n<256;n++) {
  incoming.iface=n; incoming.channel=DCHID_CHANNEL_CMD;
  receives=rearms=acks=queued=allocations=fail_alloc=0;
  dchid_handle_packet(&d,64);
  assert(rearms==1 && acks==(n<16) && allocations==0);
 }
 incoming.iface=1; incoming.channel=DCHID_CHANNEL_REPORT;
 for (int fail=0;fail<=1;fail++) {
  receives=rearms=acks=queued=allocations=0; fail_alloc=fail;
  dchid_handle_packet(&d,64);
  assert(rearms==1 && allocations==1 && queued==!fail);
 }
 fail_alloc=0;
 for (int length=0;length<(int)sizeof(struct dchid_subhdr);length++) {
  incoming.length=length;
  for (int channel=DCHID_CHANNEL_CMD;channel<=DCHID_CHANNEL_REPORT;channel++) {
   incoming.channel=channel; receives=rearms=acks=queued=allocations=0;
   dchid_handle_packet(&d,64);
   assert(rearms==1 && acks==0 && allocations==0);
  }
 }
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="azahi-receiver-test-") as temporary:
    binary = Path(temporary) / "test"
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) +
                   ["-Wall", "-Wextra", "-Wno-unused-parameter", "-fsanitize=address,undefined",
                    "-x", "c", "-", "-o", str(binary)],
                   input=stub + receiver + test, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: receiver interface values 0..255; allocation success/failure re-arm; short packets dropped; ASan/UBSan")

# Audit kernel-c H1/M1: the ACK copy and the timeout cleanup share resp_lock,
# and the returned length counts only bytes stored in the caller's buffer.
start = source.index("static int dchid_cmd(")
end = source.index("\nstatic int dchid_comm_cmd(", start)
command = source[start:end]
start = source.index("static void dchid_handle_ack(")
end = source.index("\nstatic void dchid_handle_packet(", start)
ack = source[start:end]
stub = r'''
#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int spinlock_t;
#define __packed __attribute__((packed))
#define FLAGS_GROUP 0xc0
#define FLAGS_REQ 0x3f
#define FIELD_PREP(m, v) ((((u32)(v)) << __builtin_ctz(m)) & (m))
#define COMMAND_TIMEOUT_MS 1000
#define msecs_to_jiffies(x) (x)
#define WARN_ON(x) assert(!(x))
#define dev_err(...) ((void)0)
#define min(a, b) ((a) < (b) ? (a) : (b))
struct dchid_hdr { u8 hdr_len, channel; u16 length; u8 seq, iface; u16 pad; } __packed;
struct dchid_subhdr { u8 flags, unk; u16 length; u32 retcode; } __packed;
struct dockchannel_hid { void *dev; };
struct dchid_iface {
 struct dockchannel_hid *dchid; int index; const char *name; u8 tx_seq; int out_mutex;
 spinlock_t resp_lock; u32 out_flags; int out_report; u32 retcode; void *resp_buf;
 size_t resp_size; int out_complete;
};
#define OWNER(l) ((struct dchid_iface *)((char *)(l) - offsetof(struct dchid_iface, resp_lock)))
static int locked, cleared_under_lock;
static void *buf_at_lock;
static void spin_lock(spinlock_t *l) { assert(!locked); locked=1; buf_at_lock=OWNER(l)->resp_buf; }
static void spin_unlock(spinlock_t *l) { assert(locked); locked=0; cleared_under_lock += buf_at_lock && !OWNER(l)->resp_buf; }
static void mutex_lock(int *m) {}
static void mutex_unlock(int *m) {}
static void reinit_completion(int *c) { *c=0; }
static void complete(int *c) { *c=1; }
static void (*on_wait)(struct dchid_iface *);
static struct dchid_iface *in_flight;
static unsigned long wait_for_completion_timeout(int *c, unsigned long t) { if (on_wait) on_wait(in_flight); return *c; }
static int dchid_send(struct dchid_iface *i, u32 flags, void *msg, size_t size) { in_flight=i; return 0; }
#define memcpy(d, s, n) (assert(locked), __builtin_memcpy(d, s, n))
'''
test = r'''
#undef memcpy
static u8 pkt[64];
static struct dchid_hdr ackhdr;
static int reply_length;
static void make_ack(u8 flags, u8 seq, u8 report, int length) {
 struct dchid_subhdr *shdr=(void *)pkt;
 memset(pkt,0,sizeof(pkt)); shdr->flags=flags; shdr->length=length;
 pkt[sizeof(*shdr)]=report;
 for (int n=1;n<length;n++) pkt[sizeof(*shdr)+n]=0xa0+n;
 ackhdr.seq=seq; ackhdr.length=sizeof(*shdr)+length;
}
static void deliver(struct dchid_iface *i) {
 make_ack(i->out_flags,i->tx_seq,i->out_report,reply_length);
 dchid_handle_ack(i,&ackhdr,pkt);
}
int main(void) {
 struct dockchannel_hid d={0};
 struct dchid_iface i={ .dchid=&d, .out_report=-1 };
 u8 id=0x10, set[3]={0x10,1,2};
 u8 *buf=malloc(4);
 on_wait=deliver; reply_length=21;
 assert(dchid_cmd(&i,2,1,&id,1,buf,4)==5);
 for (int n=0;n<4;n++) assert(buf[n]==0xa1+n);
 reply_length=3;
 assert(dchid_cmd(&i,1,0,set,3,NULL,0)==3);
 on_wait=NULL; cleared_under_lock=0;
 u8 seq=i.tx_seq;
 assert(dchid_cmd(&i,2,1,&id,1,buf,4)==-ETIMEDOUT && cleared_under_lock==1);
 free(buf);
 make_ack(0x81,seq,id,21);
 dchid_handle_ack(&i,&ackhdr,pkt);
 assert(!locked && i.out_report==-1);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="azahi-ack-test-") as temporary:
    binary = Path(temporary) / "test"
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) +
                   ["-Wall", "-Wextra", "-Wno-unused-parameter", "-fsanitize=address,undefined",
                    "-x", "c", "-", "-o", str(binary)],
                   input=stub + command + ack + test, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: ACK copy and timeout cleanup under resp_lock; stored-length return; late ACK ignored; ASan/UBSan")
