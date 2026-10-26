@ Download Station Volume 1 handoff; retain the original parent.
.syntax unified
.arch armv5te
.arm
.section .text,"ax",%progbits
.global relay_child
.type relay_child,%function
relay_child:
  ldr r3, =0x023fe840
  ldr r0, [r3, #0x2c]
  ldr r1, =CLIENT_ARM7_OFFSET
  sub r0, r0, r1
  ldr r1, =CLIENT_ARM9_OFFSET
  add r0, r0, r1
  ldr r1, =CLIENT_ARM9_RAM
  ldr r2, =CLIENT_ARM9_SIZE
  ldr r3, =0x0232bb08
  blx r3
  ldr r0, =0x027ffc42
  ldr r1, =0x023fe800
  mov r2, #0x3c
  ldr r3, =0x0232bbd4
  blx r3
  ldr r0, =0x023fe800
  ldr r1, =CLIENT_GGID
  str r1, [r0, #0x0c]
  ldr r3, =0x0232af24
  blx r3
  mov r0, #1
  ldr r3, =0x02323a78
  bx r3
.size relay_child, .-relay_child
.ltorg
