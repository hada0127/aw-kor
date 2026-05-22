// Headless libmgba driver. Build:
//   clang -I/opt/homebrew/include tools/mgba_harness.c -L/opt/homebrew/lib -lmgba -o /tmp/mgbah
// Run:  DYLD_LIBRARY_PATH=/opt/homebrew/lib /tmp/mgbah <rom>
// Then send commands on stdin (one per line):
//   frames N         run N frames
//   keys MASK        setKeys(MASK)   (bit0=A,1=B,2=Sel,3=Start,4=R,5=L,6=Up,7=Down,8=R,9=L)
//   w8 ADDR HEX      busWrite8 sequence of hex bytes at ADDR (e.g. w8 6000000 aabbcc..)
//   dumpvram FILE    write 0x06000000..0x06018000 (96KB) to FILE
//   dumpmem ADDR LEN FILE
//   shot FILE        write framebuffer as raw: 4-byte header w,h (uint16 LE) then color_t pixels
//   quit
#include <mgba/core/core.h>
#include <mgba/core/config.h>
#include <mgba/core/log.h>
#include <mgba/debugger/debugger.h>
#include <mgba-util/vfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdarg.h>

// Custom logger -> file, so stdout stays clean for command acks.
static FILE* g_logf;
static void harnessLog(struct mLogger* l, int cat, enum mLogLevel lv, const char* fmt, va_list args){
    (void)l;(void)cat;(void)lv;
    if(g_logf){ vfprintf(g_logf, fmt, args); fputc('\n', g_logf); fflush(g_logf); }
}
static struct mLogger g_logger = { .log = harnessLog };

static struct mCore* core;
static color_t* vbuf;
static unsigned VW, VH;

// --- read-watchpoint capture (custom debugger) ---
static struct mDebugger s_dbg;
static int s_dbg_attached = 0;
static FILE* s_wpf = NULL;
static int s_wp_order = 0;
static void wpEntered(struct mDebugger* d, enum mDebuggerEntryReason reason, struct mDebuggerEntryInfo* info) {
    if (reason == DEBUGGER_ENTER_WATCHPOINT && info && s_wpf) {
        uint32_t pc=0,lr=0,r0=0,r1=0;
        core->readRegister(core,"pc",&pc); core->readRegister(core,"lr",&lr);
        core->readRegister(core,"r0",&r0); core->readRegister(core,"r1",&r1);
        fprintf(s_wpf, "%d addr=%08X pc=%08X lr=%08X r0=%08X r1=%08X old=%08X new=%08X\n",
                s_wp_order++, info->address, pc, lr, r0, r1, info->type.wp.oldValue, info->type.wp.newValue);
        fflush(s_wpf);
    } else if (reason == DEBUGGER_ENTER_BREAKPOINT && s_wpf) {
        uint32_t r[16]; char nm[4];
        for (int i=0;i<16;i++){ snprintf(nm,4,"r%d",i); r[i]=0; core->readRegister(core,nm,&r[i]); }
        fprintf(s_wpf, "%d BP r0=%08X r1=%08X r2=%08X r3=%08X r4=%08X r5=%08X r6=%08X r7=%08X sp=%08X lr=%08X pc=%08X\n",
                s_wp_order++, r[0],r[1],r[2],r[3],r[4],r[5],r[6],r[7],r[13],r[14],r[15]);
        fflush(s_wpf);
    }
    d->state = DEBUGGER_RUNNING; // resume immediately
}

static int hexval(int c){ if(c>='0'&&c<='9')return c-'0'; if(c>='a'&&c<='f')return c-'a'+10; if(c>='A'&&c<='F')return c-'A'+10; return -1; }

int main(int argc, char** argv){
    if(argc<2){ fprintf(stderr,"usage: mgbah <rom>\n"); return 1; }
    g_logf = fopen(argc>2?argv[2]:"/tmp/mgba_swi.log","w");
    mLogSetDefaultLogger(&g_logger);
    struct VFile* vf = VFileOpen(argv[1], O_RDONLY);
    if(!vf){ fprintf(stderr,"cannot open rom\n"); return 1; }
    core = mCoreFindVF(vf);
    if(!core){ fprintf(stderr,"no core\n"); return 1; }
    core->init(core);
    mCoreInitConfig(core, NULL);
    core->desiredVideoDimensions(core, &VW, &VH);
    vbuf = malloc(VW*VH*sizeof(color_t));
    core->setVideoBuffer(core, vbuf, VW);
    core->loadROM(core, vf);
    core->reset(core);
    fprintf(stderr,"READY w=%u h=%u sizeof(color_t)=%lu\n", VW, VH, sizeof(color_t));
    fflush(stderr);

    char line[1<<20];
    while(fgets(line, sizeof(line), stdin)){
        char* cmd = strtok(line, " \t\r\n");
        if(!cmd) continue;
        if(!strcmp(cmd,"frames")){
            int n = atoi(strtok(NULL," \t\r\n"));
            for(int i=0;i<n;i++){
                if(s_dbg_attached) mDebuggerRunFrame(&s_dbg);
                else core->runFrame(core);
            }
            printf("OK frames %d\n", n);
        } else if(!strcmp(cmd,"keys")){
            uint32_t m = (uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,0);
            core->setKeys(core, m);
            printf("OK keys %u\n", m);
        } else if(!strcmp(cmd,"w16")){
            // w16 ADDR HEX  - 16-bit writes (each 4-hex-char = 1 halfword LE)
            uint32_t addr = (uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,16);
            char* hx = strtok(NULL," \t\r\n");
            int n=0;
            for(char* p=hx; p && p[0] && p[1] && p[2] && p[3]; p+=4){
                int b0_hi=hexval(p[0]), b0_lo=hexval(p[1]);
                int b1_hi=hexval(p[2]), b1_lo=hexval(p[3]);
                if(b0_hi<0||b0_lo<0||b1_hi<0||b1_lo<0) break;
                uint16_t v = ((b0_hi<<4)|b0_lo) | (((b1_hi<<4)|b1_lo)<<8);
                core->busWrite16(core, addr+n*2, v); n++;
            }
            printf("OK w16 %d halfwords\n", n);
        } else if(!strcmp(cmd,"w8")){
            uint32_t addr = (uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,16);
            char* hx = strtok(NULL," \t\r\n");
            int n=0;
            for(char* p=hx; p && p[0] && p[1]; p+=2){
                int hi=hexval(p[0]), lo=hexval(p[1]); if(hi<0||lo<0) break;
                core->busWrite8(core, addr+n, (uint8_t)((hi<<4)|lo)); n++;
            }
            printf("OK w8 %d\n", n);
        } else if(!strcmp(cmd,"dumpvram")){
            char* fn = strtok(NULL," \t\r\n");
            FILE* f=fopen(fn,"wb");
            for(uint32_t a=0;a<0x18000;a++){ uint8_t b=core->busRead8(core, 0x06000000+a); fputc(b,f); }
            fclose(f); printf("OK dumpvram\n");
        } else if(!strcmp(cmd,"dumpmem")){
            uint32_t addr=(uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,16);
            uint32_t len=(uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,0);
            char* fn=strtok(NULL," \t\r\n");
            FILE* f=fopen(fn,"wb");
            for(uint32_t a=0;a<len;a++){ uint8_t b=core->busRead8(core, addr+a); fputc(b,f); }
            fclose(f); printf("OK dumpmem %u\n", len);
        } else if(!strcmp(cmd,"shot")){
            char* fn=strtok(NULL," \t\r\n");
            const void* px; size_t stride;
            core->getPixels(core, &px, &stride);
            FILE* f=fopen(fn,"wb");
            uint16_t hdr[2]={(uint16_t)VW,(uint16_t)VH}; fwrite(hdr,2,2,f);
            // write stride*VH color_t pixels (caller knows sizeof)
            uint8_t cs = (uint8_t)sizeof(color_t); fwrite(&cs,1,1,f);
            for(unsigned y=0;y<VH;y++){
                const char* row = (const char*)px + y*stride*sizeof(color_t);
                fwrite(row, sizeof(color_t), VW, f);
            }
            fclose(f); printf("OK shot %u %u\n", VW, VH);
        } else if(!strcmp(cmd,"watchfont")){
            // watchfont BASE COUNT LOGFILE : set read watchpoints on COUNT glyph slots (32B each) from BASE
            uint32_t base=(uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,16);
            int count=atoi(strtok(NULL," \t\r\n"));
            char* fn=strtok(NULL," \t\r\n");
            if(!s_wpf || (fn && strcmp(fn, "KEEP") != 0)) {
                if(s_wpf) fclose(s_wpf);
                s_wpf=fopen(fn,"w"); s_wp_order=0;
            }
            if(!s_dbg_attached){
                memset(&s_dbg,0,sizeof(s_dbg));
                s_dbg.type=DEBUGGER_CUSTOM;
                s_dbg.entered=wpEntered;
                mDebuggerAttach(&s_dbg, core);
                if(s_dbg.init) s_dbg.init(&s_dbg);
                s_dbg_attached=1;
            }
            int set=0;
            for(int i=0;i<count;i++){
                struct mWatchpoint wp; memset(&wp,0,sizeof(wp));
                wp.address=base+i*32; wp.segment=-1; wp.type=WATCHPOINT_READ;
                if(s_dbg.platform && s_dbg.platform->setWatchpoint){
                    s_dbg.platform->setWatchpoint(s_dbg.platform,&wp); set++;
                }
            }
            s_dbg.state=DEBUGGER_RUNNING;
            printf("OK watchfont set=%d\n", set);
        } else if(!strcmp(cmd,"break")){
            // break ADDR LOGFILE : set execution breakpoint, dump regs on hit
            uint32_t addr=(uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,16);
            char* fn=strtok(NULL," \t\r\n");
            if(!s_wpf || (fn && strcmp(fn, "KEEP") != 0)) {
                if(s_wpf) fclose(s_wpf);
                s_wpf=fopen(fn,"w"); s_wp_order=0;
            }
            if(!s_dbg_attached){
                memset(&s_dbg,0,sizeof(s_dbg));
                s_dbg.type=DEBUGGER_CUSTOM; s_dbg.entered=wpEntered;
                mDebuggerAttach(&s_dbg, core);
                if(s_dbg.init) s_dbg.init(&s_dbg);
                s_dbg_attached=1;
            }
            struct mBreakpoint bp; memset(&bp,0,sizeof(bp));
            bp.address=addr; bp.segment=-1; bp.type=BREAKPOINT_HARDWARE;
            int ok=0;
            if(s_dbg.platform && s_dbg.platform->setBreakpoint){ s_dbg.platform->setBreakpoint(s_dbg.platform,&bp); ok=1; }
            s_dbg.state=DEBUGGER_RUNNING;
            printf("OK break %08X ok=%d\n", addr, ok);
        } else if(!strcmp(cmd,"watchaddr")){
            // watchaddr ADDR LEN TYPE LOGFILE : TYPE r=read w=write a=rw
            uint32_t addr=(uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,16);
            uint32_t len=(uint32_t)strtoul(strtok(NULL," \t\r\n"),NULL,0);
            char* ty=strtok(NULL," \t\r\n");
            char* fn=strtok(NULL," \t\r\n");
            if(!s_wpf || (fn && strcmp(fn, "KEEP") != 0)) {
                if(s_wpf) fclose(s_wpf);
                s_wpf=fopen(fn,"w"); s_wp_order=0;
            }
            if(!s_dbg_attached){
                memset(&s_dbg,0,sizeof(s_dbg));
                s_dbg.type=DEBUGGER_CUSTOM; s_dbg.entered=wpEntered;
                mDebuggerAttach(&s_dbg, core);
                if(s_dbg.init) s_dbg.init(&s_dbg);
                s_dbg_attached=1;
            }
            enum mWatchpointType wt = (ty&&ty[0]=='w')?WATCHPOINT_WRITE:(ty&&ty[0]=='a')?WATCHPOINT_RW:WATCHPOINT_READ;
            int ok=0;
            for(uint32_t a=addr; a<addr+len; a++){
                struct mWatchpoint wp; memset(&wp,0,sizeof(wp));
                wp.address=a; wp.segment=-1; wp.type=wt;
                if(s_dbg.platform && s_dbg.platform->setWatchpoint){ s_dbg.platform->setWatchpoint(s_dbg.platform,&wp); ok++; }
            }
            s_dbg.state=DEBUGGER_RUNNING;
            printf("OK watchaddr %08X len=%u set=%d\n", addr, len, ok);
        } else if(!strcmp(cmd,"quit")){
            printf("OK quit\n"); break;
        } else {
            printf("ERR unknown %s\n", cmd);
        }
        fflush(stdout);
    }
    return 0;
}
