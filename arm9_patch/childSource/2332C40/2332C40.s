#include "../../dlpSource/dlp_boot.inc"

/* r0 points to the saved MB context. Restore the game's original group. */
.type relay_child_fixup,%function
relay_child_fixup:
  ldr r1, =CLIENT_GGID
  str r1, [r0, #0x0c]
  bx lr
.size relay_child_fixup, .-relay_child_fixup
.ltorg
