from GMC import *
import pygame

# load assembly
with open("pong.asm") as f:
    source = f.read()

asm = Assembler()
rom = asm.assemble(source)

gpu = GPU()
cpu = GMC16CPU(gpu)

gpu.renderer = PygameRenderer(scale=3, cpu_ref=cpu)

cpu.bus.load_rom(rom)
cpu.reset()

cpu.run()