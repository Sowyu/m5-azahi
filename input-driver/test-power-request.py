#!/usr/bin/env python3
"""Compile the actual patched function against a recording transport stub."""
from pathlib import Path
from contextlib import contextmanager
import os
import shlex
import shutil
import subprocess
import tempfile


@contextmanager
def temporary_directory(prefix):
    if not shutil.which('trash-put'):
        raise RuntimeError('Install trash-cli: sudo apt-get install -y trash-cli')
    path = tempfile.mkdtemp(prefix=prefix)
    try:
        yield path
    finally:
        subprocess.run(['trash-put', path], check=True)

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
with temporary_directory(prefix="azahi-power-test-") as temporary:
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
with temporary_directory(prefix="azahi-receiver-test-") as temporary:
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
with temporary_directory(prefix="azahi-ack-test-") as temporary:
    binary = Path(temporary) / "test"
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) +
                   ["-Wall", "-Wextra", "-Wno-unused-parameter", "-fsanitize=address,undefined",
                    "-x", "c", "-", "-o", str(binary)],
                   input=stub + command + ack + test, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print("PASS: ACK copy and timeout cleanup under resp_lock; stored-length return; late ACK ignored; ASan/UBSan")

# Firmware lookup succeeds only on zero. A nonzero result must not let the
# caller consume unset output pointers or start GPIO/firmware hardware work.
start = source.index("static int dchid_start_interface(")
end = source.index("\nstatic int dchid_start(", start)
function = source[start:end]
stub = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
struct dchid_iface { bool starting; unsigned gpio_id; };
static int result, calls;
static int dchid_get_firmware(struct dchid_iface *i, void **fw, size_t *size) {
    (void)i;
    if (result) return result;
    *fw = NULL; *size = 0; return 0;
}
static int dchid_request_gpio(struct dchid_iface *i) { (void)i; calls++; return 0; }
static int dchid_send_firmware(struct dchid_iface *i, void *fw, size_t size) {
    (void)i; (void)fw; (void)size; calls++; return 0;
}
static int dchid_reset_interface(struct dchid_iface *i, int state) {
    (void)i; (void)state; calls++; return 0;
}
'''
test = r'''
int main(void) {
    const int errors[] = {-ENOENT, -EINVAL, -ENOMEM, 1};
    for (unsigned n = 0; n < sizeof(errors) / sizeof(*errors); n++) {
        struct dchid_iface i = {.gpio_id = 1};
        result = errors[n]; calls = 0;
        assert(dchid_start_interface(&i) == result);
        assert(!calls && !i.starting);
    }
    struct dchid_iface keyboard = {0};
    result = 0;
    assert(!dchid_start_interface(&keyboard));
    assert(keyboard.starting && !calls);
    assert(dchid_start_interface(&keyboard) == -EINPROGRESS);
    assert(!calls);
    return 0;
}
'''
with temporary_directory(prefix="azahi-fw-result-test-") as temporary:
    binary = Path(temporary) / 'test'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                   ['-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-x', 'c', '-', '-o', str(binary)],
                   input=stub + function + test, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: firmware lookup failures stop before GPIO/upload/reset; no-firmware keyboard path unchanged')

# Different HID interfaces share the FIFO but have separate command locks.
# Pause one packet after its header and start another sender. Validate the
# actual wire bytes, including padding/checksums, under that forced overlap.
start = source.index('static u32 dchid_checksum(')
end = source.index('\nstatic int dchid_cmd(', start)
sender = source[start:end]
stub = r'''
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/resource.h>
#include <unistd.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define __packed __attribute__((packed))
#define U16_MAX UINT16_MAX
#define DCHID_CHANNEL_CMD 0x11
#define WARN_ON_ONCE(x) assert(!(x))
#define round_down(n, a) ((n) & ~((size_t)(a) - 1))
#define round_up(n, a) round_down((n) + (a) - 1, a)
struct dchid_hdr { u8 hdr_len, channel; u16 length; u8 seq, iface; u16 pad; } __packed;
struct dchid_subhdr { u8 flags, unk; u16 length; u32 retcode; } __packed;
struct dockchannel_hid { void *dc; pthread_mutex_t tx_lock; };
struct dchid_iface { struct dockchannel_hid *dchid; u8 tx_seq, index; };
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static bool concurrent, first_paused, second_attempted, second_done;
static _Thread_local int transmitter;
static u8 wire[256];
static size_t used;
static int calls, fail_at;
static u32 get_unaligned_le32(const void *p) {
 const u8 *b=p; return (u32)b[0] | ((u32)b[1]<<8) | ((u32)b[2]<<16) | ((u32)b[3]<<24);
}
static void mutex_lock(pthread_mutex_t *m) {
 assert(!pthread_mutex_lock(&gate));
 if (concurrent && transmitter==1) {
  second_attempted=true; assert(!pthread_cond_broadcast(&changed));
 }
 assert(!pthread_mutex_unlock(&gate));
 assert(!pthread_mutex_lock(m));
}
static void mutex_unlock(pthread_mutex_t *m) { assert(!pthread_mutex_unlock(m)); }
static int dockchannel_send(void *dc, const void *p, size_t n) {
 (void)dc;
 assert(!pthread_mutex_lock(&gate));
 if (++calls==fail_at) { assert(!pthread_mutex_unlock(&gate)); return -ETIMEDOUT; }
 assert(used+n<=sizeof(wire)); memcpy(wire+used,p,n); used+=n;
 if (concurrent && transmitter==0 && !first_paused) {
  first_paused=true; assert(!pthread_cond_broadcast(&changed));
  while (!second_attempted && !second_done) assert(!pthread_cond_wait(&changed,&gate));
 }
 assert(!pthread_mutex_unlock(&gate));
 return (int)n;
}
'''
test = r'''
struct thread_arg { struct dchid_iface *iface; int who; };
static void *send_thread(void *arg) {
 struct thread_arg *a=arg; transmitter=a->who;
 if (transmitter==1) {
  assert(!pthread_mutex_lock(&gate));
  while (!first_paused) assert(!pthread_cond_wait(&changed,&gate));
  assert(!pthread_mutex_unlock(&gate));
 }
 u8 message[5]={0x40,2,3,4,(u8)transmitter};
 assert(!dchid_send(a->iface,0x80,message,sizeof(message)));
 if (transmitter==1) {
  assert(!pthread_mutex_lock(&gate)); second_done=true;
  assert(!pthread_cond_broadcast(&changed)); assert(!pthread_mutex_unlock(&gate));
 }
 return NULL;
}
int main(void) {
 struct rlimit no_core={0,0}; assert(!setrlimit(RLIMIT_CORE,&no_core)); alarm(5);
 struct dockchannel_hid d={.tx_lock=PTHREAD_MUTEX_INITIALIZER};
 struct dchid_iface ifaces[2]={{.dchid=&d,.tx_seq=7,.index=1},
                              {.dchid=&d,.tx_seq=9,.index=2}};
 struct thread_arg args[2]={{&ifaces[0],0},{&ifaces[1],1}};
 pthread_t threads[2]; concurrent=true;
 for (int i=0;i<2;i++) assert(!pthread_create(&threads[i],NULL,send_thread,&args[i]));
 for (int i=0;i<2;i++) assert(!pthread_join(threads[i],NULL));
 assert(used==56 && calls==8);
 for (int i=0;i<2;i++) {
  u8 *p=wire+i*28; u32 sum=0;
  for (int n=0;n<28;n+=4) sum+=get_unaligned_le32(p+n);
  if (sum!=UINT32_MAX) { fputs("interleaved packet checksum\n",stderr); return 1; }
  const u8 expected[24]={8,0x11,16,0,(u8)(7+2*i),(u8)(1+i),0,0,
                         0x80,0,5,0,0,0,0,0,0x40,2,3,4,(u8)i,0,0,0};
  assert(!memcmp(p,expected,sizeof(expected)));
 }
 concurrent=false;
 for (int failure=1;failure<=4;failure++) {
  used=0; calls=0; fail_at=failure;
  u8 message[5]={0x40,2,3,4,5};
  assert(dchid_send(&ifaces[0],0x80,message,sizeof(message))==-ETIMEDOUT);
  assert(calls==failure);
  assert(!pthread_mutex_trylock(&d.tx_lock)); assert(!pthread_mutex_unlock(&d.tx_lock));
 }
 used=0; calls=0; fail_at=0;
 assert(dchid_send(&ifaces[0],0x80,NULL,U16_MAX)==-EINVAL && calls==0);
 alarm(0); return 0;
}
'''
with temporary_directory(prefix='azahi-tx-test-') as temporary:
    for name, implementation in (
        ('locked', sender),
        ('unlocked', sender.replace('mutex_lock(&iface->dchid->tx_lock);', '')
                           .replace('mutex_unlock(&iface->dchid->tx_lock);', '')),
    ):
        binary = Path(temporary) / name
        subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                       ['-O2', '-Wall', '-Wextra', '-Wno-unused-function', '-pthread',
                        '-fsanitize=address,undefined', '-x', 'c', '-', '-o', str(binary)],
                       input=stub + implementation + test, text=True, check=True)
        result = subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)
        if name == 'locked':
            if result.returncode:
                raise RuntimeError(result.stderr)
        elif result.returncode != 1 or 'interleaved packet checksum' not in result.stderr:
            raise RuntimeError('unlocked mutation did not reproduce packet corruption: ' + result.stderr)
print('PASS: concurrent interfaces preserve complete packets; all send errors unlock; unlocked mutation corrupts wire checksum')

# GPIO set operations return errors in the pinned kernel. A failed pulse must
# retain the existing error ACK, while still attempting its release edge.
start = source.index('static void dchid_handle_gpio(')
end = source.index('\nstatic void dchid_handle_event(', start)
gpio_event = source[start:end]
pulse_setting = next(line for line in source.splitlines()
                     if line.startswith('static bool gpio_pulse_50ms'))
stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define __packed __attribute__((packed))
#define MAX_INTERFACES 16
#define CMD_ACK_GPIO_CMD 0xa1
#define GFP_KERNEL 0
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
struct dchid_gpio_cmd { u8 type, iface, gpio, unk, cmd; } __packed;
struct dchid_gpio_ack { u8 type; u32 retcode; u8 cmd[]; } __packed;
struct dchid_iface { void *gpio; int gpio_id; };
struct dockchannel_hid { struct dchid_iface *ifaces[MAX_INTERFACES]; };
static int acquired, edges, delays, acks, acquire_error, assert_error, release_error;
static int board, expected_delay;
static int values[2], pin;
static u8 reply[64];
static size_t reply_length;
static int dchid_request_gpio(struct dchid_iface *i) {
 acquired++;
 if (acquire_error) return acquire_error;
 i->gpio=&pin; return 0;
}
static int gpiod_set_value_cansleep(void *gpio, int value) {
 assert(gpio==&pin && edges<2); values[edges++]=value;
 return value ? assert_error : release_error;
}
static int of_machine_is_compatible(const char *name) {
 assert(!strcmp(name,"apple,j714s")); return board;
}
static void msleep(unsigned int ms) { assert(ms==(unsigned)expected_delay && edges==1); delays++; }
static void *kzalloc(size_t size, int flags) { (void)flags; return calloc(1,size); }
static void kfree(void *p) { free(p); }
static int dchid_comm_cmd(struct dockchannel_hid *d, void *p, size_t n) {
 (void)d; assert(n<=sizeof(reply)); memcpy(reply,p,n); reply_length=n; acks++; return 0;
}
'''
test = r'''
static void check_reply(u8 *event, size_t size, int success) {
 struct dchid_gpio_ack *ack=(void *)reply;
 assert(acks==1 && reply_length==sizeof(*ack)+size);
 assert(ack->type==CMD_ACK_GPIO_CMD);
 assert(ack->retcode==(success ? 0 : 0xe000f00du));
 assert(!memcmp(ack->cmd,event,size));
}
int main(void) {
 struct dchid_iface iface={.gpio_id=7};
 struct dockchannel_hid d={.ifaces={[1]=&iface}};
 assert(!gpio_pulse_50ms);
 u8 event[20]={0xa0,1,7,0,3,0,0,0,0xaa,0x55,0,0,0xf0};
 for (int mode=0;mode<4;mode++) {
 board=mode&1; gpio_pulse_50ms=mode>>1;
 expected_delay=mode==3 ? 50 : 10;
 for (int failure=0;failure<4;failure++) {
  acquired=edges=delays=acks=0;
  assert_error=(failure&1) ? -EIO : 0; release_error=(failure&2) ? -ETIMEDOUT : 0;
  dchid_handle_gpio(&d,event,sizeof(event));
  assert(acquired==1 && edges==2 && delays==1 && values[0]==1 && values[1]==0);
  check_reply(event,sizeof(event),failure==0);
 }
 }
 assert_error=release_error=0;
 for (int failure=0;failure<5;failure++) {
  u8 bad[sizeof(event)]; memcpy(bad,event,sizeof(bad));
  acquired=edges=delays=acks=acquire_error=0;
  switch (failure) {
   case 0: bad[1]=255; break;
   case 1: bad[1]=2; break;
   case 2: bad[2]=8; break;
   case 3: bad[4]=4; break;
   case 4: acquire_error=-EIO; break;
  }
  dchid_handle_gpio(&d,bad,sizeof(bad));
  assert(edges==0 && delays==0 && acquired==(failure==4));
  check_reply(bad,sizeof(bad),0);
 }
 acks=acquired=0;
 dchid_handle_gpio(&d,event,sizeof(struct dchid_gpio_cmd)-1);
 assert(!acks && !acquired);
 return 0;
}
'''
with temporary_directory(prefix='azahi-gpio-test-') as temporary:
    binary = Path(temporary) / 'test'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                   ['-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                    '-x', 'c', '-', '-o', str(binary)],
                   input=stub + pulse_setting + '\n' + gpio_event + test, text=True, check=True)
    subprocess.run([str(binary)], check=True)
print('PASS: GPIO pulse errors produce error ACKs; release always attempted; 50 ms requires opt-in and J714s; invalid requests refused')

# Raw SET_REPORT must preserve the HID caller's report type, as GET_REPORT
# already does. The old output-only helper changed feature writes on the wire.
start = source.index('static int dchid_raw_request(')
end = source.index('\nstatic struct hid_ll_driver', start)
raw_request = source[start:end]
stub = r'''
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t __u8;
#define HID_OUTPUT_REPORT 1
#define HID_FEATURE_REPORT 2
#define HID_REQ_GET_REPORT 1
#define HID_REQ_SET_REPORT 9
#define REQ_GET_REPORT 1
#define REQ_SET_REPORT 0
struct dchid_iface { int unused; };
struct hid_device { struct dchid_iface *driver_data; };
static struct dchid_iface *expected_iface;
static unsigned expected_type, expected_request;
static int calls, result;
static __u8 expected_report, *buffer;
static int dchid_cmd(struct dchid_iface *iface, unsigned type, unsigned request,
                     void *data, size_t size, void *reply, size_t capacity) {
 assert(iface==expected_iface && request==expected_request);
 calls++;
 if (type!=expected_type) return -EPROTO;
 if (request==REQ_GET_REPORT) {
  assert(size==1 && *(__u8 *)data==expected_report);
  assert(buffer[0]==expected_report && reply==buffer+1 && capacity==3);
 } else {
  assert(data==buffer && size==4 && !reply && !capacity);
 }
 return result;
}
'''
test = r'''
int main(void) {
 struct dchid_iface iface={0}; struct hid_device hid={.driver_data=&iface};
 __u8 bytes[4]={0x17,0xa1,0xa2,0xa3};
 expected_iface=&iface; buffer=bytes; expected_report=bytes[0];
 for (unsigned type=HID_OUTPUT_REPORT;type<=HID_FEATURE_REPORT;type++) {
  expected_type=type;
  for (int request=0;request<2;request++) {
   expected_request=request ? REQ_GET_REPORT : REQ_SET_REPORT;
   for (int reply=-2;reply<=4;reply++) {
    calls=0; result=reply==-2 ? -ETIMEDOUT : reply==-1 ? -EIO : reply;
    int ret=dchid_raw_request(&hid,expected_report,bytes,sizeof(bytes),type,
                             request ? HID_REQ_GET_REPORT : HID_REQ_SET_REPORT);
    int expected=result<0 || request ? result : (int)sizeof(bytes);
    if (ret!=expected) { fputs("report type or transfer length was not preserved\n",stderr); return 1; }
    assert(calls==1 && bytes[1]==0xa1 && bytes[3]==0xa3);
   }
  }
 }
 calls=0;
 assert(dchid_raw_request(&hid,0,bytes,sizeof(bytes),HID_FEATURE_REPORT,0)==-EIO);
 assert(!calls);
 return 0;
}
'''
with temporary_directory(prefix='azahi-report-test-') as temporary:
    for name, implementation in (
        ('typed', raw_request),
        ('output-only', raw_request.replace('iface, rtype, REQ_SET_REPORT',
                                            'iface, HID_OUTPUT_REPORT, REQ_SET_REPORT')),
        ('ack-length', raw_request.replace('return len;', 'return ret;')),
    ):
        binary = Path(temporary) / name
        subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                       ['-O2', '-Wall', '-Wextra', '-Werror', '-fsanitize=address,undefined',
                        '-x', 'c', '-', '-o', str(binary)],
                       input=stub + implementation + test, text=True, check=True)
        result = subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)
        if name == 'typed':
            if result.returncode:
                raise RuntimeError(result.stderr)
        elif result.returncode != 1 or 'report type or transfer length was not preserved' not in result.stderr:
            raise RuntimeError(name + ' mutation did not fail: ' + result.stderr)
print('PASS: GET/SET preserve type, buffers and errors; SET returns bytes sent; both regressions fail')

# Init blocks carry their own length; bytes in the next block are not GPIO data.
start = source.index('struct dchid_init_hdr {')
end = source.index('struct dchid_gpio_cmd {', start)
declarations = source[start:end]
start = source.index('static void dchid_handle_init(')
end = source.index('\nstatic void dchid_handle_gpio(', start)
init_parser = source[start:end]
stub = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
#define __packed __attribute__((packed))
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
struct dockchannel_hid { void *dev; int id_ready; };
struct dchid_iface { struct dockchannel_hid *dchid;const char *name;char gpio_name[32];int gpio_id;int deferred; };
static struct dchid_iface iface;
static int creates,descriptors,lookups;
static struct dchid_iface *dchid_get_interface(struct dockchannel_hid *d,int index,const char *name) {
 assert(index==1 && strlen(name)==16);lookups++;iface.dchid=d;iface.name="multi-touch";return &iface;
}
static void dchid_handle_descriptor(struct dchid_iface *i,void *p,size_t n) { assert(i==&iface && n==3 && !memcmp(p,"abc",3));descriptors++; }
static void dchid_create_interface(struct dchid_iface *i) { assert(i==&iface);creates++; }
static void strscpy(char *dest,const char *src,size_t n) { size_t i=0;for(;i+1<n && src[i];i++)dest[i]=src[i];dest[i]=0; }
'''
test = r'''
static void reset(void) { memset(&iface,0,sizeof(iface));creates=descriptors=lookups=0; }
static unsigned char *packet(size_t n) {
 unsigned char *p=calloc(1,n);assert(p);
 if(n>=sizeof(struct dchid_init_hdr)) {
  struct dchid_init_hdr *h=(void *)p;h->iface=1;memset(h->name,'x',16);
 }
 return p;
}
int main(void) {
 struct dockchannel_hid d={.id_ready=1};
 const size_t hsize=sizeof(struct dchid_init_hdr),bsize=sizeof(struct dchid_init_block_hdr);
 /* A short GPIO block must never read the following block as GPIO data. */
 for (unsigned n=0;n<sizeof(struct dchid_gpio_request);n++) {
  size_t total=hsize+bsize+n+bsize+40;unsigned char *p=packet(total);
  struct dchid_init_block_hdr *b=(void *)(p+hsize);b->type=INIT_GPIO_REQUEST;b->length=n;
  memset(p+hsize+bsize,0xa7,n);
  struct dchid_init_block_hdr *next=(void *)(p+hsize+bsize+n);next->type=0x1234;next->length=40;
  memset((unsigned char *)next+bsize,0xa7,40);
  reset();dchid_handle_init(&d,p,total);
  assert(!iface.gpio_id && !iface.gpio_name[0] && creates==1 && lookups==1);free(p);
 }
 /* Valid blocks, extension bytes, descriptor parsing and deferred creation. */
 for(unsigned n=sizeof(struct dchid_gpio_request);n<=40;n++) {
  size_t total=hsize+bsize+n+bsize+3;unsigned char *p=packet(total);
  struct dchid_init_block_hdr *b=(void *)(p+hsize);b->type=INIT_GPIO_REQUEST;b->length=n;
  struct dchid_gpio_request *r=(void *)(p+hsize+bsize);r->id=17;memcpy(r->name,"afe-reset",10);
  struct dchid_init_block_hdr *next=(void *)(p+hsize+bsize+n);next->type=INIT_HID_DESCRIPTOR;next->length=3;
  memcpy((unsigned char *)next+bsize,"abc",3);
  for(unsigned deferred=0;deferred<2;deferred++) {
   d.id_ready=!deferred;reset();dchid_handle_init(&d,p,total);
   assert(iface.gpio_id==17 && !strcmp(iface.gpio_name,"afe-reset"));
   assert(descriptors==1 && creates==!deferred && iface.deferred==(int)deferred);
  }
  free(p);
 }
 /* Every truncation of a claimed GPIO block stays inside its allocation. */
 for(size_t n=0;n<hsize+bsize+sizeof(struct dchid_gpio_request);n++) {
  unsigned char *p=packet(n?n:1);
  if(n>=hsize+bsize) {
   struct dchid_init_block_hdr *b=(void *)(p+hsize);b->type=INIT_GPIO_REQUEST;b->length=sizeof(struct dchid_gpio_request);
  }
  reset();dchid_handle_init(&d,p,n);assert(!iface.gpio_id);free(p);
 }
 puts("PASS: short GPIO blocks cannot consume sibling data; valid, extended and truncated blocks checked");
 return 0;
}
'''
with temporary_directory(prefix='azahi-init-block-test-') as temporary:
    for name, implementation in (
        ('bounded', init_parser),
        ('whole-packet', init_parser.replace('sizeof(*req) > blk->length',
                                             'sizeof(*req) > length')),
    ):
        binary = Path(temporary) / name
        subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
                       ['-std=gnu11', '-O1', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-pie', '-no-pie',
                        '-x', 'c', '-', '-o', str(binary)],
                       input=stub + declarations + implementation + test,
                       text=True, check=True)
        result = subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)
        if name == 'bounded':
            if result.returncode:
                raise RuntimeError(result.stderr)
            print(result.stdout, end='')
        elif result.returncode == 0 or 'Assertion' not in result.stderr:
            raise RuntimeError('whole-packet mutation did not fail: ' + result.stderr)
