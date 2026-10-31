#!/usr/bin/env python3
"""Run actual RX registration code with a contended transport mutex."""
import os
import re
import subprocess
import tempfile
from pathlib import Path

root=Path(os.environ.get('N1_SOURCE_ROOT',Path(__file__).with_name('experiments')))
source=(root/'s50/n1-alpha-data-rx-v2.c').read_text()
functions=[]
for name in ['n1_data_rx_attach_v2','n1_data_rx_detach_v2']:
    match=re.search(r'^(?:int|void) '+name+r'\([^;{]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions.append(match.group())
program=r'''
#include <assert.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <sched.h>
#include <stdio.h>
typedef void (*n1_rx_consumer_v2)(void *,const void *,size_t);
struct control { pthread_mutex_t io_lock; };
struct data_rx { struct control *control; n1_rx_consumer_v2 consumer; void *consumer_context; };
static struct data_rx *active;
static int result;
static bool stopping;
#define mutex_lock pthread_mutex_lock
#define mutex_unlock pthread_mutex_unlock
'''+'\n'.join(functions)+r'''
static pthread_mutex_t barrier=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static bool entered, release_callback;
static atomic_bool detach_attempted, detach_finished;
static unsigned int calls;
static int context, wrong_context;
static void callback(void *ctx,const void *data,size_t length)
{
 assert(ctx==&context && length==4 && data);
 pthread_mutex_lock(&barrier); entered=true; calls++;
 pthread_cond_broadcast(&changed);
 while(!release_callback) pthread_cond_wait(&changed,&barrier);
 pthread_mutex_unlock(&barrier);
}
static void *producer(void *unused)
{
 (void)unused;
 pthread_mutex_lock(&active->control->io_lock);
 if(active->consumer) active->consumer(active->consumer_context,"test",4);
 pthread_mutex_unlock(&active->control->io_lock);
 return NULL;
}
static void *detach(void *unused)
{
 (void)unused;
 atomic_store(&detach_attempted,true);
 n1_data_rx_detach_v2(&context);
 atomic_store(&detach_finished,true);
 return NULL;
}
int main(void)
{
 struct control control={PTHREAD_MUTEX_INITIALIZER};
 struct data_rx state={.control=&control};
 pthread_t rx,remove;
 assert(n1_data_rx_attach_v2(callback,&context)==-EINVAL);
 active=&state;
 assert(n1_data_rx_attach_v2(NULL,&context)==-EINVAL);
 assert(n1_data_rx_attach_v2(callback,NULL)==-EINVAL);
 result=-EIO; assert(n1_data_rx_attach_v2(callback,&context)==-ESHUTDOWN); result=0;
 stopping=true; assert(n1_data_rx_attach_v2(callback,&context)==-ESHUTDOWN); stopping=false;
 assert(n1_data_rx_attach_v2(callback,&context)==0);
 assert(n1_data_rx_attach_v2(callback,&wrong_context)==-EBUSY);
 n1_data_rx_detach_v2(&wrong_context); assert(state.consumer==callback);
 assert(!pthread_create(&rx,NULL,producer,NULL));
 pthread_mutex_lock(&barrier);
 while(!entered) pthread_cond_wait(&changed,&barrier);
 assert(!pthread_create(&remove,NULL,detach,NULL));
 while(!atomic_load(&detach_attempted)) sched_yield();
 assert(!atomic_load(&detach_finished)); /* callback still owns io_lock */
 release_callback=true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&barrier);
 pthread_join(rx,NULL); pthread_join(remove,NULL);
 assert(atomic_load(&detach_finished) && !state.consumer && !state.consumer_context);
 producer(NULL); assert(calls==1); /* no callback after detach */
 assert(n1_data_rx_attach_v2(callback,&context)==0);
 n1_data_rx_detach_v2(&context);
 puts("PASS: single RX consumer, invalid/failed attaches, owner-only detach, and in-flight callback lifetime");
}
'''
with tempfile.TemporaryDirectory(prefix='n1-rx-test-') as tmp:
    tmp=Path(tmp);(tmp/'test.c').write_text(program)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-pthread',
                    str(tmp/'test.c'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
