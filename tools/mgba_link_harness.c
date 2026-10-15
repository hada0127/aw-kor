// Two-core headless mGBA 0.10.5 link probe, single-threaded (VERIFY-4b).
// Build (Linux, system libmgba 0.10.5):
//   cc -O2 -Wall -Wextra tools/mgba_link_harness.c -lmgba -o temp/release_C/verify4b/mgba_link_harness
// Usage:
//   mgba_link_harness [--bios PATH] [--host-skip-bios] HOST_ROM CLIENT_MB_OR_- LOG_FILE [HOST_SAVE_SOURCE]
// With --bios both cores load that BIOS file (real BIOS SWIs, incl. MultiBoot SWI 0x25).
// CLIENT '-' leaves the client cartridge slot empty: with a BIOS it boots the
// BIOS and waits for a native MultiBoot download from the host.
//
// SIO: a deterministic in-process driver replaces mGBA's threaded lockstep.
// Both cores are interleaved by global cycle count in slices bounded by a
// TICK-cycle timing event. Multiplayer transfers latch every node's
// SIOMLT_SEND at start, complete after GBASIOCyclesPerTransfer[baud][1]
// cycles on the master, then write SIOMULTI0-3, clear busy, set the ID and
// raise SIO IRQs on both nodes. Normal-32/8 transfers exchange SIODATA
// between the internal-clock master and an external-clock slave.
//
// Commands: frames N; framesc N; frames1 PLAYER N; keys PLAYER MASK;
// shot PLAYER FILE; syncshot PLAYER FILE (advance linked until that player's
// next frame boundary, then capture); dumpmem PLAYER ADDR LEN FILE;
// w16/w32 PLAYER ADDR VALUE; setreg PLAYER NAME VALUE; regs PLAYER;
// watchaddr PLAYER ADDR LEN r|w|a LOG_FILE|KEEP; siotrace FILE; status; sio;
// savestate/loadstate PLAYER FILE; loadmb FILE (cheat fallback); quit.
#include <mgba/flags.h>
#include <mgba/core/core.h>
#include <mgba/core/config.h>
#include <mgba/core/log.h>
#include <mgba/core/serialize.h>
#include <mgba/core/timing.h>
#include <mgba/debugger/debugger.h>
#include <mgba/internal/gba/gba.h>
#include <mgba/internal/gba/io.h>
#include <mgba/internal/gba/sio.h>
#include <mgba-util/vfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdarg.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/stat.h>

#define TICK 64

typedef struct Player Player;
typedef struct Watch {
    uint32_t address;
    unsigned length;
    enum mWatchpointType mode;
    FILE* file;
    unsigned hits;
} Watch;
typedef struct SyncNode {
    struct GBASIODriver d;
    Player* owner;
    int id;
    int mode; // -1 = not loaded
} SyncNode;

struct Player {
    struct mCore* core;
    color_t* video;
    unsigned width, height;
    struct mDebugger dbg;
    int dbg_attached;
    Watch watches[32];
    unsigned watch_count;
    SyncNode multi_node, normal_node;
    struct mTimingEvent tick;
    struct VFile* bios;
};
static Player players[2];
static FILE* log_file;
static FILE* sio_trace;
static unsigned sio_trace_lines;
static char private_save[4096];
static unsigned long transfers_multi, transfers_normal;
static int linked = 1; // client participates in scheduling
static int64_t time_base[2]; // per-core offset so 'link on' can rejoin cores at equal time

// Transfer in flight (master-owned)
static struct mTimingEvent xfer_event;
static int xfer_active, xfer_mode;
static uint16_t xfer_multi[4];
static uint32_t xfer_normal[2];

static struct GBA* gba_of(Player* p) { return (struct GBA*)p->core->board; }
static uint64_t now_of(Player* p) { return p->core?mTimingGlobalTime(&gba_of(p)->timing):0; }

static void on_log(struct mLogger* logger, int category, enum mLogLevel level,
                   const char* format, va_list args) {
    (void)logger; (void)category; (void)level;
    if (log_file) { vfprintf(log_file, format, args); fputc('\n', log_file); }
}
static struct mLogger logger = { .log = on_log };

static SyncNode* active_node(Player* p) {
    if (!p->core) return NULL;
    struct GBASIO* sio=&gba_of(p)->sio;
    if (sio->activeDriver==&p->multi_node.d) return &p->multi_node;
    if (sio->activeDriver==&p->normal_node.d) return &p->normal_node;
    return NULL;
}
static int node_mode(Player* p) {
    SyncNode* n=active_node(p);
    return n?n->mode:-1;
}
static void refresh_multi_bits(void) {
    int both = node_mode(&players[0])==SIO_MULTI && node_mode(&players[1])==SIO_MULTI;
    for (int i=0;i<2;i++) {
        if (node_mode(&players[i])!=SIO_MULTI) continue;
        struct GBASIO* sio=&gba_of(&players[i])->sio;
        sio->siocnt = GBASIOMultiplayerSetReady(sio->siocnt, both);
        sio->siocnt = GBASIOMultiplayerSetSlave(sio->siocnt, i>0 || !both);
        if (i) sio->rcnt |= 4; else sio->rcnt &= ~4;
    }
}
static void trace(const char* fmt, ...) {
    if (!sio_trace || sio_trace_lines>=200000) return;
    va_list ap; va_start(ap,fmt); vfprintf(sio_trace,fmt,ap); va_end(ap);
    sio_trace_lines++;
}
static void finish_transfer(struct mTiming* timing, void* ctx, uint32_t late) {
    (void)timing; (void)ctx;
    if (!xfer_active) return;
    xfer_active=0;
    for (int i=0;i<2;i++) {
        Player* p=&players[i];
        struct GBA* gba=gba_of(p);
        struct GBASIO* sio=&gba->sio;
        int mode=node_mode(p);
        if (xfer_mode==SIO_MULTI) {
            if (mode!=SIO_MULTI) continue;
            for (int k=0;k<4;k++) gba->memory.io[(REG_SIOMULTI0>>1)+k]=xfer_multi[k];
            sio->rcnt |= 1;
            sio->siocnt = GBASIOMultiplayerClearBusy(sio->siocnt);
            sio->siocnt = GBASIOMultiplayerSetId(sio->siocnt, i);
            if (GBASIOMultiplayerIsIrq(sio->siocnt)) GBARaiseIRQ(gba, GBA_IRQ_SIO, i==0?late:0);
        } else {
            if (mode!=SIO_NORMAL_8 && mode!=SIO_NORMAL_32) continue;
            if (i==1 && !GBASIONormalIsStart(sio->siocnt)) continue; // slave not armed
            uint32_t in = xfer_normal[1-i];
            if (mode==SIO_NORMAL_32) {
                gba->memory.io[REG_SIODATA32_LO>>1]=in&0xFFFF;
                gba->memory.io[REG_SIODATA32_HI>>1]=in>>16;
            } else {
                gba->memory.io[REG_SIODATA8>>1]=in&0xFF;
            }
            sio->siocnt = GBASIONormalClearStart(sio->siocnt);
            if (GBASIONormalIsIrq(sio->siocnt)) GBARaiseIRQ(gba, GBA_IRQ_SIO, i==0?late:0);
        }
    }
    {
        struct GBA* sg=gba_of(&players[1]);
        uint32_t spc=0; players[1].core->readRegister(players[1].core,"pc",&spc);
        trace("done adj=%lld,%lld t=%llu mode=%d slave: t=%llu ime=%04X ie=%04X if=%04X i=%d halted=%d pc=%08X siocnt=%04X\n",
              (long long)((int64_t)now_of(&players[0])-time_base[0]),(long long)((int64_t)now_of(&players[1])-time_base[1]),
              (unsigned long long)now_of(&players[0]),xfer_mode,(unsigned long long)now_of(&players[1]),
              sg->memory.io[REG_IME>>1],sg->memory.io[REG_IE>>1],sg->memory.io[REG_IF>>1],
              sg->cpu->cpsr.i,sg->cpu->halted,spc,sg->sio.siocnt);
    }
}
static bool node_init(struct GBASIODriver* d) { (void)d; return true; }
static void node_deinit(struct GBASIODriver* d) { (void)d; }
static bool node_load(struct GBASIODriver* d) {
    SyncNode* n=(SyncNode*)d;
    n->mode=d->p->mode;
    refresh_multi_bits();
    trace("load p%d mode=%d t=%llu\n",n->id,n->mode,(unsigned long long)now_of(n->owner));
    return true;
}
static bool node_unload(struct GBASIODriver* d) {
    SyncNode* n=(SyncNode*)d;
    trace("unload p%d mode=%d t=%llu\n",n->id,n->mode,(unsigned long long)now_of(n->owner));
    n->mode=-1;
    if (n->id==0 && xfer_active) {
        struct mTiming* tm=&gba_of(n->owner)->timing;
        if (mTimingIsScheduled(tm,&xfer_event)) mTimingDeschedule(tm,&xfer_event);
        xfer_active=0;
    }
    // other node loses Ready
    for (int i=0;i<2;i++) {
        if (i==n->id || node_mode(&players[i])!=SIO_MULTI) continue;
        struct GBASIO* sio=&gba_of(&players[i])->sio;
        sio->siocnt=GBASIOMultiplayerClearReady(sio->siocnt);
    }
    return true;
}
static uint16_t node_write(struct GBASIODriver* d, uint32_t address, uint16_t value) {
    SyncNode* n=(SyncNode*)d;
    Player* p=n->owner;
    struct GBA* gba=gba_of(p);
    if (address!=REG_SIOCNT) return value;
    if (n->mode==SIO_MULTI) {
        int both = node_mode(&players[0])==SIO_MULTI && node_mode(&players[1])==SIO_MULTI;
        uint16_t cur=d->p->siocnt;
        if (n->id==0 && both && players[1].core && (value&0x80) && !xfer_active) {
            xfer_active=1; xfer_mode=SIO_MULTI;
            xfer_multi[0]=gba->memory.io[REG_SIOMLT_SEND>>1];
            xfer_multi[1]=gba_of(&players[1])->memory.io[REG_SIOMLT_SEND>>1];
            xfer_multi[2]=xfer_multi[3]=0xFFFF;
            struct GBASIO* ss=&gba_of(&players[1])->sio;
            ss->siocnt=GBASIOMultiplayerFillBusy(ss->siocnt);
            ss->rcnt &= ~1;
            for (int k=0;k<4;k++) gba->memory.io[(REG_SIOMULTI0>>1)+k]=0xFFFF;
            int cycles=GBASIOCyclesPerTransfer[GBASIOMultiplayerGetBaud(value)][1];
            mTimingSchedule(&gba->timing,&xfer_event,cycles);
            transfers_multi++;
            trace("multi t=%llu m=%04X s=%04X baud=%d\n",(unsigned long long)now_of(p),
                  xfer_multi[0],xfer_multi[1],GBASIOMultiplayerGetBaud(value));
        }
        // writable: baud, mode, IRQ; read-only: SI, SD, ID, error; busy tracks the link
        return (uint16_t)((value & 0xFF03) | (cur & 0x7C) | (xfer_active && xfer_mode==SIO_MULTI ? 0x80 : 0));
    }
    // normal 8/32
    value |= 0x0004; // SI high (idle)
    if (n->id==0 && (value&0x81)==0x81 && !xfer_active) {
        int other=node_mode(&players[1]);
        if (!players[1].core) return value;
        xfer_active=1; xfer_mode=n->mode;
        if (n->mode==SIO_NORMAL_32) {
            xfer_normal[0]=gba->memory.io[REG_SIODATA32_LO>>1] | ((uint32_t)gba->memory.io[REG_SIODATA32_HI>>1]<<16);
        } else xfer_normal[0]=gba->memory.io[REG_SIODATA8>>1]&0xFF;
        struct GBA* sg=gba_of(&players[1]);
        if (other==SIO_NORMAL_32) {
            xfer_normal[1]=sg->memory.io[REG_SIODATA32_LO>>1] | ((uint32_t)sg->memory.io[REG_SIODATA32_HI>>1]<<16);
        } else if (other==SIO_NORMAL_8) xfer_normal[1]=sg->memory.io[REG_SIODATA8>>1]&0xFF;
        else xfer_normal[1]=0xFFFFFFFF;
        int bits=n->mode==SIO_NORMAL_32?32:8;
        int cycles=bits*((value&2)?8:64);
        mTimingSchedule(&gba->timing,&xfer_event,cycles);
        transfers_normal++;
        trace("normal t=%llu bits=%d m=%08X s=%08X slave_start=%d\n",(unsigned long long)now_of(p),bits,
              xfer_normal[0],xfer_normal[1],(sg->sio.siocnt>>7)&1);
    }
    return value;
}
static void tick_cb(struct mTiming* timing, void* ctx, uint32_t late) {
    (void)late;
    Player* p=ctx;
    mTimingSchedule(timing,&p->tick,TICK);
    // End this runLoop even while halted; otherwise a halted core skips
    // ahead to its next IRQ (up to a frame) and outruns its link partner.
    gba_of(p)->earlyExit = true;
}
static void ensure_tick(Player* p) {
    struct mTiming* tm=&gba_of(p)->timing;
    if (!mTimingIsScheduled(tm,&p->tick)) mTimingSchedule(tm,&p->tick,TICK);
}
static void watch_entered(struct mDebugger* dbg, enum mDebuggerEntryReason reason,
                          struct mDebuggerEntryInfo* info) {
    Player* p = NULL;
    for (int i=0;i<2;i++) if (&players[i].dbg == dbg) p = &players[i];
    if (!p) return;
    if (reason == DEBUGGER_ENTER_WATCHPOINT && info) {
        uint32_t pc=0,lr=0;
        p->core->readRegister(p->core,"pc",&pc);
        p->core->readRegister(p->core,"lr",&lr);
        for (unsigned i=0;i<p->watch_count;i++) {
            Watch* w=&p->watches[i];
            if (info->address < w->address || info->address-w->address >= w->length ||
                !(w->mode & info->type.wp.accessType)) continue;
            if (w->hits < 20000) {
                fprintf(w->file,"watch=%u hit=%u frame=%u t=%llu addr=%08X pc=%08X lr=%08X old=%08X new=%08X\n",
                        i,w->hits,p->core->frameCounter(p->core),(unsigned long long)now_of(p),info->address,pc,lr,
                        info->type.wp.oldValue,info->type.wp.newValue);
                fflush(w->file);
            }
            w->hits++;
        }
    }
    dbg->state = DEBUGGER_RUNNING;
}
static int attach_watch(Player* p, uint32_t addr, unsigned len, char type, const char* path) {
    if (p->watch_count >= 32) return -1;
    FILE* file = !strcmp(path,"KEEP") ? (p->watch_count ? p->watches[p->watch_count-1].file : NULL) : fopen(path,"w");
    if (!file) return -1;
    enum mWatchpointType wt = type=='w'?WATCHPOINT_WRITE:type=='a'?WATCHPOINT_RW:WATCHPOINT_READ;
    p->watches[p->watch_count++] = (Watch){.address=addr,.length=len,.mode=wt,.file=file};
    if (!p->dbg_attached) {
        memset(&p->dbg,0,sizeof(p->dbg));
        p->dbg.type=DEBUGGER_CUSTOM; p->dbg.entered=watch_entered;
        mDebuggerAttach(&p->dbg,p->core);
        if (p->dbg.init) p->dbg.init(&p->dbg);
        p->dbg_attached=1;
    }
    int count=0;
    for (unsigned n=0;n<len;n++) {
        struct mWatchpoint wp; memset(&wp,0,sizeof(wp));
        wp.address=addr+n; wp.segment=-1; wp.type=wt;
        if (p->dbg.platform && p->dbg.platform->setWatchpoint) {
            p->dbg.platform->setWatchpoint(p->dbg.platform,&wp); count++;
        }
    }
    p->dbg.state=DEBUGGER_RUNNING;
    return count;
}
static void run_slice(Player* p) {
    ensure_tick(p);
    // Watchpoints are memory shims installed by the attached debugger and
    // fire inside runLoop too. mDebuggerRun would single-step whenever a
    // watchpoint exists, and ARMRun's processEvents loop ignores earlyExit,
    // letting a halted core run ahead of its link partner.
    p->core->runLoop(p->core);
}
// Interleave both cores (lower global time first) until stop() is true.
static unsigned long run_linked_until(int (*stop)(void*), void* arg, unsigned long max_slices) {
    unsigned long n=0;
    while (!stop(arg) && n<max_slices) {
        Player* p=&players[0];
        if (linked && (int64_t)now_of(&players[1])-time_base[1] < (int64_t)now_of(&players[0])-time_base[0]) p=&players[1];
        run_slice(p); n++;
    }
    return n;
}
struct FrameStop { int id; uint32_t target; };
static int frame_stop(void* a) {
    struct FrameStop* f=a;
    return (int32_t)(players[f->id].core->frameCounter(players[f->id].core)-f->target)>=0;
}
static int shot(Player* p, const char* path) {
    const void* pixels; size_t stride;
    p->core->getPixels(p->core,&pixels,&stride);
    FILE* out=fopen(path,"wb"); if (!out) return 0;
    uint16_t hdr[2]={(uint16_t)p->width,(uint16_t)p->height};
    uint8_t size=sizeof(color_t);
    fwrite(hdr,2,2,out); fwrite(&size,1,1,out);
    for (unsigned y=0;y<p->height;y++)
        fwrite((const char*)pixels+y*stride*sizeof(color_t),sizeof(color_t),p->width,out);
    return fclose(out)==0;
}
static void attach_sio(Player* p, int id) {
    struct GBASIO* sio=&gba_of(p)->sio;
    SyncNode* nodes[2]={&p->multi_node,&p->normal_node};
    for (int k=0;k<2;k++) {
        memset(nodes[k],0,sizeof(SyncNode));
        nodes[k]->owner=p; nodes[k]->id=id; nodes[k]->mode=-1;
        nodes[k]->d.init=node_init; nodes[k]->d.deinit=node_deinit;
        nodes[k]->d.load=node_load; nodes[k]->d.unload=node_unload;
        nodes[k]->d.writeRegister=node_write;
    }
    GBASIOSetDriver(sio,&p->multi_node.d,SIO_MULTI);
    GBASIOSetDriver(sio,&p->normal_node.d,SIO_NORMAL_32);
}
static int setup_core(Player* p, int id, const char* rom_path, const char* mb_path,
                      const char* save_path, const char* bios_path, int skip_bios) {
    struct VFile* vf=VFileOpen(rom_path,O_RDONLY);
    if (!vf) return 0;
    p->core=mCoreFindVF(vf);
    if (!p->core || !p->core->init(p->core)) return 0;
    mCoreInitConfig(p->core,NULL);
    p->core->opts.useBios = bios_path!=NULL;
    p->core->opts.skipBios = skip_bios;
    p->core->desiredVideoDimensions(p->core,&p->width,&p->height);
    p->video=calloc(p->width*p->height,sizeof(color_t));
    p->core->setVideoBuffer(p->core,p->video,p->width);
    if (bios_path) {
        p->bios=VFileOpen(bios_path,O_RDONLY);
        if (!p->bios || !p->core->loadBIOS(p->core,p->bios,0)) {
            fprintf(stderr,"BIOS load failed for player %d\n",id); return 0;
        }
    }
    if (id==0) {
        if (!p->core->loadROM(p->core,vf)) return 0;
        if (save_path) {
            struct VFile* sv=VFileOpen(save_path,O_RDWR);
            if (!sv || !p->core->loadSave(p->core,sv)) return 0;
        }
    } else {
        vf->close(vf);
        if (mb_path && strcmp(mb_path,"-")) {
            struct VFile* mb=VFileOpen(mb_path,O_RDONLY);
            if (!mb || !GBALoadMB(gba_of(p),mb)) return 0;
        }
    }
    attach_sio(p,id);
    p->tick.context=p; p->tick.callback=tick_cb; p->tick.name="link tick"; p->tick.priority=0xFF;
    p->core->reset(p->core);
    ensure_tick(p);
    return 1;
}
static int clone_save(const char* source) {
    if (!source) return 1;
    FILE* in=fopen(source,"rb"); if (!in) return 0;
    snprintf(private_save,sizeof(private_save),"temp/release_C/verify4b/save_probe_XXXXXX");
    int fd=mkstemp(private_save); if (fd<0) {fclose(in);return 0;}
    unsigned char block[8192]; size_t n; int ok=1;
    while ((n=fread(block,1,sizeof(block),in))>0) {
        if (write(fd,block,n)!=(ssize_t)n) {ok=0;break;}
    }
    if (ferror(in)) ok=0;
    fclose(in); close(fd);
    if (!ok) {unlink(private_save); private_save[0]=0;}
    return ok;
}
int main(int argc, char** argv) {
    const char* bios=NULL; int host_skip=0;
    int a=1;
    while (a<argc && !strncmp(argv[a],"--",2)) {
        if (!strcmp(argv[a],"--bios") && a+1<argc) { bios=argv[a+1]; a+=2; }
        else if (!strcmp(argv[a],"--host-skip-bios")) { host_skip=1; a++; }
        else { fprintf(stderr,"unknown option %s\n",argv[a]); return 2; }
    }
    int rest=argc-a;
    if (rest<3 || rest>4) {
        fprintf(stderr,"usage: %s [--bios PATH] [--host-skip-bios] HOST_ROM CLIENT_MB_OR_- LOG_FILE [HOST_SAVE_COPY]\n",argv[0]);
        return 2;
    }
    const char* rom=argv[a]; const char* mb=argv[a+1]; const char* logp=argv[a+2];
    const char* save=rest==4?argv[a+3]:NULL;
    if (save && !clone_save(save)) { fprintf(stderr,"cannot clone host save\n"); return 2; }
    log_file=fopen(logp,"w"); if (!log_file) return 2;
    mLogSetDefaultLogger(&logger);
    xfer_event.context=NULL; xfer_event.callback=finish_transfer; xfer_event.name="link xfer"; xfer_event.priority=0x80;
    if (!setup_core(&players[0],0,rom,NULL,save?private_save:NULL,bios,host_skip) ||
        !setup_core(&players[1],1,rom,mb,NULL,bios,0)) {
        fprintf(stderr,"failed to initialize cores\n"); return 2;
    }
    fprintf(stderr,"READY 2 cores; client=%s; bios=%s; host save=%s\n",mb,bios?bios:"HLE",save?"private copy":"none");
    char line[4096];
    while (fgets(line,sizeof(line),stdin)) {
        char* cmd=strtok(line," \t\r\n"); if (!cmd) continue;
        if (!strcmp(cmd,"frames1")) {
            char* x=strtok(NULL," \t\r\n"),*y=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1, n=y?atoi(y):-1;
            if (id<0||id>1||n<0||n>100000) {puts("ERR frames1");continue;}
            for (int i=0;i<n;i++) {
                uint32_t fc=players[id].core->frameCounter(players[id].core);
                while (players[id].core->frameCounter(players[id].core)==fc) run_slice(&players[id]);
            }
            printf("OK frames1 %d %d total=%u\n",id,n,players[id].core->frameCounter(players[id].core));
        } else if (!strcmp(cmd,"frames") || !strcmp(cmd,"framesc")) {
            char* x=strtok(NULL," \t\r\n"); int n=x?atoi(x):-1;
            if (n<0 || n>100000) { puts("ERR frame count"); continue; }
            struct FrameStop f={.id=!strcmp(cmd,"framesc")};
            f.target=players[f.id].core->frameCounter(players[f.id].core)+n;
            run_linked_until(frame_stop,&f,(unsigned long)-1);
            printf("OK %s %d host=%u client=%u xfer_multi=%lu xfer_normal=%lu\n",cmd,n,
                   players[0].core->frameCounter(players[0].core),
                   players[1].core->frameCounter(players[1].core),transfers_multi,transfers_normal);
        } else if (!strcmp(cmd,"link")) {
            char* m=strtok(NULL," \t\r\n");
            if (!m) {puts("ERR link");continue;}
            linked=!strcmp(m,"on");
            if (linked) { time_base[0]=(int64_t)now_of(&players[0]); time_base[1]=(int64_t)now_of(&players[1]); }
            printf("OK link %s\n",linked?"on":"off");
        } else if (!strcmp(cmd,"keys")) {
            char* x=strtok(NULL," \t\r\n"),*y=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1; if (id<0||id>1||!y) {puts("ERR keys");continue;}
            uint32_t mask=strtoul(y,NULL,0); players[id].core->setKeys(players[id].core,mask);
            printf("OK keys %d %u\n",id,mask);
        } else if (!strcmp(cmd,"loadmb")) {
            char* path=strtok(NULL," \t\r\n");
            struct VFile* f=path?VFileOpen(path,O_RDONLY):NULL;
            int ok=f && GBALoadMB(gba_of(&players[1]),f);
            if (ok) players[1].core->reset(players[1].core);
            printf("%s loadmb %s\n",ok?"OK":"ERR",path?path:"(null)");
        } else if (!strcmp(cmd,"shot") || !strcmp(cmd,"syncshot")) {
            char* x=strtok(NULL," \t\r\n"),*path=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1;
            if (id<0||id>1||!path) {puts("ERR shot");continue;}
            if (!strcmp(cmd,"syncshot")) {
                struct FrameStop f={.id=id,.target=players[id].core->frameCounter(players[id].core)+1};
                run_linked_until(frame_stop,&f,(unsigned long)-1);
            }
            printf("%s %s %d frame=%u\n",shot(&players[id],path)?"OK":"ERR",cmd,id,
                   players[id].core->frameCounter(players[id].core));
        } else if (!strcmp(cmd,"savestate") || !strcmp(cmd,"loadstate")) {
            int loading=!strcmp(cmd,"loadstate");
            char* x=strtok(NULL," \t\r\n"),*path=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1;
            if (id<0||id>1||!path) {puts("ERR state args");continue;}
            struct VFile* file=VFileOpen(path,loading?O_RDONLY:(O_CREAT|O_TRUNC|O_WRONLY));
            bool ok=file && (loading?mCoreLoadStateNamed(players[id].core,file,SAVESTATE_ALL)
                                    :mCoreSaveStateNamed(players[id].core,file,SAVESTATE_ALL));
            if (file) file->close(file);
            if (loading && ok) {
                // drop any in-flight transfer and recompute link status bits
                if (xfer_active) {
                    struct mTiming* tm=&gba_of(&players[0])->timing;
                    if (mTimingIsScheduled(tm,&xfer_event)) mTimingDeschedule(tm,&xfer_event);
                    xfer_active=0;
                }
                refresh_multi_bits();
                if (linked) { time_base[0]=(int64_t)now_of(&players[0]); time_base[1]=(int64_t)now_of(&players[1]); }
            }
            printf("%s %s %d %s xfer_active=%d\n",ok?"OK":"ERR",loading?"loadstate":"savestate",id,path,xfer_active);
        } else if (!strcmp(cmd,"dumpmem")) {
            char* x=strtok(NULL," \t\r\n"),*y=strtok(NULL," \t\r\n"),*z=strtok(NULL," \t\r\n"),*path=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1; uint32_t addr=y?strtoul(y,NULL,16):0; unsigned len=z?strtoul(z,NULL,0):0;
            if (id<0||id>1||!path||len>0x1000000) {puts("ERR dumpmem");continue;}
            FILE* out=fopen(path,"wb"); if (!out) {puts("ERR dumpmem open");continue;}
            for (unsigned n=0;n<len;n++) fputc(players[id].core->rawRead8(players[id].core,addr+n,-1),out);
            fclose(out); printf("OK dumpmem %d %08X %u\n",id,addr,len);
        } else if (!strcmp(cmd,"w16") || !strcmp(cmd,"w32")) {
            char* x=strtok(NULL," \t\r\n"),*y=strtok(NULL," \t\r\n"),*z=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1; uint32_t addr=y?strtoul(y,NULL,16):0;
            uint32_t value=z?strtoul(z,NULL,16):0;
            if (id<0||id>1||!z) {printf("ERR %s\n",cmd);continue;}
            if (cmd[1]=='1') players[id].core->busWrite16(players[id].core,addr,(uint16_t)value);
            else players[id].core->busWrite32(players[id].core,addr,value);
            printf("OK %s %d %08X %X\n",cmd,id,addr,value);
        } else if (!strcmp(cmd,"setreg")) {
            char* x=strtok(NULL," \t\r\n"),*name=strtok(NULL," \t\r\n"),*z=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1; uint32_t value=z?strtoul(z,NULL,16):0;
            if (id<0||id>1||!name||!z) {puts("ERR setreg");continue;}
            players[id].core->writeRegister(players[id].core,name,&value);
            printf("OK setreg %d %s %08X\n",id,name,value);
        } else if (!strcmp(cmd,"watchaddr")) {
            char* x=strtok(NULL," \t\r\n"),*y=strtok(NULL," \t\r\n"),*z=strtok(NULL," \t\r\n"),*d=strtok(NULL," \t\r\n"),*path=strtok(NULL," \t\r\n");
            int id=x?atoi(x):-1; uint32_t addr=y?strtoul(y,NULL,16):0; unsigned len=z?strtoul(z,NULL,0):0;
            if (id<0||id>1||!d||!path||!len||len>4096) {puts("ERR watchaddr");continue;}
            int count=attach_watch(&players[id],addr,len,d[0],path);
            if (count<0) puts("ERR watchaddr attach");
            else printf("OK watchaddr %d %08X len=%u set=%d\n",id,addr,len,count);
        } else if (!strcmp(cmd,"watchcount")) {
            printf("OK watchcount host=%u client=%u\n",players[0].watch_count,players[1].watch_count);
        } else if (!strcmp(cmd,"siotrace")) {
            char* path=strtok(NULL," \t\r\n");
            if (sio_trace) fclose(sio_trace);
            sio_trace=path?fopen(path,"w"):NULL; sio_trace_lines=0;
            printf("%s siotrace\n",sio_trace?"OK":"ERR");
        } else if (!strcmp(cmd,"regs")) {
            char* x=strtok(NULL," \t\r\n"); int id=x?atoi(x):-1;
            if (id<0||id>1) {puts("ERR regs");continue;}
            uint32_t pc=0,sp=0,lr=0,cpsr=0;
            players[id].core->readRegister(players[id].core,"pc",&pc);
            players[id].core->readRegister(players[id].core,"sp",&sp);
            players[id].core->readRegister(players[id].core,"lr",&lr);
            players[id].core->readRegister(players[id].core,"cpsr",&cpsr);
            printf("OK regs %d pc=%08X sp=%08X lr=%08X cpsr=%08X\n",id,pc,sp,lr,cpsr);
        } else if (!strcmp(cmd,"status")) {
            printf("OK status host=%u client=%u t=%llu,%llu xfer_multi=%lu xfer_normal=%lu watch=%u,%u\n",
                   players[0].core->frameCounter(players[0].core),
                   players[1].core->frameCounter(players[1].core),
                   (unsigned long long)now_of(&players[0]),(unsigned long long)now_of(&players[1]),
                   transfers_multi,transfers_normal,players[0].watch_count,players[1].watch_count);
        } else if (!strcmp(cmd,"sio")) {
            char buf[2][160];
            for (int id=0;id<2;id++) {
                struct GBA* g=gba_of(&players[id]);
                snprintf(buf[id],sizeof(buf[id]),"p%d mode=%d node=%d siocnt=%04X rcnt=%04X send=%04X multi=%04X,%04X",
                         id,g->sio.mode,node_mode(&players[id]),g->sio.siocnt,g->sio.rcnt,
                         g->memory.io[REG_SIOMLT_SEND>>1],g->memory.io[REG_SIOMULTI0>>1],g->memory.io[REG_SIOMULTI1>>1]);
            }
            printf("OK sio %s | %s\n",buf[0],buf[1]);
        } else if (!strcmp(cmd,"quit")) { puts("OK quit"); break; }
        else printf("ERR unknown %s\n",cmd);
        fflush(stdout);
    }
    if (sio_trace) fclose(sio_trace);
    for (int id=0;id<2;id++) for (unsigned i=0;i<players[id].watch_count;i++) {
        FILE* file=players[id].watches[i].file;
        int prior=0;
        for (unsigned j=0;j<i;j++) if (players[id].watches[j].file==file) prior=1;
        if (!prior) fclose(file);
    }
    if (private_save[0]) unlink(private_save);
    return 0;
}
