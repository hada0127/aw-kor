// Headless libmgba + Lua scripting driver (WIP — 2026-06-23). Build:
//   clang -I/opt/homebrew/include tools/mgba_lua.c -L/opt/homebrew/lib -lmgba -o /tmp/mgbalua
// Run:  DYLD_LIBRARY_PATH=/opt/homebrew/lib /tmp/mgbalua <rom> <script.lua> [frames]
//
// 상태: Lua 엔진(_mSCRIPT_ENGINE_LUA)이 libmgba에 있어 .lua를 **컴파일**한다(문법오류 보고 동작).
//   그러나 mScriptContextLoadFile + TriggerCallback + 엔진 run() 어느 조합으로도 **top-level chunk가
//   실행되지 않음**(emu:write 마커 미반영, console:log 무출력). 즉 헤드리스 임베딩에서 스크립트 실행
//   트리거를 아직 못 찾음(프론트엔드 소스 미공개). 추후: mScriptContext 내부 run 경로 RE 또는
//   mScriptBridge 경로 시도. docs/fail.md 2026-06-23 續4 참조.
#include <mgba/core/core.h>
#include <mgba/core/scripting.h>
#include <mgba/script/context.h>
#include <mgba-util/vfs.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <stdarg.h>

static FILE* g_out;
static void luaLog(struct mLogger* l, int cat, enum mLogLevel lv, const char* fmt, va_list args){
    (void)l;(void)cat;(void)lv;
    vfprintf(g_out, fmt, args); fputc('\n', g_out); fflush(g_out);
}
static struct mLogger g_logger = { .log = luaLog };

int main(int argc, char** argv){
    if(argc<3){ fprintf(stderr,"usage: mgbalua <rom> <script.lua> [frames]\n"); return 1; }
    g_out = stdout;
    mLogSetDefaultLogger(&g_logger);
    struct VFile* vf = VFileOpen(argv[1], O_RDONLY);
    if(!vf){ fprintf(stderr,"cannot open rom\n"); return 1; }
    struct mCore* core = mCoreFindVF(vf);
    if(!core){ fprintf(stderr,"no core\n"); return 1; }
    core->init(core);
    mCoreInitConfig(core, NULL);
    unsigned w,h; core->desiredVideoDimensions(core,&w,&h);
    void* vbuf = malloc(w*h*sizeof(color_t));
    core->setVideoBuffer(core, (color_t*)vbuf, w);
    core->loadROM(core, vf);
    core->reset(core);

    struct mScriptContext ctx;
    mScriptContextInit(&ctx);
    mScriptContextAttachStdlib(&ctx);
    mScriptContextAttachCore(&ctx, core);
    mScriptContextAttachLogger(&ctx, &g_logger);
    mScriptContextRegisterEngines(&ctx);

    if(!mScriptContextLoadFile(&ctx, argv[2])){
        fprintf(stderr,"script load failed: %s\n", argv[2]);
        return 2;
    }
    mScriptContextTriggerCallback(&ctx, "frame");
    fprintf(stderr,"MARKER@0x03007F00 = %08X (스크립트 top-level 실행 여부)\n",
            core->busRead32(core, 0x03007F00));
    int frames = argc>3 ? atoi(argv[3]) : 600;
    for(int i=0;i<frames;i++){
        core->runFrame(core);
        mScriptContextTriggerCallback(&ctx, "frame");
    }
    mScriptContextDeinit(&ctx);
    fprintf(stderr,"DONE %d frames\n", frames);
    return 0;
}
