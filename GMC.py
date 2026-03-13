"""
GMC-16 CPU Emulator
Game Machine CPU - 16 Bit
Based on GMC-16 Console Architecture Specification v1.0

Changelog
---------
v1  Initial implementation.
v2  Collision O(n^2), explicit memory map, GPU command register,
    DIV flag fix, ADD overflow clarity, expression assembler, cycle timing.
v3  ROM overflow, register bounds, drift-free VBlank, debug mode, framebuffer API.
v4  Bankswitching up to 1 MB total cartridge space.
v5  VRAM-backed tile engine: 8×8 tiles, 32×16 tilemap, scroll/flip, VRAMWR/VRAMRD.
v6  Mono 16-bit APU with pyaudio backend. 4 channels.
v7  (this version)
    Hardware interrupt system: IVT, IME, IE/IF registers.
    8 sources: VBLANK, TIMER, INPUT, APU, IRQ0-3.
    New opcodes: SEI 0x3A, CLI 0x3B, RETI 0x3C, TRIG 0x3D.
    4 channels: square / sine / triangle / sawtooth / noise / PCM.
    22 050 Hz sample rate, background thread, optional pyaudio (silent fallback).
    8 KB audio RAM for PCM samples (PCMWR / PCMRD CPU instructions).
    IO registers 0xFF50-0xFF59 (REG_APU_*).
    New opcodes: PCMWR 0x38, PCMRD 0x39.
    APU commands: PLAY_TONE 0x01, PLAY_NOISE 0x02, STOP 0x03, STOP_ALL 0x04, PLAY_PCM 0x05.
    - Fixed bank:  0x2000-0x3FFF (8 KB, always visible, bank 0)
    - Banked window: 0x4000-0xFEFF (48 KB window, 22 switchable banks)
    - Total addressable ROM: 8 KB + 22 * 48 KB = 1,064 KB > 1 MB
    - IO register 0xFF30 (REG_BANK): write to switch bank, read current bank
    - Two new CPU opcodes: SETBANK imm (0x34), GETBANK Rd (0x35)
    - MemoryBus.load_bank(bank, data) loads cartridge data per bank
    - Assembler: BANK <n> directive switches output target bank
    - Assembler: BUILTINS BANK_FIXED_START, BANK_WIN_START, BANK_WIN_END,
                           BANK_SIZE, BANK_WIN_SIZE, NUM_BANKS
"""

import math
import random
import re
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional


# =============================================================
# MEMORY MAP
# =============================================================
#
#   0x0000 - 0x1FFF   RAM   (8 KB, read/write)
#   0x2000 - 0xFEFF   ROM   (read-only; writes silently ignored)
#   0xFF00 - 0xFFFF   IO    (memory-mapped hardware registers)
#
RAM_START = 0x0000
RAM_END   = 0x1FFF
ROM_START = 0x2000
ROM_END   = 0xFEFF
IO_START  = 0xFF00
IO_END    = 0xFFFF

RAM_SIZE  = RAM_END - RAM_START + 1    # 8 192
ROM_SIZE  = ROM_END - ROM_START + 1    # 57 088
IO_SIZE   = IO_END  - IO_START  + 1   # 256
TOTAL_MEM = 0x10000

VRAM_SIZE = 0x10000
SCREEN_W  = 256
SCREEN_H  = 128

# =============================================================
# VRAM LAYOUT  (v5 -- tile engine)
# =============================================================
#
#  VRAM is a 64 KB address space separate from RAM/ROM.
#  Accessed by the CPU via VRAMWR/VRAMRD instructions, and
#  read internally by the GPU during tile and sprite rendering.
#
#  0x0000-0x3FFF  Tile pixel data
#                  256 tiles × 8×8 px × 2 bytes (RGB565) = 32 768 bytes
#                  Tile N base: VRAM_TILE_BASE + N * TILE_BYTES
#                  Pixels stored row-major, 2 bytes each (little-endian).
#
#  0x4000-0x47FF  Tilemap  (32 cols × 16 rows × 2 bytes = 1 024 bytes)
#                  Entry at (col, row): VRAM_MAP_BASE + (row*32 + col)*2
#                  Bits [7:0]  = tile index (0-255)
#                  Bit  [8]    = flip-X
#                  Bit  [9]    = flip-Y
#
#  0x4800-0xFFFF  Free (sprite sheets, user data)
#
TILE_W         = 8
TILE_H         = 8
TILE_BYTES     = TILE_W * TILE_H * 2           # 128 bytes per tile
MAX_TILES      = 256
TILEMAP_COLS   = 32
TILEMAP_ROWS   = 16

VRAM_TILE_BASE = 0x0000
VRAM_TILE_END  = VRAM_TILE_BASE + MAX_TILES * TILE_BYTES - 1   # 0x3FFF
VRAM_MAP_BASE  = 0x4000
VRAM_MAP_END   = VRAM_MAP_BASE + TILEMAP_COLS * TILEMAP_ROWS * 2 - 1  # 0x47FF
VRAM_USER_BASE = 0x4800

# =============================================================
# INTERRUPT SYSTEM  (v7)
# =============================================================
#  IVT (top of fixed ROM): 0x3FF0 VBLANK 0x3FF2 TIMER 0x3FF4 INPUT
#                           0x3FF6 APU    0x3FF8-0x3FFE IRQ0-3
#  IE=0xFF80 enable mask   IF=0xFF81 pending flags
#  bit0=VBLANK bit1=TIMER bit2=INPUT bit3=APU bits4-7=IRQ0-3
IVT_BASE    = 0x3FF0
IVT_VBLANK  = 0x3FF0
IVT_TIMER   = 0x3FF2
IVT_INPUT   = 0x3FF4
IVT_APU     = 0x3FF6
IVT_IRQ0    = 0x3FF8
IVT_IRQ1    = 0x3FFA
IVT_IRQ2    = 0x3FFC
IVT_IRQ3    = 0x3FFE
INT_VBLANK  = 0x01
INT_TIMER   = 0x02
INT_INPUT   = 0x04
INT_APU     = 0x08
INT_IRQ0    = 0x10
INT_IRQ1    = 0x20
INT_IRQ2    = 0x40
INT_IRQ3    = 0x80

# =============================================================
# BANKSWITCHING  (v4)
# =============================================================
#
#  ROM window split:
#   0x2000-0x3FFF  FIXED BANK (8 KB, always bank 0, never paged)
#   0x4000-0xFEFF  BANKED WINDOW (~48 KB, one of NUM_BANKS switchable banks)
#
#  Physical layout:  bank N starts at N * BANK_WIN_SIZE bytes into cartridge.
#  Total: 8 KB fixed + 22 * 48 KB banked = 1,064 KB > 1 MB.
#
#  Control: write bank number (0-21) to REG_BANK (0xFF30).
#  New instructions: SETBANK imm  (0x34),  GETBANK Rd  (0x35).
#
BANK_FIXED_START = ROM_START           # 0x2000
BANK_FIXED_END   = 0x3FFF
BANK_FIXED_SIZE  = BANK_FIXED_END - BANK_FIXED_START + 1  # 8 192

BANK_WIN_START   = 0x4000
BANK_WIN_END     = ROM_END             # 0xFEFF
BANK_WIN_SIZE    = BANK_WIN_END - BANK_WIN_START + 1       # 49 152 (~48 KB)

NUM_BANKS        = 22                  # banks 0-21
MAX_CART_SIZE    = BANK_FIXED_SIZE + NUM_BANKS * BANK_WIN_SIZE  # >1 MB


# =============================================================
# HARDWARE REGISTERS (IO region 0xFF00-0xFFFF)
# =============================================================

REG_CONTROLLER_1    = 0xFF00
REG_GPU_COMMAND     = 0xFF10
REG_GPU_X           = 0xFF11
REG_GPU_Y           = 0xFF12
REG_GPU_COLOR       = 0xFF13
REG_COLLISION_FLAG  = 0xFF20
REG_COLLISION_SPR_A = 0xFF21
REG_COLLISION_SPR_B = 0xFF22
REG_BANK            = 0xFF30   # write: select bank 0-21; read: current bank
# VRAM DMA port (v5)
REG_VRAM_ADDR_LO    = 0xFF40   # lo byte of VRAM address
REG_VRAM_ADDR_HI    = 0xFF41   # hi byte of VRAM address
REG_VRAM_DATA_LO    = 0xFF42   # lo byte of VRAM data (read/write)
REG_VRAM_DATA_HI    = 0xFF43   # hi byte; writing this commits word to VRAM
# APU registers (v6)  0xFF50-0xFF59
REG_APU_CMD         = 0xFF50   # write: APU command (see ApuCmd)
REG_APU_CHAN        = 0xFF51   # target channel 0-3
REG_APU_FREQ_LO     = 0xFF52   # frequency lo byte (Hz, 16-bit)
REG_APU_FREQ_HI     = 0xFF53   # frequency hi byte
REG_APU_VOL         = 0xFF54   # volume 0-255
REG_APU_WAVE        = 0xFF55   # waveform: 0=square 1=sine 2=triangle 3=sawtooth
REG_APU_PCM_LO      = 0xFF56   # PCM sample start address lo (word index)
REG_APU_PCM_HI      = 0xFF57   # PCM sample start address hi
REG_APU_PCM_LEN_LO  = 0xFF58   # PCM sample length lo (in samples)
REG_APU_PCM_LEN_HI  = 0xFF59   # PCM sample length hi
REG_IE              = 0xFF80   # Interrupt Enable  (bitmask)
REG_IF              = 0xFF81   # Interrupt Flags   (write 0 to clear)
REG_TIMER_PERIOD_LO = 0xFF82   # timer period lo byte (cycles; 0=off)
REG_TIMER_PERIOD_HI = 0xFF83   # timer period hi byte


# =============================================================
# GPU COMMANDS
# =============================================================

class GpuCmd:
    CLEAR        = 0x01   # fill back-buffer with REG_GPU_COLOR
    DRAW_SPRITES = 0x02   # blit all visible sprites onto back-buffer
    FLIP_BUFFER  = 0x03   # swap front/back, fire on_flip_buffer()
    DRAW_TILEMAP = 0x04   # render tilemap into back-buffer (before sprites)


# =============================================================
# APU COMMANDS
# =============================================================

class ApuCmd:
    PLAY_TONE  = 0x01   # play tone on channel (freq, vol, wave)
    PLAY_NOISE = 0x02   # white noise on channel (vol)
    STOP       = 0x03   # stop channel
    STOP_ALL   = 0x04   # silence all channels
    PLAY_PCM   = 0x05   # play PCM from audio RAM (addr, len)


APU_SAMPLE_RATE  = 22050          # Hz
APU_CHANNELS     = 4              # independent sound channels (0-3)
APU_CHUNK        = 512            # samples per pyaudio callback chunk
APU_AUDIO_RAM    = 8192           # 8 KB = 4 096 × 16-bit samples
APU_MAX_SAMPLES  = APU_AUDIO_RAM // 2

WAVE_SQUARE   = 0
WAVE_SINE     = 1
WAVE_TRIANGLE = 2
WAVE_SAWTOOTH = 3
WAVE_NOISE    = 4   # used internally; set via PLAY_NOISE command


# =============================================================
# FLAGS
# =============================================================

FLAG_Z = 0b0001
FLAG_C = 0b0010
FLAG_N = 0b0100
FLAG_O = 0b1000


# =============================================================
# COLLISION TYPES
# =============================================================

COL_NONE   = 0
COL_PLAYER = 1
COL_ENEMY  = 2
COL_BULLET = 3
COL_ITEM   = 4


# =============================================================
# CYCLE TABLE
# =============================================================

CYCLE_TABLE: dict[int, int] = {
    0x00: 1,  0x01: 1,   # NOP, HALT
    0x02: 1,  0x03: 2,   # MOV, LOAD
    0x04: 2,  0x05: 2,   # STORE, LOADI
    0x06: 1,             # SWAP
    0x07: 1,  0x08: 1,   # ADD, SUB
    0x09: 3,  0x0A: 6,   # MUL, DIV
    0x0B: 1,  0x0C: 1,   # INC, DEC
    0x0D: 1,  0x0E: 1,   # NEG, ABS
    0x0F: 1,  0x10: 1,   # AND, OR
    0x11: 1,  0x12: 1,   # XOR, NOT
    0x13: 1,  0x14: 1,   # SHL, SHR
    0x15: 1,             # CMP
    0x16: 3,  0x17: 3,   # JMP, JZ   (taken; not-taken -> 1)
    0x18: 3,  0x19: 3,   # JNZ, JG
    0x1A: 3,             # JL
    0x1B: 2,  0x1C: 2,   # PUSH, POP
    0x1D: 4,  0x1E: 4,   # CALL, RET
    0x1F: 1,             # RAND
    0x20: 5,  0x21: 5,   # SPRITEPOS, SPRITEMOVE
    0x22: 5,  0x23: 2,   # SPRITEIMG, SPRITEENABLE
    0x24: 2,             # SPRITEDISABLE
    0x25: 3,  0x26: 3,   # SETTILE, GETTILE
    0x27: 2,  0x28: 2,   # SCROLLX, SCROLLY
    0x29: 8,  0x2A: 4,   # CLS, PIXEL
    0x2B: 8,  0x2C: 8,   # LINE, RECT
    0x2D: 5,  0x2E: 1,   # COLCHECK, COLSPR1
    0x2F: 1,             # COLSPR2
    0x30: 1,  0x31: 1,   # INPUT, BUTTON
    0x32: 1,  0x33: 1,   # WAITVBLANK, TIMER
    0x34: 2,  0x35: 1,   # SETBANK, GETBANK
    0x36: 3,  0x37: 3,   # VRAMWR, VRAMRD
    0x38: 3,  0x39: 3,   # PCMWR, PCMRD
    0x3A: 1,  0x3B: 1,   # SEI, CLI
    0x3C: 4,  0x3D: 2,   # RETI, TRIG
}

# Mnemonic name lookup (opcode -> name) used by the disassembler
_OPCODE_NAMES: dict[int, str] = {
    0x00:"NOP",   0x01:"HALT",  0x02:"MOV",    0x03:"LOAD",
    0x04:"STORE", 0x05:"LOADI", 0x06:"SWAP",   0x07:"ADD",
    0x08:"SUB",   0x09:"MUL",   0x0A:"DIV",    0x0B:"INC",
    0x0C:"DEC",   0x0D:"NEG",   0x0E:"ABS",    0x0F:"AND",
    0x10:"OR",    0x11:"XOR",   0x12:"NOT",    0x13:"SHL",
    0x14:"SHR",   0x15:"CMP",   0x16:"JMP",    0x17:"JZ",
    0x18:"JNZ",   0x19:"JG",   0x1A:"JL",     0x1B:"PUSH",
    0x1C:"POP",   0x1D:"CALL", 0x1E:"RET",    0x1F:"RAND",
    0x20:"SPRITEPOS",   0x21:"SPRITEMOVE", 0x22:"SPRITEIMG",
    0x23:"SPRITEENABLE",0x24:"SPRITEDISABLE",
    0x25:"SETTILE",     0x26:"GETTILE",
    0x27:"SCROLLX",     0x28:"SCROLLY",
    0x29:"CLS",   0x2A:"PIXEL", 0x2B:"LINE",  0x2C:"RECT",
    0x2D:"COLCHECK",    0x2E:"COLSPR1",    0x2F:"COLSPR2",
    0x30:"INPUT", 0x31:"BUTTON",0x32:"WAITVBLANK",0x33:"TIMER",
    0x34:"SETBANK", 0x35:"GETBANK",
    0x36:"VRAMWR",  0x37:"VRAMRD",
    0x38:"PCMWR",   0x39:"PCMRD",
    0x3A:"SEI",     0x3B:"CLI",
    0x3C:"RETI",    0x3D:"TRIG",
}


# =============================================================
# EXCEPTIONS
# =============================================================

class CPUFault(RuntimeError):
    """Raised for architectural violations detected at runtime."""


# =============================================================
# SPRITE
# =============================================================

@dataclass
class Sprite:
    x: int = 0
    y: int = 0
    tile_index: int = 0
    flags: int = 0
    collision_type: int = 0

    @property
    def visible(self):  return bool(self.flags & 0x01)
    @property
    def flip_x(self):   return bool(self.flags & 0x02)
    @property
    def flip_y(self):   return bool(self.flags & 0x04)
    @property
    def priority(self): return bool(self.flags & 0x08)


# =============================================================
# FRAMEBUFFER DISPLAY API  (Fix #5)
# =============================================================

class FramebufferRenderer:
    """
    Base class for displaying the GMC-16 framebuffer from Python.

    Subclass this and attach it to a GPU instance to receive
    frame-complete callbacks:

        class MyRenderer(FramebufferRenderer):
            def render(self, pixels: list[int], width: int, height: int):
                # pixels is a flat list of RGB565 ints, row-major
                ...

        gpu = GPU()
        gpu.renderer = MyRenderer()
        cpu = GMC16CPU(gpu)

    Alternatively, use the built-in helpers:
        NullRenderer        -- no-op (default)
        PygameRenderer      -- renders via pygame (requires pygame install)
        CallbackRenderer    -- calls a user-supplied function each frame

    RGB565 helpers:
        rgb565_to_rgb(pixel) -> (r, g, b)  each 0-255
        rgb565_to_bytes(pixels) -> bytes   flat RGB bytes for PIL / numpy
    """

    def render(self, pixels: list[int], width: int, height: int) -> None:
        """Called once per frame after CMD_FLIP_BUFFER. Override in subclass."""

    # --- Static colour conversion helpers -----------------------

    @staticmethod
    def rgb565_to_rgb(pixel: int) -> tuple[int, int, int]:
        """Unpack a 16-bit RGB565 value to (r, g, b) each in 0-255."""
        r = ((pixel >> 11) & 0x1F) << 3
        g = ((pixel >>  5) & 0x3F) << 2
        b = ( pixel        & 0x1F) << 3
        return r, g, b

    @staticmethod
    def rgb565_to_bytes(pixels: list[int]) -> bytes:
        """Convert the flat RGB565 pixel list to packed RGB bytes (3 bytes/pixel)."""
        out = bytearray(len(pixels) * 3)
        for i, p in enumerate(pixels):
            r = ((p >> 11) & 0x1F) << 3
            g = ((p >>  5) & 0x3F) << 2
            b = ( p        & 0x1F) << 3
            out[i*3    ] = r
            out[i*3 + 1] = g
            out[i*3 + 2] = b
        return bytes(out)


class NullRenderer(FramebufferRenderer):
    """No-op renderer. Used by default so GPU works without a display."""


class CallbackRenderer(FramebufferRenderer):
    """Calls a user-supplied function each frame.

    Example:
        def my_hook(pixels, w, h):
            print(f"Frame: {len(pixels)} pixels")

        gpu.renderer = CallbackRenderer(my_hook)
    """

    def __init__(self, fn: Callable[[list[int], int, int], None]):
        self._fn = fn

    def render(self, pixels: list[int], width: int, height: int) -> None:
        self._fn(pixels, width, height)


class PygameRenderer(FramebufferRenderer):
    """
    Renders the GMC-16 framebuffer into a pygame window.

    Requires:  pip install pygame

    Usage:
        gpu = GPU()
        gpu.renderer = PygameRenderer(scale=3)   # 768x384 window
        cpu = GMC16CPU(gpu)
        cpu.bus.load_rom(rom)
        cpu.reset()
        cpu.run()

    Controller input:
        The renderer maps keyboard keys to controller1 bits.
        Pass a reference to the CPU so it can update controller1:

        gpu.renderer = PygameRenderer(scale=3, cpu_ref=cpu)

    Default key bindings:
        Arrow keys -> UP/DOWN/LEFT/RIGHT
        Z          -> A button
        X          -> B button
        Enter      -> START
        Right Shift-> SELECT
    """

    # Controller bit masks matching the spec
    BTN_UP     = 0x01
    BTN_DOWN   = 0x02
    BTN_LEFT   = 0x04
    BTN_RIGHT  = 0x08
    BTN_A      = 0x10
    BTN_B      = 0x20
    BTN_START  = 0x40
    BTN_SELECT = 0x80

    def __init__(self, scale: int = 2, title: str = "GMC-16",
                 cpu_ref: Optional["GMC16CPU"] = None):
        try:
            import pygame
            self._pygame = pygame
        except ImportError:
            raise ImportError(
                "PygameRenderer requires pygame. Install it with: pip install pygame"
            )
        self._scale   = scale
        self._cpu_ref = cpu_ref
        self._surface = None
        self._screen  = None
        self._init_display(title)

        # Key -> controller bit mapping
        self._keymap = {
            pygame.K_UP:     self.BTN_UP,
            pygame.K_DOWN:   self.BTN_DOWN,
            pygame.K_LEFT:   self.BTN_LEFT,
            pygame.K_RIGHT:  self.BTN_RIGHT,
            pygame.K_z:      self.BTN_A,
            pygame.K_x:      self.BTN_B,
            pygame.K_RETURN: self.BTN_START,
            pygame.K_RSHIFT: self.BTN_SELECT,
        }

    def _init_display(self, title: str):
        pygame = self._pygame
        if not pygame.get_init():
            pygame.init()
        w = SCREEN_W * self._scale
        h = SCREEN_H * self._scale
        self._screen  = pygame.display.set_mode((w, h))
        self._surface = pygame.Surface((SCREEN_W, SCREEN_H))
        pygame.display.set_caption(title)

    def render(self, pixels: list[int], width: int, height: int) -> None:
        pygame = self._pygame

        # Handle quit + keyboard input
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                raise SystemExit

        # Update controller state from held keys
        if self._cpu_ref is not None:
            keys    = pygame.key.get_pressed()
            buttons = 0
            for key, bit in self._keymap.items():
                if keys[key]:
                    buttons |= bit
            self._cpu_ref.controller1 = buttons

        # Blit pixels to surface
        surf_array = pygame.surfarray.pixels2d(self._surface)
        for y in range(height):
            for x in range(width):
                r, g, b = self.rgb565_to_rgb(pixels[y * width + x])
                surf_array[x, y] = (r << 16) | (g << 8) | b
        del surf_array

        # Scale up and display
        scaled = pygame.transform.scale(
            self._surface,
            (width * self._scale, height * self._scale)
        )
        self._screen.blit(scaled, (0, 0))
        pygame.display.flip()

    def close(self):
        self._pygame.quit()


# =============================================================
# GPU
# =============================================================

class GPU:
    """
    GMC-16 GPU  (v5 -- VRAM-backed tile engine).

    VRAM layout (64 KB):
      0x0000-0x3FFF  Tile pixel data: 256 tiles × 128 bytes (8×8 × RGB565)
      0x4000-0x47FF  Tilemap: 32×16 entries, 2 bytes each
                       bits [7:0] = tile_id, bit [8] = flip-X, bit [9] = flip-Y
      0x4800-0xFFFF  Free

    Rendering order each frame:
      CLEAR → DRAW_TILEMAP → DRAW_SPRITES → FLIP_BUFFER

    Transparency: colour 0x0000 in a sprite's tile pixels is transparent.
    Tilemap pixels are always opaque (tile 0 = background colour).
    """

    SPRITE_COUNT = 256
    SPRITE_W     = 16     # sprites are 2×2 tiles = 16×16 px
    SPRITE_H     = 16

    def __init__(self):
        self.vram    = bytearray(VRAM_SIZE)   # 64 KB, sole backing store for tiles+map
        self.sprites = [Sprite() for _ in range(self.SPRITE_COUNT)]
        self.scroll_x = 0
        self.scroll_y = 0

        self.collision_flag  = 0
        self.collision_spr_a = 0
        self.collision_spr_b = 0

        self.framebuffer      = [0] * (SCREEN_W * SCREEN_H)
        self.back_framebuffer = [0] * (SCREEN_W * SCREEN_H)
        self.renderer: FramebufferRenderer = NullRenderer()
        self._irq_callback = None

    # --- VRAM word access ----------------------------------------

    def vram_read(self, vaddr: int) -> int:
        """Read a 16-bit word from VRAM (little-endian)."""
        a = vaddr & 0xFFFF
        return self.vram[a] | (self.vram[(a + 1) & 0xFFFF] << 8)

    def vram_write(self, vaddr: int, value: int):
        """Write a 16-bit word to VRAM (little-endian)."""
        a = vaddr & 0xFFFF
        v = value & 0xFFFF
        self.vram[a]               = v & 0xFF
        self.vram[(a + 1) & 0xFFFF] = (v >> 8) & 0xFF

    # --- Tile pixel API ------------------------------------------

    def load_tile(self, tile_id: int, pixels: list):
        """Load a full 8×8 tile from 64 RGB565 values (row-major)."""
        if not (0 <= tile_id < MAX_TILES):
            return
        base = VRAM_TILE_BASE + tile_id * TILE_BYTES
        for i, c in enumerate(pixels[:TILE_W * TILE_H]):
            off = base + i * 2
            self.vram[off]     = c & 0xFF
            self.vram[off + 1] = (c >> 8) & 0xFF

    def write_tile_pixel(self, tile_id: int, px: int, py: int, color: int):
        """Write one pixel into a tile's VRAM data."""
        if not (0 <= tile_id < MAX_TILES and 0 <= px < TILE_W and 0 <= py < TILE_H):
            return
        self.vram_write(VRAM_TILE_BASE + tile_id * TILE_BYTES + (py * TILE_W + px) * 2, color)

    def read_tile_pixel(self, tile_id: int, px: int, py: int) -> int:
        """Read one pixel from a tile's VRAM data."""
        if not (0 <= tile_id < MAX_TILES and 0 <= px < TILE_W and 0 <= py < TILE_H):
            return 0
        return self.vram_read(VRAM_TILE_BASE + tile_id * TILE_BYTES + (py * TILE_W + px) * 2)

    # --- Tilemap API (VRAM-backed) --------------------------------

    def _map_vaddr(self, col: int, row: int) -> int:
        return VRAM_MAP_BASE + (row * TILEMAP_COLS + col) * 2

    def set_tile(self, col: int, row: int, entry: int):
        """Write tilemap entry. bits [7:0]=tile_id, [8]=flipX, [9]=flipY."""
        if 0 <= col < TILEMAP_COLS and 0 <= row < TILEMAP_ROWS:
            self.vram_write(self._map_vaddr(col, row), entry)

    def get_tile(self, col: int, row: int) -> int:
        if 0 <= col < TILEMAP_COLS and 0 <= row < TILEMAP_ROWS:
            return self.vram_read(self._map_vaddr(col, row))
        return 0

    # --- GPU command dispatch ------------------------------------

    def execute_command(self, cmd: int, color: int):
        if   cmd == GpuCmd.CLEAR:        self._cmd_clear(color & 0xFFFF)
        elif cmd == GpuCmd.DRAW_TILEMAP: self._cmd_draw_tilemap()
        elif cmd == GpuCmd.DRAW_SPRITES: self._cmd_draw_sprites()
        elif cmd == GpuCmd.FLIP_BUFFER:  self._cmd_flip_buffer()

    def _cmd_clear(self, color: int):
        self.back_framebuffer = [color] * (SCREEN_W * SCREEN_H)

    def _cmd_draw_tilemap(self):
        """
        Render the visible tilemap window into the back-buffer.

        The full tilemap is 256×128 pixels (TILEMAP_COLS×TILEMAP_ROWS tiles).
        scroll_x / scroll_y offset the view; the map wraps seamlessly.
        Tile entry: bits [7:0] = tile_id, bit [8] = flip-X, bit [9] = flip-Y.
        All tilemap pixels are opaque (use CLEAR first to set background).
        """
        sx       = self.scroll_x & 0xFFFF
        sy       = self.scroll_y & 0xFFFF
        map_pw   = TILEMAP_COLS * TILE_W    # 256 px wide
        map_ph   = TILEMAP_ROWS * TILE_H    # 128 px tall
        vram     = self.vram                # local alias for speed
        fb       = self.back_framebuffer

        for sy_screen in range(SCREEN_H):
            src_y    = (sy_screen + sy) % map_ph
            tile_row = src_y  // TILE_H
            ty       = src_y  %  TILE_H
            row_off  = sy_screen * SCREEN_W

            for sx_screen in range(SCREEN_W):
                src_x    = (sx_screen + sx) % map_pw
                tile_col = src_x  // TILE_W
                tx       = src_x  %  TILE_W

                # Tilemap entry from VRAM
                mva   = VRAM_MAP_BASE + (tile_row * TILEMAP_COLS + tile_col) * 2
                entry = vram[mva] | (vram[mva + 1] << 8)

                tid   = entry & 0xFF
                px_   = (TILE_W - 1 - tx) if (entry & 0x100) else tx
                py_   = (TILE_H - 1 - ty) if (entry & 0x200) else ty

                tva   = VRAM_TILE_BASE + tid * TILE_BYTES + (py_ * TILE_W + px_) * 2
                fb[row_off + sx_screen] = vram[tva] | (vram[tva + 1] << 8)

    def _cmd_draw_sprites(self):
        """
        Blit all visible sprites onto the back-buffer using VRAM tile data.
        Each sprite is 16x16 px built from 2x2 tiles starting at tile_index.
        Colour 0x0000 in tile pixel data is transparent.
        Honours sprite.flip_x (flags bit1) and sprite.flip_y (flags bit2).
        """
        vram = self.vram
        fb   = self.back_framebuffer

        for sprite in self.sprites:
            if not sprite.visible:
                continue
            base_tid = sprite.tile_index & 0xFF
            fx = sprite.flip_x
            fy = sprite.flip_y
            for sty in range(2):           # output sub-tile row (screen space)
                src_sty = (1 - sty) if fy else sty
                for stx in range(2):       # output sub-tile col (screen space)
                    src_stx = (1 - stx) if fx else stx
                    # Source tile index comes from the mirrored sub-tile position
                    tid   = (base_tid + src_sty * 2 + src_stx) & 0xFF
                    tbase = VRAM_TILE_BASE + tid * TILE_BYTES
                    for py in range(TILE_H):
                        src_py    = (TILE_H - 1 - py) if fy else py
                        sy_screen = sprite.y + sty * TILE_H + py
                        if not (0 <= sy_screen < SCREEN_H):
                            continue
                        for px in range(TILE_W):
                            src_px    = (TILE_W - 1 - px) if fx else px
                            sx_screen = sprite.x + stx * TILE_W + px
                            if not (0 <= sx_screen < SCREEN_W):
                                continue
                            off   = tbase + (src_py * TILE_W + src_px) * 2
                            color = vram[off] | (vram[off + 1] << 8)
                            if color:
                                fb[sy_screen * SCREEN_W + sx_screen] = color

    def _cmd_flip_buffer(self):
        self.framebuffer, self.back_framebuffer = (
            self.back_framebuffer, self.framebuffer
        )
        self.renderer.render(self.framebuffer, SCREEN_W, SCREEN_H)
        if self._irq_callback:
            self._irq_callback(INT_VBLANK)

    def set_irq_callback(self, cb):
        self._irq_callback = cb

    # --- Sprite control ------------------------------------------

    def sprite_set_pos(self, sid: int, x: int, y: int):
        if 0 <= sid < self.SPRITE_COUNT:
            self.sprites[sid].x = x & 0xFFFF
            self.sprites[sid].y = y & 0xFFFF

    def sprite_move(self, sid: int, dx: int, dy: int):
        if 0 <= sid < self.SPRITE_COUNT:
            self.sprites[sid].x = (self.sprites[sid].x + dx) & 0xFFFF
            self.sprites[sid].y = (self.sprites[sid].y + dy) & 0xFFFF

    def sprite_set_image(self, sid: int, tile: int):
        if 0 <= sid < self.SPRITE_COUNT:
            self.sprites[sid].tile_index = tile & 0xFFFF

    def sprite_enable(self, sid: int):
        if 0 <= sid < self.SPRITE_COUNT:
            self.sprites[sid].flags |= 0x01

    def sprite_disable(self, sid: int):
        if 0 <= sid < self.SPRITE_COUNT:
            self.sprites[sid].flags &= ~0x01

    # --- Direct draw ---------------------------------------------

    def cls(self, color: int):
        self.back_framebuffer = [color & 0xFFFF] * (SCREEN_W * SCREEN_H)

    def set_pixel(self, x: int, y: int, color: int):
        if 0 <= x < SCREEN_W and 0 <= y < SCREEN_H:
            self.back_framebuffer[y * SCREEN_W + x] = color & 0xFFFF

    def draw_line(self, x1: int, y1: int, x2: int, y2: int, color: int):
        color &= 0xFFFF
        dx, dy = abs(x2 - x1), abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy
        while True:
            self.set_pixel(x1, y1, color)
            if x1 == x2 and y1 == y2:
                break
            e2 = 2 * err
            if e2 > -dy: err -= dy; x1 += sx
            if e2 <  dx: err += dx; y1 += sy

    def draw_rect(self, x: int, y: int, w: int, h: int, color: int):
        color &= 0xFFFF
        for row in range(h):
            for col in range(w):
                self.set_pixel(x + col, y + row, color)

    # --- Collision -----------------------------------------------

    def check_collisions(self):
        self.collision_flag  = 0
        self.collision_spr_a = 0
        self.collision_spr_b = 0

        active: list[tuple[int, Sprite]] = [
            (i, s) for i, s in enumerate(self.sprites)
            if s.visible and s.collision_type != COL_NONE
        ]

        for ii in range(len(active)):
            for jj in range(ii + 1, len(active)):
                i, a = active[ii]
                j, b = active[jj]
                if (abs(a.x - b.x) < self.SPRITE_W and
                        abs(a.y - b.y) < self.SPRITE_H):
                    self.collision_flag  = 1
                    self.collision_spr_a = i
                    self.collision_spr_b = j
                    return


# =============================================================
# APU  (v6 -- mono 16-bit speaker)
# =============================================================

class _Channel:
    """State for one APU channel."""
    __slots__ = ("active","waveform","freq","vol","phase","pcm_start","pcm_len","pcm_pos")

    def __init__(self):
        self.active    = False
        self.waveform  = WAVE_SQUARE
        self.freq      = 440
        self.vol       = 128
        self.phase     = 0.0        # accumulated phase (0.0-1.0)
        self.pcm_start = 0          # word index into audio_ram
        self.pcm_len   = 0
        self.pcm_pos   = 0          # current playback word index


class APU:
    """
    GMC-16 Audio Processing Unit  (v6).

    4-channel mono synthesiser with an optional pyaudio backend.
    If pyaudio is not installed the APU operates in silent mode —
    all CPU instructions work and audio RAM is readable/writable,
    but no sound is produced.

    Channels 0-3 each support:
      - Square / sine / triangle / sawtooth wave at any frequency
      - White noise
      - PCM playback from audio RAM (8 KB = 4 096 × 16-bit samples)

    Audio RAM
    ---------
    8 KB of dedicated 16-bit sample storage.
    Write samples with the PCMWR CPU instruction (word-addressed).
    Read with PCMRD.
    Host Python can also call apu.write_audio_ram(addr, value) directly.

    Usage
    -----
        apu = APU()
        apu.start()          # launch background audio thread
        # ... configure via IO registers / CPU instructions ...
        apu.stop()           # when done

    IO registers are written via the MemoryBus; the APU is passed to
    MemoryBus so _io_write can call apu.handle_register_write().
    """

    def __init__(self):
        self._channels  = [_Channel() for _ in range(APU_CHANNELS)]
        self._audio_ram = bytearray(APU_AUDIO_RAM)   # 8 KB, 16-bit samples
        self._lock      = threading.Lock()
        self._stream    = None
        self._pa        = None
        self._running   = False
        self._irq_callback = None

        # Staging registers (written by IO writes before APU_CMD)
        self._reg_chan      = 0
        self._reg_freq      = 440
        self._reg_vol       = 128
        self._reg_wave      = WAVE_SQUARE
        self._reg_pcm_addr  = 0
        self._reg_pcm_len   = 0

    def set_irq_callback(self, cb):
        self._irq_callback = cb

    # --- Audio RAM -----------------------------------------------

    def write_audio_ram(self, word_addr: int, value: int):
        """Write a signed 16-bit sample to audio RAM at word address."""
        addr = (word_addr & 0x1FFF) * 2
        value &= 0xFFFF
        self._audio_ram[addr]     = value & 0xFF
        self._audio_ram[addr + 1] = (value >> 8) & 0xFF

    def read_audio_ram(self, word_addr: int) -> int:
        """Read a 16-bit sample from audio RAM. Returns unsigned 16-bit."""
        addr = (word_addr & 0x1FFF) * 2
        return self._audio_ram[addr] | (self._audio_ram[addr + 1] << 8)

    # --- Register staging + command dispatch ---------------------

    def handle_register_write(self, reg: int, value: int):
        """Called by MemoryBus._io_write for REG_APU_* addresses."""
        v = value & 0xFF
        if   reg == REG_APU_CHAN:       self._reg_chan     = v & 0x03
        elif reg == REG_APU_FREQ_LO:    self._reg_freq     = (self._reg_freq & 0xFF00) | v
        elif reg == REG_APU_FREQ_HI:    self._reg_freq     = (self._reg_freq & 0x00FF) | (v << 8)
        elif reg == REG_APU_VOL:        self._reg_vol      = v
        elif reg == REG_APU_WAVE:       self._reg_wave     = v & 0x07
        elif reg == REG_APU_PCM_LO:     self._reg_pcm_addr = (self._reg_pcm_addr & 0xFF00) | v
        elif reg == REG_APU_PCM_HI:     self._reg_pcm_addr = (self._reg_pcm_addr & 0x00FF) | (v << 8)
        elif reg == REG_APU_PCM_LEN_LO: self._reg_pcm_len  = (self._reg_pcm_len  & 0xFF00) | v
        elif reg == REG_APU_PCM_LEN_HI: self._reg_pcm_len  = (self._reg_pcm_len  & 0x00FF) | (v << 8)
        elif reg == REG_APU_CMD:
            self._dispatch_command(v)

    def _dispatch_command(self, cmd: int):
        ch = self._reg_chan
        with self._lock:
            if cmd == ApuCmd.PLAY_TONE:
                c = self._channels[ch]
                c.active   = True
                c.waveform = self._reg_wave
                c.freq     = max(1, self._reg_freq)
                c.vol      = self._reg_vol
                c.phase    = 0.0
            elif cmd == ApuCmd.PLAY_NOISE:
                c = self._channels[ch]
                c.active   = True
                c.waveform = WAVE_NOISE
                c.vol      = self._reg_vol
            elif cmd == ApuCmd.STOP:
                self._channels[ch].active = False
            elif cmd == ApuCmd.STOP_ALL:
                for c in self._channels:
                    c.active = False
            elif cmd == ApuCmd.PLAY_PCM:
                c = self._channels[ch]
                c.active    = True
                c.waveform  = -1          # sentinel: PCM mode
                c.pcm_start = self._reg_pcm_addr & 0x1FFF
                c.pcm_len   = max(1, self._reg_pcm_len)
                c.pcm_pos   = 0
                c.vol       = self._reg_vol

    # --- Sample generation ---------------------------------------

    def _generate_chunk(self, n_frames: int) -> bytes:
        """
        Mix n_frames samples from all active channels.
        Returns little-endian 16-bit signed PCM bytes.
        """
        dt  = 1.0 / APU_SAMPLE_RATE
        mix = [0.0] * n_frames

        with self._lock:
            for ch in self._channels:
                if not ch.active:
                    continue
                vol = ch.vol / 255.0

                if ch.waveform == -1:
                    # PCM playback
                    ram = self._audio_ram
                    for i in range(n_frames):
                        if ch.pcm_pos >= ch.pcm_len:
                            ch.active = False
                            if self._irq_callback:
                                self._irq_callback(INT_APU)
                            break
                        waddr = (ch.pcm_start + ch.pcm_pos) & 0x1FFF
                        raw   = ram[waddr * 2] | (ram[waddr * 2 + 1] << 8)
                        # Interpret as signed 16-bit
                        s     = raw if raw < 32768 else raw - 65536
                        mix[i] += (s / 32767.0) * vol
                        ch.pcm_pos += 1

                elif ch.waveform == WAVE_NOISE:
                    for i in range(n_frames):
                        mix[i] += (random.random() * 2.0 - 1.0) * vol

                else:
                    # Tone synthesis
                    freq  = ch.freq
                    phase = ch.phase
                    wave  = ch.waveform
                    for i in range(n_frames):
                        if   wave == WAVE_SQUARE:
                            s = 1.0 if phase < 0.5 else -1.0
                        elif wave == WAVE_SINE:
                            s = math.sin(2.0 * math.pi * phase)
                        elif wave == WAVE_TRIANGLE:
                            s = 1.0 - 4.0 * abs(phase - 0.5)
                        else:   # WAVE_SAWTOOTH
                            s = 2.0 * phase - 1.0
                        mix[i] += s * vol
                        phase += freq * dt
                        if phase >= 1.0:
                            phase -= 1.0
                    ch.phase = phase

        # Clamp, convert to int16, pack
        out = bytearray(n_frames * 2)
        for i, s in enumerate(mix):
            # Normalise by channel count to prevent clipping
            s = max(-1.0, min(1.0, s / APU_CHANNELS))
            sample = int(s * 32767)
            struct.pack_into('<h', out, i * 2, sample)
        return bytes(out)

    # --- pyaudio backend -----------------------------------------

    def start(self):
        """Open the pyaudio stream.  Silent if pyaudio unavailable."""
        if self._running:
            return
        try:
            import pyaudio as _pa
            self._pa = _pa.PyAudio()
            self._stream = self._pa.open(
                format            = _pa.paInt16,
                channels          = 1,
                rate              = APU_SAMPLE_RATE,
                output            = True,
                frames_per_buffer = APU_CHUNK,
                stream_callback   = self._callback,
            )
            self._stream.start_stream()
            self._running = True
        except Exception:
            # pyaudio not available or no audio device -- run silently
            self._running = False

    def _callback(self, in_data, frame_count, time_info, status):
        try:
            import pyaudio as _pa
            data = self._generate_chunk(frame_count)
            return (data, _pa.paContinue)
        except Exception:
            return (b'\x00' * frame_count * 2, 0)

    def stop(self):
        """Stop and close the pyaudio stream."""
        self._running = False
        try:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
            if self._pa:
                self._pa.terminate()
                self._pa = None
        except Exception:
            pass

    def __del__(self):
        self.stop()

    # --- Convenience (host-side) ---------------------------------

    def play_tone(self, channel: int, freq: int, vol: int = 200,
                  wave: int = WAVE_SQUARE):
        """Play a tone directly without going through IO registers."""
        with self._lock:
            c = self._channels[channel & 3]
            c.active   = True
            c.waveform = wave
            c.freq     = max(1, freq)
            c.vol      = vol
            c.phase    = 0.0

    def stop_channel(self, channel: int):
        with self._lock:
            self._channels[channel & 3].active = False

    def stop_all(self):
        with self._lock:
            for c in self._channels:
                c.active = False

    def is_active(self, channel: int) -> bool:
        return self._channels[channel & 3].active


# =============================================================
# MEMORY BUS
# =============================================================

class MemoryBus:
    """
    GMC-16 memory bus with bankswitching (v4).

    Map:  0x0000-0x1FFF RAM | 0x2000-0x3FFF Fixed ROM | 0x4000-0xFEFF Banked ROM | 0xFF00+ IO

    load_rom(data)           -- backward-compat: fills fixed then bank 0
    load_bank('fixed', data) -- load the fixed bank
    load_bank(n, data)       -- load banked bank n (0-21)
    switch_bank(n)           -- swap the banked window at runtime
    Write REG_BANK (0xFF30)  -- same as switch_bank from assembly
    """

    def __init__(self, gpu: GPU, apu: "APU | None" = None):
        self._ram       = bytearray(RAM_SIZE)
        self._rom_fixed = bytearray(BANK_FIXED_SIZE)
        self._rom_banks = [bytearray(BANK_WIN_SIZE) for _ in range(NUM_BANKS)]
        self._io        = bytearray(IO_SIZE)
        self._gpu       = gpu
        self._apu       = apu or APU()
        self._cur_bank  = 0

    # --- Cartridge loading ---------------------------------------

    def load_rom(self, data, offset: int = 0):
        """Backward-compatible loader. Also accepts a BankImage."""
        if isinstance(data, BankImage):
            data.load_into(self)
            return
        data = bytes(data)
        fixed_space = BANK_FIXED_SIZE - offset
        if len(data) <= fixed_space:
            if offset + len(data) > BANK_FIXED_SIZE:
                raise ValueError(
                    f"ROM overflow in fixed bank: {len(data)} bytes at offset "
                    f"0x{offset:04X} exceeds {BANK_FIXED_SIZE} bytes."
                )
            self._rom_fixed[offset:offset + len(data)] = data
        else:
            fixed_part  = data[:fixed_space]
            banked_part = data[fixed_space:]
            self._rom_fixed[offset:] = fixed_part
            if len(banked_part) > BANK_WIN_SIZE:
                raise ValueError(
                    f"ROM overflow: {len(data)} bytes exceeds fixed + bank0 "
                    f"({BANK_FIXED_SIZE + BANK_WIN_SIZE} bytes)."
                )
            self._rom_banks[0][:len(banked_part)] = banked_part

    def load_bank(self, bank, data: bytes, offset: int = 0):
        """Load data into a specific bank. bank='fixed' or int 0-21."""
        if bank == 'fixed':
            if offset + len(data) > BANK_FIXED_SIZE:
                raise ValueError(
                    f"Fixed bank overflow: {len(data)} bytes at offset "
                    f"0x{offset:04X} exceeds {BANK_FIXED_SIZE} bytes."
                )
            self._rom_fixed[offset:offset + len(data)] = data
        else:
            bank = int(bank)
            if not (0 <= bank < NUM_BANKS):
                raise ValueError(f"Bank {bank} out of range (0-{NUM_BANKS-1}).")
            if offset + len(data) > BANK_WIN_SIZE:
                raise ValueError(
                    f"Bank {bank} overflow: {len(data)} bytes at offset "
                    f"0x{offset:04X} exceeds {BANK_WIN_SIZE} bytes."
                )
            self._rom_banks[bank][offset:offset + len(data)] = data

    def switch_bank(self, bank: int):
        """Switch the banked window to bank n (0-21)."""
        if not (0 <= bank < NUM_BANKS):
            raise CPUFault(f"SETBANK: bank {bank} out of range (0-{NUM_BANKS-1}).")
        self._cur_bank = bank
        self._io[REG_BANK - IO_START] = bank & 0xFF

    # --- Unified read/write --------------------------------------

    def read(self, addr: int) -> int:
        addr &= 0xFFFF
        if addr <= RAM_END:        return self._ram[addr]
        if addr <= BANK_FIXED_END: return self._rom_fixed[addr - BANK_FIXED_START]
        if addr <= BANK_WIN_END:   return self._rom_banks[self._cur_bank][addr - BANK_WIN_START]
        return self._io_read(addr)

    def write(self, addr: int, value: int):
        addr  &= 0xFFFF
        value &= 0xFF
        if addr <= RAM_END:  self._ram[addr] = value
        elif addr <= ROM_END: pass   # ROM: silently discard
        else:                self._io_write(addr, value)

    def read16(self, addr: int) -> int:
        lo = self.read(addr)
        hi = self.read((addr + 1) & 0xFFFF)
        return (hi << 8) | lo

    def write16(self, addr: int, value: int):
        value &= 0xFFFF
        self.write(addr,     value & 0xFF)
        self.write(addr + 1, (value >> 8) & 0xFF)

    # --- IO handlers ---------------------------------------------

    def _io_read(self, addr: int) -> int:
        if addr == REG_COLLISION_FLAG:  return self._gpu.collision_flag  & 0xFF
        if addr == REG_COLLISION_SPR_A: return self._gpu.collision_spr_a & 0xFF
        if addr == REG_COLLISION_SPR_B: return self._gpu.collision_spr_b & 0xFF
        if addr == REG_BANK:            return self._cur_bank & 0xFF
        # VRAM DMA read: reading DATA_LO stages the word;
        # reading DATA_HI returns hi byte and auto-increments addr (mirrors write)
        if addr == REG_VRAM_DATA_LO:
            va   = (self._io[REG_VRAM_ADDR_HI - IO_START] << 8) | \
                    self._io[REG_VRAM_ADDR_LO  - IO_START]
            word = self._gpu.vram_read(va)
            self._io[REG_VRAM_DATA_LO - IO_START] = word & 0xFF
            self._io[REG_VRAM_DATA_HI - IO_START] = (word >> 8) & 0xFF
            return word & 0xFF
        if addr == REG_VRAM_DATA_HI:
            hi  = self._io[REG_VRAM_DATA_HI - IO_START]
            va  = (self._io[REG_VRAM_ADDR_HI - IO_START] << 8) | \
                   self._io[REG_VRAM_ADDR_LO  - IO_START]
            va  = (va + 2) & 0xFFFF
            self._io[REG_VRAM_ADDR_LO - IO_START] = va & 0xFF
            self._io[REG_VRAM_ADDR_HI - IO_START] = (va >> 8) & 0xFF
            return hi
        return self._io[addr - IO_START]

    def _io_write(self, addr: int, value: int):
        self._io[addr - IO_START] = value
        if addr == REG_GPU_COMMAND:
            color = self._io[REG_GPU_COLOR - IO_START]
            self._gpu.execute_command(value, color)
        elif addr == REG_BANK:
            self.switch_bank(value & 0xFF)
        elif addr == REG_VRAM_DATA_HI:
            lo   = self._io[REG_VRAM_DATA_LO - IO_START]
            word = (value << 8) | lo
            va   = self._io[REG_VRAM_ADDR_LO - IO_START] | \
                   (self._io[REG_VRAM_ADDR_HI - IO_START] << 8)
            self._gpu.vram_write(va, word)
            va = (va + 2) & 0xFFFF
            self._io[REG_VRAM_ADDR_LO - IO_START] = va & 0xFF
            self._io[REG_VRAM_ADDR_HI - IO_START] = (va >> 8) & 0xFF
        elif REG_APU_CMD <= addr <= REG_APU_PCM_LEN_HI:
            self._apu.handle_register_write(addr, value)
        elif addr == REG_IF:
            self._io[REG_IF - IO_START] &= value & 0xFF

    def raise_interrupt(self, mask: int):
        """Set bits in IF. Called by GPU, APU, and TRIG."""
        self._io[REG_IF - IO_START] |= mask & 0xFF


# =============================================================
# CPU
# =============================================================

class GMC16CPU:
    """
    GMC-16 16-bit CPU emulator.

    Quick start:
        gpu = GPU()
        gpu.renderer = PygameRenderer(scale=3)   # optional display
        cpu = GMC16CPU(gpu)
        cpu.bus.load_rom(Assembler().assemble(source))
        cpu.reset()
        while not cpu.halted:
            cpu.step()

    Debug mode:
        cpu.step(debug=True)   # prints disassembly + register state each step
        cpu.run(debug=True)    # same for a full run

    Framebuffer access (no renderer):
        pixels = cpu.gpu.framebuffer          # list[int] RGB565, row-major
        rgb    = FramebufferRenderer.rgb565_to_bytes(pixels)  # raw RGB bytes
    """

    def __init__(self, gpu: Optional[GPU] = None, apu: "APU | None" = None):
        self.gpu = gpu or GPU()
        self.apu = apu or APU()
        self.bus = MemoryBus(self.gpu, self.apu)

        self.R  = [0] * 8
        self.PC = ROM_START
        self.SP = RAM_END - 1
        self.FL = 0

        self.halted            = False
        self.total_cycles      = 0
        self.IME               = False
        self._timer_counter    = 0
        self._last_controller1 = 0x00

        # Fix #3: absolute target time avoids drift accumulation
        self._vblank_target = time.monotonic()
        self._frame_time    = 1 / 60

        self.controller1: int = 0x00

        self.gpu.set_irq_callback(self.bus.raise_interrupt)
        self.apu.set_irq_callback(self.bus.raise_interrupt)

    # --- Internal helpers ----------------------------------------

    def _set_flag(self, flag: int, val: bool):
        if val: self.FL |= flag
        else:   self.FL &= ~flag

    def _get_flag(self, flag: int) -> bool:
        return bool(self.FL & flag)

    def _update_nz(self, result: int):
        self._set_flag(FLAG_Z, (result & 0xFFFF) == 0)
        self._set_flag(FLAG_N, bool(result & 0x8000))

    def _push(self, value: int):
        self.SP = (self.SP - 2) & 0xFFFF
        self.bus.write16(self.SP, value)

    def _pop(self) -> int:
        value   = self.bus.read16(self.SP)
        self.SP = (self.SP + 2) & 0xFFFF
        return value

    # Fix #2: register validation helper
    def _check_regs(self, *indices: int):
        for idx in indices:
            if idx >= 8:
                raise CPUFault(
                    f"Invalid register index R{idx} at PC=0x{self.PC:04X}. "
                    f"GMC-16 has R0-R7 only."
                )

    def reset(self):
        self.R            = [0] * 8
        self.PC           = ROM_START
        self.SP           = RAM_END - 1
        self.FL           = 0
        self.halted            = False
        self.total_cycles      = 0
        self.IME               = False
        self._timer_counter    = 0
        self._last_controller1 = 0
        self._vblank_target    = time.monotonic()

    # --- Debug / disassembly  (Fix #4) ---------------------------

    def _disassemble_at(self, addr: int) -> tuple[str, int]:
        """
        Disassemble one instruction at `addr`.
        Returns (text, next_addr).
        """
        instr   = self.bus.read16(addr)
        addr   += 2
        op      = (instr >> 8) & 0xFF
        ra      = (instr >> 4) & 0x0F
        rb      =  instr       & 0x0F
        mnem    = _OPCODE_NAMES.get(op, f"??({op:02X})")

        def peek() -> tuple[int, int]:
            nonlocal addr
            v    = self.bus.read16(addr)
            addr += 2
            return v

        # Format operands based on instruction class
        if op in (0x00, 0x01, 0x1E, 0x32):    # no operands
            text = mnem

        elif op in (0x02, 0x04, 0x06, 0x07, 0x08, 0x09, 0x0A,
                    0x0F, 0x10, 0x11, 0x15):   # Rd, Rs
            text = f"{mnem} R{ra}, R{rb}"

        elif op in (0x03,):                    # LOAD Rd, [Rs]
            text = f"{mnem} R{ra}, [R{rb}]"

        elif op in (0x0B, 0x0C, 0x0D, 0x0E, 0x12, 0x13, 0x14,
                    0x1B, 0x1C, 0x1F, 0x2D, 0x2E, 0x2F,
                    0x30, 0x33):               # single register
            text = f"{mnem} R{ra}"

        elif op == 0x05:                       # LOADI Rd, imm
            imm  = peek()
            text = f"{mnem} R{ra}, 0x{imm:04X}"

        elif op in (0x16, 0x17, 0x18, 0x19, 0x1A, 0x1D):  # addr
            target = peek()
            text   = f"{mnem} 0x{target:04X}"

        elif op == 0x31:                       # BUTTON Rd, mask
            mask = peek()
            text = f"{mnem} R{ra}, 0x{mask:02X}"

        elif op in (0x20, 0x21):               # SPRITE* id, x, y
            sid = peek(); x = peek(); y = peek()
            text = f"{mnem} {sid}, {x}, {y}"

        elif op == 0x22:                       # SPRITEIMG id, tile
            sid  = peek(); tile = peek()
            text = f"{mnem} {sid}, {tile}"

        elif op in (0x23, 0x24):               # SPRITE[EN|DIS]ABLE id
            text = f"{mnem} {peek()}"

        elif op == 0x25:                       # SETTILE col, row, tile
            col = peek(); row = peek(); tile = peek()
            text = f"{mnem} {col}, {row}, {tile}"

        elif op == 0x26:                       # GETTILE Rd, col, row
            col = peek(); row = peek()
            text = f"{mnem} R{ra}, {col}, {row}"

        elif op in (0x27, 0x28, 0x29):         # SCROLL*, CLS  value
            text = f"{mnem} 0x{peek():04X}"

        elif op == 0x2A:                       # PIXEL x, y, color
            x = peek(); y = peek(); color = peek()
            text = f"{mnem} {x}, {y}, 0x{color:04X}"

        elif op in (0x2B, 0x2C):               # LINE/RECT
            a1=peek(); a2=peek(); a3=peek(); a4=peek(); a5=peek()
            text = f"{mnem} {a1},{a2},{a3},{a4},0x{a5:04X}"

        else:
            text = f"{mnem} R{ra}, R{rb}"

        return text, addr

    def _debug_print(self, pc_before: int, op: int, ra: int, rb: int):
        """Print one line of debug output before executing the instruction."""
        disasm, _ = self._disassemble_at(pc_before)

        # Determine which registers are relevant for this instruction
        two_reg = {0x02,0x04,0x06,0x07,0x08,0x09,0x0A,
                   0x0F,0x10,0x11,0x15}
        one_reg = {0x0B,0x0C,0x0D,0x0E,0x05,0x12,0x13,0x14,
                   0x1B,0x1C,0x1F,0x2D,0x2E,0x2F,0x30,0x31,0x33}

        reg_info = ""
        if op in two_reg:
            reg_info = (f"  R{ra}=0x{self.R[ra]:04X}"
                        f"  R{rb}=0x{self.R[rb]:04X}")
        elif op in one_reg and ra < 8:
            reg_info = f"  R{ra}=0x{self.R[ra]:04X}"

        fl = self.FL
        flags = (f"  [Z={int(bool(fl&FLAG_Z))}"
                 f" C={int(bool(fl&FLAG_C))}"
                 f" N={int(bool(fl&FLAG_N))}"
                 f" O={int(bool(fl&FLAG_O))}]")

        print(f"  PC={pc_before:04X}  {disasm:<28}{reg_info}{flags}")

    # --- Step  (Fix #4: debug parameter) ------------------------

    def step(self, debug: bool = False):
        if self.halted:
            return

        pc_before = self.PC
        instr     = self.bus.read16(self.PC)
        self.PC   = (self.PC + 2) & 0xFFFF
        op  = (instr >> 8) & 0xFF
        ra  = (instr >> 4) & 0x0F
        rb  =  instr       & 0x0F

        if debug:
            self._debug_print(pc_before, op, ra, rb)

        cycles = self._execute(op, ra, rb)
        self.total_cycles += cycles

        if self.controller1 != self._last_controller1:
            self._last_controller1 = self.controller1
            self.bus.raise_interrupt(INT_INPUT)

        period = ((self.bus._io[REG_TIMER_PERIOD_HI - IO_START] << 8) |
                   self.bus._io[REG_TIMER_PERIOD_LO - IO_START])
        if period:
            self._timer_counter += cycles
            if self._timer_counter >= period:
                self._timer_counter -= period
                self.bus.raise_interrupt(INT_TIMER)

        self._check_interrupts()

    def _check_interrupts(self):
        if not self.IME:
            return
        ie  = self.bus._io[REG_IE - IO_START]
        iff = self.bus._io[REG_IF - IO_START]
        pending = ie & iff
        if not pending:
            return
        bit       = pending & (-pending)
        bit_index = bit.bit_length() - 1
        self.bus._io[REG_IF - IO_START] &= ~bit & 0xFF
        self.IME = False
        self._push(self.PC)   # push return address first
        self._push(self.FL)   # push flags on top
        self.PC = self.bus.read16(IVT_BASE + bit_index * 2)

    def _fetch_mixed(self, bus: "MemoryBus", R: list, n: int) -> list:
        """
        Read a reg_flags word then n argument words from the instruction stream.
        Bit i of reg_flags set  -> arg i is a register index, resolve to R[idx].
        Bit i clear             -> arg i is a signed 16-bit immediate.
        Returns a plain list of n resolved Python integers.
        """
        reg_flags = bus.read16(self.PC)
        self.PC   = (self.PC + 2) & 0xFFFF
        result    = []
        for i in range(n):
            raw = bus.read16(self.PC)
            self.PC = (self.PC + 2) & 0xFFFF
            if reg_flags & (1 << i):
                result.append(R[raw & 0x7])
            else:
                # Sign-extend 16-bit two's-complement
                result.append(raw if raw < 0x8000 else raw - 0x10000)
        return result

    def _execute(self, op: int, ra: int, rb: int) -> int:
        bus    = self.bus
        R      = self.R
        cycles = CYCLE_TABLE.get(op, 1)

        # Fix #2: validate register indices up front for instructions that use them
        two_reg_ops = {0x02,0x03,0x04,0x06,0x07,0x08,0x09,0x0A,
                       0x0F,0x10,0x11,0x15}
        one_reg_ops = {0x05,0x0B,0x0C,0x0D,0x0E,0x12,0x13,0x14,
                       0x1B,0x1C,0x1F,0x2D,0x2E,0x2F,0x30,0x31,0x33,0x35}

        if op in two_reg_ops:
            self._check_regs(ra, rb)
        elif op in one_reg_ops:
            self._check_regs(ra)

        def rd() -> int: return R[ra]
        def rs() -> int: return R[rb]
        def wr(v: int):  R[ra] = v & 0xFFFF

        def fetch() -> int:
            v = bus.read16(self.PC)
            self.PC = (self.PC + 2) & 0xFFFF
            return v

        # --- Core ------------------------------------------------
        if   op == 0x00: pass
        elif op == 0x01: self.halted = True

        # --- Data movement ---------------------------------------
        elif op == 0x02: wr(rs()); self._update_nz(rs())
        elif op == 0x03: v = bus.read16(rs()); wr(v); self._update_nz(v)
        elif op == 0x04: bus.write16(rs(), rd())  # STORE Ra, Rb: mem[Rb] = Ra
        elif op == 0x05: imm = fetch(); wr(imm); self._update_nz(imm)
        elif op == 0x06: R[ra], R[rb] = R[rb], R[ra]

        # --- Math ------------------------------------------------
        elif op == 0x07:
            a, b = rd(), rs()
            result   = a + b
            overflow = ((a ^ b) & 0x8000 == 0) and ((a ^ result) & 0x8000 != 0)
            self._set_flag(FLAG_C, result > 0xFFFF)
            self._set_flag(FLAG_O, overflow)
            wr(result); self._update_nz(result)

        elif op == 0x08:
            result = rd() - rs()
            self._set_flag(FLAG_C, result < 0)
            wr(result); self._update_nz(result)

        elif op == 0x09:
            result = rd() * rs()
            self._set_flag(FLAG_C, result > 0xFFFF)
            wr(result); self._update_nz(result)

        elif op == 0x0A:
            divisor = rs()
            result  = 0xFFFF if divisor == 0 else rd() // divisor
            wr(result); self._update_nz(result)

        elif op == 0x0B: result = rd() + 1; wr(result); self._update_nz(result)
        elif op == 0x0C: result = rd() - 1; wr(result); self._update_nz(result)
        elif op == 0x0D: result = (-rd()) & 0xFFFF; wr(result); self._update_nz(result)
        elif op == 0x0E:
            v = rd()
            if v & 0x8000: v = (-v) & 0xFFFF
            wr(v); self._update_nz(v)

        # --- Bitwise ---------------------------------------------
        elif op == 0x0F: result = rd() & rs(); wr(result); self._update_nz(result)
        elif op == 0x10: result = rd() | rs(); wr(result); self._update_nz(result)
        elif op == 0x11: result = rd() ^ rs(); wr(result); self._update_nz(result)
        elif op == 0x12: result = (~rd()) & 0xFFFF; wr(result); self._update_nz(result)
        elif op == 0x13:
            self._set_flag(FLAG_C, bool(rd() & 0x8000))
            result = (rd() << 1) & 0xFFFF; wr(result); self._update_nz(result)
        elif op == 0x14:
            self._set_flag(FLAG_C, bool(rd() & 0x0001))
            result = rd() >> 1; wr(result); self._update_nz(result)

        # --- Comparison ------------------------------------------
        elif op == 0x15:
            result = rd() - rs()
            self._set_flag(FLAG_Z, result == 0)
            self._set_flag(FLAG_N, bool(result & 0x8000))
            self._set_flag(FLAG_C, result < 0)

        # --- Branching -------------------------------------------
        elif op == 0x16: self.PC = fetch()
        elif op == 0x17:
            addr = fetch()
            if self._get_flag(FLAG_Z):   self.PC = addr
            else:                        cycles  = 1
        elif op == 0x18:
            addr = fetch()
            if not self._get_flag(FLAG_Z): self.PC = addr
            else:                          cycles  = 1
        elif op == 0x19:
            addr = fetch()
            if not self._get_flag(FLAG_Z) and not self._get_flag(FLAG_N):
                self.PC = addr
            else:
                cycles = 1
        elif op == 0x1A:
            addr = fetch()
            if self._get_flag(FLAG_N): self.PC = addr
            else:                      cycles  = 1

        # --- Stack -----------------------------------------------
        elif op == 0x1B: self._push(rd())
        elif op == 0x1C: v = self._pop(); wr(v); self._update_nz(v)
        elif op == 0x1D: addr = fetch(); self._push(self.PC); self.PC = addr
        elif op == 0x1E: self.PC = self._pop()

        # --- Random ----------------------------------------------
        elif op == 0x1F: wr(random.randint(0, 0xFFFF))

        # --- Sprites ---------------------------------------------
        elif op == 0x20:
            sid = fetch()
            x, y = self._fetch_mixed(bus, R, 2)
            self.gpu.sprite_set_pos(sid, x, y)
        elif op == 0x21:
            sid = fetch()
            dx, dy = self._fetch_mixed(bus, R, 2)
            self.gpu.sprite_move(sid, dx, dy)
        elif op == 0x22:          # SPRITEIMG sid_imm, tile (sid always immediate)
            sid  = fetch()
            tile = self._fetch_mixed(bus, R, 1)[0]
            self.gpu.sprite_set_image(sid & 0xFF, tile)
        elif op == 0x23: self.gpu.sprite_enable(fetch())
        elif op == 0x24: self.gpu.sprite_disable(fetch())

        # --- Tiles -----------------------------------------------
        elif op == 0x25: self.gpu.set_tile(fetch(), fetch(), fetch())
        elif op == 0x26: wr(self.gpu.get_tile(fetch(), fetch()))
        elif op == 0x27: self.gpu.scroll_x = fetch()
        elif op == 0x28: self.gpu.scroll_y = fetch()

        # --- Draw ------------------------------------------------
        elif op == 0x29: self.gpu.cls(fetch())
        elif op == 0x2A:
            x, y, color = self._fetch_mixed(bus, R, 3)
            self.gpu.set_pixel(x, y, color)
        elif op == 0x2B:
            x1, y1, x2, y2, color = self._fetch_mixed(bus, R, 5)
            self.gpu.draw_line(x1, y1, x2, y2, color)
        elif op == 0x2C:
            x, y, w, h, color = self._fetch_mixed(bus, R, 5)
            self.gpu.draw_rect(x, y, w, h, color)

        # --- Collision -------------------------------------------
        elif op == 0x2D:
            self.gpu.check_collisions()
            wr(self.gpu.collision_flag); self._update_nz(self.gpu.collision_flag)
        elif op == 0x2E: wr(self.gpu.collision_spr_a)
        elif op == 0x2F: wr(self.gpu.collision_spr_b)

        # --- Input -----------------------------------------------
        elif op == 0x30: wr(self.controller1)
        elif op == 0x31:
            mask = fetch(); result = self.controller1 & mask
            wr(result); self._update_nz(result)

        # --- Timing  (Fix #3: drift-free vblank) -----------------
        elif op == 0x32:
            # Advance absolute target by one frame period, then sleep
            # to reach it.  If we're already past it, skip immediately.
            self._vblank_target += self._frame_time
            now = time.monotonic()
            remaining = self._vblank_target - now
            if remaining > 0:
                time.sleep(remaining)
            else:
                # Fell behind -- reset target so we don't chase a backlog
                self._vblank_target = time.monotonic()

        elif op == 0x33: wr(int(time.monotonic() * 1000) & 0xFFFF)

        # --- Bankswitching (v4) ----------------------------------
        elif op == 0x34:          # SETBANK imm
            bank = fetch()
            bus.switch_bank(bank)

        elif op == 0x35:          # GETBANK Rd
            self._check_regs(ra)
            wr(bus._cur_bank)

        # --- VRAM access (v5) ------------------------------------
        elif op == 0x36:          # VRAMWR vram_addr, value
            vaddr, value = self._fetch_mixed(bus, R, 2)
            self.gpu.vram_write(vaddr, value)

        elif op == 0x37:          # VRAMRD Rd, vram_addr
            self._check_regs(ra)
            vaddr = self._fetch_mixed(bus, R, 1)[0]
            wr(self.gpu.vram_read(vaddr))

        # --- Audio RAM access (v6) ---------------------------
        elif op == 0x38:          # PCMWR addr, value
            waddr, value = self._fetch_mixed(bus, R, 2)
            self.apu.write_audio_ram(waddr, value)

        elif op == 0x39:          # PCMRD Rd, addr
            self._check_regs(ra)
            waddr = self._fetch_mixed(bus, R, 1)[0]
            wr(self.apu.read_audio_ram(waddr))

        # --- Interrupts (v7) ---------------------------------
        elif op == 0x3A: self.IME = True
        elif op == 0x3B: self.IME = False
        elif op == 0x3C:          # RETI: pop FL (top), then PC
            self.FL  = self._pop()
            self.PC  = self._pop()
            self.IME = True
        elif op == 0x3D:          # TRIG n: 0-3 -> IRQ0-3 (bits 4-7)
            n = fetch() & 0x03
            self.bus.raise_interrupt(1 << (4 + n))

        else:
            raise CPUFault(
                f"Unknown opcode 0x{op:02X} at PC=0x{(self.PC - 2) & 0xFFFF:04X}"
            )

        return cycles

    # --- Run -----------------------------------------------------

    def run(self, max_steps: int = 0, debug: bool = False):
        """Run until halted. Pass debug=True to trace every instruction."""
        steps = 0
        while not self.halted:
            self.step(debug=debug)
            steps += 1
            if max_steps and steps >= max_steps:
                break

    # --- Debug helpers -------------------------------------------

    def dump_registers(self) -> str:
        lines = ["=== GMC-16 Registers ==="]
        for i, v in enumerate(self.R):
            lines.append(f"  R{i} = 0x{v:04X}  ({v})")
        fl = self.FL
        lines.append(f"  PC = 0x{self.PC:04X}  SP = 0x{self.SP:04X}")
        lines.append(
            f"  FL = Z:{int(bool(fl & FLAG_Z))} "
            f"C:{int(bool(fl & FLAG_C))} "
            f"N:{int(bool(fl & FLAG_N))} "
            f"O:{int(bool(fl & FLAG_O))}"
        )
        lines.append(f"  Cycles = {self.total_cycles}")
        return "\n".join(lines)

    def dump_ram(self, start: int = 0, length: int = 64) -> str:
        lines = [f"=== RAM 0x{start:04X}-0x{start + length - 1:04X} ==="]
        for i in range(0, length, 16):
            addr  = start + i
            chunk = [self.bus.read(addr + j) for j in range(min(16, length - i))]
            lines.append(f"  0x{addr:04X}: {' '.join(f'{b:02X}' for b in chunk)}")
        return "\n".join(lines)

    def disassemble(self, start: int = ROM_START, length: int = 32) -> str:
        """Disassemble `length` bytes from `start`."""
        lines  = [f"=== Disassembly 0x{start:04X} ==="]
        addr   = start
        end    = start + length
        while addr < end:
            text, next_addr = self._disassemble_at(addr)
            lines.append(f"  0x{addr:04X}  {text}")
            addr = next_addr
        return "\n".join(lines)


# =============================================================
# ASSEMBLER
# =============================================================

class BankImage:
    """
    Result of Assembler.assemble().

    Attributes:  .fixed (bytes), .banks (dict[int, bytes])
    Usage:       image.load_into(bus)
    Compat:      bytes(image) returns fixed bank bytes
    """

    def __init__(self, fixed: bytes, banks: dict):
        self.fixed = fixed
        self.banks = banks

    def load_into(self, bus):
        if self.fixed:
            bus.load_bank("fixed", self.fixed)
        for bank_num, data in self.banks.items():
            if data:
                bus.load_bank(bank_num, data)

    def __bytes__(self) -> bytes:
        return self.fixed

    def __len__(self) -> int:
        return len(self.fixed) + sum(len(d) for d in self.banks.values())

    def summary(self) -> str:
        lines = [f"BankImage: fixed={len(self.fixed)} bytes"]
        for k, v in sorted(self.banks.items()):
            lines.append(f"  bank {k:2d}: {len(v)} bytes")
        lines.append(f"  total : {len(self)} bytes")
        return "\n".join(lines)


class Assembler:
    """
    Two-pass assembler for GMC-16.

    Syntax:
        [LABEL:]  MNEMONIC  [OPERANDS]  [; comment]
        NAME      EQU       EXPRESSION

    Operand expressions:
        decimal, 0x hex, arithmetic (+,-,*,/,()), named symbols, labels

    Built-in constants: SCREEN_W, SCREEN_H, RAM_START, RAM_END,
                        ROM_START, COL_NONE, COL_PLAYER, COL_ENEMY,
                        COL_BULLET, COL_ITEM

    Example:
        HALF_W   EQU  SCREEN_W / 2
        LOADI    R0,  HALF_W
        LOADI    R1,  (10 * 4) - 8
        SPRITEPOS 0,  SCREEN_W / 2,  SCREEN_H / 2
    """

    MNEMONICS: dict[str, int] = {
        "NOP":0x00,"HALT":0x01,"MOV":0x02,"LOAD":0x03,"STORE":0x04,
        "LOADI":0x05,"SWAP":0x06,"ADD":0x07,"SUB":0x08,"MUL":0x09,
        "DIV":0x0A,"INC":0x0B,"DEC":0x0C,"NEG":0x0D,"ABS":0x0E,
        "AND":0x0F,"OR":0x10,"XOR":0x11,"NOT":0x12,"SHL":0x13,
        "SHR":0x14,"CMP":0x15,"JMP":0x16,"JZ":0x17,"JNZ":0x18,
        "JG":0x19,"JL":0x1A,"PUSH":0x1B,"POP":0x1C,"CALL":0x1D,
        "RET":0x1E,"RAND":0x1F,"SPRITEPOS":0x20,"SPRITEMOVE":0x21,
        "SPRITEIMG":0x22,"SPRITEENABLE":0x23,"SPRITEDISABLE":0x24,
        "SETTILE":0x25,"GETTILE":0x26,"SCROLLX":0x27,"SCROLLY":0x28,
        "CLS":0x29,"PIXEL":0x2A,"LINE":0x2B,"RECT":0x2C,
        "COLCHECK":0x2D,"COLSPR1":0x2E,"COLSPR2":0x2F,
        "INPUT":0x30,"BUTTON":0x31,"WAITVBLANK":0x32,"TIMER":0x33,
        "SETBANK":0x34,"GETBANK":0x35,
        "VRAMWR":0x36,"VRAMRD":0x37,
        "PCMWR":0x38,"PCMRD":0x39,
        "SEI":0x3A,"CLI":0x3B,"RETI":0x3C,"TRIG":0x3D,
    }

    BUILTINS: dict[str, int] = {
        "SCREEN_W":SCREEN_W,"SCREEN_H":SCREEN_H,
        "RAM_START":RAM_START,"RAM_END":RAM_END,"ROM_START":ROM_START,
        "COL_NONE":COL_NONE,"COL_PLAYER":COL_PLAYER,
        "COL_ENEMY":COL_ENEMY,"COL_BULLET":COL_BULLET,"COL_ITEM":COL_ITEM,
        "BANK_FIXED_START":BANK_FIXED_START,"BANK_FIXED_END":BANK_FIXED_END,
        "BANK_FIXED_SIZE":BANK_FIXED_SIZE,"BANK_WIN_START":BANK_WIN_START,
        "BANK_WIN_END":BANK_WIN_END,"BANK_WIN_SIZE":BANK_WIN_SIZE,
        "NUM_BANKS":NUM_BANKS,
        # Tile engine (v5)
        "TILE_W":TILE_W,"TILE_H":TILE_H,"TILE_BYTES":TILE_BYTES,
        "MAX_TILES":MAX_TILES,"TILEMAP_COLS":TILEMAP_COLS,"TILEMAP_ROWS":TILEMAP_ROWS,
        "VRAM_TILE_BASE":VRAM_TILE_BASE,"VRAM_TILE_END":VRAM_TILE_END,
        "VRAM_MAP_BASE":VRAM_MAP_BASE,"VRAM_MAP_END":VRAM_MAP_END,
        "VRAM_USER_BASE":VRAM_USER_BASE,
        # APU (v6)
        "APU_SAMPLE_RATE":APU_SAMPLE_RATE,"APU_CHANNELS":APU_CHANNELS,
        "APU_MAX_SAMPLES":APU_MAX_SAMPLES,
        "WAVE_SQUARE":WAVE_SQUARE,"WAVE_SINE":WAVE_SINE,
        "WAVE_TRIANGLE":WAVE_TRIANGLE,"WAVE_SAWTOOTH":WAVE_SAWTOOTH,
        "REG_APU_CMD":REG_APU_CMD,"REG_APU_CHAN":REG_APU_CHAN,
        "REG_APU_FREQ_LO":REG_APU_FREQ_LO,"REG_APU_FREQ_HI":REG_APU_FREQ_HI,
        "REG_APU_VOL":REG_APU_VOL,"REG_APU_WAVE":REG_APU_WAVE,
        "REG_APU_PCM_LO":REG_APU_PCM_LO,"REG_APU_PCM_HI":REG_APU_PCM_HI,
        "REG_APU_PCM_LEN_LO":REG_APU_PCM_LEN_LO,"REG_APU_PCM_LEN_HI":REG_APU_PCM_LEN_HI,
        "PLAY_TONE":0x01,"PLAY_NOISE":0x02,"SND_STOP":0x03,
        "SND_STOP_ALL":0x04,"PLAY_PCM":0x05,
        "IVT_VBLANK":IVT_VBLANK,"IVT_TIMER":IVT_TIMER,
        "IVT_INPUT":IVT_INPUT,"IVT_APU":IVT_APU,
        "IVT_IRQ0":IVT_IRQ0,"IVT_IRQ1":IVT_IRQ1,
        "IVT_IRQ2":IVT_IRQ2,"IVT_IRQ3":IVT_IRQ3,
        "INT_VBLANK":INT_VBLANK,"INT_TIMER":INT_TIMER,
        "INT_INPUT":INT_INPUT,"INT_APU":INT_APU,
        "INT_IRQ0":INT_IRQ0,"INT_IRQ1":INT_IRQ1,
        "INT_IRQ2":INT_IRQ2,"INT_IRQ3":INT_IRQ3,
        "REG_IE":REG_IE,"REG_IF":REG_IF,
        "REG_TIMER_PERIOD_LO":REG_TIMER_PERIOD_LO,
        "REG_TIMER_PERIOD_HI":REG_TIMER_PERIOD_HI,
    }

    _IDENT = re.compile(r'\b(?!0[xX])[A-Za-z_][A-Za-z0-9_]*\b')
    _SAFE  = set('0123456789+-*/() .|&^~')

    def __init__(self):
        self.labels:     dict[str, int]        = {}
        self.constants:  dict[str, int]        = {}
        self.output:     bytearray             = bytearray()
        self.patch_list: list                  = []
        # Multi-bank state (v4)
        self._asm_bank    = "fixed"
        self._asm_buffers : dict = {"fixed": bytearray()}
        self._asm_origins : dict = {"fixed": BANK_FIXED_START}

    # --- Multi-bank helpers (v4) ---------------------------------

    def _switch_asm_bank(self, bank):
        """Switch assembler output target to 'fixed' or int 0-21."""
        if bank != "fixed":
            bank = int(bank)
            if not (0 <= bank < NUM_BANKS):
                raise ValueError(f"BANK directive: bank {bank} out of range.")
            if bank not in self._asm_buffers:
                self._asm_buffers[bank] = bytearray()
                self._asm_origins[bank] = BANK_WIN_START
        self._asm_bank = bank
        self.output    = self._asm_buffers[bank]

    def _current_origin(self) -> int:
        return self._asm_origins[self._asm_bank]

    def _eval(self, expr: str) -> int:
        def sub(m: re.Match) -> str:
            name = m.group(0)
            if self._is_reg(name):
                raise ValueError(
                    f"Register '{name}' used where a constant expression "
                    f"is expected. Use LOADI to load register values first."
                )
            if name in self.constants: return str(self.constants[name])
            if name in self.labels:    return str(self.labels[name])
            raise ValueError(f"Undefined symbol: '{name}'")

        subst = self._IDENT.sub(sub, expr.strip())
        subst = re.sub(r'0[xX]([0-9a-fA-F]+)',
                       lambda m: str(int(m.group(1), 16)), subst)
        if not all(c in self._SAFE for c in subst):
            raise ValueError(f"Unsafe expression: '{expr}'")
        subst = re.sub(r'(?<!/)/(?!/)', '//', subst)   # force integer division
        return int(eval(subst, {"__builtins__": {}})) & 0xFFFF  # noqa: S307

    def _has_forward_ref(self, expr: str) -> bool:
        for m in self._IDENT.finditer(expr):
            name = m.group(0)
            # Register names are not symbols - skip them
            if self._is_reg(name):
                continue
            if name not in self.constants and name not in self.labels:
                return True
        return False

    def _emit16(self, word: int):
        word &= 0xFFFF
        self.output += bytes([word & 0xFF, (word >> 8) & 0xFF])

    def _emit_expr(self, expr: str):
        if self._has_forward_ref(expr):
            self.patch_list.append((len(self.output), expr, self._asm_bank))
            self._emit16(0x0000)
        else:
            self._emit16(self._eval(expr))

    def _emit_mixed(self, *args: str):
        """
        Emit a reg-flags word followed by one word per arg.
        If an arg is a register name (R0-R7), the corresponding bit in
        reg_flags is set and the register index is emitted.
        Otherwise the arg is evaluated as a constant expression and emitted
        as a 16-bit word (signed two's-complement for negative values).
        """
        reg_flags = 0
        for i, tok in enumerate(args):
            if self._is_reg(tok):
                reg_flags |= (1 << i)
        self._emit16(reg_flags)
        for i, tok in enumerate(args):
            if self._is_reg(tok):
                self._emit16(self._reg(tok))
            else:
                self._emit_expr(tok)

    @staticmethod
    def _reg(tok: str) -> int:
        tok = tok.strip().upper()
        if tok.startswith("R") and tok[1:].isdigit():
            n = int(tok[1:])
            if 0 <= n <= 7:
                return n
        raise ValueError(f"Not a register: '{tok}'")

    @staticmethod
    def _is_reg(tok: str) -> bool:
        """True if tok looks like a register name R0-R7."""
        tok = tok.strip().upper()
        return (tok.startswith("R") and tok[1:].isdigit()
                and 0 <= int(tok[1:]) <= 7)

    def assemble(self, source: str, origin: int = ROM_START) -> "BankImage":
        """Assemble source. Returns BankImage. Use image.load_into(bus) to load."""
        self.labels       = {}
        self.constants    = dict(self.BUILTINS)
        self.patch_list   = []
        self._asm_bank    = "fixed"
        self._asm_buffers = {"fixed": bytearray()}
        self._asm_origins = {"fixed": BANK_FIXED_START}
        self.output       = self._asm_buffers["fixed"]

        for line in source.splitlines():
            line = line.split(";")[0].strip()
            if not line:
                continue
            if ":" in line:
                lbl, _, line = line.partition(":")
                lbl  = lbl.strip()
                rest = line.strip()
                # "NAME: EQU expr" -- constant, not a code label
                rparts = rest.split()
                if rparts and rparts[0].upper() == "EQU":
                    self.constants[lbl] = self._eval(" ".join(rparts[1:]))
                    continue
                # Normal address label
                self.labels[lbl] = self._current_origin() + len(self.output)
                line = rest
                if not line:
                    continue
            parts = line.split()
            mnem  = parts[0].upper()
            if len(parts) >= 3 and parts[1].upper() == "EQU":
                self.constants[parts[0]] = self._eval(" ".join(parts[2:]))
                continue
            if mnem == "BANK":
                target = parts[1].strip().upper() if len(parts) > 1 else "FIXED"
                self._switch_asm_bank("fixed" if target == "FIXED" else int(parts[1]))
                continue
            args = [p.strip(",") for p in parts[1:]]
            op   = self.MNEMONICS.get(mnem)
            if op is None:
                raise ValueError(f"Unknown mnemonic: '{mnem}'")
            self._encode(op, mnem, args)

        # Second pass: resolve patches
        for offset, expr, bank_key in self.patch_list:
            v   = self._eval(expr)
            buf = self._asm_buffers[bank_key]
            buf[offset]     = v & 0xFF
            buf[offset + 1] = (v >> 8) & 0xFF

        return BankImage(
            fixed=bytes(self._asm_buffers.get("fixed", b"")),
            banks={k: bytes(v) for k, v in self._asm_buffers.items() if k != "fixed"},
        )

    def _encode(self, op: int, mnem: str, args: list[str]):
        reg = self._reg
        ex  = self._emit_expr

        if mnem in ("NOP","HALT","RET","WAITVBLANK"):
            self._emit16(op << 8)
        elif mnem in ("INC","DEC","NEG","ABS","NOT","SHL","SHR",
                      "PUSH","POP","RAND","INPUT",
                      "COLCHECK","COLSPR1","COLSPR2","TIMER"):
            ra = reg(args[0]) if args else 0
            self._emit16((op << 8) | (ra << 4))
        elif mnem in ("MOV","LOAD","STORE","SWAP",
                      "ADD","SUB","MUL","DIV","AND","OR","XOR","CMP"):
            ra, rb = reg(args[0]), reg(args[1])
            self._emit16((op << 8) | (ra << 4) | rb)
        elif mnem == "LOADI":
            self._emit16((op << 8) | (reg(args[0]) << 4))
            ex(" ".join(args[1:]))
        elif mnem in ("JMP","JZ","JNZ","JG","JL","CALL"):
            self._emit16(op << 8)
            ex(args[0] if args else "0")
        elif mnem in ("SPRITEPOS", "SPRITEMOVE"):
            # [opcode] [sid-imm] [reg_flags] [arg0] [arg1]
            # sid is always an immediate; x/y or dx/dy may be registers.
            self._emit16(op << 8)
            ex(args[0])                        # sprite id (always imm)
            self._emit_mixed(args[1], args[2]) # x,y or dx,dy
        elif mnem == "SETTILE":
            self._emit16(op << 8)
            self._emit_mixed(args[0], args[1], args[2])
        elif mnem == "SPRITEIMG":   # sid: always-immediate; tile: reg-or-imm
            self._emit16(op << 8)
            ex(args[0])             # sid as plain immediate
            self._emit_mixed(args[1])  # tile as 1 mixed arg
        elif mnem in ("SPRITEENABLE","SPRITEDISABLE","SCROLLX","SCROLLY","CLS"):
            self._emit16(op << 8); ex(args[0])
        elif mnem == "GETTILE":
            self._emit16((op << 8) | (reg(args[0]) << 4))
            ex(args[1]); ex(args[2])
        elif mnem == "PIXEL":
            # [opcode] [reg_flags] x y color
            self._emit16(op << 8)
            self._emit_mixed(args[0], args[1], args[2])
        elif mnem in ("LINE", "RECT"):
            # [opcode] [reg_flags] arg0 arg1 arg2 arg3 arg4
            self._emit16(op << 8)
            self._emit_mixed(*args[:5])
        elif mnem == "BUTTON":
            self._emit16((op << 8) | (reg(args[0]) << 4))
            ex(args[1])
        elif mnem == "SETBANK":
            self._emit16(op << 8)
            ex(args[0])
        elif mnem == "GETBANK":
            self._emit16((op << 8) | (reg(args[0]) << 4))
        elif mnem == "VRAMWR":          # VRAMWR vaddr, value
            self._emit16(op << 8)
            self._emit_mixed(args[0], args[1])
        elif mnem == "VRAMRD":          # VRAMRD Rd, vaddr
            self._emit16((op << 8) | (reg(args[0]) << 4))
            self._emit_mixed(args[1])
        elif mnem == "PCMWR":           # PCMWR addr, value
            self._emit16(op << 8)
            self._emit_mixed(args[0], args[1])
        elif mnem == "PCMRD":           # PCMRD Rd, addr
            self._emit16((op << 8) | (reg(args[0]) << 4))
            self._emit_mixed(args[1])
        elif mnem in ("SEI", "CLI", "RETI"):
            self._emit16(op << 8)
        elif mnem == "TRIG":
            self._emit16(op << 8)
            ex(args[0])
        else:
            raise ValueError(f"Unhandled mnemonic: '{mnem}'")


# =============================================================
# SELF-TESTS
# =============================================================

def _run_tests():
    print("=" * 64)
    print("GMC-16 Emulator v3  --  self-test suite")
    print("=" * 64)

    asm = Assembler()

    # -----------------------------------------------------------------
    def make_cpu(source: str) -> "GMC16CPU":
        cpu = GMC16CPU()
        cpu.bus.load_rom(asm.assemble(source))
        cpu.reset()
        cpu.run(max_steps=10_000)
        return cpu

    # -----------------------------------------------------------------
    print("\n[1] Basic arithmetic + loop + EQU")
    cpu = make_cpu("""
    HALF_W  EQU  SCREEN_W / 2
        LOADI  R0, 10
        LOADI  R1, 20
        ADD    R0, R1
        LOADI  R2, 5
    LOOP:
        INC    R0
        DEC    R2
        JNZ    LOOP
        LOADI  R3, HALF_W
        HALT
    """)
    assert cpu.R[0] == 35,  f"R0={cpu.R[0]}"
    assert cpu.R[2] == 0,   f"R2={cpu.R[2]}"
    assert cpu.R[3] == 128, f"R3={cpu.R[3]}"
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[2] ROM overflow protection (Fix #1)")
    bus = MemoryBus(GPU())
    try:
        bus.load_rom(bytes(ROM_SIZE + 1))   # one byte too many
        assert False, "Should have raised"
    except ValueError as e:
        print(f"  Caught: {e}")
        print("  PASS")

    # -----------------------------------------------------------------
    print("\n[3] Register bounds checking (Fix #2)")
    cpu3 = GMC16CPU()
    cpu3.bus.load_rom(asm.assemble("NOP\nHALT"))
    cpu3.reset()
    try:
        cpu3._check_regs(9)   # R9 does not exist
        assert False, "Should have raised CPUFault"
    except CPUFault as e:
        print(f"  Caught: {e}")
        print("  PASS")

    # -----------------------------------------------------------------
    print("\n[4] Drift-free VBlank (Fix #3) -- timing structure check")
    cpu4 = GMC16CPU()
    t0 = cpu4._vblank_target
    # Simulate two vblank steps without actually sleeping (set target in past)
    cpu4._vblank_target = time.monotonic() - 10.0   # already behind
    cpu4._execute(0x32, 0, 0)   # WAITVBLANK -- should snap forward, not sleep
    assert cpu4._vblank_target >= time.monotonic() - 0.1, "Target should reset"
    print("  Drift recovery: PASS")
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[5] Debug mode output (Fix #4)")
    cpu5 = GMC16CPU()
    cpu5.bus.load_rom(asm.assemble("""
        LOADI  R0, 42
        LOADI  R1, 8
        ADD    R0, R1
        HALT
    """))
    cpu5.reset()
    print("  --- debug trace ---")
    cpu5.run(debug=True)
    print("  -------------------")
    assert cpu5.R[0] == 50, f"R0={cpu5.R[0]}"
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[6] Disassembler")
    cpu6 = GMC16CPU()
    cpu6.bus.load_rom(asm.assemble("""
        LOADI  R0, 0xFF
        ADD    R0, R1
        HALT
    """))
    cpu6.reset()
    dis = cpu6.disassemble(ROM_START, 10)
    print(dis)
    assert "LOADI" in dis
    assert "ADD"   in dis
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[7] Framebuffer renderer API (Fix #5)")
    frames_seen = []

    def capture(pixels, w, h):
        frames_seen.append((len(pixels), w, h))

    gpu7 = GPU()
    gpu7.renderer = CallbackRenderer(capture)
    gpu7._cmd_clear(0xF800)   # red
    gpu7._cmd_flip_buffer()

    assert len(frames_seen) == 1,            f"Expected 1 frame, got {len(frames_seen)}"
    assert frames_seen[0] == (SCREEN_W * SCREEN_H, SCREEN_W, SCREEN_H)

    # Check RGB565 conversion helper
    r, g, b = FramebufferRenderer.rgb565_to_rgb(0xF800)
    assert r == 248 and g == 0 and b == 0, f"RGB: {r},{g},{b}"
    print(f"  Frame delivered: {frames_seen[0]}")
    print(f"  RGB565 decode 0xF800 -> R={r} G={g} B={b}")
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[8] Collision detection")
    gpu8 = GPU()
    A, B = 50, 200
    gpu8.sprite_enable(A); gpu8.sprites[A].x = 100; gpu8.sprites[A].y = 100
    gpu8.sprites[A].collision_type = COL_PLAYER
    gpu8.sprite_enable(B); gpu8.sprites[B].x = 108; gpu8.sprites[B].y = 106
    gpu8.sprites[B].collision_type = COL_ENEMY
    gpu8.check_collisions()
    assert gpu8.collision_flag == 1
    assert gpu8.collision_spr_a == A
    assert gpu8.collision_spr_b == B
    print(f"  Sprite {A} <-> sprite {B}: PASS")

    # -----------------------------------------------------------------
    print("\n[9] Cycle counting")
    cpu9 = make_cpu("NOP\nLOADI R0, 5\nINC R0\nHALT")
    assert cpu9.total_cycles == 5, f"Got {cpu9.total_cycles}"
    print(f"  Cycles: {cpu9.total_cycles}  PASS")

    # -----------------------------------------------------------------
    print("\n[10] Memory map enforcement")
    bus10 = MemoryBus(GPU())
    bus10.write(0x0010, 0xAB)
    assert bus10.read(0x0010) == 0xAB
    bus10.load_rom(bytes([0x42]))
    bus10.write(BANK_FIXED_START, 0xFF)   # ROM write silently ignored
    assert bus10.read(BANK_FIXED_START) == 0x42
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[11] Bankswitching (v4)")

    # load_bank / switch_bank
    bus11 = MemoryBus(GPU())
    for b, val in {0: 0xAA, 1: 0xBB, 2: 0xCC}.items():
        data = bytearray(BANK_WIN_SIZE); data[0] = val; data[1] = val
        bus11.load_bank(b, bytes(data))
    for b, val in {0: 0xAA, 1: 0xBB, 2: 0xCC}.items():
        bus11.switch_bank(b)
        assert bus11.read(BANK_WIN_START) == val, f"Bank {b} sentinel wrong"
        assert bus11.read(REG_BANK) == b,         f"REG_BANK wrong for bank {b}"
    print("  load_bank / switch_bank: PASS")

    # SETBANK / GETBANK CPU instructions
    cpu11 = GMC16CPU()
    image11 = asm.assemble("""
        SETBANK 0
        GETBANK R1
        SETBANK 2
        GETBANK R2
        SETBANK 1
        GETBANK R3
        HALT
    """)
    image11.load_into(cpu11.bus)
    cpu11.reset(); cpu11.run(max_steps=1000)
    assert cpu11.R[1] == 0, f"GETBANK after SETBANK 0: R1={cpu11.R[1]}"
    assert cpu11.R[2] == 2, f"GETBANK after SETBANK 2: R2={cpu11.R[2]}"
    assert cpu11.R[3] == 1, f"GETBANK after SETBANK 1: R3={cpu11.R[3]}"
    print("  SETBANK / GETBANK: PASS")

    # Cross-bank data read: put sentinel in bank 1, read from banked window
    bus12 = MemoryBus(GPU())
    bdata = bytearray(BANK_WIN_SIZE); bdata[0]=0x34; bdata[1]=0x12
    bus12.load_bank(1, bytes(bdata))
    cpu12 = GMC16CPU()
    image12 = asm.assemble("""
        SETBANK 1
        LOADI   R0, BANK_WIN_START
        LOAD    R1, R0
        HALT
    """)
    image12.load_into(cpu12.bus)
    cpu12.bus.load_bank(1, bytes(bdata))  # load the data bank
    cpu12.reset(); cpu12.run(max_steps=1000)
    assert cpu12.R[1] == 0x1234, f"Cross-bank read: R1=0x{cpu12.R[1]:04X}"
    print("  Cross-bank data read: PASS")

    # BankImage multi-bank assembly
    image_m = asm.assemble("""
        BANK FIXED
        LOADI R0, 42
        HALT
        BANK 0
        LOADI R1, 99
        HALT
        BANK 3
        LOADI R2, 77
        HALT
    """)
    print(f"  {image_m.summary()}")
    assert 0   in image_m.banks
    assert 3   in image_m.banks
    assert len(image_m.fixed) > 0
    print("  BankImage multi-bank assembly: PASS")
    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[12] Tile engine (v5)")

    gpu_te = GPU()

    # load_tile / read_tile_pixel round-trip
    RED  = 0xF800
    gpu_te.load_tile(0, [RED] * 64)
    for ry in range(TILE_H):
        for rx in range(TILE_W):
            got = gpu_te.read_tile_pixel(0, rx, ry)
            assert got == RED, f"Tile 0 ({rx},{ry}) = 0x{got:04X}"
    print("  load_tile / read_tile_pixel: PASS")

    # vram_write / vram_read round-trip
    gpu_te.vram_write(0x8000, 0xABCD)
    assert gpu_te.vram_read(0x8000) == 0xABCD
    print("  vram_write / vram_read: PASS")

    # VRAMWR / VRAMRD CPU instructions
    cpu_vr = GMC16CPU()
    img_vr = asm.assemble("""
        LOADI  R0, 0x0020
        LOADI  R2, 0x5A5A
        VRAMWR R0, R2
        VRAMRD R1, R0
        HALT
    """)
    img_vr.load_into(cpu_vr.bus)
    cpu_vr.reset(); cpu_vr.run(max_steps=500)
    assert cpu_vr.R[1] == 0x5A5A, f"VRAMRD: R1=0x{cpu_vr.R[1]:04X}"
    print("  VRAMWR / VRAMRD instructions: PASS")

    # SETTILE / get_tile backed by VRAM
    gpu_te2 = GPU()
    gpu_te2.set_tile(5, 3, 0x0142)   # tile_id=0x42, flip-X set
    entry = gpu_te2.get_tile(5, 3)
    assert entry == 0x0142, f"get_tile: 0x{entry:04X}"
    raw = gpu_te2.vram_read(VRAM_MAP_BASE + (3 * TILEMAP_COLS + 5) * 2)
    assert raw == 0x0142, f"VRAM map backing: 0x{raw:04X}"
    print("  set_tile / get_tile / VRAM backing: PASS")

    # DRAW_TILEMAP rendering: tile 1 = solid blue at map (0,0)
    BLUE = 0x001F
    gpu_te3 = GPU()
    gpu_te3.load_tile(1, [BLUE] * 64)
    gpu_te3.set_tile(0, 0, 1)
    gpu_te3._cmd_clear(0x0000)
    gpu_te3._cmd_draw_tilemap()
    for ry in range(TILE_H):
        for rx in range(TILE_W):
            got = gpu_te3.back_framebuffer[ry * SCREEN_W + rx]
            assert got == BLUE, f"Tilemap ({rx},{ry}) = 0x{got:04X}"
    # Pixel in next tile position should be 0 (tile_id=0 = all black)
    assert gpu_te3.back_framebuffer[TILE_W] == 0x0000
    print("  DRAW_TILEMAP solid tile: PASS")

    # Scroll wrapping: scroll right 1 tile, tile 1 scrolls off left edge
    gpu_te4 = GPU()
    GREEN = 0x07E0
    gpu_te4.load_tile(2, [GREEN] * 64)
    gpu_te4.set_tile(0, 0, 2)
    gpu_te4.scroll_x = TILE_W
    gpu_te4._cmd_clear(0x0000)
    gpu_te4._cmd_draw_tilemap()
    # screen (0,0) now shows map column 1, which is tile 0 (black)
    assert gpu_te4.back_framebuffer[0] == 0x0000, \
        f"Scroll: expected 0x0000, got 0x{gpu_te4.back_framebuffer[0]:04X}"
    print("  Scroll wrapping: PASS")

    # Flip-X: tile with left-column red, rest black; flip-X → red on right
    gpu_te5 = GPU()
    stripe = [RED if px == 0 else 0x0000
              for py in range(TILE_H) for px in range(TILE_W)]
    gpu_te5.load_tile(3, stripe)
    gpu_te5.set_tile(0, 0, 3 | 0x100)   # flip-X
    gpu_te5._cmd_clear(0x0000)
    gpu_te5._cmd_draw_tilemap()
    assert gpu_te5.back_framebuffer[0]          == 0x0000, "flip-X left should be black"
    assert gpu_te5.back_framebuffer[TILE_W - 1] == RED,    "flip-X right should be RED"
    print("  Flip-X tile: PASS")

    # Flip-Y: tile with top-row red, rest black; flip-Y → red on bottom row
    gpu_te6 = GPU()
    hstripe = [RED if py == 0 else 0x0000
               for py in range(TILE_H) for px in range(TILE_W)]
    gpu_te6.load_tile(4, hstripe)
    gpu_te6.set_tile(0, 0, 4 | 0x200)   # flip-Y
    gpu_te6._cmd_clear(0x0000)
    gpu_te6._cmd_draw_tilemap()
    assert gpu_te6.back_framebuffer[0]                           == 0x0000, "flip-Y top should be black"
    assert gpu_te6.back_framebuffer[(TILE_H - 1) * SCREEN_W]    == RED,    "flip-Y bottom should be RED"
    print("  Flip-Y tile: PASS")

    print("  PASS")

    # -----------------------------------------------------------------
    print("\n[13] APU (v6) -- audio RAM + tone synthesis (silent mode)")

    apu_t = APU()
    # Do NOT call apu_t.start() -- no audio hardware in test environment

    # Audio RAM write / read round-trip
    apu_t.write_audio_ram(0,    0x1234)
    apu_t.write_audio_ram(4095, 0xABCD)
    assert apu_t.read_audio_ram(0)    == 0x1234, "audio RAM[0] mismatch"
    assert apu_t.read_audio_ram(4095) == 0xABCD, "audio RAM[4095] mismatch"
    print("  Audio RAM read/write: PASS")

    # PCMWR / PCMRD CPU instructions
    cpu_apu = GMC16CPU()
    img_apu = asm.assemble("""
        LOADI  R0, 10
        LOADI  R1, 0x7FFF
        PCMWR  R0, R1
        PCMRD  R2, R0
        HALT
    """)
    img_apu.load_into(cpu_apu.bus)
    cpu_apu.reset(); cpu_apu.run(max_steps=500)
    assert cpu_apu.R[2] == 0x7FFF, f"PCMRD: R2=0x{cpu_apu.R[2]:04X}"
    print("  PCMWR / PCMRD instructions: PASS")

    # Channel state: play_tone sets channel active
    apu_t.play_tone(0, 440, vol=200, wave=WAVE_SQUARE)
    assert apu_t.is_active(0), "Channel 0 should be active after play_tone"
    apu_t.stop_channel(0)
    assert not apu_t.is_active(0), "Channel 0 should be inactive after stop"
    print("  play_tone / stop_channel: PASS")

    # stop_all silences all channels
    for c in range(APU_CHANNELS):
        apu_t.play_tone(c, 220 * (c + 1))
    apu_t.stop_all()
    for c in range(APU_CHANNELS):
        assert not apu_t.is_active(c), f"Channel {c} still active after stop_all"
    print("  stop_all: PASS")

    # Sample generation: square wave produces non-zero output
    apu_t.play_tone(0, 440, vol=255, wave=WAVE_SQUARE)
    chunk = apu_t._generate_chunk(APU_CHUNK)
    samples = struct.unpack_from(f'<{APU_CHUNK}h', chunk)
    assert any(s != 0 for s in samples), "Square wave chunk is all zeros"
    print("  Square wave generates non-zero samples: PASS")

    # Sine wave chunk check
    apu_t.stop_all()
    apu_t.play_tone(0, 440, vol=255, wave=WAVE_SINE)
    chunk_sine = apu_t._generate_chunk(APU_CHUNK)
    samps_sine = struct.unpack_from(f'<{APU_CHUNK}h', chunk_sine)
    assert any(s != 0 for s in samps_sine), "Sine wave chunk is all zeros"
    print("  Sine wave generates non-zero samples: PASS")

    # PCM playback via IO registers (no pyaudio needed)
    apu_io = APU()
    for i in range(16):
        apu_io.write_audio_ram(i, 0x4000)   # 0.5 amplitude samples
    apu_io.handle_register_write(REG_APU_CHAN,        0)
    apu_io.handle_register_write(REG_APU_VOL,       255)
    apu_io.handle_register_write(REG_APU_PCM_LO,     0)
    apu_io.handle_register_write(REG_APU_PCM_HI,     0)
    apu_io.handle_register_write(REG_APU_PCM_LEN_LO, 16)
    apu_io.handle_register_write(REG_APU_PCM_LEN_HI,  0)
    apu_io.handle_register_write(REG_APU_CMD, ApuCmd.PLAY_PCM)
    assert apu_io.is_active(0), "Channel 0 should be active for PCM"
    pcm_chunk = apu_io._generate_chunk(16)
    pcm_samps = struct.unpack_from('<16h', pcm_chunk)
    assert all(s > 0 for s in pcm_samps), f"PCM samples should be positive: {pcm_samps}"
    print("  PCM playback via IO registers: PASS")

    # STOP_ALL via IO register command
    apu_io.handle_register_write(REG_APU_CMD, ApuCmd.STOP_ALL)
    assert not apu_io.is_active(0), "Channel should stop after STOP_ALL"
    print("  STOP_ALL command: PASS")

    print("  PASS")


    # ------------------------------------------------------------------
    print("\n[14] Interrupt system (v7)")
    a14 = Assembler()

    # SEI / CLI
    c = GMC16CPU(); a14.assemble("SEI\nHALT").load_into(c.bus)
    c.reset(); c.run(max_steps=50)
    assert c.IME == True,  "SEI must set IME"
    c = GMC16CPU(); a14.assemble("CLI\nHALT").load_into(c.bus)
    c.reset(); c.run(max_steps=50)
    assert c.IME == False, "CLI must clear IME"
    print("  SEI / CLI: PASS")

    # TRIG 0 + RETI
    # Fixed ROM 0x2000: SEI(2) TRIG0(4) HALT(2) -> handler@0x2008
    MAGIC = 0xBEEF; TARGET = 0x0010
    cpu_t = GMC16CPU()
    a14.assemble(
        "BANK FIXED\n"
        "SEI\n"
        "TRIG 0\n"
        "HALT\n"
        "handler:\n"
        f"LOADI  R0, {0xBEEF}\n"
        f"LOADI  R1, {0x0010}\n"
        "STORE  R0, R1\n"
        "RETI\n"
    ).load_into(cpu_t.bus)
    off = IVT_IRQ0 - BANK_FIXED_START
    ha  = BANK_FIXED_START + 8
    cpu_t.bus._rom_fixed[off]     = ha & 0xFF
    cpu_t.bus._rom_fixed[off + 1] = (ha >> 8) & 0xFF
    cpu_t.bus._io[REG_IE - IO_START] = INT_IRQ0
    cpu_t.reset(); cpu_t.run(max_steps=500)
    got = cpu_t.bus.read16(TARGET)
    assert got == MAGIC, f"IRQ0 handler not run: 0x{got:04X}"
    print("  TRIG / RETI dispatch: PASS")

    # Timer sets IF
    cpu_tmr = GMC16CPU()
    a14.assemble(
        "LOADI  R0, 5\n"
        "LOADI  R7, REG_TIMER_PERIOD_LO\n"
        "STORE  R0, R7\n"
        "LOADI  R0, 0\n"
        "LOADI  R7, REG_TIMER_PERIOD_HI\n"
        "STORE  R0, R7\n"
        "NOP\nNOP\nNOP\nNOP\nNOP\nNOP\nNOP\n"
        "HALT\n"
    ).load_into(cpu_tmr.bus)
    cpu_tmr.reset(); cpu_tmr.run(max_steps=200)
    assert cpu_tmr.bus._io[REG_IF - IO_START] & INT_TIMER, "TIMER IF not set"
    print("  Timer sets IF: PASS")

    # VBLANK on FLIP_BUFFER
    cpu_vbl = GMC16CPU()
    cpu_vbl.gpu._cmd_flip_buffer()
    assert cpu_vbl.bus._io[REG_IF - IO_START] & INT_VBLANK, "VBLANK not set"
    print("  VBLANK sets IF on FLIP_BUFFER: PASS")

    # REG_IF write-to-clear
    cpu_vbl.bus._io[REG_IF - IO_START] = 0xFF
    cpu_vbl.bus.write(REG_IF, ~INT_VBLANK & 0xFF)
    if_after = cpu_vbl.bus._io[REG_IF - IO_START]
    assert not (if_after & INT_VBLANK), "VBLANK not cleared"
    assert     (if_after & INT_TIMER),  "other bits must remain"
    print("  REG_IF write-to-clear: PASS")

    # IME=False blocks dispatch
    cpu_nd = GMC16CPU()
    cpu_nd.bus._io[REG_IE - IO_START] = INT_IRQ0
    cpu_nd.bus._io[REG_IF - IO_START] = INT_IRQ0
    cpu_nd.IME = False
    pc0 = cpu_nd.PC
    cpu_nd._check_interrupts()
    assert cpu_nd.PC == pc0, "PC changed when IME=False"
    print("  IME=False blocks dispatch: PASS")

    print("  PASS")

    # ------------------------------------------------------------------
    print("\n[15] Bug fixes (v7.1)")

    # Fix 1: TRIG 0 sets INT_IRQ0 (bit 4), NOT INT_VBLANK (bit 0)
    cpu_tm = GMC16CPU()
    Assembler().assemble("TRIG 0\nHALT").load_into(cpu_tm.bus)
    cpu_tm.bus._io[REG_IE - IO_START] = 0xFF
    cpu_tm.IME = False
    cpu_tm.reset()
    cpu_tm.bus._io[REG_IE - IO_START] = 0xFF
    cpu_tm.IME = False
    cpu_tm.run(max_steps=50)
    ifv = cpu_tm.bus._io[REG_IF - IO_START]
    assert ifv & INT_IRQ0,        f"TRIG 0 must set INT_IRQ0: IF=0x{ifv:02X}"
    assert not (ifv & INT_VBLANK),f"TRIG 0 must not set VBLANK: IF=0x{ifv:02X}"
    print("  TRIG mask (IRQ0=bit4): PASS")

    # Fix 2: PUSH/POP order -- stack balanced after RETI
    cpu_st = GMC16CPU()
    Assembler().assemble(
        "BANK FIXED\nSEI\nTRIG 0\nHALT\nhandler:\nRETI"
    ).load_into(cpu_st.bus)
    off2 = IVT_IRQ0 - BANK_FIXED_START
    ha2  = BANK_FIXED_START + 8
    cpu_st.bus._rom_fixed[off2]     = ha2 & 0xFF
    cpu_st.bus._rom_fixed[off2 + 1] = (ha2 >> 8) & 0xFF
    cpu_st.bus._io[REG_IE - IO_START] = INT_IRQ0
    cpu_st.reset()
    sp0 = cpu_st.SP
    cpu_st.run(max_steps=200)
    assert cpu_st.SP == sp0, f"Stack unbalanced: SP=0x{cpu_st.SP:04X} != 0x{sp0:04X}"
    assert cpu_st.halted
    print("  PUSH/POP order (stack balanced after RETI): PASS")

    # Fix 3: SPRITEIMG sid always-immediate
    cpu_si = GMC16CPU()
    Assembler().assemble("SPRITEIMG 3, 7\nHALT").load_into(cpu_si.bus)
    cpu_si.reset(); cpu_si.run(max_steps=50)
    assert cpu_si.gpu.sprites[3].tile_index == 7
    print("  SPRITEIMG sid-immediate: PASS")

    # Fix 4: EQU colon syntax
    asm_eq = Assembler()
    img_eq = asm_eq.assemble("ANSWER: EQU 42\nLOADI R0, ANSWER\nHALT")
    cpu_eq = GMC16CPU()
    img_eq.load_into(cpu_eq.bus)
    cpu_eq.reset(); cpu_eq.run(max_steps=50)
    assert cpu_eq.R[0] == 42,                     f"EQU: R0={cpu_eq.R[0]}"
    assert "ANSWER" not in asm_eq.labels,          "ANSWER should not be a label"
    assert asm_eq.constants.get("ANSWER") == 42,  "ANSWER should be in constants"
    print("  EQU colon syntax: PASS")

    # Fix 5: VRAM read auto-increment
    gpu_vr = GPU()
    RED16  = 0xF800; BLUE16 = 0x001F
    gpu_vr.vram_write(0x0000, RED16)
    gpu_vr.vram_write(0x0002, BLUE16)
    bus_vr = MemoryBus(gpu_vr)
    bus_vr.write(REG_VRAM_ADDR_LO, 0x00)
    bus_vr.write(REG_VRAM_ADDR_HI, 0x00)
    lo1 = bus_vr.read(REG_VRAM_DATA_LO)
    hi1 = bus_vr.read(REG_VRAM_DATA_HI)   # auto-increments to 0x0002
    assert (lo1 | (hi1 << 8)) == RED16,  f"VRAM read[0]=0x{lo1|(hi1<<8):04X}"
    lo2 = bus_vr.read(REG_VRAM_DATA_LO)
    hi2 = bus_vr.read(REG_VRAM_DATA_HI)
    assert (lo2 | (hi2 << 8)) == BLUE16, f"VRAM read[1]=0x{lo2|(hi2<<8):04X}"
    print("  VRAM read auto-increment: PASS")

    # Fix 6: Sprite flip_x / flip_y
    RED16 = 0xF800
    # Tile with left column red, rest black
    col_stripe = [RED16 if px == 0 else 0x0000
                  for py in range(TILE_H) for px in range(TILE_W)]
    gpu_sf = GPU()
    for t in range(4): gpu_sf.load_tile(t, col_stripe)
    s = gpu_sf.sprites[0]
    s.tile_index = 0; s.x = 0; s.y = 0; s.flags = 0x01  # visible
    gpu_sf._cmd_clear(0x0000); gpu_sf._cmd_draw_sprites()
    assert gpu_sf.back_framebuffer[0] == RED16,   "no-flip: (0,0) RED"
    assert gpu_sf.back_framebuffer[1] == 0x0000,  "no-flip: (1,0) black"
    s.flags = 0x01 | 0x02  # flip_x
    gpu_sf._cmd_clear(0x0000); gpu_sf._cmd_draw_sprites()
    assert gpu_sf.back_framebuffer[0] == 0x0000,              "flip_x: (0,0) black"
    assert gpu_sf.back_framebuffer[TILE_W * 2 - 1] == RED16, "flip_x: right edge RED"
    # Tile with top row red, rest black
    row_stripe = [RED16 if py == 0 else 0x0000
                  for py in range(TILE_H) for px in range(TILE_W)]
    for t in range(4): gpu_sf.load_tile(t, row_stripe)
    s.flags = 0x01 | 0x04  # flip_y
    gpu_sf._cmd_clear(0x0000); gpu_sf._cmd_draw_sprites()
    assert gpu_sf.back_framebuffer[0] == 0x0000,                          "flip_y: top black"
    assert gpu_sf.back_framebuffer[(TILE_H*2 - 1)*SCREEN_W] == RED16,     "flip_y: bottom RED"
    print("  Sprite flip_x / flip_y: PASS")

    print("  PASS")
    print("\n" + "=" * 64)
    print("All 15 tests passed!")
    print("=" * 64)


if __name__ == "__main__":
    _run_tests()
