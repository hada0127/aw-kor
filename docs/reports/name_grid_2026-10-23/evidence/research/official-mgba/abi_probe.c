#include <mgba/flags.h>
#include <mgba/core/core.h>
#include <mgba/debugger/debugger.h>
#include <mgba/internal/gba/gba.h>
#include <stddef.h>
const unsigned long abi_layout[] = {
 sizeof(color_t), sizeof(struct mCore), offsetof(struct mCore, board),
 offsetof(struct mCore, attachDebugger), offsetof(struct mCore, savedataClone),
 sizeof(struct mDebugger), sizeof(struct mDebuggerEntryInfo), sizeof(struct GBA),
 offsetof(struct GBA, memory), offsetof(struct GBA, sio), offsetof(struct GBA, timing),
 sizeof(struct GBASIO), sizeof(struct GBASIODriver), sizeof(struct mTimingEvent)
};
