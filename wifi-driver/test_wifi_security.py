#!/usr/bin/env python3
"""Exercise the actual cfg80211 security-selection functions with alternatives."""
import os
import re
import subprocess
import tempfile
from pathlib import Path
root=Path(os.environ.get("N1_SOURCE_ROOT",Path(__file__).with_name("experiments")))
source=(root/'s61/n1-wifi.c').read_text()
functions=[]
for name in ['has_suite','supported_psk']:
    match=re.search(r'^static bool '+name+r'\([^;{]*\)\n\{.*?^\}',source,re.M|re.S)
    assert match,name
    functions.append(match.group())
program=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define NL80211_WPA_VERSION_2 2
#define WLAN_CIPHER_SUITE_CCMP 0x000fac04
#define WLAN_AKM_SUITE_PSK 0x000fac02
struct cfg80211_crypto_settings {
 unsigned int wpa_versions;
 int n_ciphers_pairwise, n_akm_suites;
 u32 ciphers_pairwise[4], akm_suites[4], cipher_group;
 const void *psk;
};
'''+'\n'.join(functions)+r'''
int main(void)
{
 unsigned char synthetic[32]={0};
 struct cfg80211_crypto_settings c={.wpa_versions=2,.n_ciphers_pairwise=1,.n_akm_suites=1,
  .ciphers_pairwise={WLAN_CIPHER_SUITE_CCMP},.akm_suites={WLAN_AKM_SUITE_PSK},
  .cipher_group=WLAN_CIPHER_SUITE_CCMP,.psk=synthetic};
 assert(supported_psk(&c));
 c.n_akm_suites=2;c.akm_suites[1]=0x000fac06;assert(supported_psk(&c));
 c.akm_suites[0]=0x000fac06;c.akm_suites[1]=WLAN_AKM_SUITE_PSK;assert(supported_psk(&c));
 c.n_akm_suites=1;assert(!supported_psk(&c));
 c.n_akm_suites=0;assert(!supported_psk(&c));
 c.n_akm_suites=2;c.psk=NULL;assert(!supported_psk(&c));c.psk=synthetic;
 c.cipher_group=0x000fac02;assert(!supported_psk(&c));c.cipher_group=WLAN_CIPHER_SUITE_CCMP;
 c.n_ciphers_pairwise=2;c.ciphers_pairwise[0]=0x000fac02;c.ciphers_pairwise[1]=WLAN_CIPHER_SUITE_CCMP;
 assert(supported_psk(&c));
 c.n_ciphers_pairwise=1;assert(!supported_psk(&c));
 c.n_ciphers_pairwise=0;assert(!supported_psk(&c));
 c.n_ciphers_pairwise=2;c.wpa_versions=1;assert(!supported_psk(&c));
 puts("PASS: PSK/CCMP selection from allowed alternatives; unsupported-only, missing-key and group mismatch rejection");
}
'''
with tempfile.TemporaryDirectory(prefix='n1-security-test-') as tmp:
    tmp=Path(tmp);(tmp/'test.c').write_text(program)
    subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
                    str(tmp/'test.c'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
