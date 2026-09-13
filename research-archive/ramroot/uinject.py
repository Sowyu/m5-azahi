#!/usr/bin/env python3
"""
uinject - synthetic keyboard+mouse for the T6050 guest via /dev/uinput.

The M5's internal keyboard/trackpad need MTP/dockchannel bring-up; this
sidesteps hardware entirely.  Devices created here land on seat0 and are
picked up by libinput/kwin like real hardware.

Run in the guest (needs uinput.ko, present in the full rootfs):
    modprobe uinput
    uinject &          # reads commands from /run/uinject.fifo

Then from the vuart shell:
    echo 'move 100 50'      > /run/uinject.fifo
    echo 'click left'       > /run/uinject.fifo
    echo 'key ctrl+alt+t'   > /run/uinject.fifo
    echo 'type hello world' > /run/uinject.fifo
"""
import os, sys, time, struct, fcntl

UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_RELBIT = 0x40045564, 0x40045565, 0x40045566
UI_DEV_SETUP, UI_DEV_CREATE = 0x405C5503, 0x5501
EV_SYN, EV_KEY, EV_REL = 0, 1, 2
REL_X, REL_Y, REL_WHEEL = 0, 1, 8
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112

K = {  # name -> keycode (input-event-codes.h)
 'esc':1,'1':2,'2':3,'3':4,'4':5,'5':6,'6':7,'7':8,'8':9,'9':10,'0':11,
 'minus':12,'equal':13,'backspace':14,'tab':15,'q':16,'w':17,'e':18,'r':19,
 't':20,'y':21,'u':22,'i':23,'o':24,'p':25,'leftbrace':26,'rightbrace':27,
 'enter':28,'ctrl':29,'a':30,'s':31,'d':32,'f':33,'g':34,'h':35,'j':36,
 'k':37,'l':38,'semicolon':39,'apostrophe':40,'grave':41,'shift':42,
 'backslash':43,'z':44,'x':45,'c':46,'v':47,'b':48,'n':49,'m':50,'comma':51,
 'dot':52,'slash':53,'rightshift':54,'alt':56,'space':57,'capslock':58,
 'f1':59,'f2':60,'f3':61,'f4':62,'f5':63,'f6':64,'f7':65,'f8':66,'f9':67,
 'f10':68,'f11':87,'f12':88,'home':102,'up':103,'pageup':104,'left':105,
 'right':106,'end':107,'down':108,'pagedown':109,'insert':110,'delete':111,
 'meta':125,'super':125,'menu':127,
}
SHIFTED = {'A':'a','B':'b','C':'c','D':'d','E':'e','F':'f','G':'g','H':'h',
 'I':'i','J':'j','K':'k','L':'l','M':'m','N':'n','O':'o','P':'p','Q':'q',
 'R':'r','S':'s','T':'t','U':'u','V':'v','W':'w','X':'x','Y':'y','Z':'z',
 '!':'1','@':'2','#':'3','$':'4','%':'5','^':'6','&':'7','*':'8','(':'9',
 ')':'0','_':'minus','+':'equal','{':'leftbrace','}':'rightbrace',
 ':':'semicolon','"':'apostrophe','~':'grave','|':'backslash','<':'comma',
 '>':'dot','?':'slash'}
PLAIN = {' ':'space','\t':'tab','\n':'enter','-':'minus','=':'equal',
 '[':'leftbrace',']':'rightbrace',';':'semicolon',"'":'apostrophe',
 '`':'grave','\\':'backslash',',':'comma','.':'dot','/':'slash'}

fd = None

def emit(t, c, v):
    os.write(fd, struct.pack('qqHHi', 0, 0, t, c, v))

def syn():
    emit(EV_SYN, 0, 0)

def tap(code):
    emit(EV_KEY, code, 1); syn(); time.sleep(0.01)
    emit(EV_KEY, code, 0); syn(); time.sleep(0.01)

def chord(names):
    codes = [K[n] for n in names]
    for c in codes: emit(EV_KEY, c, 1); syn()
    time.sleep(0.02)
    for c in reversed(codes): emit(EV_KEY, c, 0); syn()

def typestr(s):
    for ch in s:
        if ch.lower() in K and ch.isalnum() and ch.islower() or ch.isdigit():
            tap(K[ch.lower()])
        elif ch in SHIFTED:
            emit(EV_KEY, K['shift'], 1); syn()
            tap(K[SHIFTED[ch]])
            emit(EV_KEY, K['shift'], 0); syn()
        elif ch in PLAIN:
            tap(K[PLAIN[ch]])
        elif ch.lower() in K:
            tap(K[ch.lower()])

def main():
    global fd
    fd = os.open('/dev/uinput', os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_REL)
    for code in set(list(K.values()) + [BTN_LEFT, BTN_RIGHT, BTN_MIDDLE]):
        fcntl.ioctl(fd, UI_SET_KEYBIT, code)
    for r in (REL_X, REL_Y, REL_WHEEL):
        fcntl.ioctl(fd, UI_SET_RELBIT, r)
    # struct uinput_setup: input_id(bus,vend,prod,ver) + name[80] + ff
    setup = struct.pack('HHHH80sI', 0x06, 0x1209, 0x0001, 1,
                        b'm1n1 vuart injector', 0)
    fcntl.ioctl(fd, UI_DEV_SETUP, setup)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    time.sleep(0.5)

    fifo = '/run/uinject.fifo'
    if not os.path.exists(fifo):
        os.mkfifo(fifo)
    print(f'uinject: ready, feed commands to {fifo}', flush=True)
    while True:
        with open(fifo) as f:
            for ln in f:
                t = ln.strip().split(None, 1)
                if not t: continue
                cmd, arg = t[0], (t[1] if len(t) > 1 else '')
                try:
                    if cmd == 'move':
                        dx, dy = map(int, arg.split())
                        emit(EV_REL, REL_X, dx); emit(EV_REL, REL_Y, dy); syn()
                    elif cmd == 'click':
                        b = {'left':BTN_LEFT,'right':BTN_RIGHT,'middle':BTN_MIDDLE}[arg or 'left']
                        emit(EV_KEY, b, 1); syn(); time.sleep(0.05)
                        emit(EV_KEY, b, 0); syn()
                    elif cmd == 'scroll':
                        emit(EV_REL, REL_WHEEL, int(arg)); syn()
                    elif cmd == 'key':
                        chord(arg.replace('-', '+').split('+'))
                    elif cmd == 'type':
                        typestr(arg)
                except Exception as e:
                    print('uinject error:', e, flush=True)

if __name__ == '__main__':
    main()
