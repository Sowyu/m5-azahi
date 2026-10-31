#!/usr/bin/env python3
"""Exercise the actual join completion against cfg80211's address contract."""
import os
from pathlib import Path
import re
import subprocess
import tempfile

root=Path(os.environ.get('N1_SOURCE_ROOT',Path(__file__).with_name('experiments')))
source=(root/'s61/n1-wifi.c').read_text()
match=re.search(r'^static void join_done\([^;{]*\)\n\{.*?^\}',source,re.M|re.S)
assert match
program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
struct cfg80211_bss { unsigned char bssid[6]; };
struct net_device { unsigned int unused; };
struct n1_wifi {
 struct cfg80211_bss *join_bss;
 struct net_device *dev;
 bool connecting, reported_connected;
 unsigned char bssid[6], request[300];
 size_t request_len;
};
#define GFP_KERNEL 1
#define NL80211_TIMEOUT_UNSPECIFIED 0
#define pr_info(...) ((void)0)
#define memzero_explicit memset_zero
static void memset_zero(void *p,size_t n) { memset(p,0,n); }
static struct n1_wifi *current;
static struct cfg80211_bss *expected_bss;
static unsigned int notifications, carriers;
static int expected_status;
static void cfg80211_connect_bss(struct net_device *dev,const unsigned char *addr,
 struct cfg80211_bss *bss,const void *req,size_t req_len,const void *resp,size_t resp_len,
 int status,int gfp,int timeout)
{
 unsigned int i;
 assert(dev==current->dev && bss==expected_bss);
 /* Kernel 7.0 copies this address even when the BSS record is supplied. */
 assert(addr && !memcmp(addr,expected_bss->bssid,6));
 assert(!req && !req_len && !resp && !resp_len);
 assert(status==expected_status && gfp==GFP_KERNEL && timeout==NL80211_TIMEOUT_UNSPECIFIED);
 assert(!current->connecting && !current->join_bss && !current->request_len);
 for(i=0;i<sizeof(current->request);i++) assert(!current->request[i]);
 notifications++;
}
static void packets_on(struct n1_wifi *s)
{
 assert(s==current && s->reported_connected && notifications==1);
 carriers++;
}
''' + match.group() + r'''
int main(void)
{
 struct cfg80211_bss bss={{2,0,0,0,0,1}};
 struct net_device dev={0};
 struct n1_wifi state;
 int statuses[]={0,-1,1};
 unsigned int i;
 for(i=0;i<sizeof(statuses)/sizeof(statuses[0]);i++) {
  memset(&state,0,sizeof(state)); state.dev=&dev;
  state.join_bss=&bss;state.connecting=true;state.request_len=sizeof(state.request);
  memset(state.request,0xa5,sizeof(state.request));memcpy(state.bssid,bss.bssid,6);
  current=&state;expected_bss=&bss;expected_status=statuses[i];notifications=carriers=0;
  join_done(&state,statuses[i]);
  assert(notifications==1 && carriers==(statuses[i]==0));
  assert(state.reported_connected==(statuses[i]==0));
  join_done(&state,statuses[i]);assert(notifications==1); /* reference consumed once */
 }
 puts("PASS: non-null matching AP address, single BSS handoff, request erasure and success-only carrier");
}
'''
with tempfile.TemporaryDirectory(prefix='n1-notification-test-') as directory:
    tmp=Path(directory)
    (tmp/'test.c').write_text(program)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    str(tmp/'test.c'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
