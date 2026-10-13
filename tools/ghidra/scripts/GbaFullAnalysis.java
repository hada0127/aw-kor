// Whole-ROM Ghidra analysis + export for the GBA ROM (static aid; confirm at runtime).
// Run via tools/ghidra/full_analysis.sh (import with -noanalysis, then this postScript).
// Args: outdir seeds.tsv overlays.tsv
//   seeds.tsv    : "ADDR<TAB>t|a<TAB>note"  (known function entries)
//   overlays.tsv : "NAME<TAB>IWRAM_ADDR<TAB>ROM_ADDR<TAB>LEN<TAB>PART"   (ROM->IWRAM copies)
// Decisions (recorded to outdir/decisions.log):
//   * pattern based function start search and aggressive instruction finder are OFF
//     (raw 16 MiB image is mostly data; patterns create code in graphics/text).
//   * Create Address Tables OFF (it disassembles at table targets without validation).
//   * extra seeds: header entries (0x080000C0 + embedded game headers), known list,
//     aligned ROM words that point to a Thumb PUSH{..,lr} (odd value) or ARM STMFD sp!,{..,lr}
//     (even value), raw Thumb BL targets hit from >=2 sites whose target is PUSH{..,lr}.
//   * ROM->IWRAM copies are added as initialized overlay blocks (one overlay space each);
//     ROM code literals pointing into the copied range seed the overlay.
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
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.pcode.JumpTable;
import java.io.*;
import java.math.BigInteger;
import java.util.*;

public class GbaFullAnalysis extends GhidraScript {
    Memory mem; Listing lst; Register tmode; PrintWriter dlog; File outdir;
    static final long ROM0 = 0x08000000L, ROM1 = 0x09FFFFFFL;
    List<Object[]> overlays = new ArrayList<>(); // name, iwram, rom, len, part, AddressSpace

    void d(String s) { dlog.println(s); dlog.flush(); println(s); }

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
        MemoryBlock rom = mem.getBlock(toAddr(ROM0));
        if (rom != null) { rom.setWrite(false); rom.setName("ROM"); }
    }

    void addOverlays(File tsv) throws Exception {
        if (!tsv.exists()) return;
        for (String line : java.nio.file.Files.readAllLines(tsv.toPath())) {
            if (line.isBlank() || line.startsWith("#")) continue;
            String[] p = line.split("\t");
            String name = p[0]; long iw = Long.decode(p[1]), ro = Long.decode(p[2]); int len = Integer.decode(p[3]);
            MemoryBlock existing = mem.getBlock(name);
            if (existing == null) {
                byte[] buf = new byte[len];
                mem.getBytes(toAddr(ro), buf);
                existing = mem.createInitializedBlock(name, toAddr(iw), new ByteArrayInputStream(buf), len, monitor, true);
                existing.setRead(true); existing.setWrite(true); existing.setExecute(true);
                existing.setComment(String.format("copy of ROM %08X len 0x%X part %s (from IWRAM dump match)", ro, len, p[4]));
            }
            overlays.add(new Object[]{name, iw, ro, len, p[4], existing.getStart().getAddressSpace()});
            d(String.format("overlay %s IWRAM %08X <- ROM %08X len 0x%X part %s", name, iw, ro, len, p[4]));
        }
    }

    boolean disas(Address a, boolean thumb) {
        if (lst.getInstructionAt(a) != null) return true;
        if (lst.getDefinedDataContaining(a) != null) return false;
        if (lst.getInstructionContaining(a) != null) return false; // offcut: leave
        DisassembleCommand dc = new DisassembleCommand(new AddressSet(a), null, true);
        dc.setInitialContext(new RegisterValue(tmode, BigInteger.valueOf(thumb ? 1 : 0)));
        dc.applyTo(currentProgram, monitor);
        return lst.getInstructionAt(a) != null;
    }

    int seedFunc(Address a, boolean thumb) {
        if (!disas(a, thumb)) return 0;
        if (getFunctionAt(a) == null) new CreateFunctionCmd(a).applyTo(currentProgram, monitor);
        return getFunctionAt(a) != null ? 1 : 0;
    }

    int u16(long off) throws Exception { return mem.getShort(toAddr(off)) & 0xffff; }
    long u32(long off) throws Exception { return mem.getInt(toAddr(off)) & 0xffffffffL; }

    boolean thumbPushLr(long a) throws Exception { return (u16(a) & 0xFF00) == 0xB500; }
    boolean armStmfdLr(long a) throws Exception { return (u32(a) & 0xFFFF4000L) == 0xE92D4000L; }

    void setOpt(Map<String,String> cur, String name, String val) {
        if (!cur.containsKey(name)) { d("option missing (skip): " + name); return; }
        setAnalysisOption(currentProgram, name, val);
        d("option " + name + " = " + val + " (was " + cur.get(name) + ")");
    }

    void fixReturns() throws Exception {
        int n = 0;
        for (Instruction ins : lst.getInstructions(true)) {
            if (!ins.getMnemonicString().equalsIgnoreCase("bx")) continue;
            Object[] o = ins.getOpObjects(0);
            if (o.length != 1 || !(o[0] instanceof Register) || ((Register)o[0]).getName().equals("lr")) continue;
            Instruction prev = ins.getPrevious();
            if (prev != null && prev.getMnemonicString().equalsIgnoreCase("pop")
                && prev.toString().contains(((Register)o[0]).getName())
                && ins.getFlowOverride() != FlowOverride.RETURN) {
                ins.setFlowOverride(FlowOverride.RETURN); n++;
            }
        }
        d("pop{rX};bx rX marked RETURN: " + n);
    }

    @Override public void run() throws Exception {
        long t0 = System.currentTimeMillis();
        mem = currentProgram.getMemory(); lst = currentProgram.getListing();
        tmode = currentProgram.getRegister("TMode");
        String[] args = getScriptArgs();
        outdir = new File(args[0]); outdir.mkdirs();
        dlog = new PrintWriter(new FileWriter(new File(outdir, "decisions.log"), true));
        d("=== GbaFullAnalysis " + new Date() + " program=" + currentProgram.getName());
        ensureBlocks();
        addOverlays(new File(args[2]));
        boolean already = currentProgram.getFunctionManager().getFunctionCount() > 50;

        if (!already) {
            Map<String,String> cur = getCurrentAnalysisOptionsAndValues(currentProgram);
            try (PrintWriter pw = new PrintWriter(new File(outdir, "analysis_options_default.txt"))) {
                for (Map.Entry<String,String> e : new TreeMap<>(cur).entrySet()) pw.println(e.getKey() + "=" + e.getValue());
            }
            setOpt(cur, "ARM Aggressive Instruction Finder", "false");
            setOpt(cur, "Function Start Search", "false");
            setOpt(cur, "Function Start Search After Code", "false");
            setOpt(cur, "Function Start Search After Data", "false");
            setOpt(cur, "Create Address Tables", "false");
            setOpt(cur, "ASCII Strings", "false");
            setOpt(cur, "Embedded Media", "false");
            setOpt(cur, "Condense Filler Bytes", "false");

            // ---- seeds
            int nHdr = 0, nKnown = 0, nPtrT = 0, nPtrA = 0, nBl = 0;
            long[] hdr = {0x08000000L, 0x080000C0L, 0x08300000L, 0x083000C0L, 0x08B00000L, 0x08B000C0L};
            for (long h : hdr) nHdr += seedFunc(toAddr(h), false);
            d("seed header ARM entries: " + nHdr + "/" + hdr.length);
            for (String line : java.nio.file.Files.readAllLines(new File(args[1]).toPath())) {
                if (line.isBlank() || line.startsWith("#")) continue;
                String[] p = line.split("\t");
                long a = Long.decode(p[0]) & ~1L;
                if (a < ROM0 || a > ROM1) continue;
                nKnown += seedFunc(toAddr(a), p.length < 2 || p[1].startsWith("t"));
            }
            d("seed known list: " + nKnown);
            MemoryBlock rom = mem.getBlock(toAddr(ROM0));
            long rs = rom.getStart().getOffset(), re = rom.getEnd().getOffset();
            byte[] img = new byte[(int)(re - rs + 1)];
            mem.getBytes(rom.getStart(), img);
            java.nio.ByteBuffer bb = java.nio.ByteBuffer.wrap(img).order(java.nio.ByteOrder.LITTLE_ENDIAN);
            TreeSet<Long> ptrT = new TreeSet<>(), ptrA = new TreeSet<>();
            for (int i = 0; i + 4 <= img.length; i += 4) {
                long v = bb.getInt(i) & 0xffffffffL;
                if (v < rs || v > re - 4) continue;
                if ((v & 1) == 1) { if (thumbPushLr(v - 1)) ptrT.add(v - 1); }
                else if ((v & 3) == 0 && armStmfdLr(v)) ptrA.add(v);
            }
            for (long a : ptrT) nPtrT += seedFunc(toAddr(a), true);
            for (long a : ptrA) nPtrA += seedFunc(toAddr(a), false);
            d("seed pointer-table targets: thumb cand=" + ptrT.size() + " ok=" + nPtrT + "  arm cand=" + ptrA.size() + " ok=" + nPtrA);
            HashMap<Long,Integer> blHits = new HashMap<>();
            for (int i = 0; i + 4 <= img.length; i += 2) {
                int h1 = bb.getShort(i) & 0xffff, h2 = bb.getShort(i + 2) & 0xffff;
                if ((h1 & 0xF800) != 0xF000 || (h2 & 0xF800) != 0xF800) continue;
                int off = ((h1 & 0x7FF) << 12) | ((h2 & 0x7FF) << 1);
                if ((off & 0x400000) != 0) off -= 0x800000;
                long t = rs + i + 4 + off;
                if (t < rs || t > re - 2) continue;
                blHits.merge(t, 1, Integer::sum);
            }
            int blCand = 0;
            for (Map.Entry<Long,Integer> e : blHits.entrySet()) {
                if (e.getValue() < 2 || !thumbPushLr(e.getKey())) continue;
                blCand++; nBl += seedFunc(toAddr(e.getKey()), true);
            }
            d("seed raw BL targets (>=2 sites, PUSH lr): cand=" + blCand + " ok=" + nBl);
            fixReturns();
            long ta = System.currentTimeMillis();
            analyzeAll(currentProgram);
            d("analyzeAll pass1 sec=" + (System.currentTimeMillis() - ta) / 1000);
            fixReturns();
            // overlay seeds: ROM literal words pointing into copied IWRAM ranges
            int nOv = 0;
            for (Object[] ov : overlays) {
                long iw = (Long) ov[1]; int len = (Integer) ov[3]; String part = (String) ov[4];
                AddressSpace sp = (AddressSpace) ov[5];
                long lo = part.equals("p1") ? 0x08B00000L : 0x08300000L, hi = part.equals("p1") ? 0x09000000L : 0x08B00000L;
                for (int i = (int)(lo - rs); i + 4 <= img.length && i < hi - rs; i += 4) {
                    long v = bb.getInt(i) & 0xffffffffL;
                    if (v < iw || v >= iw + len) continue;
                    Address a = sp.getAddress(v & ~1L);
                    long hw = mem.getShort(a) & 0xffff;
                    boolean th = (v & 1) == 1;
                    if (th ? (hw & 0xFE00) == 0xB400 || (hw & 0xFF00) == 0xB500 : (v & 3) == 0 && ((mem.getInt(a) & 0xFFFF0000L) == 0xE92D0000L))
                        nOv += seedFunc(a, th);
                }
            }
            d("seed overlay entries from ROM literals: " + nOv);
            ta = System.currentTimeMillis();
            analyzeChanges(currentProgram);
            fixReturns();
            d("analyzeChanges pass2 sec=" + (System.currentTimeMillis() - ta) / 1000);
        } else d("program already analyzed; export only");

        export();
        d("total sec=" + (System.currentTimeMillis() - t0) / 1000);
        dlog.close();
    }

    String mode(Address a) {
        BigInteger v = currentProgram.getProgramContext().getValue(tmode, a, false);
        return v == null ? "?" : (v.intValue() == 1 ? "t" : "a");
    }

    String hx(Address a) {
        String s = String.format("%08X", a.getOffset());
        return a.getAddressSpace().isOverlaySpace() ? a.getAddressSpace().getName() + ":" + s : s;
    }

    void export() throws Exception {
        FunctionManager fm = currentProgram.getFunctionManager();
        ReferenceManager rm = currentProgram.getReferenceManager();
        int nf = 0, nbad = 0;
        try (PrintWriter fw = new PrintWriter(new File(outdir, "functions.tsv"));
             PrintWriter rw = new PrintWriter(new File(outdir, "rom_refs.tsv"));
             PrintWriter cw = new PrintWriter(new File(outdir, "const_refs.tsv"));
             PrintWriter bw = new PrintWriter(new File(outdir, "bodies.tsv"));
             PrintWriter xw = new PrintWriter(new File(outdir, "feature.tsv"))) {
            fw.println("entry\tmode\tsize\tmin\tmax\tname\tncallers\tcallers\tcallees");
            rw.println("insn\tfunc\tkind\tliteral_addr\tvalue\tmnemonic");
            cw.println("insn\tfunc\tliteral_addr\tvalue");
            bw.println("func\tstart\tend");
            xw.println("func\tn_insn\tldrb\tstrb\tstrh\tswi\tcmp_imm\tbl_targets\tconst_vram\tconst_io\tconst_iwram\tconst_ewram\tcomputed_jumps\tloops");
            for (Function f : fm.getFunctions(true)) {
                nf++;
                Address e = f.getEntryPoint();
                TreeSet<String> callers = new TreeSet<>(), callees = new TreeSet<>();
                for (Function c : f.getCallingFunctions(monitor)) callers.add(hx(c.getEntryPoint()));
                for (Function c : f.getCalledFunctions(monitor)) callees.add(hx(c.getEntryPoint()));
                AddressSetView body = f.getBody();
                fw.println(hx(e) + "\t" + mode(e) + "\t" + body.getNumAddresses() + "\t" + hx(body.getMinAddress()) + "\t"
                    + hx(body.getMaxAddress()) + "\t" + f.getName() + "\t" + callers.size() + "\t" + String.join(",", callers)
                    + "\t" + String.join(",", callees));
                for (AddressRange r : body) bw.println(hx(e) + "\t" + hx(r.getMinAddress()) + "\t" + hx(r.getMaxAddress()));
                int ni = 0, ldrb = 0, strb = 0, strh = 0, cj = 0, loops = 0;
                TreeSet<String> swi = new TreeSet<>(), cmps = new TreeSet<>(), bls = new TreeSet<>();
                int cv = 0, cio = 0, ciw = 0, cew = 0;
                for (Instruction ins : lst.getInstructions(body, true)) {
                    ni++;
                    String m = ins.getMnemonicString().toLowerCase();
                    if (m.startsWith("ldrb")) ldrb++;
                    if (m.startsWith("strb")) strb++;
                    if (m.startsWith("strh")) strh++;
                    if (m.startsWith("swi") || m.startsWith("svc")) {
                        Scalar s = ins.getScalar(0); if (s != null) swi.add(String.format("%X", s.getUnsignedValue()));
                    }
                    if (m.startsWith("cmp")) {
                        for (int k = 0; k < ins.getNumOperands(); k++) {
                            Scalar s = ins.getScalar(k);
                            if (s != null) cmps.add(String.format("%X", s.getUnsignedValue()));
                        }
                    }
                    FlowType ft = ins.getFlowType();
                    if (ft.isComputed() && ft.isJump()) cj++;
                    for (Reference ref : ins.getReferencesFrom()) {
                        Address to = ref.getToAddress();
                        if (ref.getReferenceType().isCall()) bls.add(hx(to));
                        if (ft.isJump() && !ft.isComputed() && to.compareTo(ins.getAddress()) < 0 && body.contains(to)) loops++;
                        if (ref.getReferenceType().isRead() && m.startsWith("ldr") && to.getAddressSpace().equals(e.getAddressSpace().getPhysicalSpace())
                            && to.getOffset() >= ROM0 && to.getOffset() <= ROM1 && (to.getOffset() & 3) == 0 && mem.contains(to)) {
                            // pc-relative literal load: target within the LDR-PC window ahead of the insn
                            long dlt = to.getOffset() - ins.getAddress().getOffset();
                            boolean pcrel = dlt > 0 && dlt <= 4096 + 8 && lst.getInstructionAt(to) == null;
                            if (!pcrel) continue;
                            long v;
                            try { v = mem.getInt(to) & 0xffffffffL; } catch (Exception ex) { continue; }
                            cw.println(hx(ins.getAddress()) + "\t" + hx(e) + "\t" + hx(to) + "\t" + String.format("%08X", v));
                            if (v >= ROM0 && v <= ROM1)
                                rw.println(hx(ins.getAddress()) + "\t" + hx(e) + "\tliteral\t" + hx(to) + "\t" + String.format("%08X", v) + "\t" + m);
                            if (v >= 0x06000000L && v < 0x06018000L) cv++;
                            if (v >= 0x04000000L && v < 0x04000400L) cio++;
                            if (v >= 0x03000000L && v < 0x03008000L) ciw++;
                            if (v >= 0x02000000L && v < 0x02040000L) cew++;
                        } else if (!ref.getReferenceType().isCall() && !ref.getReferenceType().isFlow()
                                   && to.getOffset() >= ROM0 && to.getOffset() <= ROM1 && !m.startsWith("ldr")) {
                            rw.println(hx(ins.getAddress()) + "\t" + hx(e) + "\tdirect\t-\t" + hx(to) + "\t" + m);
                        }
                    }
                }
                xw.println(hx(e) + "\t" + ni + "\t" + ldrb + "\t" + strb + "\t" + strh + "\t" + String.join(",", swi) + "\t"
                    + String.join(",", cmps) + "\t" + String.join(",", bls) + "\t" + cv + "\t" + cio + "\t" + ciw + "\t" + cew + "\t" + cj + "\t" + loops);
            }
        }
        // bad-instruction bookmarks (disassembly errors) = data-as-code signal
        try (PrintWriter pw = new PrintWriter(new File(outdir, "disasm_errors.tsv"))) {
            pw.println("addr\tcategory\tcomment");
            Iterator<Bookmark> it = currentProgram.getBookmarkManager().getBookmarksIterator(BookmarkType.ERROR);
            while (it.hasNext()) { Bookmark b = it.next(); nbad++; pw.println(hx(b.getAddress()) + "\t" + b.getCategory() + "\t" + b.getComment().replace('\t',' ')); }
        }
        // code ranges (instructions) for classification of raw words
        try (PrintWriter pw = new PrintWriter(new File(outdir, "code_ranges.tsv"))) {
            pw.println("start\tend\tmode");
            Address s = null, last = null; String ms = null;
            for (Instruction ins : lst.getInstructions(true)) {
                Address a = ins.getAddress(); String mm = mode(a);
                if (s != null && last != null && a.getAddressSpace().equals(last.getAddressSpace())
                    && a.getOffset() == last.getOffset() + 1 && mm.equals(ms)) { last = ins.getMaxAddress(); continue; }
                if (s != null) pw.println(hx(s) + "\t" + hx(last) + "\t" + ms);
                s = a; last = ins.getMaxAddress(); ms = mm;
            }
            if (s != null) pw.println(hx(s) + "\t" + hx(last) + "\t" + ms);
        }
        // switch tables: computed jumps + decompiler-recovered tables with case values
        int nsw = 0, nswf = 0;
        DecompInterface di = new DecompInterface();
        DecompileOptions o = new DecompileOptions(); o.grabFromProgram(currentProgram);
        di.setOptions(o); di.toggleCCode(false); di.toggleSyntaxTree(true); di.setSimplificationStyle("decompile");
        di.openProgram(currentProgram);
        try (PrintWriter pw = new PrintWriter(new File(outdir, "switches.tsv"))) {
            pw.println("func\tswitch_insn\tncases\tcases(value:target)");
            for (Function f : fm.getFunctions(true)) {
                boolean has = false;
                for (Instruction ins : lst.getInstructions(f.getBody(), true)) {
                    FlowType ft = ins.getFlowType();
                    if (ft.isComputed() && ft.isJump()) { has = true; break; }
                }
                if (!has) continue;
                nswf++;
                DecompileResults r = di.decompileFunction(f, 60, monitor);
                if (r == null || r.getHighFunction() == null) { pw.println(hx(f.getEntryPoint()) + "\t-\t-1\tDECOMPILE_FAILED"); continue; }
                JumpTable[] jts = r.getHighFunction().getJumpTables();
                if (jts.length == 0) pw.println(hx(f.getEntryPoint()) + "\t-\t0\tUNRESOLVED");
                for (JumpTable jt : jts) {
                    nsw++;
                    Address[] cs = jt.getCases(); Integer[] lv = jt.getLabelValues();
                    StringBuilder sb = new StringBuilder();
                    for (int i = 0; i < cs.length; i++) {
                        if (sb.length() > 0) sb.append(',');
                        sb.append(lv != null && i < lv.length ? String.format("%X", lv[i]) : "?").append(':').append(hx(cs[i]));
                    }
                    pw.println(hx(f.getEntryPoint()) + "\t" + hx(jt.getSwitchAddress()) + "\t" + cs.length + "\t" + sb);
                }
            }
        }
        di.dispose();
        d("export: functions=" + nf + " disasm_errors=" + nbad + " funcs_with_computed_jump=" + nswf + " jumptables=" + nsw);
    }
}
