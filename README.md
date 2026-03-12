# GMC-16

GMC-16 — a small fantasy console with a custom CPU, graphics system, sound chip, and assembler, implemented in Python.

---

## What is it?

The GMC-16 is a 16-bit console, not just a CPU. It consists of a double-framebuffer GPU capable of rendering graphics using a tile engine with 64KB of VRAM. It also includes an APU capable of generating 16-bit mono audio.

The goal of the project is to simulate a simple retro-style game console with its own architecture, instruction set, and development tools.

---

## Features

### Custom 16-bit CPU

The GMC-16 CPU is a custom-designed architecture created specifically for this console.

* 16-bit architecture
* 8 general purpose registers
* flags register (Z, C, N, O)
* stack support (CALL / RET / PUSH / POP)
* branching and control flow instructions
* memory-mapped I/O

Programs for the GMC-16 are written in its own assembly language and assembled into ROMs.

---

### GPU (Graphics Processing Unit)

The GMC-16 GPU provides simple but flexible 2D rendering.

* 256 × 128 resolution
* RGB565 color format
* double framebuffer for tear-free rendering
* 64 KB VRAM
* tile engine
* sprite support
* hardware commands accessible through memory-mapped registers

Rendering commands include primitives such as rectangles, tiles, sprites, and framebuffer flipping.

---

### APU (Audio Processing Unit)

The GMC-16 includes a built-in audio system capable of generating simple game audio.

* 4 audio channels
* 16-bit mono output
* ~22 kHz sample rate
* multiple waveform types (square, triangle, sine, saw, noise)
* PCM playback support

The APU runs independently of the CPU once configured.

---

### Assembler

A custom assembler is included for writing GMC-16 programs.

Features include:

* labels
* constants (`EQU`)
* expressions
* ROM generation
* bank support

Example:

```
LOADI R0, 10
ADD   R1, R0
JMP   LOOP
```

---

### Example Programs

The repository includes example software written for the console.

Current examples:

* Pong (two-player)

These programs demonstrate how to write games directly in GMC-16 assembly.

---

## Project Goals

The GMC-16 is designed as a learning and experimentation platform for:

* low-level programming
* CPU architecture design
* console-style game development
* emulator development

The system intentionally resembles classic game consoles where cartridges contain the full game and run directly on boot.

---

## License

GMC-16 is licensed under the GNU GPL v3.

This ensures that the console, emulator, and development tools remain free and open-source forever.
