// Headless GBA decompile helper (PoC). Args:
//   outdir  spec...   where spec = ADDR[:t|:a]  (decompile function at ADDR, Thumb default)
//                     or xref=ADDR (find literal-pool refs to the 32-bit constant ADDR,
//                     create the containing Thumb functions, list them)
//@category GBA
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.app.cmd.disassemble.DisassembleCommand;
import ghidra.app.cmd.function.CreateFunctionCmd;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.math.BigInteger;
import java.util.*;

public class GbaDecomp extends GhidraScript {
    Memory mem; Listing lst; Register tmode;

    void ensureBlocks() throws Exception {
        String[][] b = {{"EWRAM","0x02000000","0x40000"},{"IWRAM","0x03000000","0x8000"},
                        {"IO","0x04000000","0x400"},{"PAL","0x05000000","0x400"},
                        {"VRAM","0x06000000","0x18000"},{"OAM","0x07000000","0x400"},
                        {"SRAM","0x0E000000","0x10000"}};
        for (String[] e : b) {
            Address a = toAddr(e[1]);
            if (mem.getBlock(a) != null) continue;
            MemoryBlock blk = mem.createUninitializedBlock(e[0], a, Long.decode(e[2]), false);
            blk.setRead(true); blk.setWrite(true); blk.setExecute(e[0].equals("IWRAM")||e[0].equals("EWRAM"));
            if (e[0].equals("IO")) blk.setVolatile(true);
        }
        MemoryBlock rom = mem.getBlock(toAddr(0x08000000L));
        if (rom != null) { rom.setWrite(false); rom.setName("ROM"); }
    }

    Function makeFunc(Address a, boolean thumb) throws Exception {
        Function f = getFunctionAt(a);
        if (f != null) { fixReturns(f); return f; }
        Instruction ins = lst.getInstructionAt(a);
        if (ins == null) {
            AddressSet one = new AddressSet(a);
            DisassembleCommand dc = new DisassembleCommand(one, null, true);
            dc.setInitialContext(new RegisterValue(tmode, BigInteger.valueOf(thumb ? 1 : 0)));
            dc.applyTo(currentProgram, monitor);
        }
        CreateFunctionCmd cf = new CreateFunctionCmd(a);
        cf.applyTo(currentProgram, monitor);
        f = getFunctionAt(a);
        if (f != null) seedJumpTables(f, thumb);
        return getFunctionAt(a);
    }

    // Disassemble the targets of every call so callees get names, and resolve
    // simple Thumb jump tables (ldr rX,[rY] ; mov pc,rX) by letting the
    // decompiler recover them, then re-creating the function body.
    // ARMv4T returns via "pop {rX}; bx rX" (no pop {pc} interworking): mark as RETURN.
    void fixReturns(Function f) throws Exception {
        for (Instruction ins : lst.getInstructions(f.getBody(), true)) {
            if (!ins.getMnemonicString().equalsIgnoreCase("bx")) continue;
            Object[] o = ins.getOpObjects(0);
            if (o.length != 1 || !(o[0] instanceof Register) || ((Register)o[0]).getName().equals("lr")) continue;
            Instruction prev = ins.getPrevious();
            if (prev != null && prev.getMnemonicString().equalsIgnoreCase("pop")
                && prev.toString().contains(((Register)o[0]).getName()))
                ins.setFlowOverride(ghidra.program.model.listing.FlowOverride.RETURN);
        }
    }

    void seedJumpTables(Function f, boolean thumb) throws Exception {
        fixReturns(f);
        for (int pass = 0; pass < 3; pass++) {
            DecompInterface di = newDI();
            DecompileResults r = di.decompileFunction(f, 120, monitor);
            boolean changed = false;
            if (r != null && r.getHighFunction() != null) {
                for (ghidra.program.model.pcode.JumpTable jt : r.getHighFunction().getJumpTables()) {
                    for (Address t : jt.getCases()) {
                        if (lst.getInstructionAt(t) == null) {
                            DisassembleCommand dc = new DisassembleCommand(new AddressSet(t), null, true);
                            dc.setInitialContext(new RegisterValue(tmode, BigInteger.valueOf(thumb ? 1 : 0)));
                            dc.applyTo(currentProgram, monitor);
                            changed = true;
                        }
                    }
                    for (Address t : jt.getCases())
                        currentProgram.getReferenceManager().addMemoryReference(jt.getSwitchAddress(), t,
                            ghidra.program.model.symbol.RefType.COMPUTED_JUMP, SourceType.ANALYSIS, CodeUnit.MNEMONIC);
                    // refs only: the decompiler re-recovers the table itself and keeps real case values

                }
            }
            di.dispose();
            if (!changed) break;
            CreateFunctionCmd.fixupFunctionBody(currentProgram, f, monitor);
            fixReturns(f);
        }
        for (Instruction ins : lst.getInstructions(f.getBody(), true)) {
            for (Reference ref : ins.getReferencesFrom()) {
                if (ref.getReferenceType().isCall()) {
                    Address t = ref.getToAddress();
                    if (getFunctionAt(t) == null && mem.contains(t) && mem.getBlock(t).isInitialized()) {
                        boolean th = thumb && !ins.getMnemonicString().toLowerCase().startsWith("blx");
                        DisassembleCommand dc = new DisassembleCommand(new AddressSet(t), null, true);
                        dc.setInitialContext(new RegisterValue(tmode, BigInteger.valueOf(th ? 1 : 0)));
                        dc.applyTo(currentProgram, monitor);
                        new CreateFunctionCmd(t).applyTo(currentProgram, monitor);
                    }
                }
            }
        }
    }

    DecompInterface newDI() {
        DecompInterface di = new DecompInterface();
        DecompileOptions o = new DecompileOptions();
        o.grabFromProgram(currentProgram);
        di.setOptions(o);
        di.toggleCCode(true); di.toggleSyntaxTree(true);
        di.setSimplificationStyle("decompile");
        di.openProgram(currentProgram);
        return di;
    }

    void writeDecomp(Function f, File outdir, StringBuilder log) throws Exception {
        DecompInterface di = newDI();
        DecompileResults r = di.decompileFunction(f, 180, monitor);
        String name = String.format("%08X", f.getEntryPoint().getOffset());
        File out = new File(outdir, name + ".c");
        try (PrintWriter pw = new PrintWriter(out)) {
            pw.println("// Ghidra " + getGhidraVersion() + " decompile of " + f.getName() + " @ " + f.getEntryPoint()
                + " body=" + f.getBody().getMinAddress() + ".." + f.getBody().getMaxAddress()
                + " TMode=" + currentProgram.getProgramContext().getValue(tmode, f.getEntryPoint(), false));
            if (r.decompileCompleted()) pw.println(r.getDecompiledFunction().getC());
            else pw.println("// DECOMPILE FAILED: " + r.getErrorMessage());
            pw.println("/* ---- disassembly ----");
            for (Instruction ins : lst.getInstructions(f.getBody(), true)) {
                StringBuilder refs = new StringBuilder();
                for (Reference rf : ins.getReferencesFrom()) refs.append(" ->").append(rf.getToAddress());
                pw.println(ins.getAddress() + "  " + ins + refs);
            }
            pw.println("*/");
        }
        log.append(name).append(" ").append(f.getName()).append(r.decompileCompleted() ? " OK " : " FAIL ")
           .append(out.getPath()).append("\n");
        di.dispose();
    }

    Function xrefFunc(Address lit) throws Exception {
        // Find Thumb LDR Rd,[PC,#imm8*4] within 1020 bytes before lit that targets lit.
        long L = lit.getOffset();
        for (long a = L - 2; a >= L - 1022 && a >= 0x08000000L; a -= 2) {
            int hw = mem.getShort(toAddr(a)) & 0xffff;
            if ((hw & 0xF800) != 0x4800) continue;
            long tgt = ((a + 4) & ~3L) + (hw & 0xff) * 4L;
            if (tgt != L) continue;
            // walk back to nearest PUSH {..,lr} (b5xx) as function start
            for (long s = a; s >= a - 0x2000 && s >= 0x08000000L; s -= 2) {
                int h = mem.getShort(toAddr(s)) & 0xffff;
                if ((h & 0xFF00) == 0xB500) {
                    Function f = getFunctionContaining(toAddr(a));
                    if (f == null) f = makeFunc(toAddr(s), true);
                    if (f != null && !f.getBody().contains(toAddr(a))) {
                        // not on the flow from that PUSH; still record the site
                        println("  ldr site " + toAddr(a) + " not in body of " + f.getName());
                    }
                    return f;
                }
            }
        }
        return null;
    }

    @Override public void run() throws Exception {
        mem = currentProgram.getMemory(); lst = currentProgram.getListing();
        tmode = currentProgram.getRegister("TMode");
        String[] args = getScriptArgs();
        File outdir = new File(args[0]); outdir.mkdirs();
        ensureBlocks();
        StringBuilder log = new StringBuilder();
        for (int i = 1; i < args.length; i++) {
            String s = args[i];
            if (s.startsWith("xref=")) {
                long v = Long.decode(s.substring(5));
                byte[] pat = {(byte)v,(byte)(v>>8),(byte)(v>>16),(byte)(v>>24)};
                Address a = mem.getBlock(toAddr(0x08000000L)).getStart();
                Address end = mem.getBlock(toAddr(0x08000000L)).getEnd();
                log.append(String.format("XREF %08X\n", v));
                while (a != null && a.compareTo(end) < 0) {
                    Address hit = mem.findBytes(a, end, pat, null, true, monitor);
                    if (hit == null) break;
                    if ((hit.getOffset() & 3) == 0) {
                        Function f = xrefFunc(hit);
                        Instruction li = null;
                        log.append(String.format("  literal@%s  func=%s\n", hit,
                            f == null ? "(no Thumb LDR-PC within 1KB: data/table or ARM)" : f.getName() + "@" + f.getEntryPoint()));
                    } else log.append("  unaligned hit@" + hit + " (data)\n");
                    a = hit.add(1);
                }
                continue;
            }
            String[] p = s.split(":");
            boolean thumb = p.length < 2 || p[1].startsWith("t");
            Address a = toAddr(Long.decode(p[0]) & ~1L);
            Function f = makeFunc(a, thumb);
            if (f == null) { log.append(p[0] + " could not create function\n"); continue; }
            writeDecomp(f, outdir, log);
        }
        print(log.toString());
        try (PrintWriter pw = new PrintWriter(new FileWriter(new File(outdir, "run.log"), true))) { pw.print(log); }
    }
}
