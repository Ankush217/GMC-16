# GMC-16 Console Architecture — Complete Technical Reference
### Version 7 | Game Machine CPU — 16-Bit

---

## Table of Contents

1. [Overview & Architecture Philosophy](#1-overview--architecture-philosophy)
2. [Memory Map](#2-memory-map)
3. [CPU Registers & Flags](#3-cpu-registers--flags)
4. [Instruction Set Architecture (ISA)](#4-instruction-set-architecture-isa)
   - 4.1 [Instruction Encoding](#41-instruction-encoding)
   - 4.2 [Data Movement](#42-data-movement)
   - 4.3 [Arithmetic](#43-arithmetic)
   - 4.4 [Bitwise & Shift](#44-bitwise--shift)
   - 4.5 [Comparison & Branching](#45-comparison--branching)
   - 4.6 [Stack & Subroutines](#46-stack--subroutines)
   - 4.7 [Sprite Control](#47-sprite-control)
   - 4.8 [Tile Engine](#48-tile-engine)
   - 4.9 [Direct Draw](#49-direct-draw)
   - 4.10 [Collision Detection](#410-collision-detection)
   - 4.11 [Input](#411-input)
   - 4.12 [Timing & Synchronization](#412-timing--synchronization)
   - 4.13 [Bankswitching](#413-bankswitching)
   - 4.14 [VRAM Access](#414-vram-access)
   - 4.15 [Audio RAM Access](#415-audio-ram-access)
   - 4.16 [Interrupt Control](#416-interrupt-control)
   - 4.17 [Miscellaneous](#417-miscellaneous)
5. [Cycle Timing Table](#5-cycle-timing-table)
6. [GPU — Graphics Processing Unit](#6-gpu--graphics-processing-unit)
   - 6.1 [GPU Command Register](#61-gpu-command-register)
   - 6.2 [Framebuffer](#62-framebuffer)
   - 6.3 [VRAM Layout](#63-vram-layout)
   - 6.4 [Tile Engine](#64-tile-engine)
   - 6.5 [Sprite System](#65-sprite-system)
   - 6.6 [Direct Draw Operations](#66-direct-draw-operations)
   - 6.7 [Collision Detection](#67-collision-detection)
   - 6.8 [Rendering Pipeline](#68-rendering-pipeline)
7. [APU — Audio Processing Unit](#7-apu--audio-processing-unit)
   - 7.1 [Channels](#71-channels)
   - 7.2 [Waveforms](#72-waveforms)
   - 7.3 [Audio RAM](#73-audio-ram)
   - 7.4 [APU IO Registers](#74-apu-io-registers)
   - 7.5 [APU Commands](#75-apu-commands)
   - 7.6 [PCM Playback](#76-pcm-playback)
8. [Interrupt System](#8-interrupt-system)
   - 8.1 [Interrupt Sources](#81-interrupt-sources)
   - 8.2 [Interrupt Vector Table (IVT)](#82-interrupt-vector-table-ivt)
   - 8.3 [IE and IF Registers](#83-ie-and-if-registers)
   - 8.4 [Interrupt Dispatch Flow](#84-interrupt-dispatch-flow)
   - 8.5 [Writing Interrupt Handlers](#85-writing-interrupt-handlers)
9. [Bankswitching System](#9-bankswitching-system)
   - 9.1 [Bank Layout](#91-bank-layout)
   - 9.2 [Switching Banks at Runtime](#92-switching-banks-at-runtime)
   - 9.3 [Assembler BANK Directive](#93-assembler-bank-directive)
10. [Hardware IO Registers](#10-hardware-io-registers)
11. [Framebuffer Renderer API](#11-framebuffer-renderer-api)
    - 11.1 [NullRenderer](#111-nullrenderer)
    - 11.2 [CallbackRenderer](#112-callbackrenderer)
    - 11.3 [PygameRenderer](#113-pygamerenderer)
    - 11.4 [Custom Renderers](#114-custom-renderers)
    - 11.5 [RGB565 Color Format](#115-rgb565-color-format)
12. [Assembler](#12-assembler)
    - 12.1 [Syntax Reference](#121-syntax-reference)
    - 12.2 [Labels & Constants (EQU)](#122-labels--constants-equ)
    - 12.3 [Expression Evaluator](#123-expression-evaluator)
    - 12.4 [Mixed Register/Immediate Encoding](#124-mixed-registerimmediate-encoding)
    - 12.5 [Built-in Constants](#125-built-in-constants)
    - 12.6 [BANK Directive](#126-bank-directive)
    - 12.7 [Two-Pass Assembly](#127-two-pass-assembly)
    - 12.8 [BankImage Output](#128-bankimage-output)
13. [Python Host API](#13-python-host-api)
    - 13.1 [GMC16CPU](#131-gmc16cpu)
    - 13.2 [MemoryBus](#132-memorybus)
    - 13.3 [GPU](#133-gpu)
    - 13.4 [APU](#134-apu)
14. [Complete Opcode Reference Table](#14-complete-opcode-reference-table)
15. [IO Register Map](#15-io-register-map)
16. [Programming Guide & Examples](#16-programming-guide--examples)
    - 16.1 [Hello World — Drawing to Screen](#161-hello-world--drawing-to-screen)
    - 16.2 [Sprite Animation Loop](#162-sprite-animation-loop)
    - 16.3 [Input Handling](#163-input-handling)
    - 16.4 [Tilemap Rendering](#164-tilemap-rendering)
    - 16.5 [Playing Sound](#165-playing-sound)
    - 16.6 [Interrupt-Driven Timer](#166-interrupt-driven-timer)
    - 16.7 [Multi-Bank Cartridge](#167-multi-bank-cartridge)
    - 16.8 [PCM Audio Playback](#168-pcm-audio-playback)
    - 16.9 [Collision Detection Game Loop](#169-collision-detection-game-loop)
17. [Version History & Changelog](#17-version-history--changelog)
18. [Appendix A — Flag Behavior Per Instruction](#appendix-a--flag-behavior-per-instruction)
19. [Appendix B — Sprite Flags Bitmask](#appendix-b--sprite-flags-bitmask)
20. [Appendix C — Controller Bitmask](#appendix-c--controller-bitmask)
21. [Appendix D — RGB565 Common Colors](#appendix-d--rgb565-common-colors)
22. [Appendix E — Error Reference](#appendix-e--error-reference)

---

## 1. Overview & Architecture Philosophy

The GMC-16 ("Game Machine CPU — 16-Bit") is a fictional retro game console architecture implemented as a Python emulator. It is designed in the spirit of late-1980s and early-1990s home consoles — think a hypothetical mashup between a Game Boy, a Sega Master System, and a simplified 65816 — but with a clean, regular ISA that makes it easy to both program in assembly and to extend via Python.

### Key Specifications

| Property | Value |
|---|---|
| Word Size | 16-bit |
| General Registers | 8 (R0–R7) |
| Program Counter | 16-bit (PC) |
| Stack Pointer | 16-bit (SP) |
| Flag Register | 4-bit (Z, C, N, O) |
| Total Address Space | 64 KB (0x0000–0xFFFF) |
| RAM | 8 KB (0x0000–0x1FFF) |
| ROM | 57 KB (0x2000–0xFEFF), bankswitchable |
| IO Space | 256 bytes (0xFF00–0xFFFF) |
| VRAM | 64 KB (separate address space) |
| Screen Resolution | 256 × 128 pixels |
| Color Depth | 16-bit RGB565 |
| Sprites | 256 hardware sprites, 16×16 px each |
| Tilemap | 32×16 tiles (each tile 8×8 px) |
| Max Tiles | 256 |
| APU Channels | 4 (square, sine, triangle, sawtooth, noise, PCM) |
| Audio Sample Rate | 22,050 Hz |
| Audio RAM | 8 KB (4,096 × 16-bit samples) |
| Interrupt Sources | 8 (VBLANK, TIMER, INPUT, APU, IRQ0–IRQ3) |
| Max Cartridge Size | >1 MB (8 KB fixed + 22 × 48 KB banks) |

### Design Principles

The GMC-16 architecture is built around several core ideas:

**Regularity.** All general-purpose registers (R0–R7) are interchangeable. There are no special-purpose registers like accumulators that restrict which register an instruction can use. Any register can be a source or destination in any instruction.

**Simplicity.** The ISA avoids instruction encoding complexity. Most instructions are either one word (opcode + two register nibbles) or a word followed by immediate operand words. There are no variable-length compressed encodings, prefix bytes, or addressing mode combinatorics.

**Expressiveness for games.** Unlike minimal teaching CPUs, the GMC-16 includes native hardware support for sprites, tiles, scrolling, collision detection, input, and audio at the instruction level. Writing a game does not require complex software layers — you call `SPRITEPOS`, `SPRITEENABLE`, `WAITVBLANK`, and so on directly.

**Python extensibility.** The entire architecture is implemented in a single Python file. Every subsystem (CPU, GPU, APU, MemoryBus) is a normal Python object. The host program can inspect and modify any state directly, load ROM data from Python `bytes`, attach a custom renderer, intercept memory accesses, and so on.

---

## 2. Memory Map

The GMC-16 has a unified 16-bit address space (64 KB total). It is divided into four non-overlapping regions:

```
0x0000 ─────────────────────────────────── RAM START
         RAM  (8 192 bytes, read/write)
0x1FFF ─────────────────────────────────── RAM END

0x2000 ─────────────────────────────────── ROM START / FIXED BANK START
         FIXED BANK  (8 192 bytes, always bank 0)
         Contains the IVT at the very top: 0x3FF0–0x3FFF
0x3FFF ─────────────────────────────────── FIXED BANK END

0x4000 ─────────────────────────────────── BANKED WINDOW START
         BANKED WINDOW  (~49 152 bytes)
         One of 22 switchable banks visible at a time
         Controlled by writing to REG_BANK (0xFF30)
         or using SETBANK instruction
0xFEFF ─────────────────────────────────── BANKED WINDOW END / ROM END

0xFF00 ─────────────────────────────────── IO START
         Memory-Mapped IO Registers  (256 bytes)
         GPU, APU, Collision, VRAM DMA, Interrupts, Bank, Controller
0xFFFF ─────────────────────────────────── IO END
```

### Defined Constants

```python
RAM_START  = 0x0000    RAM_END  = 0x1FFF    RAM_SIZE  = 8192
ROM_START  = 0x2000    ROM_END  = 0xFEFF    ROM_SIZE  = 57088
IO_START   = 0xFF00    IO_END   = 0xFFFF    IO_SIZE   = 256
```

### Access Rules

| Region | CPU Read | CPU Write | Notes |
|---|---|---|---|
| RAM | ✅ | ✅ | Full read/write |
| Fixed ROM | ✅ | ❌ (silently ignored) | Always bank 0 |
| Banked ROM | ✅ | ❌ (silently ignored) | One of 22 banks |
| IO | ✅ | ✅ | Side-effecting |

Writes to ROM addresses are silently discarded — no exception is raised. This matches real hardware behavior where the cartridge ROM is not writable.

### Stack

The hardware stack lives in RAM. The stack pointer (SP) is initialized to `RAM_END - 1 = 0x1FFE` and grows downward. PUSH decrements SP by 2, writes a 16-bit word; POP reads and increments SP by 2. The stack can hold at most ~4096 16-bit values before colliding with code or data at the bottom of RAM.

### VRAM

VRAM is a **separate** 64 KB address space, not mapped into the main 16-bit address space. It cannot be read or written by LOAD/STORE. Access is through the dedicated `VRAMWR` and `VRAMRD` CPU instructions, or via the VRAM DMA IO registers (0xFF40–0xFF43). See [Section 6.3](#63-vram-layout) for the VRAM layout.

---

## 3. CPU Registers & Flags

### General Purpose Registers

The GMC-16 has eight 16-bit general-purpose registers: **R0 through R7**. All are interchangeable. There is no designated accumulator, index register, or base register — any register can appear in any position in any instruction.

```
R0   0x0000   16-bit, general purpose
R1   0x0000   16-bit, general purpose
R2   0x0000   16-bit, general purpose
R3   0x0000   16-bit, general purpose
R4   0x0000   16-bit, general purpose
R5   0x0000   16-bit, general purpose
R6   0x0000   16-bit, general purpose
R7   0x0000   16-bit, general purpose
```

All registers reset to 0 on `cpu.reset()`.

Values are always unsigned 16-bit (0x0000–0xFFFF) when stored. Arithmetic that produces values outside this range wraps via `& 0xFFFF`. Signed arithmetic (NEG, CMP with N flag, etc.) uses two's-complement interpretation.

### Special Registers

| Register | Width | Initial Value | Description |
|---|---|---|---|
| PC | 16-bit | `ROM_START` (0x2000) | Program Counter — address of next instruction word |
| SP | 16-bit | `RAM_END - 1` (0x1FFE) | Stack Pointer — grows downward through RAM |
| FL | 4-bit | 0 | Flags register |

### Flags Register (FL)

The flag register is a 4-bit value. Individual bits are set or cleared by arithmetic and comparison instructions.

| Bit | Mask | Name | Meaning |
|---|---|---|---|
| 0 | `0b0001` | **Z** (Zero) | Set when the result is zero |
| 1 | `0b0010` | **C** (Carry) | Set on unsigned overflow/underflow/carry out |
| 2 | `0b0100` | **N** (Negative) | Set when bit 15 of the result is 1 (two's-complement negative) |
| 3 | `0b1000` | **O** (Overflow) | Set on signed two's-complement overflow (ADD only) |

Not all instructions update all flags. See [Appendix A](#appendix-a--flag-behavior-per-instruction) for per-instruction flag behavior.

Flags are preserved across CALL/RET. They are saved (pushed) and restored (popped) by the interrupt system during RETI.

---

## 4. Instruction Set Architecture (ISA)

### 4.1 Instruction Encoding

Every GMC-16 instruction starts with a **16-bit instruction word**:

```
Bits 15–8   Opcode        (8 bits)
Bits  7–4   Ra            (4-bit register index, 0–7; upper nibble of lower byte)
Bits  3–0   Rb            (4-bit register index, 0–7; lower nibble)
```

Most instructions are encoded in a single 16-bit word. Instructions that require immediate operands fetch additional 16-bit words from the instruction stream in sequence after the instruction word. The PC advances by 2 bytes for each word consumed.

Example: `LOADI R3, 0x00FF`
- Word 0: `0x05 << 8 | 3 << 4 | 0` = `0x0530` (opcode=LOADI, ra=3)
- Word 1: `0x00FF` (immediate value)

The Rb nibble is unused (zero) in single-register and no-register instructions, but must still be present in the word.

#### Mixed Register/Immediate Encoding

Several instructions (PIXEL, LINE, RECT, SPRITEPOS, SPRITEMOVE, SPRITEIMG, SETTILE, VRAMWR, VRAMRD, PCMWR, PCMRD) use a special **mixed** encoding that allows each operand to be either a register or an immediate. After the instruction word, a **reg_flags** word is emitted, then one word per argument:

```
[instruction word]
[reg_flags word]      bit i = 1 means arg i is a register index, 0 means immediate
[arg0 word]           register index (0–7) OR signed 16-bit immediate
[arg1 word]
...
```

This allows expressions like `PIXEL R0, R1, 0xFF00` (x from R0, y from R1, color literal) without sacrificing either flexibility or regularity.

---

### 4.2 Data Movement

#### NOP — No Operation
```
Opcode: 0x00
Format: NOP
Cycles: 1
Flags:  None
```
Does nothing. Advances PC by 2. Useful for timing padding or placeholder slots.

---

#### HALT — Halt CPU
```
Opcode: 0x01
Format: HALT
Cycles: 1
Flags:  None
```
Sets `cpu.halted = True`. The CPU stops fetching and executing instructions. `cpu.run()` returns. `cpu.step()` is a no-op when halted. The machine can be resumed by calling `cpu.reset()` followed by `cpu.run()`.

---

#### MOV — Move Register to Register
```
Opcode: 0x02
Format: MOV Rd, Rs
Cycles: 1
Flags:  Z, N
```
Copies the value of Rs into Rd. Updates Z and N based on the copied value. Does not modify Rs.

```asm
MOV R0, R3       ; R0 = R3
```

---

#### LOAD — Load from Memory
```
Opcode: 0x03
Format: LOAD Rd, [Rs]
Cycles: 2
Flags:  Z, N
```
Reads a 16-bit little-endian word from the memory address in Rs and stores it in Rd. The address in Rs is not modified. Updates Z and N based on the loaded value.

```asm
LOADI R1, 0x0010    ; R1 = address 0x0010
LOAD  R0, R1        ; R0 = mem16[0x0010]
```

Memory reads crossing region boundaries (e.g., 0xFEFF/0xFF00) read each byte independently through the normal bus logic.

---

#### STORE — Store to Memory
```
Opcode: 0x04
Format: STORE Ra, [Rb]
Cycles: 2
Flags:  None
```
Writes the 16-bit value in Ra to memory address Rb (little-endian, two bytes). Writes to ROM addresses are silently discarded. Writes to IO addresses may trigger hardware side effects.

```asm
LOADI R0, 0xABCD
LOADI R1, 0x0020
STORE R0, R1         ; mem16[0x0020] = 0xABCD
```

---

#### LOADI — Load Immediate
```
Opcode: 0x05
Format: LOADI Rd, imm16
Cycles: 2
Flags:  Z, N
```
Loads a 16-bit immediate constant into Rd. The constant is the next word in the instruction stream. Updates Z and N based on the value.

```asm
LOADI R0, 42
LOADI R1, 0xFF00
LOADI R2, SCREEN_W      ; built-in constant
LOADI R3, MY_LABEL      ; forward references allowed
LOADI R4, (10 * 4) - 2  ; expression evaluated at assembly time
```

---

#### SWAP — Swap Two Registers
```
Opcode: 0x06
Format: SWAP Ra, Rb
Cycles: 1
Flags:  None
```
Atomically exchanges the values of Ra and Rb in a single cycle. No temporary register needed.

```asm
LOADI R0, 100
LOADI R1, 200
SWAP  R0, R1      ; now R0=200, R1=100
```

---

### 4.3 Arithmetic

#### ADD — Add
```
Opcode: 0x07
Format: ADD Rd, Rs
Cycles: 1
Flags:  Z, C, N, O
```
Adds Rs to Rd, stores result in Rd. Result is masked to 16 bits (`& 0xFFFF`).

- **C** is set if the 17-bit result exceeds 0xFFFF (unsigned carry out).
- **O** is set if both operands have the same sign and the result's sign differs (signed overflow).
- **Z** is set if the 16-bit result is zero.
- **N** is set if bit 15 of the result is 1.

```asm
LOADI R0, 0xFFFE
LOADI R1, 0x0003
ADD   R0, R1       ; R0=0x0001, C=1 (carry), O=0
```

---

#### SUB — Subtract
```
Opcode: 0x08
Format: SUB Rd, Rs
Cycles: 1
Flags:  Z, C, N
```
Subtracts Rs from Rd, stores result in Rd (masked to 16 bits).

- **C** is set if the mathematical result is negative (borrow occurred; `Rd < Rs` unsigned).
- **N** is set if bit 15 of the result is 1.
- **Z** is set if the result is zero.

Note: O (overflow) is **not** updated by SUB.

```asm
LOADI R0, 10
LOADI R1, 15
SUB   R0, R1   ; R0 = 0xFFFB (wraps), C=1 (borrow), N=1
```

---

#### MUL — Multiply
```
Opcode: 0x09
Format: MUL Rd, Rs
Cycles: 3
Flags:  Z, C, N
```
Multiplies Rd by Rs. The lower 16 bits of the product are stored in Rd. C is set if the full product exceeded 0xFFFF (upper bits were lost).

```asm
LOADI R0, 300
LOADI R1, 200
MUL   R0, R1    ; R0 = (300*200) & 0xFFFF = 60000 = 0xEA60, C=0
```

---

#### DIV — Divide
```
Opcode: 0x0A
Format: DIV Rd, Rs
Cycles: 6
Flags:  Z, N
```
Integer divides Rd by Rs, result stored in Rd (floor division, truncated toward zero since values are unsigned). If Rs is zero, result is forced to `0xFFFF` (all-ones sentinel). Remainder is discarded.

```asm
LOADI R0, 100
LOADI R1, 7
DIV   R0, R1    ; R0 = 14 (100 // 7)
```

---

#### INC — Increment
```
Opcode: 0x0B
Format: INC Rd
Cycles: 1
Flags:  Z, N
```
Adds 1 to Rd, wrapping at 0xFFFF → 0x0000. Updates Z and N.

---

#### DEC — Decrement
```
Opcode: 0x0C
Format: DEC Rd
Cycles: 1
Flags:  Z, N
```
Subtracts 1 from Rd, wrapping at 0x0000 → 0xFFFF. Updates Z and N.

---

#### NEG — Negate (Two's Complement)
```
Opcode: 0x0D
Format: NEG Rd
Cycles: 1
Flags:  Z, N
```
Replaces Rd with its two's-complement negation: `Rd = (-Rd) & 0xFFFF`. NEG of 0 is 0 (Z=1). NEG of 0x8000 is 0x8000 (no change, the only self-inverse value).

---

#### ABS — Absolute Value
```
Opcode: 0x0E
Format: ABS Rd
Cycles: 1
Flags:  Z, N
```
If bit 15 of Rd is set (value is negative in two's-complement), negates Rd. Otherwise leaves Rd unchanged. Result is always non-negative.

```asm
LOADI R0, 0xFF00   ; = -256 signed
ABS   R0           ; R0 = 256 = 0x0100
```

---

### 4.4 Bitwise & Shift

#### AND — Bitwise AND
```
Opcode: 0x0F
Format: AND Rd, Rs
Cycles: 1
Flags:  Z, N
```
Bitwise AND of Rd and Rs, stored in Rd. Commonly used for masking bits.

```asm
LOADI R0, 0xFF3C
LOADI R1, 0x00FF
AND   R0, R1     ; R0 = 0x003C  (keep lower byte only)
```

---

#### OR — Bitwise OR
```
Opcode: 0x10
Format: OR Rd, Rs
Cycles: 1
Flags:  Z, N
```
Bitwise OR of Rd and Rs, stored in Rd. Commonly used to set specific bits.

---

#### XOR — Bitwise XOR
```
Opcode: 0x11
Format: XOR Rd, Rs
Cycles: 1
Flags:  Z, N
```
Bitwise exclusive-OR of Rd and Rs, stored in Rd. Useful for toggling bits or simple encryption.

```asm
; Toggle a flag in a state register
LOADI R1, 0x0010      ; bit 4 mask
XOR   R0, R1          ; toggle bit 4 of R0
```

---

#### NOT — Bitwise NOT
```
Opcode: 0x12
Format: NOT Rd
Cycles: 1
Flags:  Z, N
```
Inverts all 16 bits of Rd: `Rd = (~Rd) & 0xFFFF`.

```asm
LOADI R0, 0x00FF
NOT   R0           ; R0 = 0xFF00
```

---

#### SHL — Shift Left
```
Opcode: 0x13
Format: SHL Rd
Cycles: 1
Flags:  Z, C, N
```
Shifts Rd left by 1 bit. The MSB (bit 15) is shifted into C. The LSB is filled with 0. Result stored in Rd. Equivalent to unsigned multiply-by-2.

```asm
LOADI R0, 0x4000   ; bit 14 set
SHL   R0           ; R0 = 0x8000, C=0 (old bit 15 was 0)
SHL   R0           ; R0 = 0x0000, C=1 (old bit 15 was 1), Z=1
```

---

#### SHR — Shift Right
```
Opcode: 0x14
Format: SHR Rd
Cycles: 1
Flags:  Z, C, N
```
Shifts Rd right by 1 bit. The LSB (bit 0) is shifted into C. The MSB is filled with 0 (logical shift, not arithmetic). Result stored in Rd. Equivalent to unsigned divide-by-2.

---

### 4.5 Comparison & Branching

#### CMP — Compare
```
Opcode: 0x15
Format: CMP Ra, Rb
Cycles: 1
Flags:  Z, N, C
```
Computes `Ra - Rb` and updates flags, but **does not** store the result. Used before conditional jump instructions.

- **Z** = 1 if Ra == Rb
- **N** = 1 if Ra < Rb (signed interpretation, bit 15 of difference is 1)
- **C** = 1 if Ra < Rb (unsigned borrow)

```asm
CMP  R0, R1
JZ   equal_label     ; jump if R0 == R1
JG   greater_label   ; jump if R0 > R1 (unsigned, no N, no Z)
JL   less_label      ; jump if R0 < R1 (N flag set)
```

---

#### JMP — Unconditional Jump
```
Opcode: 0x16
Format: JMP target
Cycles: 3
Flags:  None
```
Sets PC to the 16-bit immediate target address. The target is always the next word in the instruction stream after the opcode word.

```asm
JMP  main_loop      ; jump to label
JMP  0x2040         ; jump to absolute address
```

---

#### JZ — Jump if Zero
```
Opcode: 0x17
Format: JZ target
Cycles: 3 (taken) / 1 (not taken)
Flags:  None
```
Jumps to target if Z=1. If Z=0, PC advances past the target word (1 cycle).

```asm
CMP  R0, R1
JZ   are_equal
```

---

#### JNZ — Jump if Not Zero
```
Opcode: 0x18
Format: JNZ target
Cycles: 3 (taken) / 1 (not taken)
Flags:  None
```
Jumps to target if Z=0. Useful for loop counters.

```asm
LOADI R2, 10
loop:
    ; ... body ...
    DEC R2
    JNZ loop
```

---

#### JG — Jump if Greater
```
Opcode: 0x19
Format: JG target
Cycles: 3 (taken) / 1 (not taken)
Flags:  None
```
Jumps to target if `Z=0 AND N=0` — i.e., the result of the preceding CMP was neither equal nor negative. This tests for unsigned "greater than" when preceded by CMP.

---

#### JL — Jump if Less
```
Opcode: 0x1A
Format: JL target
Cycles: 3 (taken) / 1 (not taken)
Flags:  None
```
Jumps to target if `N=1` — the result of the preceding CMP was negative (Ra < Rb signed). For unsigned less-than, check C instead.

---

### 4.6 Stack & Subroutines

#### PUSH — Push to Stack
```
Opcode: 0x1B
Format: PUSH Ra
Cycles: 2
Flags:  None
```
Decrements SP by 2, then writes Ra to `mem16[SP]`. Grows downward through RAM.

```asm
PUSH R0    ; save R0
PUSH R1    ; save R1
```

---

#### POP — Pop from Stack
```
Opcode: 0x1C
Format: POP Rd
Cycles: 2
Flags:  Z, N
```
Reads a 16-bit word from `mem16[SP]`, stores in Rd, increments SP by 2. Updates Z and N.

```asm
POP  R1    ; restore R1
POP  R0    ; restore R0 (LIFO order — push R0, push R1, pop R1, pop R0)
```

---

#### CALL — Call Subroutine
```
Opcode: 0x1D
Format: CALL target
Cycles: 4
Flags:  None
```
Pushes the current PC (the address of the instruction after CALL) onto the stack, then jumps to target.

```asm
CALL my_function
; execution resumes here after RET
```

---

#### RET — Return from Subroutine
```
Opcode: 0x1E
Format: RET
Cycles: 4
Flags:  None
```
Pops the return address from the stack and jumps to it. Exactly undoes the CALL.

```asm
my_function:
    LOADI R0, 42
    RET
```

---

### 4.7 Sprite Control

The GMC-16 supports 256 hardware sprites. Each sprite is 16×16 pixels, composed of a 2×2 arrangement of 8×8 tiles from VRAM. Sprites have flags for visibility, flip-X, flip-Y, and priority. Color 0x0000 in a tile pixel is transparent.

#### SPRITEPOS — Set Sprite Position
```
Opcode: 0x20
Format: SPRITEPOS sid, x, y
Cycles: 5
Flags:  None
```
Sets sprite `sid` to screen position (x, y). `sid` is always an immediate integer (0–255). `x` and `y` may be registers or immediates (mixed encoding). Position 0,0 is top-left.

```asm
SPRITEPOS 0, 100, 50          ; sprite 0 at (100, 50)
SPRITEPOS 0, R0, R1           ; sprite 0 at (R0, R1)
SPRITEPOS 0, SCREEN_W/2, 10   ; using expressions
```

---

#### SPRITEMOVE — Move Sprite by Delta
```
Opcode: 0x21
Format: SPRITEMOVE sid, dx, dy
Cycles: 5
Flags:  None
```
Adds (dx, dy) to sprite `sid`'s current position. `sid` is always immediate. `dx` and `dy` may be registers (for per-frame velocity) or signed immediates.

```asm
SPRITEMOVE 0, R2, R3     ; move by velocity stored in R2, R3
SPRITEMOVE 1, 1, 0       ; nudge sprite 1 right by 1 pixel
SPRITEMOVE 2, -2, 0      ; nudge sprite 2 left (signed immediate)
```

---

#### SPRITEIMG — Set Sprite Tile Image
```
Opcode: 0x22
Format: SPRITEIMG sid, tile
Cycles: 5
Flags:  None
```
Sets the base tile index for sprite `sid`. Since sprites are 16×16 (2×2 tiles), the assembler loads four tiles starting at `tile` (tile, tile+1, tile+2, tile+3) arranged as:
```
[tile+0][tile+1]    top row
[tile+2][tile+3]    bottom row
```
`sid` is always an immediate. `tile` may be a register or immediate (mixed encoding).

```asm
SPRITEIMG 0, 4        ; sprite 0 uses tiles 4,5,6,7
SPRITEIMG 0, R5       ; tile from register (for animation frames)
```

---

#### SPRITEENABLE — Enable Sprite
```
Opcode: 0x23
Format: SPRITEENABLE sid
Cycles: 2
Flags:  None
```
Makes sprite `sid` visible (sets flags bit 0). The sprite will be rendered on the next DRAW_SPRITES command.

---

#### SPRITEDISABLE — Disable Sprite
```
Opcode: 0x24
Format: SPRITEDISABLE sid
Cycles: 2
Flags:  None
```
Hides sprite `sid` (clears flags bit 0). The sprite is excluded from rendering and collision detection.

---

### 4.8 Tile Engine

The tilemap is a 32×16 grid. Each cell holds an entry word: bits [7:0] = tile_id (which of 256 tiles to draw), bit [8] = flip-X, bit [9] = flip-Y. Tile pixel data lives in VRAM at address `VRAM_TILE_BASE + tile_id * 128`.

#### SETTILE — Set Tilemap Cell
```
Opcode: 0x25
Format: SETTILE col, row, entry
Cycles: 3
Flags:  None
```
Writes `entry` to tilemap cell (col, row). All three operands use mixed encoding (register or immediate). `entry` is a 16-bit value: `tile_id | (flipX << 8) | (flipY << 9)`.

```asm
SETTILE 5, 2, 0x0001     ; cell (5,2) = tile 1, no flip
SETTILE 0, 0, 0x0101     ; tile 1 with flip-X
SETTILE R0, R1, R2       ; all from registers
```

---

#### GETTILE — Read Tilemap Cell
```
Opcode: 0x26
Format: GETTILE Rd, col, row
Cycles: 3
Flags:  None
```
Reads the tilemap entry at (col, row) into Rd. `col` and `row` are immediates; `Rd` is a register.

```asm
GETTILE R0, 5, 2    ; R0 = tilemap entry at column 5, row 2
```

---

#### SCROLLX — Set Horizontal Scroll
```
Opcode: 0x27
Format: SCROLLX value
Cycles: 2
Flags:  None
```
Sets the GPU's scroll_x register to `value`. The tilemap is rendered with this horizontal pixel offset, wrapping seamlessly. The full scrollable map is 256 pixels wide.

```asm
SCROLLX 0       ; no scroll
SCROLLX R0      ; scroll from register
SCROLLX 128     ; scroll right by half the map width
```

---

#### SCROLLY — Set Vertical Scroll
```
Opcode: 0x28
Format: SCROLLY value
Cycles: 2
Flags:  None
```
Sets GPU's scroll_y register. The scrollable map is 128 pixels tall (fills the screen height exactly, so vertical scroll wraps cleanly only at multiples of the screen height).

---

### 4.9 Direct Draw

These instructions draw directly into the GPU's back-framebuffer. They bypass the tile and sprite systems.

#### CLS — Clear Screen
```
Opcode: 0x29
Format: CLS color
Cycles: 8
Flags:  None
```
Fills the entire back-framebuffer with `color` (RGB565). This is equivalent to the GPU command `CLEAR`, but executed directly through the CPU instruction stream. Use before drawing each frame.

```asm
CLS 0x0000     ; clear to black
CLS 0xF800     ; clear to red
CLS R0         ; clear to color in R0
```

---

#### PIXEL — Draw Pixel
```
Opcode: 0x2A
Format: PIXEL x, y, color
Cycles: 4
Flags:  None
```
Draws a single pixel at (x, y) with RGB565 color. All arguments use mixed encoding. Pixels outside 0–255 (x) or 0–127 (y) are silently clipped.

```asm
PIXEL 128, 64, 0xFFFF    ; white pixel at center
PIXEL R0, R1, 0xF800     ; position from registers
PIXEL R0, R1, R2         ; all from registers
```

---

#### LINE — Draw Line
```
Opcode: 0x2B
Format: LINE x1, y1, x2, y2, color
Cycles: 8
Flags:  None
```
Draws a straight line using Bresenham's line algorithm. All five arguments use mixed encoding.

```asm
LINE 0, 0, 255, 127, 0xFFFF     ; diagonal across screen
LINE R0, R1, R2, R3, 0x07E0     ; endpoints from registers
```

---

#### RECT — Draw Filled Rectangle
```
Opcode: 0x2C
Format: RECT x, y, w, h, color
Cycles: 8
Flags:  None
```
Draws a filled rectangle. (x, y) is the top-left corner, (w, h) is width and height. All five arguments use mixed encoding. Pixels outside the screen bounds are clipped.

```asm
RECT 10, 10, 50, 30, 0x001F    ; blue filled rectangle
RECT R0, R1, R2, R3, R4        ; all from registers
```

---

### 4.10 Collision Detection

The GMC-16 has a hardware collision detection unit that tests all enabled sprites pairwise using axis-aligned bounding boxes (16×16 pixels each). Results are stored in IO registers.

#### COLCHECK — Check Collisions
```
Opcode: 0x2D
Format: COLCHECK Rd
Cycles: 5
Flags:  Z, N
```
Runs collision detection across all visible sprites with non-zero collision types. Stores 1 in Rd (and REG_COLLISION_FLAG) if any collision was detected, 0 otherwise. Also stores the indices of the first colliding pair in REG_COLLISION_SPR_A and REG_COLLISION_SPR_B. Updates Z and N on Rd.

```asm
COLCHECK R0
JZ  no_collision
; handle collision
COLSPR1 R1    ; R1 = index of sprite A
COLSPR2 R2    ; R2 = index of sprite B
no_collision:
```

---

#### COLSPR1 — Get First Colliding Sprite
```
Opcode: 0x2E
Format: COLSPR1 Rd
Cycles: 1
Flags:  None
```
Loads the index of the first sprite in the most recently detected collision into Rd. Only valid after a COLCHECK that found a collision.

---

#### COLSPR2 — Get Second Colliding Sprite
```
Opcode: 0x2F
Format: COLSPR2 Rd
Cycles: 1
Flags:  None
```
Loads the index of the second sprite in the most recently detected collision into Rd.

---

### 4.11 Input

#### INPUT — Read Full Controller State
```
Opcode: 0x30
Format: INPUT Rd
Cycles: 1
Flags:  None
```
Reads the full 8-bit controller state byte into Rd (upper 8 bits are zero). Each bit corresponds to a button. See [Appendix C](#appendix-c--controller-bitmask).

```asm
INPUT R0
LOADI R1, 0x01      ; UP button mask
AND   R0, R1
JNZ   moving_up
```

---

#### BUTTON — Test Specific Buttons
```
Opcode: 0x31
Format: BUTTON Rd, mask
Cycles: 1
Flags:  Z, N
```
ANDs the controller state with the immediate `mask` and stores the result in Rd. Z is set if no masked buttons are pressed. More efficient than INPUT + AND when checking specific buttons.

```asm
BUTTON R0, 0x10     ; test A button (bit 4)
JNZ    a_pressed
```

---

### 4.12 Timing & Synchronization

#### WAITVBLANK — Wait for Vertical Blank
```
Opcode: 0x32
Format: WAITVBLANK
Cycles: 1
Flags:  None
```
Sleeps until the next 60 Hz frame deadline using a drift-free absolute timer. This is the primary frame-synchronization mechanism. Call once per game loop iteration to lock frame rate to 60 FPS.

The implementation uses `time.monotonic()` and an absolute target time that advances by `1/60` seconds each call. If the CPU falls behind, the target resets to prevent chasing a backlog (the console drops frames rather than accumulating lag).

```asm
game_loop:
    ; ... update and draw ...
    WAITVBLANK
    JMP game_loop
```

---

#### TIMER — Read System Timer
```
Opcode: 0x33
Format: TIMER Rd
Cycles: 1
Flags:  None
```
Reads the lower 16 bits of the current system time in milliseconds into Rd. Wraps at 0xFFFF (every ~65.5 seconds). Useful for measuring elapsed time, seeding random number generators, or animation timing.

```asm
TIMER R0     ; R0 = current time in ms (lower 16 bits)
```

---

### 4.13 Bankswitching

#### SETBANK — Switch ROM Bank
```
Opcode: 0x34
Format: SETBANK imm
Cycles: 2
Flags:  None
```
Switches the 48 KB banked window (0x4000–0xFEFF) to the specified bank number (0–21). The immediate is a 16-bit value, but only the lower 5 bits are meaningful. Also updates REG_BANK (0xFF30) to reflect the active bank.

```asm
SETBANK 0      ; switch to bank 0
SETBANK 5      ; switch to bank 5
```

Raises `CPUFault` if the bank number is out of range (0–21).

---

#### GETBANK — Read Current Bank
```
Opcode: 0x35
Format: GETBANK Rd
Cycles: 1
Flags:  None
```
Reads the currently active bank number into Rd.

```asm
GETBANK R0    ; R0 = current bank number (0–21)
```

---

### 4.14 VRAM Access

#### VRAMWR — Write to VRAM
```
Opcode: 0x36
Format: VRAMWR vaddr, value
Cycles: 3
Flags:  None
```
Writes a 16-bit `value` to VRAM address `vaddr`. Both arguments use mixed encoding (register or immediate). VRAM addresses are 16-bit (0x0000–0xFFFF). Writes 2 bytes (little-endian word).

```asm
VRAMWR 0x0000, 0xF800      ; write RED to VRAM[0]
VRAMWR R0, R1              ; address and value from registers
```

---

#### VRAMRD — Read from VRAM
```
Opcode: 0x37
Format: VRAMRD Rd, vaddr
Cycles: 3
Flags:  None
```
Reads a 16-bit word from VRAM address `vaddr` into Rd. The address uses mixed encoding.

```asm
VRAMRD R1, 0x4000     ; read tilemap entry at VRAM_MAP_BASE
VRAMRD R0, R2         ; address from register
```

---

### 4.15 Audio RAM Access

#### PCMWR — Write PCM Sample
```
Opcode: 0x38
Format: PCMWR addr, value
Cycles: 3
Flags:  None
```
Writes a 16-bit signed sample to audio RAM at word address `addr`. Both arguments use mixed encoding. Address 0 is the first sample, address 4095 is the last. The value is a signed 16-bit integer (−32768 to +32767 encoded as unsigned 0x0000–0xFFFF).

```asm
PCMWR 0, 0x7FFF      ; write maximum-amplitude sample at position 0
PCMWR R0, R1         ; address and sample from registers
```

---

#### PCMRD — Read PCM Sample
```
Opcode: 0x39
Format: PCMRD Rd, addr
Cycles: 3
Flags:  None
```
Reads a 16-bit sample from audio RAM at word address `addr` into Rd.

```asm
PCMRD R2, R0    ; read sample at address R0 into R2
```

---

### 4.16 Interrupt Control

#### SEI — Set Interrupt Enable (Master)
```
Opcode: 0x3A
Format: SEI
Cycles: 1
Flags:  None
```
Sets the IME (Interrupt Master Enable) flag to true. Interrupts will now be dispatched when pending in IF and enabled in IE.

```asm
SEI    ; enable interrupts globally
```

---

#### CLI — Clear Interrupt Enable (Master)
```
Opcode: 0x3B
Format: CLI
Cycles: 1
Flags:  None
```
Clears IME to false. All interrupt dispatch is suppressed regardless of IE/IF. Individual IE bits are not affected.

---

#### RETI — Return from Interrupt
```
Opcode: 0x3C
Format: RETI
Cycles: 4
Flags:  (restored from stack)
```
Returns from an interrupt handler. Pops the flags register (FL) first, then pops the return PC. Re-enables interrupts by setting IME = true.

Stack layout on interrupt entry (top of stack = lowest address):
```
[FL]    ← SP  (pushed second, on top)
[PC]    ← SP+2
```
RETI pops FL first (restoring flags exactly as they were before the interrupt), then pops PC.

---

#### TRIG — Software Trigger Interrupt
```
Opcode: 0x3D
Format: TRIG n
Cycles: 2
Flags:  None
```
Manually raises IRQ `n` (0–3), corresponding to interrupt sources IRQ0–IRQ3 (bits 4–7 in IF). Equivalent to `raise_interrupt(1 << (4 + n))`. Does not immediately dispatch; the interrupt will be processed at the end of the current step if IME and IE allow.

```asm
TRIG 0    ; raise IRQ0 (INT_IRQ0, bit 4 of IF)
TRIG 3    ; raise IRQ3 (INT_IRQ3, bit 7 of IF)
```

---

#### RAND — Random Number
```
Opcode: 0x1F
Format: RAND Rd
Cycles: 1
Flags:  None
```
Loads a random 16-bit unsigned integer (0x0000–0xFFFF) into Rd using Python's `random.randint`.

```asm
RAND R0       ; R0 = random value
```

---

### 4.17 Miscellaneous

The remaining "miscellaneous" instructions not categorized above are NOP (4.2) and HALT (4.2).

---

## 5. Cycle Timing Table

All instruction cycle counts. Branch cycles are for the taken case; not-taken costs 1 cycle.

| Opcode | Mnemonic | Cycles | Notes |
|---|---|---|---|
| 0x00 | NOP | 1 | |
| 0x01 | HALT | 1 | |
| 0x02 | MOV | 1 | |
| 0x03 | LOAD | 2 | memory read |
| 0x04 | STORE | 2 | memory write |
| 0x05 | LOADI | 2 | fetch imm |
| 0x06 | SWAP | 1 | |
| 0x07 | ADD | 1 | |
| 0x08 | SUB | 1 | |
| 0x09 | MUL | 3 | |
| 0x0A | DIV | 6 | |
| 0x0B | INC | 1 | |
| 0x0C | DEC | 1 | |
| 0x0D | NEG | 1 | |
| 0x0E | ABS | 1 | |
| 0x0F | AND | 1 | |
| 0x10 | OR | 1 | |
| 0x11 | XOR | 1 | |
| 0x12 | NOT | 1 | |
| 0x13 | SHL | 1 | |
| 0x14 | SHR | 1 | |
| 0x15 | CMP | 1 | |
| 0x16 | JMP | 3 | |
| 0x17 | JZ | 3 / 1 | taken / not-taken |
| 0x18 | JNZ | 3 / 1 | taken / not-taken |
| 0x19 | JG | 3 / 1 | taken / not-taken |
| 0x1A | JL | 3 / 1 | taken / not-taken |
| 0x1B | PUSH | 2 | |
| 0x1C | POP | 2 | |
| 0x1D | CALL | 4 | push + jump |
| 0x1E | RET | 4 | pop + jump |
| 0x1F | RAND | 1 | |
| 0x20 | SPRITEPOS | 5 | |
| 0x21 | SPRITEMOVE | 5 | |
| 0x22 | SPRITEIMG | 5 | |
| 0x23 | SPRITEENABLE | 2 | |
| 0x24 | SPRITEDISABLE | 2 | |
| 0x25 | SETTILE | 3 | |
| 0x26 | GETTILE | 3 | |
| 0x27 | SCROLLX | 2 | |
| 0x28 | SCROLLY | 2 | |
| 0x29 | CLS | 8 | fills 32,768 pixels |
| 0x2A | PIXEL | 4 | |
| 0x2B | LINE | 8 | Bresenham |
| 0x2C | RECT | 8 | |
| 0x2D | COLCHECK | 5 | O(n²) scan |
| 0x2E | COLSPR1 | 1 | |
| 0x2F | COLSPR2 | 1 | |
| 0x30 | INPUT | 1 | |
| 0x31 | BUTTON | 1 | |
| 0x32 | WAITVBLANK | 1 | (sleep not counted) |
| 0x33 | TIMER | 1 | |
| 0x34 | SETBANK | 2 | |
| 0x35 | GETBANK | 1 | |
| 0x36 | VRAMWR | 3 | |
| 0x37 | VRAMRD | 3 | |
| 0x38 | PCMWR | 3 | |
| 0x39 | PCMRD | 3 | |
| 0x3A | SEI | 1 | |
| 0x3B | CLI | 1 | |
| 0x3C | RETI | 4 | pop FL + pop PC |
| 0x3D | TRIG | 2 | |

---

## 6. GPU — Graphics Processing Unit

The GPU manages all visual output. It maintains two framebuffers (front and back), the VRAM containing tile pixel data and the tilemap, and a list of 256 sprites.

### 6.1 GPU Command Register

Writing to `REG_GPU_COMMAND` (0xFF10) triggers a GPU operation immediately. The color operand is read from `REG_GPU_COLOR` (0xFF13) at command time.

| Command | Value | Description |
|---|---|---|
| `GpuCmd.CLEAR` | 0x01 | Fill back-buffer with REG_GPU_COLOR |
| `GpuCmd.DRAW_TILEMAP` | 0x04 | Render tilemap into back-buffer |
| `GpuCmd.DRAW_SPRITES` | 0x02 | Blit all visible sprites onto back-buffer |
| `GpuCmd.FLIP_BUFFER` | 0x03 | Swap front/back buffers, fire VBLANK IRQ |

**Typical frame sequence:**
```asm
; write 0x01 (CLEAR) to REG_GPU_COMMAND
; write 0x04 (DRAW_TILEMAP) to REG_GPU_COMMAND
; write 0x02 (DRAW_SPRITES) to REG_GPU_COMMAND
; write 0x03 (FLIP_BUFFER) to REG_GPU_COMMAND
WAITVBLANK
```

---

### 6.2 Framebuffer

The GMC-16 uses a double-buffering scheme:
- **Front buffer** — the currently displayed frame. Read-only from the CPU's perspective.
- **Back buffer** — the frame being drawn. All GPU draw commands target the back buffer.

When `FLIP_BUFFER` is issued, the two buffers swap (pointer swap, no copy), and the renderer's `render()` callback is invoked with the new front buffer. Then a VBLANK interrupt is raised.

Each buffer is a flat `list[int]` of `SCREEN_W * SCREEN_H = 32,768` RGB565 values in row-major order. Index `y * SCREEN_W + x` gives the pixel at (x, y).

Accessible from Python:
```python
pixels = cpu.gpu.framebuffer          # front buffer (latest completed frame)
back   = cpu.gpu.back_framebuffer     # back buffer (being drawn)
```

---

### 6.3 VRAM Layout

VRAM is a 64 KB address space separate from main RAM. Layout:

```
0x0000 ── VRAM_TILE_BASE
          Tile pixel data
          256 tiles × 8×8 pixels × 2 bytes (RGB565)
          = 256 × 128 = 32,768 bytes
          Tile N base address: 0x0000 + N × 128
          Pixels stored row-major, 2 bytes each (little-endian)
0x3FFF ── VRAM_TILE_END

0x4000 ── VRAM_MAP_BASE
          Tilemap
          32 columns × 16 rows × 2 bytes = 1,024 bytes
          Entry at (col, row): 0x4000 + (row × 32 + col) × 2
          Bits [7:0]  = tile index (0–255)
          Bit  [8]    = flip-X
          Bit  [9]    = flip-Y
0x47FF ── VRAM_MAP_END

0x4800 ── VRAM_USER_BASE
          Free for user use (sprite sheets, extra graphics data)
0xFFFF ── VRAM end
```

Defined constants:
```python
VRAM_TILE_BASE = 0x0000
VRAM_TILE_END  = 0x3FFF
VRAM_MAP_BASE  = 0x4000
VRAM_MAP_END   = 0x47FF
VRAM_USER_BASE = 0x4800
TILE_BYTES     = 128          # bytes per tile (8×8 × 2)
MAX_TILES      = 256
TILEMAP_COLS   = 32
TILEMAP_ROWS   = 16
```

---

### 6.4 Tile Engine

Each tile is an 8×8 grid of RGB565 pixels. Tiles are referenced by index (0–255). The tilemap assigns a tile to each of the 32×16 map cells. During rendering, the GPU looks up each cell's tile ID, finds the tile in VRAM, and blits it to the back-buffer, applying flip-X and flip-Y transformations as indicated by the entry word.

**Tile pixel data address:**
```
tile_pixel_addr(tile_id, px, py) = VRAM_TILE_BASE + tile_id × 128 + (py × 8 + px) × 2
```

**Tilemap entry address:**
```
map_entry_addr(col, row) = VRAM_MAP_BASE + (row × 32 + col) × 2
```

**Entry word format:**
```
bits [7:0]  = tile_id
bit  [8]    = flip_x  (mirror horizontally)
bit  [9]    = flip_y  (mirror vertically)
```

Setting a tilemap cell from Python:
```python
# tile 5, no flip:
gpu.set_tile(col=3, row=1, entry=5)

# tile 5 with flip-X:
gpu.set_tile(col=3, row=1, entry=5 | 0x100)

# tile 5 with flip-X and flip-Y:
gpu.set_tile(col=3, row=1, entry=5 | 0x300)
```

Loading tile pixel data from Python:
```python
# pixels: list of 64 RGB565 integers, row-major
gpu.load_tile(tile_id=0, pixels=[0xF800]*64)  # solid red tile
```

---

### 6.5 Sprite System

Sprites are defined by the `Sprite` dataclass:

```python
@dataclass
class Sprite:
    x: int = 0           # screen X (pixels)
    y: int = 0           # screen Y (pixels)
    tile_index: int = 0  # base tile (sprite uses tiles tile_index..tile_index+3)
    flags: int = 0       # see below
    collision_type: int = 0  # COL_NONE, COL_PLAYER, COL_ENEMY, etc.
```

**Sprite flags bitmask:**

| Bit | Mask | Property | Description |
|---|---|---|---|
| 0 | 0x01 | visible | Sprite is rendered and participates in collision |
| 1 | 0x02 | flip_x | Mirror sprite horizontally |
| 2 | 0x04 | flip_y | Mirror sprite vertically |
| 3 | 0x08 | priority | (Reserved for future use) |

**Sprite tile layout (2×2 tiles = 16×16 px):**
```
tile_index+0  |  tile_index+1     (top row)
tile_index+2  |  tile_index+3     (bottom row)
```

When flip_x is set, the left and right columns of sub-tiles are swapped AND each tile's pixels are mirrored. Similarly for flip_y.

**Transparency:** VRAM tile pixel value 0x0000 is treated as transparent — back-buffer pixels beneath it are preserved.

**Collision types:**
```python
COL_NONE   = 0
COL_PLAYER = 1
COL_ENEMY  = 2
COL_BULLET = 3
COL_ITEM   = 4
```
Only sprites with `collision_type != COL_NONE` participate in collision detection.

---

### 6.6 Direct Draw Operations

The GPU exposes direct-draw methods callable from Python:

```python
gpu.cls(color)                          # fill back-buffer
gpu.set_pixel(x, y, color)             # draw one pixel
gpu.draw_line(x1, y1, x2, y2, color)  # Bresenham line
gpu.draw_rect(x, y, w, h, color)      # filled rectangle
```

These target the back-buffer. All coordinates are clipped to the screen (0–255 x, 0–127 y). Colors are masked to 16 bits.

---

### 6.7 Collision Detection

`gpu.check_collisions()` does an O(n²) pairwise scan of all visible sprites with `collision_type != COL_NONE`. It uses axis-aligned bounding boxes of size `SPRITE_W × SPRITE_H = 16 × 16` pixels.

Detection condition:
```python
abs(a.x - b.x) < 16 and abs(a.y - b.y) < 16
```

On the first collision found:
- `gpu.collision_flag = 1`
- `gpu.collision_spr_a = i`  (index of first sprite)
- `gpu.collision_spr_b = j`  (index of second sprite)

If no collision: `collision_flag = 0`.

Results are also reflected in IO registers:
- `REG_COLLISION_FLAG`  = 0xFF20
- `REG_COLLISION_SPR_A` = 0xFF21
- `REG_COLLISION_SPR_B` = 0xFF22

---

### 6.8 Rendering Pipeline

The correct order for each frame:

```
1. CLEAR           — fill back-buffer with background color
2. DRAW_TILEMAP    — render tilemap (always opaque; tile 0 = background)
3. DRAW_SPRITES    — blit sprites (transparent pixels skip)
4. FLIP_BUFFER     — display, fire VBLANK, call renderer.render()
```

The VBLANK interrupt is fired inside `FLIP_BUFFER`. If you use `WAITVBLANK`, call it after `FLIP_BUFFER` to sleep until the next frame deadline.

---

## 7. APU — Audio Processing Unit

The GMC-16 APU is a 4-channel mono synthesizer running at 22,050 Hz. If pyaudio is installed, audio is output through the system sound device in real time via a background thread. If pyaudio is not installed, the APU operates silently — all registers, commands, and audio RAM are fully functional, but no sound is produced. This allows game logic to be developed and tested without audio hardware.

### 7.1 Channels

The APU has 4 independent channels (0–3). Each channel can independently:
- Play a tone (square, sine, triangle, or sawtooth wave)
- Play white noise
- Play a PCM sample from audio RAM
- Be stopped

All channels are mixed and normalized before output.

### 7.2 Waveforms

| Constant | Value | Description |
|---|---|---|
| `WAVE_SQUARE` | 0 | Square wave (50% duty cycle). Characteristic harsh/retro tone. |
| `WAVE_SINE` | 1 | Sine wave. Smooth, pure tone. |
| `WAVE_TRIANGLE` | 2 | Triangle wave. Softer than square, harmonically between square and sine. |
| `WAVE_SAWTOOTH` | 3 | Sawtooth wave. Bright, buzzy. Common for bass sounds. |
| `WAVE_NOISE` | 4 | White noise. Useful for percussion and explosion effects. (Set internally by PLAY_NOISE command.) |

### 7.3 Audio RAM

The APU has 8 KB (8,192 bytes) of dedicated audio RAM storing up to 4,096 × 16-bit signed samples. This is separate from main RAM and VRAM. Audio RAM is addressed by word index (0–4095).

Write samples from assembly:
```asm
PCMWR 0, 0x7FFF      ; word 0 = +32767 (max positive)
PCMWR 1, 0x8001      ; word 1 = -32767 (max negative)
```

Write samples from Python:
```python
apu.write_audio_ram(word_addr, value)   # value: unsigned 0–65535
apu.read_audio_ram(word_addr)           # returns unsigned 16-bit
```

Values are stored as unsigned 16-bit but interpreted as signed during PCM playback (values ≥ 32768 are treated as negative via `raw - 65536`).

### 7.4 APU IO Registers

| Register | Address | Description |
|---|---|---|
| REG_APU_CMD | 0xFF50 | Write: execute APU command |
| REG_APU_CHAN | 0xFF51 | Target channel (0–3) |
| REG_APU_FREQ_LO | 0xFF52 | Frequency low byte (Hz, 16-bit) |
| REG_APU_FREQ_HI | 0xFF53 | Frequency high byte |
| REG_APU_VOL | 0xFF54 | Volume (0–255) |
| REG_APU_WAVE | 0xFF55 | Waveform (0=square, 1=sine, 2=triangle, 3=sawtooth) |
| REG_APU_PCM_LO | 0xFF56 | PCM start address low byte (word index) |
| REG_APU_PCM_HI | 0xFF57 | PCM start address high byte |
| REG_APU_PCM_LEN_LO | 0xFF58 | PCM sample count low byte |
| REG_APU_PCM_LEN_HI | 0xFF59 | PCM sample count high byte |

**Usage pattern:** Set all staging registers (channel, frequency, volume, waveform), then write the command to REG_APU_CMD to execute.

### 7.5 APU Commands

| Command | Value | Description |
|---|---|---|
| `PLAY_TONE` | 0x01 | Play a tone using frequency, volume, waveform registers |
| `PLAY_NOISE` | 0x02 | Play white noise using volume register |
| `STOP` | 0x03 | Stop playback on the target channel |
| `STOP_ALL` | 0x04 | Stop playback on all 4 channels |
| `PLAY_PCM` | 0x05 | Play PCM from audio RAM using addr and len registers |

**Playing a tone (assembly):**
```asm
; Play 440 Hz A4 on channel 0, full volume, square wave
LOADI  R0, 0xFF51
LOADI  R1, 0          ; channel 0
STORE  R1, R0         ; REG_APU_CHAN = 0

LOADI  R0, 0xFF52
LOADI  R1, 440
STORE  R1, R0         ; REG_APU_FREQ_LO = 440 & 0xFF

LOADI  R0, 0xFF53
LOADI  R1, 1          ; 440 >> 8 = 1
STORE  R1, R0         ; REG_APU_FREQ_HI = 1

LOADI  R0, 0xFF54
LOADI  R1, 255
STORE  R1, R0         ; REG_APU_VOL = 255

LOADI  R0, 0xFF55
LOADI  R1, 0          ; WAVE_SQUARE
STORE  R1, R0         ; REG_APU_WAVE = 0

LOADI  R0, 0xFF50
LOADI  R1, 1          ; PLAY_TONE
STORE  R1, R0         ; fire!
```

### 7.6 PCM Playback

To play a PCM sample:
1. Write sample data to audio RAM via PCMWR or `apu.write_audio_ram()`
2. Set REG_APU_CHAN to the target channel
3. Set REG_APU_VOL to the playback volume
4. Set REG_APU_PCM_LO / HI to the start word address
5. Set REG_APU_PCM_LEN_LO / HI to the number of samples
6. Write PLAY_PCM (0x05) to REG_APU_CMD

When playback ends (all samples consumed), the channel is automatically stopped and an APU interrupt is raised (INT_APU, bit 3 of IF).

---

## 8. Interrupt System

The GMC-16 v7 interrupt system adds hardware interrupt support with an 8-source Interrupt Vector Table, master enable/disable (IME), per-source enable bits (IE), and pending flags (IF).

### 8.1 Interrupt Sources

| Source | Constant | Bit | Mask | Trigger |
|---|---|---|---|---|
| VBLANK | `INT_VBLANK` | 0 | 0x01 | GPU FLIP_BUFFER command |
| TIMER | `INT_TIMER` | 1 | 0x02 | Hardware timer overflow |
| INPUT | `INT_INPUT` | 2 | 0x04 | Controller state change |
| APU | `INT_APU` | 3 | 0x08 | PCM playback completed |
| IRQ0 | `INT_IRQ0` | 4 | 0x10 | Software: TRIG 0 |
| IRQ1 | `INT_IRQ1` | 5 | 0x20 | Software: TRIG 1 |
| IRQ2 | `INT_IRQ2` | 6 | 0x40 | Software: TRIG 2 |
| IRQ3 | `INT_IRQ3` | 7 | 0x80 | Software: TRIG 3 |

### 8.2 Interrupt Vector Table (IVT)

The IVT lives at the very top of the fixed ROM bank (0x3FF0–0x3FFE). Each entry is a 16-bit handler address.

```
0x3FF0   VBLANK handler address
0x3FF2   TIMER  handler address
0x3FF4   INPUT  handler address
0x3FF6   APU    handler address
0x3FF8   IRQ0   handler address
0x3FFA   IRQ1   handler address
0x3FFC   IRQ2   handler address
0x3FFE   IRQ3   handler address
```

To install a handler from Python:
```python
off = IVT_IRQ0 - BANK_FIXED_START    # = 0x3FF8 - 0x2000 = 0x1FF8
handler_addr = 0x2010                  # address of handler in ROM
cpu.bus._rom_fixed[off]     = handler_addr & 0xFF
cpu.bus._rom_fixed[off + 1] = (handler_addr >> 8) & 0xFF
```

To install from assembly, use a label in the fixed bank:
```asm
BANK FIXED

; IVT at 0x3FF0 — place handler address bytes here manually
; (use org/data pseudo-ops or patch from Python)

main:
    ; ... setup IE, SEI, main loop ...

vblank_handler:
    ; ... handler code ...
    RETI
```

### 8.3 IE and IF Registers

**IE (Interrupt Enable) — 0xFF80**

A bitmask. Setting a bit enables the corresponding interrupt source. If a bit is 0, that interrupt's pending flag in IF is ignored during dispatch.

```asm
; Enable VBLANK and TIMER interrupts
LOADI  R0, REG_IE
LOADI  R1, INT_VBLANK | INT_TIMER   ; = 0x03
STORE  R1, R0
```

**IF (Interrupt Flags) — 0xFF81**

A bitmask of pending interrupts. Bits are set by hardware when an event occurs. Writing a byte with certain bits cleared to IF clears those bits (write-to-clear).

```asm
; Clear the VBLANK pending flag
LOADI  R0, REG_IF
LOADI  R1, ~INT_VBLANK              ; = 0xFE
AND    R1, R1                        ; mask to 8 bits
STORE  R1, R0
```

From Python:
```python
cpu.bus._io[REG_IF - IO_START] &= ~INT_VBLANK  # clear VBLANK flag
```

**Hardware timer:**
Configure with REG_TIMER_PERIOD_LO (0xFF82) and REG_TIMER_PERIOD_HI (0xFF83). The timer counts CPU cycles. When the count reaches the period value, INT_TIMER is raised and the counter resets. Set period to 0 to disable.

```asm
; Set timer period to 100 cycles
LOADI  R0, REG_TIMER_PERIOD_LO
LOADI  R1, 100
STORE  R1, R0
LOADI  R0, REG_TIMER_PERIOD_HI
LOADI  R1, 0
STORE  R1, R0
```

### 8.4 Interrupt Dispatch Flow

After each instruction step, the CPU checks for pending interrupts:

```
1. If IME == False: stop, no dispatch
2. pending = IE & IF
3. If pending == 0: stop, no dispatch
4. Find lowest set bit in pending (highest priority = lowest bit)
5. Clear that bit in IF
6. Set IME = False (prevent re-entrant interrupts)
7. PUSH current PC
8. PUSH current FL (flags)
9. PC = IVT[bit_index]   (handler address from IVT)
10. Begin executing handler
```

The handler must end with RETI, which restores FL, restores PC, and re-enables IME.

**Interrupt latency:** At most 1 instruction (the current instruction completes before dispatch is checked).

### 8.5 Writing Interrupt Handlers

Rules for interrupt handlers:
- Always end with `RETI` (not `RET`)
- Save/restore any registers you modify with `PUSH`/`POP` (the CPU only saves PC and FL automatically)
- Keep handlers short — IME is off during the handler, so no re-entrant interrupts
- Do not use `WAITVBLANK` in a VBLANK handler (deadlock)

```asm
; Minimal VBLANK handler
vblank_isr:
    PUSH  R0
    PUSH  R1
    ; ... your frame-sync code ...
    POP   R1
    POP   R0
    RETI
```

---

## 9. Bankswitching System

### 9.1 Bank Layout

The ROM region is split into two parts:

```
0x2000–0x3FFF   FIXED BANK (8 KB, always bank 0, never paged)
                Contains code accessible from any bank.
                Top of this region is the IVT (0x3FF0–0x3FFE).

0x4000–0xFEFF   BANKED WINDOW (~48 KB, one of 22 banks)
                Bank 0–21 mapped here. Only one at a time.
```

| Constant | Value | Description |
|---|---|---|
| `BANK_FIXED_START` | 0x2000 | Start of fixed bank |
| `BANK_FIXED_END` | 0x3FFF | End of fixed bank |
| `BANK_FIXED_SIZE` | 8192 | Fixed bank size in bytes |
| `BANK_WIN_START` | 0x4000 | Start of banked window |
| `BANK_WIN_END` | 0xFEFF | End of banked window |
| `BANK_WIN_SIZE` | 49152 | Banked window size (~48 KB) |
| `NUM_BANKS` | 22 | Number of switchable banks (0–21) |

Total cartridge capacity: `8 KB + 22 × 48 KB = 1,064 KB > 1 MB`

### 9.2 Switching Banks at Runtime

From assembly:
```asm
SETBANK 3      ; switch banked window to bank 3
GETBANK R0     ; R0 = current bank (should be 3)
```

From Python:
```python
cpu.bus.switch_bank(3)          # switch to bank 3
bus.load_bank(3, data)          # load data into bank 3
bus.load_bank('fixed', data)    # load data into fixed bank
```

Via IO register:
```asm
LOADI  R0, 0xFF30   ; REG_BANK
LOADI  R1, 5
STORE  R1, R0       ; switch to bank 5
```

### 9.3 Assembler BANK Directive

The assembler supports multi-bank output through the `BANK` directive:

```asm
BANK FIXED       ; switch assembler output to fixed bank
; code here goes into fixed bank (0x2000–0x3FFF)

BANK 0           ; switch to bank 0
; code here goes into bank 0 (visible at 0x4000–0xFEFF)

BANK 3           ; switch to bank 3
; code here goes into bank 3
```

The assembler maintains separate output buffers for each bank. `assemble()` returns a `BankImage` object containing all bank data. Call `image.load_into(bus)` to load all banks into the emulator.

```python
image = Assembler().assemble(source)
print(image.summary())      # shows sizes of all banks
image.load_into(cpu.bus)    # loads everything
```

**Label scope:** Labels defined in one bank section are visible from all banks (they resolve to absolute addresses). Use `CALL` / `JMP` carefully across banks — jumping to a label in the banked window from the wrong bank will execute incorrect code. Always ensure the target bank is active before jumping to banked code.

---

## 10. Hardware IO Registers

All IO registers live in 0xFF00–0xFFFF. Reads and writes go through `MemoryBus._io_read()` and `_io_write()` which may have side effects.

| Address | Name | R/W | Description |
|---|---|---|---|
| 0xFF00 | REG_CONTROLLER_1 | R | Controller 1 button state (bitmask) |
| 0xFF10 | REG_GPU_COMMAND | W | Write to trigger GPU command |
| 0xFF11 | REG_GPU_X | R/W | GPU scratch X coordinate |
| 0xFF12 | REG_GPU_Y | R/W | GPU scratch Y coordinate |
| 0xFF13 | REG_GPU_COLOR | R/W | Color for GPU CLEAR command (RGB565) |
| 0xFF20 | REG_COLLISION_FLAG | R | 1 if last COLCHECK found collision |
| 0xFF21 | REG_COLLISION_SPR_A | R | First colliding sprite index |
| 0xFF22 | REG_COLLISION_SPR_B | R | Second colliding sprite index |
| 0xFF30 | REG_BANK | R/W | Read current bank; write to switch |
| 0xFF40 | REG_VRAM_ADDR_LO | R/W | VRAM DMA address low byte |
| 0xFF41 | REG_VRAM_ADDR_HI | R/W | VRAM DMA address high byte |
| 0xFF42 | REG_VRAM_DATA_LO | R/W | VRAM DMA data low byte |
| 0xFF43 | REG_VRAM_DATA_HI | R/W | VRAM DMA data high; writing commits word |
| 0xFF50 | REG_APU_CMD | W | APU command |
| 0xFF51 | REG_APU_CHAN | R/W | APU target channel (0–3) |
| 0xFF52 | REG_APU_FREQ_LO | R/W | APU frequency low byte |
| 0xFF53 | REG_APU_FREQ_HI | R/W | APU frequency high byte |
| 0xFF54 | REG_APU_VOL | R/W | APU volume (0–255) |
| 0xFF55 | REG_APU_WAVE | R/W | APU waveform (0–3) |
| 0xFF56 | REG_APU_PCM_LO | R/W | PCM start address low byte |
| 0xFF57 | REG_APU_PCM_HI | R/W | PCM start address high byte |
| 0xFF58 | REG_APU_PCM_LEN_LO | R/W | PCM sample count low byte |
| 0xFF59 | REG_APU_PCM_LEN_HI | R/W | PCM sample count high byte |
| 0xFF80 | REG_IE | R/W | Interrupt Enable bitmask |
| 0xFF81 | REG_IF | R/W | Interrupt Flags (write-to-clear) |
| 0xFF82 | REG_TIMER_PERIOD_LO | R/W | Timer period low byte (cycles) |
| 0xFF83 | REG_TIMER_PERIOD_HI | R/W | Timer period high byte |

**VRAM DMA:** To write a word to VRAM without using VRAMWR:
1. Write VRAM address lo byte to REG_VRAM_ADDR_LO
2. Write VRAM address hi byte to REG_VRAM_ADDR_HI
3. Write data lo byte to REG_VRAM_DATA_LO
4. Write data hi byte to REG_VRAM_DATA_HI — this commits the word to VRAM and auto-increments the address by 2

To read: write address, read REG_VRAM_DATA_LO (stages the word), read REG_VRAM_DATA_HI (returns hi byte, auto-increments address).

---

## 11. Framebuffer Renderer API

The `FramebufferRenderer` base class defines the interface for displaying GMC-16 output. Attach a renderer to the GPU before running:

```python
gpu = GPU()
gpu.renderer = MyRenderer()
cpu = GMC16CPU(gpu)
```

`render(pixels, width, height)` is called once per `FLIP_BUFFER` command with:
- `pixels`: flat `list[int]` of `width × height` RGB565 values, row-major
- `width`: always `SCREEN_W = 256`
- `height`: always `SCREEN_H = 128`

### 11.1 NullRenderer

The default renderer. `render()` is a no-op. Used when no display output is needed (headless testing, AI training, batch processing).

```python
gpu.renderer = NullRenderer()   # default
```

### 11.2 CallbackRenderer

Calls a user-supplied Python function each frame. Useful for capturing frames, piping to ffmpeg, or custom display logic.

```python
def my_hook(pixels, w, h):
    # pixels is list[int] RGB565
    print(f"Frame received: {w}×{h}")

gpu.renderer = CallbackRenderer(my_hook)
```

### 11.3 PygameRenderer

Renders frames into a pygame window with optional scaling. Handles quit events and keyboard input.

```python
gpu = GPU()
cpu = GMC16CPU(gpu)
gpu.renderer = PygameRenderer(
    scale=3,              # window = 768×384 (3× scale)
    title="My Game",
    cpu_ref=cpu           # enables keyboard → controller mapping
)
```

**Default key bindings:**

| Key | Button | Bit |
|---|---|---|
| Arrow Up | UP | 0x01 |
| Arrow Down | DOWN | 0x02 |
| Arrow Left | LEFT | 0x04 |
| Arrow Right | RIGHT | 0x08 |
| Z | A | 0x10 |
| X | B | 0x20 |
| Enter | START | 0x40 |
| Right Shift | SELECT | 0x80 |

When `cpu_ref` is provided, the renderer reads `pygame.key.get_pressed()` each frame and updates `cpu.controller1` accordingly.

### 11.4 Custom Renderers

To write a custom renderer, subclass `FramebufferRenderer`:

```python
class MyRenderer(FramebufferRenderer):
    def render(self, pixels: list[int], width: int, height: int) -> None:
        rgb_bytes = self.rgb565_to_bytes(pixels)
        # do something with rgb_bytes (PIL, numpy, socket, etc.)
```

### 11.5 RGB565 Color Format

The GMC-16 uses 16-bit RGB565 colors throughout:
- Bits 15–11: Red (5 bits, 0–31)
- Bits 10–5: Green (6 bits, 0–63)
- Bits 4–0: Blue (5 bits, 0–31)

**Conversion helpers:**
```python
# RGB565 to (r, g, b) each 0–255
r, g, b = FramebufferRenderer.rgb565_to_rgb(0xF800)  # red
# → (248, 0, 0)

# list[int] RGB565 to flat RGB bytes (for PIL, numpy, etc.)
rgb_bytes = FramebufferRenderer.rgb565_to_bytes(pixels)
```

**Encoding (Python):**
```python
def rgb_to_565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
```

---

## 12. Assembler

The GMC-16 assembler is a two-pass assembler implemented in the `Assembler` class. It translates GMC-16 assembly source text into binary machine code packaged as a `BankImage`.

### 12.1 Syntax Reference

```asm
; This is a comment (semicolon to end of line)
; Blank lines and comment-only lines are ignored

; Label definition
my_label:

; Label + code on same line
start: LOADI R0, 42

; EQU constant definition (two forms)
MAX_SPEED   EQU  10
MAX_SPEED:  EQU  10      ; colon form also valid

; Instruction with various operand types
NOP                      ; no operands
HALT
MOV  R0, R1              ; two registers
LOADI R2, 42             ; register + immediate
LOADI R3, 0xFF           ; hex immediate
LOADI R4, MY_CONST       ; named constant
LOADI R5, SCREEN_W / 2   ; expression
LOADI R6, (10 * 4) - 2   ; parenthesized expression
JMP  my_label            ; label reference (forward ok)
SPRITEPOS 0, R0, R1      ; mixed: id-imm, x-reg, y-reg
PIXEL R0, R1, 0xF800     ; mixed: x-reg, y-reg, color-imm

; BANK directive
BANK FIXED
BANK 0
BANK 5
```

Mnemonics are case-insensitive. Register names (R0–R7) are case-insensitive.

### 12.2 Labels & Constants (EQU)

**Labels** record the current assembly address. They can be referenced before definition (forward references work because of the two-pass design).

```asm
loop_start:
    DEC R0
    JNZ loop_start      ; backward reference — known at pass 1
    
    JMP after_data      ; forward reference — patched in pass 2
data_byte:
    NOP                 ; used as data marker
after_data:
```

**EQU constants** are evaluated at assembly time and substituted into expressions. They do not emit code.

```asm
PLAYER_SPRITE EQU 0
TILE_WALK_1   EQU 4
TILE_WALK_2   EQU 8

SPRITEIMG PLAYER_SPRITE, TILE_WALK_1
```

The colon form `NAME: EQU expr` prevents the name from being recorded as a code label. Use it for named constants when you want to use colon syntax:

```asm
GRAVITY:   EQU  1
MAX_FALL:  EQU  8
```

### 12.3 Expression Evaluator

Operand expressions support:
- Decimal integers: `42`, `1024`
- Hexadecimal: `0xFF`, `0x1F4`
- Arithmetic operators: `+`, `-`, `*`, `/` (integer division), `()`
- Bitwise operators: `|`, `&`, `^`, `~`
- Named symbols (labels, EQU constants, built-in constants)

```asm
HALF_SCREEN   EQU  SCREEN_W / 2        ; 128
CENTER_X      EQU  SCREEN_W / 2 - 8   ; 120
TILE_ENTRY    EQU  5 | 0x100           ; tile 5 with flip-X

LOADI R0, HALF_SCREEN
LOADI R1, (TILE_H * 3) + 4
SETTILE 0, 0, 5 | 0x200               ; tile 5 with flip-Y
```

Register names (R0–R7) inside expressions raise a `ValueError` — you cannot use register values in assembly-time expressions.

### 12.4 Mixed Register/Immediate Encoding

For instructions that support it (PIXEL, LINE, RECT, SPRITEPOS, SPRITEMOVE, SPRITEIMG, SETTILE, VRAMWR, VRAMRD, PCMWR, PCMRD), operands are detected as registers if they match `R0`–`R7`:

```asm
PIXEL  100, 50, 0xF800      ; all immediates → reg_flags = 0b000
PIXEL  R0, R1, 0xF800       ; x,y as registers → reg_flags = 0b011
PIXEL  R0, R1, R2           ; all registers → reg_flags = 0b111
PIXEL  100, R1, 0xF800      ; y as register → reg_flags = 0b010
```

The assembler emits a `reg_flags` word where bit `i` is set if argument `i` is a register. The CPU reads this at runtime to decide whether to use the register value or the literal word.

### 12.5 Built-in Constants

The assembler pre-defines all architecture constants:

**Screen & Memory:**
```
SCREEN_W = 256      SCREEN_H = 128
RAM_START = 0x0000  RAM_END  = 0x1FFF  ROM_START = 0x2000
```

**Collision Types:**
```
COL_NONE = 0  COL_PLAYER = 1  COL_ENEMY = 2
COL_BULLET = 3  COL_ITEM = 4
```

**Bankswitching:**
```
BANK_FIXED_START = 0x2000   BANK_FIXED_END = 0x3FFF
BANK_FIXED_SIZE  = 8192     BANK_WIN_START = 0x4000
BANK_WIN_END     = 0xFEFF   BANK_WIN_SIZE  = 49152
NUM_BANKS        = 22
```

**Tile Engine:**
```
TILE_W = 8  TILE_H = 8  TILE_BYTES = 128
MAX_TILES = 256  TILEMAP_COLS = 32  TILEMAP_ROWS = 16
VRAM_TILE_BASE = 0x0000  VRAM_TILE_END = 0x3FFF
VRAM_MAP_BASE  = 0x4000  VRAM_MAP_END  = 0x47FF
VRAM_USER_BASE = 0x4800
```

**APU:**
```
APU_SAMPLE_RATE = 22050  APU_CHANNELS = 4  APU_MAX_SAMPLES = 4096
WAVE_SQUARE = 0  WAVE_SINE = 1  WAVE_TRIANGLE = 2  WAVE_SAWTOOTH = 3
REG_APU_CMD = 0xFF50  REG_APU_CHAN = 0xFF51
REG_APU_FREQ_LO = 0xFF52  REG_APU_FREQ_HI = 0xFF53
REG_APU_VOL = 0xFF54  REG_APU_WAVE = 0xFF55
REG_APU_PCM_LO = 0xFF56  REG_APU_PCM_HI = 0xFF57
REG_APU_PCM_LEN_LO = 0xFF58  REG_APU_PCM_LEN_HI = 0xFF59
PLAY_TONE = 0x01  PLAY_NOISE = 0x02  SND_STOP = 0x03
SND_STOP_ALL = 0x04  PLAY_PCM = 0x05
```

**Interrupts:**
```
IVT_VBLANK = 0x3FF0  IVT_TIMER = 0x3FF2  IVT_INPUT = 0x3FF4
IVT_APU    = 0x3FF6  IVT_IRQ0  = 0x3FF8  IVT_IRQ1  = 0x3FFA
IVT_IRQ2   = 0x3FFC  IVT_IRQ3  = 0x3FFE
INT_VBLANK = 0x01   INT_TIMER = 0x02  INT_INPUT = 0x04
INT_APU    = 0x08   INT_IRQ0  = 0x10  INT_IRQ1  = 0x20
INT_IRQ2   = 0x40   INT_IRQ3  = 0x80
REG_IE = 0xFF80  REG_IF = 0xFF81
REG_TIMER_PERIOD_LO = 0xFF82  REG_TIMER_PERIOD_HI = 0xFF83
```

### 12.6 BANK Directive

The `BANK` directive switches the assembler's output target:

```asm
BANK FIXED   ; output to fixed bank (default)
BANK 0       ; output to bank 0 (visible at 0x4000–0xFEFF)
BANK 7       ; output to bank 7
```

Each bank has its own byte buffer. The fixed bank starts at `BANK_FIXED_START = 0x2000`; banked windows start at `BANK_WIN_START = 0x4000`. Labels record absolute addresses relative to their bank's origin.

### 12.7 Two-Pass Assembly

**Pass 1 (single linear scan):**
- Record labels at current bank's write position
- Process EQU constants
- Handle BANK directives
- Emit instruction bytes; use placeholder (0x0000) for forward references
- Record forward references in `patch_list` with `(offset, expr, bank_key)`

**Pass 2:**
- Re-evaluate all patched expressions now that all labels are known
- Overwrite placeholder words in the appropriate bank buffer

This means forward label references always work:

```asm
JMP  after_me       ; forward reference — safe!
LOADI R0, 99
HALT
after_me:
LOADI R0, 42
HALT
```

### 12.8 BankImage Output

`Assembler.assemble()` returns a `BankImage`:

```python
image = Assembler().assemble(source)
image.fixed           # bytes: fixed bank data
image.banks           # dict[int, bytes]: banked data per bank number
len(image)            # total bytes across all banks
image.summary()       # human-readable size report
image.load_into(bus)  # load all banks into a MemoryBus
bytes(image)          # returns fixed bank bytes (backwards compat)
```

`load_into()` calls `bus.load_bank('fixed', ...)` and `bus.load_bank(n, ...)` for each populated bank.

---

## 13. Python Host API

### 13.1 GMC16CPU

```python
class GMC16CPU:
    def __init__(self, gpu=None, apu=None)
```

The top-level CPU object. Creates a GPU and APU if not provided.

**Attributes:**
```python
cpu.R            # list[int], 8 registers R0–R7
cpu.PC           # int, program counter
cpu.SP           # int, stack pointer
cpu.FL           # int, flags (Z|C|N|O bits)
cpu.halted       # bool, True after HALT
cpu.total_cycles # int, cumulative cycle count
cpu.IME          # bool, interrupt master enable
cpu.controller1  # int, controller button state (set from host)
cpu.gpu          # GPU instance
cpu.apu          # APU instance
cpu.bus          # MemoryBus instance
```

**Methods:**
```python
cpu.reset()                    # reset all state, PC = ROM_START
cpu.step(debug=False)          # execute one instruction
cpu.run(max_steps=0, debug=False)  # run until halt or max_steps
cpu.dump_registers() -> str    # formatted register dump
cpu.dump_ram(start, length) -> str  # hex dump of RAM region
cpu.disassemble(start, length) -> str  # disassemble bytes from address
```

**Debug mode:**
```python
cpu.run(debug=True)
# prints one line per instruction:
#   PC=2000  LOADI R0, 0x002A           R0=0x0000  [Z=0 C=0 N=0 O=0]
```

**Minimal usage:**
```python
gpu = GPU()
gpu.renderer = PygameRenderer(scale=3)
cpu = GMC16CPU(gpu)
cpu.bus.load_rom(Assembler().assemble(source))
cpu.reset()
cpu.run()
```

### 13.2 MemoryBus

```python
class MemoryBus:
    def __init__(self, gpu, apu=None)
```

**Loading ROM:**
```python
bus.load_rom(data)                    # backward-compat: fills fixed then bank 0
bus.load_rom(bank_image)             # accepts BankImage directly
bus.load_bank('fixed', data)         # load fixed bank
bus.load_bank(n, data)               # load bank n (0–21)
bus.load_bank(n, data, offset=0)     # load at offset within bank
bus.switch_bank(n)                   # switch banked window at runtime
```

**Memory access:**
```python
bus.read(addr) -> int        # read 1 byte
bus.write(addr, value)       # write 1 byte
bus.read16(addr) -> int      # read 16-bit little-endian word
bus.write16(addr, value)     # write 16-bit little-endian word
bus.raise_interrupt(mask)    # set bits in IF register
```

**Internal state (advanced):**
```python
bus._ram          # bytearray(8192)
bus._rom_fixed    # bytearray(8192)
bus._rom_banks    # list of 22 bytearray(49152)
bus._io           # bytearray(256)
bus._cur_bank     # int, currently active bank
```

### 13.3 GPU

```python
class GPU:
    SPRITE_COUNT = 256
    SPRITE_W     = 16
    SPRITE_H     = 16
```

**Tile API:**
```python
gpu.load_tile(tile_id, pixels)          # pixels: list[int] of 64 RGB565 values
gpu.write_tile_pixel(tile_id, px, py, color)
gpu.read_tile_pixel(tile_id, px, py) -> int
```

**Tilemap API:**
```python
gpu.set_tile(col, row, entry)          # entry: tile_id | (flipX<<8) | (flipY<<9)
gpu.get_tile(col, row) -> int
```

**VRAM direct access:**
```python
gpu.vram_read(vaddr) -> int            # read 16-bit word from VRAM
gpu.vram_write(vaddr, value)           # write 16-bit word to VRAM
```

**Sprite control:**
```python
gpu.sprite_set_pos(sid, x, y)
gpu.sprite_move(sid, dx, dy)
gpu.sprite_set_image(sid, tile)
gpu.sprite_enable(sid)
gpu.sprite_disable(sid)
```

**Rendering:**
```python
gpu.execute_command(cmd, color)        # fire a GPU command
gpu.cls(color)                         # clear back-buffer
gpu.set_pixel(x, y, color)
gpu.draw_line(x1, y1, x2, y2, color)
gpu.draw_rect(x, y, w, h, color)
```

**Collision:**
```python
gpu.check_collisions()
gpu.collision_flag    # int: 1 if collision detected
gpu.collision_spr_a   # int: first sprite index
gpu.collision_spr_b   # int: second sprite index
```

**Scroll:**
```python
gpu.scroll_x = 0      # pixels, wraps at 256
gpu.scroll_y = 0      # pixels, wraps at 128
```

**IRQ callback:**
```python
gpu.set_irq_callback(fn)   # fn(mask): called on VBLANK
```

### 13.4 APU

```python
class APU:
    def __init__(self)
    def start(self)        # open pyaudio stream (silent if unavailable)
    def stop(self)         # close stream
```

**Direct control (host-side):**
```python
apu.play_tone(channel, freq, vol=200, wave=WAVE_SQUARE)
apu.stop_channel(channel)
apu.stop_all()
apu.is_active(channel) -> bool
```

**Audio RAM:**
```python
apu.write_audio_ram(word_addr, value)   # value: unsigned 0–65535
apu.read_audio_ram(word_addr) -> int
```

**IO register interface:**
```python
apu.handle_register_write(reg, value)   # called by MemoryBus for 0xFF50–0xFF59
```

**Advanced:**
```python
apu._generate_chunk(n_frames) -> bytes  # generate n_frames of signed 16-bit mono PCM
```

---

## 14. Complete Opcode Reference Table

| Opcode | Mnemonic | Format | Description |
|---|---|---|---|
| 0x00 | NOP | NOP | No operation |
| 0x01 | HALT | HALT | Stop CPU |
| 0x02 | MOV | MOV Rd, Rs | Rd = Rs |
| 0x03 | LOAD | LOAD Rd, [Rs] | Rd = mem16[Rs] |
| 0x04 | STORE | STORE Ra, [Rb] | mem16[Rb] = Ra |
| 0x05 | LOADI | LOADI Rd, imm | Rd = immediate |
| 0x06 | SWAP | SWAP Ra, Rb | Exchange Ra ↔ Rb |
| 0x07 | ADD | ADD Rd, Rs | Rd = Rd + Rs |
| 0x08 | SUB | SUB Rd, Rs | Rd = Rd - Rs |
| 0x09 | MUL | MUL Rd, Rs | Rd = Rd × Rs |
| 0x0A | DIV | DIV Rd, Rs | Rd = Rd ÷ Rs |
| 0x0B | INC | INC Rd | Rd = Rd + 1 |
| 0x0C | DEC | DEC Rd | Rd = Rd - 1 |
| 0x0D | NEG | NEG Rd | Rd = -Rd (two's complement) |
| 0x0E | ABS | ABS Rd | Rd = |Rd| |
| 0x0F | AND | AND Rd, Rs | Rd = Rd & Rs |
| 0x10 | OR | OR Rd, Rs | Rd = Rd \| Rs |
| 0x11 | XOR | XOR Rd, Rs | Rd = Rd ^ Rs |
| 0x12 | NOT | NOT Rd | Rd = ~Rd |
| 0x13 | SHL | SHL Rd | Rd <<= 1, old MSB → C |
| 0x14 | SHR | SHR Rd | Rd >>= 1, old LSB → C |
| 0x15 | CMP | CMP Ra, Rb | Set flags on Ra-Rb, no store |
| 0x16 | JMP | JMP addr | PC = addr |
| 0x17 | JZ | JZ addr | if Z: PC = addr |
| 0x18 | JNZ | JNZ addr | if !Z: PC = addr |
| 0x19 | JG | JG addr | if !Z && !N: PC = addr |
| 0x1A | JL | JL addr | if N: PC = addr |
| 0x1B | PUSH | PUSH Ra | Stack push Ra |
| 0x1C | POP | POP Rd | Stack pop → Rd |
| 0x1D | CALL | CALL addr | Push PC, jump |
| 0x1E | RET | RET | Pop PC, return |
| 0x1F | RAND | RAND Rd | Rd = random 0–65535 |
| 0x20 | SPRITEPOS | SPRITEPOS sid, x, y | Set sprite position |
| 0x21 | SPRITEMOVE | SPRITEMOVE sid, dx, dy | Move sprite by delta |
| 0x22 | SPRITEIMG | SPRITEIMG sid, tile | Set sprite base tile |
| 0x23 | SPRITEENABLE | SPRITEENABLE sid | Make sprite visible |
| 0x24 | SPRITEDISABLE | SPRITEDISABLE sid | Hide sprite |
| 0x25 | SETTILE | SETTILE col, row, entry | Write tilemap cell |
| 0x26 | GETTILE | GETTILE Rd, col, row | Read tilemap cell into Rd |
| 0x27 | SCROLLX | SCROLLX val | Set horizontal scroll |
| 0x28 | SCROLLY | SCROLLY val | Set vertical scroll |
| 0x29 | CLS | CLS color | Clear back-buffer |
| 0x2A | PIXEL | PIXEL x, y, color | Draw pixel |
| 0x2B | LINE | LINE x1,y1,x2,y2,color | Draw line |
| 0x2C | RECT | RECT x,y,w,h,color | Draw filled rectangle |
| 0x2D | COLCHECK | COLCHECK Rd | Run collision detection |
| 0x2E | COLSPR1 | COLSPR1 Rd | Get first colliding sprite |
| 0x2F | COLSPR2 | COLSPR2 Rd | Get second colliding sprite |
| 0x30 | INPUT | INPUT Rd | Read controller buttons |
| 0x31 | BUTTON | BUTTON Rd, mask | Test specific button(s) |
| 0x32 | WAITVBLANK | WAITVBLANK | Sleep to 60 Hz frame |
| 0x33 | TIMER | TIMER Rd | Rd = ms timer (lower 16 bits) |
| 0x34 | SETBANK | SETBANK imm | Switch ROM bank |
| 0x35 | GETBANK | GETBANK Rd | Rd = current bank |
| 0x36 | VRAMWR | VRAMWR vaddr, val | Write word to VRAM |
| 0x37 | VRAMRD | VRAMRD Rd, vaddr | Rd = VRAM word |
| 0x38 | PCMWR | PCMWR addr, val | Write PCM sample |
| 0x39 | PCMRD | PCMRD Rd, addr | Read PCM sample into Rd |
| 0x3A | SEI | SEI | Enable interrupts (IME=1) |
| 0x3B | CLI | CLI | Disable interrupts (IME=0) |
| 0x3C | RETI | RETI | Return from interrupt |
| 0x3D | TRIG | TRIG n | Raise IRQn (0–3) |

---

## 15. IO Register Map

```
0xFF00  REG_CONTROLLER_1      R    Controller 1 button bitmask
0xFF01  (reserved)
...
0xFF0F  (reserved)
0xFF10  REG_GPU_COMMAND        W    GPU command trigger
0xFF11  REG_GPU_X              R/W  GPU scratch X
0xFF12  REG_GPU_Y              R/W  GPU scratch Y
0xFF13  REG_GPU_COLOR          R/W  GPU clear color (RGB565 low byte)
0xFF14  (reserved)
...
0xFF1F  (reserved)
0xFF20  REG_COLLISION_FLAG     R    Collision detected (0/1)
0xFF21  REG_COLLISION_SPR_A    R    First colliding sprite index
0xFF22  REG_COLLISION_SPR_B    R    Second colliding sprite index
0xFF23  (reserved)
...
0xFF2F  (reserved)
0xFF30  REG_BANK               R/W  Current bank; write to switch
0xFF31  (reserved)
...
0xFF3F  (reserved)
0xFF40  REG_VRAM_ADDR_LO       R/W  VRAM DMA address low
0xFF41  REG_VRAM_ADDR_HI       R/W  VRAM DMA address high
0xFF42  REG_VRAM_DATA_LO       R/W  VRAM DMA data low
0xFF43  REG_VRAM_DATA_HI       R/W  VRAM DMA data high (commits on write)
0xFF44  (reserved)
...
0xFF4F  (reserved)
0xFF50  REG_APU_CMD            W    APU command (executes immediately)
0xFF51  REG_APU_CHAN           R/W  APU target channel (0-3)
0xFF52  REG_APU_FREQ_LO        R/W  Frequency low byte
0xFF53  REG_APU_FREQ_HI        R/W  Frequency high byte
0xFF54  REG_APU_VOL            R/W  Volume (0-255)
0xFF55  REG_APU_WAVE           R/W  Waveform (0-3)
0xFF56  REG_APU_PCM_LO         R/W  PCM start word-address low
0xFF57  REG_APU_PCM_HI         R/W  PCM start word-address high
0xFF58  REG_APU_PCM_LEN_LO     R/W  PCM sample count low
0xFF59  REG_APU_PCM_LEN_HI     R/W  PCM sample count high
0xFF5A  (reserved)
...
0xFF7F  (reserved)
0xFF80  REG_IE                 R/W  Interrupt Enable bitmask
0xFF81  REG_IF                 R/W  Interrupt Flags (write to clear bits)
0xFF82  REG_TIMER_PERIOD_LO    R/W  Timer period cycles low
0xFF83  REG_TIMER_PERIOD_HI    R/W  Timer period cycles high
0xFF84  (reserved)
...
0xFFFF  (reserved)
```

---

## 16. Programming Guide & Examples

### 16.1 Hello World — Drawing to Screen

The minimal program that clears the screen to a color and halts:

```asm
; Clear screen to blue, flip to display, halt.
BANK FIXED

    LOADI  R0, 0xFF13          ; REG_GPU_COLOR
    LOADI  R1, 0x001F          ; RGB565 blue
    STORE  R1, R0              ; set clear color

    LOADI  R0, 0xFF10          ; REG_GPU_COMMAND
    LOADI  R1, 0x01            ; GpuCmd.CLEAR
    STORE  R1, R0

    LOADI  R1, 0x03            ; GpuCmd.FLIP_BUFFER
    STORE  R1, R0

    HALT
```

From Python:
```python
gpu = GPU()
gpu.renderer = CallbackRenderer(lambda p,w,h: print("Frame!"))
cpu = GMC16CPU(gpu)
cpu.bus.load_rom(Assembler().assemble(source))
cpu.reset()
cpu.run()
```

### 16.2 Sprite Animation Loop

```asm
; Animate sprite 0 walking right across screen
BANK FIXED

    ; Set up sprite image (tile 0 = first frame)
    SPRITEIMG    0, 0
    SPRITEENABLE 0
    SPRITEPOS    0, 0, 60

    ; Initialize animation counter
    LOADI  R0, 0        ; X position
    LOADI  R1, 0        ; animation frame counter
    LOADI  R2, 8        ; frames per tile swap
    LOADI  R3, 0        ; current tile (0 or 4)

game_loop:
    ; Clear and render
    LOADI  R6, 0xFF13
    LOADI  R7, 0x0000
    STORE  R7, R6          ; black background

    LOADI  R6, 0xFF10
    LOADI  R7, 0x01
    STORE  R7, R6          ; CLEAR

    LOADI  R7, 0x02
    STORE  R7, R6          ; DRAW_SPRITES

    LOADI  R7, 0x03
    STORE  R7, R6          ; FLIP_BUFFER

    WAITVBLANK

    ; Move sprite right
    INC    R0
    LOADI  R4, SCREEN_W
    CMP    R0, R4
    JL     no_wrap
    LOADI  R0, 0
no_wrap:
    SPRITEPOS 0, R0, 60

    ; Animate tile
    INC    R1
    CMP    R1, R2
    JL     no_tile_swap
    LOADI  R1, 0
    LOADI  R4, 4
    LOADI  R5, 0
    CMP    R3, R5
    JNZ    switch_to_0
    MOV    R3, R4
    JMP    done_tile
switch_to_0:
    LOADI  R3, 0
done_tile:
    SPRITEIMG 0, R3
no_tile_swap:

    JMP game_loop
```

### 16.3 Input Handling

```asm
; Move a sprite with the D-pad
BANK FIXED

    SPRITEPOS    0, SCREEN_W/2, SCREEN_H/2
    SPRITEENABLE 0

    LOADI  R0, SCREEN_W/2    ; X position
    LOADI  R1, SCREEN_H/2    ; Y position
    LOADI  R2, 2             ; speed

game_loop:
    ; Read input
    BUTTON  R3, 0x01    ; UP
    JZ      no_up
    SUB     R1, R2
no_up:
    BUTTON  R3, 0x02    ; DOWN
    JZ      no_down
    ADD     R1, R2
no_down:
    BUTTON  R3, 0x04    ; LEFT
    JZ      no_left
    SUB     R0, R2
no_left:
    BUTTON  R3, 0x08    ; RIGHT
    JZ      no_right
    ADD     R0, R2
no_right:

    ; Clamp X
    LOADI  R4, 0
    CMP    R0, R4
    JG     clamp_x_max
    LOADI  R0, 0
    JMP    done_clamp_x
clamp_x_max:
    LOADI  R4, SCREEN_W - 16
    CMP    R0, R4
    JL     done_clamp_x
    LOADI  R0, SCREEN_W - 16
done_clamp_x:

    SPRITEPOS 0, R0, R1

    LOADI  R6, 0xFF10
    LOADI  R7, 0x01 : STORE R7, R6    ; CLEAR
    LOADI  R7, 0x02 : STORE R7, R6    ; DRAW_SPRITES
    LOADI  R7, 0x03 : STORE R7, R6    ; FLIP_BUFFER
    WAITVBLANK

    JMP game_loop
```

### 16.4 Tilemap Rendering

```python
# Python: set up a checkerboard tilemap
import itertools

gpu = cpu.gpu

# Tile 0: black
gpu.load_tile(0, [0x0000] * 64)

# Tile 1: white
gpu.load_tile(1, [0xFFFF] * 64)

# Fill tilemap with checkerboard
for row in range(16):
    for col in range(32):
        tile = (row + col) % 2
        gpu.set_tile(col, row, tile)
```

```asm
; Assembly: render tilemap each frame
BANK FIXED

game_loop:
    LOADI  R0, 0xFF10
    LOADI  R1, 0x01
    STORE  R1, R0          ; CLEAR

    LOADI  R1, 0x04
    STORE  R1, R0          ; DRAW_TILEMAP

    LOADI  R1, 0x02
    STORE  R1, R0          ; DRAW_SPRITES

    LOADI  R1, 0x03
    STORE  R1, R0          ; FLIP_BUFFER

    WAITVBLANK
    JMP game_loop
```

### 16.5 Playing Sound

```asm
; Play A4 (440 Hz) square wave on channel 0 at full volume
BANK FIXED

play_a4:
    LOADI  R7, REG_APU_CHAN
    LOADI  R0, 0
    STORE  R0, R7           ; channel 0

    LOADI  R7, REG_APU_FREQ_LO
    LOADI  R0, 440 & 0xFF   ; = 184
    STORE  R0, R7

    LOADI  R7, REG_APU_FREQ_HI
    LOADI  R0, 440 / 256    ; = 1
    STORE  R0, R7

    LOADI  R7, REG_APU_VOL
    LOADI  R0, 200
    STORE  R0, R7

    LOADI  R7, REG_APU_WAVE
    LOADI  R0, WAVE_SQUARE
    STORE  R0, R7

    LOADI  R7, REG_APU_CMD
    LOADI  R0, PLAY_TONE
    STORE  R0, R7           ; fire!

    ; Play 60 frames (~1 second), then stop
    LOADI  R5, 60
wait_loop:
    WAITVBLANK
    DEC    R5
    JNZ    wait_loop

    LOADI  R7, REG_APU_CMD
    LOADI  R0, SND_STOP_ALL
    STORE  R0, R7

    HALT
```

### 16.6 Interrupt-Driven Timer

```asm
; Use hardware timer to blink a pixel every 500ms
BANK FIXED

    ; Install timer handler
    ; (Handler address must be patched into IVT from Python or data section)

    ; Enable timer interrupt
    LOADI  R0, REG_IE
    LOADI  R1, INT_TIMER
    STORE  R1, R0

    ; Set timer period to 3000 cycles
    LOADI  R0, REG_TIMER_PERIOD_LO
    LOADI  R1, 3000 & 0xFF
    STORE  R1, R0
    LOADI  R0, REG_TIMER_PERIOD_HI
    LOADI  R1, 3000 >> 8
    STORE  R1, R0

    ; Global enable
    SEI

    ; Main loop (idle)
idle:
    WAITVBLANK
    JMP idle

; Timer interrupt handler
timer_isr:
    PUSH   R0
    PUSH   R1
    LOADI  R0, 0x0000        ; blink state variable address
    LOAD   R1, R0
    LOADI  R0, 1
    XOR    R1, R0            ; toggle bit 0
    LOADI  R0, 0x0000
    STORE  R1, R0
    POP    R1
    POP    R0
    RETI
```

### 16.7 Multi-Bank Cartridge

```asm
; Main game uses fixed bank + up to 22 data/code banks
BANK FIXED

    ; Initially in fixed bank — set up engine, load bank 0 assets
    SETBANK 0
    CALL   load_level_1

    ; Switch to game loop
    JMP    main_loop

main_loop:
    ; core game loop in fixed bank
    WAITVBLANK
    JMP    main_loop

; Subroutine that lives in fixed bank but calls code in bank 1
play_cutscene:
    PUSH   R7
    GETBANK R7              ; save current bank
    SETBANK 1               ; switch to cutscene bank
    CALL   BANK_WIN_START   ; jump to start of bank 1
    ; (returns here)
    MOV    R0, R7
    SETBANK R0              ; restore previous bank — WAIT
    ; Note: SETBANK takes an immediate. Use STORE to REG_BANK instead:
    LOADI  R0, 0xFF30       ; REG_BANK
    STORE  R7, R0           ; restore bank
    POP    R7
    RET

BANK 0
; Level 1 assets
load_level_1:
    ; ... load tile data into VRAM, set up tilemap ...
    RET

BANK 1
; Cutscene code
    ; ... cutscene logic ...
    RET
```

### 16.8 PCM Audio Playback

```python
# Python: generate a sine wave and load into audio RAM
import math

apu = cpu.apu
sample_rate = 22050
freq = 440
n_samples = sample_rate  # 1 second

for i in range(min(n_samples, 4096)):
    t = i / sample_rate
    sample = int(math.sin(2 * math.pi * freq * t) * 32767)
    apu.write_audio_ram(i, sample & 0xFFFF)

# Now trigger from assembly or Python:
apu.handle_register_write(0xFF51, 0)    # channel 0
apu.handle_register_write(0xFF54, 200)  # volume
apu.handle_register_write(0xFF56, 0)    # PCM start lo
apu.handle_register_write(0xFF57, 0)    # PCM start hi
apu.handle_register_write(0xFF58, 4096 & 0xFF)   # len lo
apu.handle_register_write(0xFF59, 4096 >> 8)     # len hi
apu.handle_register_write(0xFF50, 0x05)           # PLAY_PCM
```

### 16.9 Collision Detection Game Loop

```asm
; Shoot bullet, check collision with enemies
BANK FIXED

PLAYER_SPR  EQU 0
BULLET_SPR  EQU 1
ENEMY_SPR   EQU 2

    ; Set collision types (from Python or via RAM writes)
    ; cpu.gpu.sprites[PLAYER_SPR].collision_type = COL_PLAYER
    ; cpu.gpu.sprites[BULLET_SPR].collision_type = COL_BULLET
    ; cpu.gpu.sprites[ENEMY_SPR].collision_type  = COL_ENEMY

    SPRITEENABLE PLAYER_SPR
    SPRITEENABLE ENEMY_SPR
    SPRITEPOS    PLAYER_SPR, 10, 60
    SPRITEPOS    ENEMY_SPR, 200, 60

game_loop:
    ; Render frame
    LOADI  R6, 0xFF10
    LOADI  R7, 0x01 : STORE R7, R6     ; CLEAR
    LOADI  R7, 0x02 : STORE R7, R6     ; DRAW_SPRITES
    LOADI  R7, 0x03 : STORE R7, R6     ; FLIP_BUFFER
    WAITVBLANK

    ; Fire bullet on A button
    BUTTON R0, 0x10
    JZ     no_fire
    ; Enable bullet sprite at player position + offset
    SPRITEENABLE BULLET_SPR
no_fire:

    ; Move bullet if active
    SPRITEMOVE BULLET_SPR, 4, 0

    ; Collision check
    COLCHECK R0
    JZ       no_hit
    COLSPR1  R1      ; R1 = sprite A index
    COLSPR2  R2      ; R2 = sprite B index
    ; Handle hit: disable both sprites
    SPRITEDISABLE BULLET_SPR
    SPRITEDISABLE ENEMY_SPR
no_hit:

    JMP game_loop
```

---

## 17. Version History & Changelog

| Version | Summary |
|---|---|
| **v1** | Initial implementation. Core CPU, assembler, basic rendering. |
| **v2** | Collision O(n²) with sprite pairs. Explicit memory map. GPU command register. DIV flag fix. ADD overflow detection. Expression assembler. Cycle timing table. |
| **v3** | ROM overflow protection. Register bounds checking (R0–R7 enforced). Drift-free VBlank using absolute monotonic timer target. Debug/disassembly mode (`step(debug=True)`). Framebuffer renderer API (`FramebufferRenderer`, `PygameRenderer`, `CallbackRenderer`). |
| **v4** | Bankswitching: 8 KB fixed bank + 22 × ~48 KB switchable banks. Total >1 MB cartridge space. `SETBANK`, `GETBANK` opcodes. `REG_BANK` IO register. `load_bank()` method. Assembler `BANK` directive. `BankImage` output object. |
| **v5** | VRAM-backed tile engine: 8×8 tiles, 32×16 tilemap, scroll/flip-X/flip-Y. `VRAMWR`, `VRAMRD` CPU instructions. VRAM DMA IO registers (0xFF40–0xFF43). GPU `DRAW_TILEMAP` command. `SETTILE`, `GETTILE` CPU instructions. `SCROLLX`, `SCROLLY` CPU instructions. |
| **v6** | Mono 16-bit APU with optional pyaudio backend. 4 channels: square/sine/triangle/sawtooth/noise/PCM. 22,050 Hz sample rate, background thread. 8 KB audio RAM (4,096 × 16-bit samples). `PCMWR`, `PCMRD` CPU instructions. IO registers 0xFF50–0xFF59. APU commands: PLAY_TONE, PLAY_NOISE, STOP, STOP_ALL, PLAY_PCM. Silent fallback if pyaudio unavailable. |
| **v7** | Hardware interrupt system: IVT at 0x3FF0, IME flag, IE/IF registers (0xFF80–0xFF81). 8 sources: VBLANK, TIMER, INPUT, APU, IRQ0–3. `SEI`, `CLI`, `RETI`, `TRIG` opcodes. Hardware timer via REG_TIMER_PERIOD (0xFF82–0xFF83). Input change interrupt. APU end-of-PCM interrupt. 15-test self-test suite. |

---

## Appendix A — Flag Behavior Per Instruction

| Instruction | Z | C | N | O | Notes |
|---|---|---|---|---|---|
| NOP | — | — | — | — | |
| HALT | — | — | — | — | |
| MOV | ✓ | — | ✓ | — | |
| LOAD | ✓ | — | ✓ | — | |
| STORE | — | — | — | — | |
| LOADI | ✓ | — | ✓ | — | |
| SWAP | — | — | — | — | |
| ADD | ✓ | ✓ | ✓ | ✓ | C=unsigned overflow, O=signed overflow |
| SUB | ✓ | ✓ | ✓ | — | C=borrow (result<0) |
| MUL | ✓ | ✓ | ✓ | — | C=product exceeded 16 bits |
| DIV | ✓ | — | ✓ | — | Result 0xFFFF if divisor=0 |
| INC | ✓ | — | ✓ | — | |
| DEC | ✓ | — | ✓ | — | |
| NEG | ✓ | — | ✓ | — | |
| ABS | ✓ | — | ✓ | — | |
| AND | ✓ | — | ✓ | — | |
| OR | ✓ | — | ✓ | — | |
| XOR | ✓ | — | ✓ | — | |
| NOT | ✓ | — | ✓ | — | |
| SHL | ✓ | ✓ | ✓ | — | C=old bit 15 |
| SHR | ✓ | ✓ | ✓ | — | C=old bit 0 |
| CMP | ✓ | ✓ | ✓ | — | Computes Ra-Rb, no store |
| JMP | — | — | — | — | |
| JZ/JNZ/JG/JL | — | — | — | — | |
| PUSH | — | — | — | — | |
| POP | ✓ | — | ✓ | — | |
| CALL | — | — | — | — | |
| RET | — | — | — | — | |
| RAND | — | — | — | — | |
| SPRITEPOS | — | — | — | — | |
| SPRITEMOVE | — | — | — | — | |
| SPRITEIMG | — | — | — | — | |
| SPRITEENABLE | — | — | — | — | |
| SPRITEDISABLE | — | — | — | — | |
| SETTILE | — | — | — | — | |
| GETTILE | — | — | — | — | |
| SCROLLX | — | — | — | — | |
| SCROLLY | — | — | — | — | |
| CLS | — | — | — | — | |
| PIXEL | — | — | — | — | |
| LINE | — | — | — | — | |
| RECT | — | — | — | — | |
| COLCHECK | ✓ | — | ✓ | — | Z=1 means no collision |
| COLSPR1/2 | — | — | — | — | |
| INPUT | — | — | — | — | |
| BUTTON | ✓ | — | ✓ | — | Z=1 means button not pressed |
| WAITVBLANK | — | — | — | — | |
| TIMER | — | — | — | — | |
| SETBANK | — | — | — | — | |
| GETBANK | — | — | — | — | |
| VRAMWR | — | — | — | — | |
| VRAMRD | — | — | — | — | |
| PCMWR | — | — | — | — | |
| PCMRD | — | — | — | — | |
| SEI | — | — | — | — | |
| CLI | — | — | — | — | |
| RETI | ✓ | ✓ | ✓ | ✓ | Restores FL from stack |
| TRIG | — | — | — | — | |

---

## Appendix B — Sprite Flags Bitmask

```
Bit 0  (mask 0x01)  visible     1 = sprite is rendered and checked for collisions
Bit 1  (mask 0x02)  flip_x      1 = mirror sprite horizontally
Bit 2  (mask 0x04)  flip_y      1 = mirror sprite vertically
Bit 3  (mask 0x08)  priority    Reserved (not yet implemented)
Bits 4–15           Reserved
```

Setting from Python:
```python
s = cpu.gpu.sprites[0]
s.flags |= 0x01          # enable
s.flags |= 0x02          # flip_x on
s.flags &= ~0x02         # flip_x off
s.flags = 0x01 | 0x04   # visible + flip_y
```

---

## Appendix C — Controller Bitmask

The `REG_CONTROLLER_1` register (0xFF00) and `cpu.controller1` use this bitmask:

| Bit | Mask | Button | PygameRenderer Key |
|---|---|---|---|
| 0 | 0x01 | UP | Arrow Up |
| 1 | 0x02 | DOWN | Arrow Down |
| 2 | 0x04 | LEFT | Arrow Left |
| 3 | 0x08 | RIGHT | Arrow Right |
| 4 | 0x10 | A | Z |
| 5 | 0x20 | B | X |
| 6 | 0x40 | START | Enter |
| 7 | 0x80 | SELECT | Right Shift |

Setting from Python (for automated testing / scripted input):
```python
cpu.controller1 = 0x01 | 0x10   # UP + A pressed
cpu.controller1 = 0x00           # all released
```

When `cpu_ref` is passed to `PygameRenderer`, the renderer automatically updates `cpu.controller1` each frame from keyboard state.

---

## Appendix D — RGB565 Common Colors

| Color | RGB565 | Hex | R,G,B |
|---|---|---|---|
| Black | 0x0000 | 0b0000000000000000 | 0,0,0 |
| White | 0xFFFF | 0b1111111111111111 | 255,255,255 |
| Red | 0xF800 | 0b1111100000000000 | 248,0,0 |
| Green | 0x07E0 | 0b0000011111100000 | 0,255,0 |
| Blue | 0x001F | 0b0000000000011111 | 0,0,248 |
| Yellow | 0xFFE0 | 0b1111111111100000 | 255,255,0 |
| Cyan | 0x07FF | 0b0000011111111111 | 0,255,255 |
| Magenta | 0xF81F | 0b1111100000011111 | 255,0,255 |
| Orange | 0xFC00 | 0b1111110000000000 | 255,128,0 |
| Dark Gray | 0x4208 | | 64,64,64 |
| Light Gray | 0xC618 | | 192,192,192 |
| Transparent | 0x0000 | | (same as black; treated as transparent in sprites) |

**Encoding formula:**
```python
def rgb888_to_565(r, g, b):
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)

def rgb565_to_888(c):
    r = ((c >> 11) & 0x1F) << 3
    g = ((c >>  5) & 0x3F) << 2
    b = ( c        & 0x1F) << 3
    return r, g, b
```

Note: Because black (0,0,0) encodes to 0x0000, which is the sprite transparency color, sprites cannot have opaque black pixels. Use color (8,8,8) or similar near-black as a substitute.

---

## Appendix E — Error Reference

### CPUFault

Raised when the CPU detects an architectural violation at runtime.

| Condition | Message |
|---|---|
| Invalid register index | `Invalid register index R{n} at PC=0x{addr}. GMC-16 has R0-R7 only.` |
| Unknown opcode | `Unknown opcode 0x{op} at PC=0x{addr}` |
| SETBANK out of range | `SETBANK: bank {n} out of range (0-21).` |

### ValueError (Assembler)

| Condition | Message |
|---|---|
| Unknown mnemonic | `Unknown mnemonic: '{mnem}'` |
| Undefined symbol | `Undefined symbol: '{name}'` |
| Register in expression | `Register '{name}' used where a constant expression is expected.` |
| Unsafe expression | `Unsafe expression: '{expr}'` |
| Fixed bank overflow | `Fixed bank overflow: {n} bytes at offset 0x{off} exceeds {size} bytes.` |
| Bank out of range | `BANK directive: bank {n} out of range.` |
| ROM overflow (load_rom) | `ROM overflow: {n} bytes exceeds fixed + bank0 ({m} bytes).` |

### Common Programming Mistakes

**Forgetting WAITVBLANK:** Without WAITVBLANK, the game loop runs as fast as the Python interpreter allows — typically thousands of frames per second — making the game unplayably fast and burning 100% CPU.

**Jumping to banked code from wrong bank:** A CALL or JMP to a label in the banked window (0x4000–0xFEFF) will execute whatever bank is currently loaded. Always ensure the correct bank is active before such jumps.

**Stack overflow:** The stack grows downward from RAM_END (0x1FFE). Deep recursion or too many PUSHes without POPs will eventually overwrite program data or code in RAM. GMC-16 has no hardware stack overflow detection.

**Transparent black in sprites:** RGB565 value 0x0000 (pure black) is treated as transparent in sprite tile pixels. To render an opaque black-colored sprite, use a very dark near-black like 0x0821 (R=8,G=8,B=8).

**IVT not initialized:** If interrupts are enabled (SEI + IE bits set) but the IVT entries are zero or contain invalid addresses, interrupts will jump to address 0x0000 (RAM), which will execute garbage as instructions. Always install handler addresses in the IVT before enabling interrupts.

**RETI instead of RET:** Using RET inside an interrupt handler will return to the correct address but will leave IME=False (interrupts remain disabled). Always use RETI in interrupt handlers.

**Bank switching mid-instruction-stream:** Do not SETBANK while the PC is currently fetching instructions from the banked window, or the next fetch will come from the new bank at the same address — which is different code. All bank switches should happen from the fixed bank or right before a JMP to the target bank's known entry point.

---

*GMC-16 Technical Reference v7 — Complete Architecture Documentation*
*For the GMC-16 Python emulator, Game Machine CPU — 16-Bit*
