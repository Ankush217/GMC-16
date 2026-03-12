; ============================================================
;  PONG  --  GMC-16 Assembly
;  Two-player. W/S = P1.  Arrow Up/Down = P2.
;  First to 9 wins.
; ============================================================

; ---- Controller bit masks ----------------------------------
BTN_UP     EQU 0x01
BTN_DOWN   EQU 0x02
BTN_LEFT   EQU 0x04
BTN_RIGHT  EQU 0x08
BTN_A      EQU 0x10
BTN_START  EQU 0x40

; ---- Screen dimensions -------------------------------------
SW         EQU SCREEN_W          ; 256
SH         EQU SCREEN_H          ; 128

; ---- Paddle geometry ---------------------------------------
PAD_W      EQU 4
PAD_H      EQU 20
PAD_SPEED  EQU 3
PAD1_X     EQU 8
PAD2_X     EQU SW - 8 - PAD_W   ; 244

; ---- Ball geometry -----------------------------------------
BALL_W     EQU 4
BALL_H     EQU 4

; ---- Score limit -------------------------------------------
WIN_SCORE  EQU 9

; ---- RAM layout  (addresses in 0x0000-0x1FFF) --------------
; Paddle 1
PAD1_Y     EQU 0x0000   ; word  -- paddle 1 Y position
; Paddle 2
PAD2_Y     EQU 0x0002   ; word  -- paddle 2 Y position
; Ball
BALL_X     EQU 0x0004   ; word  -- ball X (pixel)
BALL_Y     EQU 0x0006   ; word  -- ball Y (pixel)
BALL_VX    EQU 0x0008   ; word  -- ball X velocity (signed, 2's comp)
BALL_VY    EQU 0x000A   ; word  -- ball Y velocity (signed, 2's comp)
; Scores
SCORE1     EQU 0x000C   ; word  -- player 1 score
SCORE2     EQU 0x000E   ; word  -- player 2 score
; Scratch
TMP        EQU 0x0010   ; word  -- general scratch

; ---- Colours (RGB565) --------------------------------------
COL_BG     EQU 0x0000   ; black
COL_NET    EQU 0x2945   ; dark grey
COL_PAD1   EQU 0x07FF   ; cyan
COL_PAD2   EQU 0xF81F   ; magenta
COL_BALL   EQU 0xFFE0   ; yellow
COL_SCORE  EQU 0x07E0   ; green
COL_WIN    EQU 0xF800   ; red (win flash)

; ---- Sprite IDs -------------------------------------------
SPR_PAD1   EQU 0
SPR_PAD2   EQU 1
SPR_BALL   EQU 2

; ============================================================
;  ENTRY POINT
; ============================================================
START:
    CALL   INIT
MAIN_LOOP:
    CALL   READ_INPUT
    CALL   MOVE_PADDLES
    CALL   MOVE_BALL
    CALL   CHECK_SCORE
    CALL   DRAW_FRAME
    WAITVBLANK
    JMP    MAIN_LOOP

; ============================================================
;  INIT  -- set up everything once
; ============================================================
INIT:
    ; Clear scores
    LOADI  R0, 0
    LOADI  R1, SCORE1
    STORE  R1, R0
    LOADI  R1, SCORE2
    STORE  R1, R0

    ; Paddle start positions (vertically centred)
    LOADI  R0, (SH - PAD_H) / 2
    LOADI  R1, PAD1_Y
    STORE  R1, R0
    LOADI  R1, PAD2_Y
    STORE  R1, R0

    ; Ball start
    CALL   RESET_BALL

    ; Set up sprite images (colour-coded solid rectangles)
    ; We abuse tile_index as flat colour in the GPU's _cmd_draw_sprites,
    ; so set each sprite's image to its colour word.
    SPRITEIMG  SPR_PAD1, COL_PAD1
    SPRITEIMG  SPR_PAD2, COL_PAD2
    SPRITEIMG  SPR_BALL, COL_BALL

    SPRITEENABLE SPR_PAD1
    SPRITEENABLE SPR_PAD2
    SPRITEENABLE SPR_BALL

    RET

; ============================================================
;  RESET_BALL  -- centre, random-ish velocity
; ============================================================
RESET_BALL:
    ; Position: centre of screen
    LOADI  R0, (SW - BALL_W) / 2
    LOADI  R1, BALL_X
    STORE  R1, R0

    LOADI  R0, (SH - BALL_H) / 2
    LOADI  R1, BALL_Y
    STORE  R1, R0

    ; VX = 2  (always start moving right; alternates after each point)
    LOADI  R0, BALL_X
    LOAD   R7, R0            ; load ball_x just as a dummy read to use R7
    ; Use RAND to pick an initial VY  (-1 or +1)
    RAND   R0
    LOADI  R1, 1
    AND    R0, R1            ; bit 0 only → 0 or 1
    ; if R0==0 → VY = 0xFFFE (-2), else VY = 2
    LOADI  R2, 2
    LOADI  R3, 0xFFFE        ; -2 in 16-bit 2's complement
    CMP    R0, R1            ; compare R0 with 1
    JZ     RESET_VY_POS
    LOADI  R2, 0xFFFE
RESET_VY_POS:
    LOADI  R1, BALL_VY
    STORE  R1, R2

    ; VX always starts at +2
    LOADI  R0, 2
    LOADI  R1, BALL_VX
    STORE  R1, R0

    RET

; ============================================================
;  READ_INPUT  -- poll controller, store intent in R5/R6
;  R5 = P1 buttons,  R6 = P2 buttons
;  (Both players share one controller register in this build;
;   P1 uses W/S  = UP/DOWN bits, P2 uses Arrow UP/DOWN.)
; ============================================================
READ_INPUT:
    INPUT  R5            ; R5 = full controller byte (P1 = W/S mapped to UP/DOWN)
    ; P2 shares the same controller but via LEFT/RIGHT repurposed --
    ; actually the spec only has one controller register 0xFF00.
    ; We'll map P1 = bits 0/1 (UP/DOWN), P2 = bits 2/3 (LEFT/RIGHT → up/down)
    MOV    R6, R5        ; copy for P2 extraction
    ; mask P1 to UP/DOWN only
    LOADI  R0, BTN_UP | BTN_DOWN
    AND    R5, R0
    ; shift P2 bits: LEFT→UP, RIGHT→DOWN  (bits 2,3 → 0,1)
    LOADI  R0, BTN_LEFT | BTN_RIGHT
    AND    R6, R0
    LOADI  R0, 2
    SHR    R6             ; one right shift
    SHR    R6             ; second right shift  → P2 now in bits 0,1
    RET

; ============================================================
;  MOVE_PADDLES
; ============================================================
MOVE_PADDLES:
    ; ---- Paddle 1 (R5) ----
    LOADI  R1, PAD1_Y
    LOAD   R0, R1           ; R0 = current P1 Y

    LOADI  R2, BTN_UP
    AND    R2, R5
    JZ     P1_CHECK_DOWN
    ; Move up
    LOADI  R3, PAD_SPEED
    SUB    R0, R3
    ; clamp to 0
    LOADI  R3, 0
    CMP    R0, R3
    JL     P1_CLAMP_TOP
    JMP    P1_DONE_UP
P1_CLAMP_TOP:
    LOADI  R0, 0
P1_DONE_UP:
    JMP    P1_STORE

P1_CHECK_DOWN:
    LOADI  R2, BTN_DOWN
    AND    R2, R5
    JZ     P1_STORE
    ; Move down
    LOADI  R3, PAD_SPEED
    ADD    R0, R3
    ; clamp to SH - PAD_H
    LOADI  R3, SH - PAD_H
    CMP    R0, R3
    JG     P1_CLAMP_BOT
    JMP    P1_STORE
P1_CLAMP_BOT:
    LOADI  R0, SH - PAD_H

P1_STORE:
    LOADI  R1, PAD1_Y
    STORE  R1, R0

    ; ---- Paddle 2 (R6) ----
    LOADI  R1, PAD2_Y
    LOAD   R0, R1           ; R0 = current P2 Y

    LOADI  R2, BTN_UP
    AND    R2, R6
    JZ     P2_CHECK_DOWN
    LOADI  R3, PAD_SPEED
    SUB    R0, R3
    LOADI  R3, 0
    CMP    R0, R3
    JL     P2_CLAMP_TOP
    JMP    P2_DONE_UP
P2_CLAMP_TOP:
    LOADI  R0, 0
P2_DONE_UP:
    JMP    P2_STORE

P2_CHECK_DOWN:
    LOADI  R2, BTN_DOWN
    AND    R2, R6
    JZ     P2_STORE
    LOADI  R3, PAD_SPEED
    ADD    R0, R3
    LOADI  R3, SH - PAD_H
    CMP    R0, R3
    JG     P2_CLAMP_BOT
    JMP    P2_STORE
P2_CLAMP_BOT:
    LOADI  R0, SH - PAD_H

P2_STORE:
    LOADI  R1, PAD2_Y
    STORE  R1, R0
    RET

; ============================================================
;  MOVE_BALL
; ============================================================
MOVE_BALL:
    ; Load ball state
    LOADI  R0, BALL_X
    LOAD   R1, R0           ; R1 = BX
    LOADI  R0, BALL_Y
    LOAD   R2, R0           ; R2 = BY
    LOADI  R0, BALL_VX
    LOAD   R3, R0           ; R3 = VX
    LOADI  R0, BALL_VY
    LOAD   R4, R0           ; R4 = VY

    ; Apply velocity
    ADD    R1, R3           ; BX += VX
    ADD    R2, R4           ; BY += VY

    ; ---- Top/bottom wall bounce ----
    LOADI  R0, 0
    CMP    R2, R0
    JL     BOUNCE_TOP

    LOADI  R0, SH - BALL_H
    CMP    R2, R0
    JG     BOUNCE_BOT
    JMP    CHECK_PADDLES

BOUNCE_TOP:
    LOADI  R2, 0
    NEG    R4               ; flip VY
    JMP    CHECK_PADDLES

BOUNCE_BOT:
    LOADI  R2, SH - BALL_H
    NEG    R4               ; flip VY

    ; ---- Paddle collision ----
CHECK_PADDLES:
    ; -- P1 paddle: X range [PAD1_X, PAD1_X+PAD_W)  left edge --
    ; Ball hits P1 if BX <= PAD1_X+PAD_W  AND  BX+BALL_W >= PAD1_X
    ;              AND BY+BALL_H >= PAD1_Y AND BY <= PAD1_Y+PAD_H
    ; Simple: only test when ball moving left (VX is negative, i.e. bit15 set)
    LOADI  R0, 0x8000
    AND    R0, R3
    JZ     CHECK_P2_PAD     ; VX positive → ball going right, skip P1 check

    ; Check X overlap with P1
    LOADI  R0, PAD1_X + PAD_W
    CMP    R1, R0            ; BX vs PAD1_X+PAD_W
    JG     CHECK_P2_PAD     ; BX > right edge of P1 → no hit

    ; Check Y overlap with P1
    LOADI  R0, PAD1_Y
    LOAD   R0, R0            ; R0 = P1Y
    LOADI  R7, PAD_H
    ADD    R7, R0            ; R7 = P1Y + PAD_H

    CMP    R2, R7            ; BY vs P1Y+PAD_H
    JG     CHECK_P2_PAD     ; BY > bottom of paddle → miss

    ADD    R0, R0            ; dirty trick: just use scratch
    ; BY + BALL_H >= P1Y?
    LOADI  R0, PAD1_Y
    LOAD   R0, R0
    CMP    R2, R0            ; BY vs P1Y  (BY must be >= P1Y - BALL_H, approx)
    ; use: BY <= P1Y + PAD_H already checked; BY + BALL_H >= P1Y → BY >= P1Y - BALL_H
    LOADI  R7, BALL_H
    SUB    R0, R7            ; P1Y - BALL_H
    CMP    R2, R0
    JL     CHECK_P2_PAD     ; BY < P1Y-BALL_H → above paddle

    ; HIT P1 paddle
    LOADI  R0, PAD1_X + PAD_W
    MOV    R1, R0            ; snap BX to right of paddle
    NEG    R3                ; flip VX
    ; Slight speed increase: add 1 to magnitude (VX now positive after NEG)
    LOADI  R0, 1
    ADD    R3, R0
    ; Cap speed at 6
    LOADI  R0, 6
    CMP    R3, R0
    JG     CAP_VX_P1
    JMP    CHECK_P2_PAD
CAP_VX_P1:
    LOADI  R3, 6

CHECK_P2_PAD:
    ; Only test when ball moving right (VX positive, bit15 clear)
    LOADI  R0, 0x8000
    AND    R0, R3
    JNZ    BALL_SAVE         ; VX negative → skip P2 check

    ; Check X overlap with P2
    LOADI  R0, PAD2_X
    CMP    R1, R0            ; BX vs PAD2_X
    JL     BALL_SAVE         ; BX < PAD2_X → not there yet

    ; Check Y overlap with P2
    LOADI  R0, PAD2_Y
    LOAD   R0, R0            ; R0 = P2Y
    LOADI  R7, PAD_H
    ADD    R7, R0            ; R7 = P2Y + PAD_H

    CMP    R2, R7
    JG     BALL_SAVE

    LOADI  R0, PAD2_Y
    LOAD   R0, R0
    LOADI  R7, BALL_H
    SUB    R0, R7
    CMP    R2, R0
    JL     BALL_SAVE

    ; HIT P2 paddle
    LOADI  R0, PAD2_X - BALL_W
    MOV    R1, R0
    NEG    R3
    LOADI  R0, 1
    SUB    R3, R0            ; subtract 1 to increase magnitude (VX is negative)
    ; Cap at -6 (0xFFFA)
    LOADI  R0, 0xFFFA        ; -6
    CMP    R3, R0
    JL     CAP_VX_P2
    JMP    BALL_SAVE
CAP_VX_P2:
    LOADI  R3, 0xFFFA

BALL_SAVE:
    ; Write back
    LOADI  R0, BALL_X
    STORE  R0, R1
    LOADI  R0, BALL_Y
    STORE  R0, R2
    LOADI  R0, BALL_VX
    STORE  R0, R3
    LOADI  R0, BALL_VY
    STORE  R0, R4
    RET

; ============================================================
;  CHECK_SCORE  -- did ball go past a paddle?
; ============================================================
CHECK_SCORE:
    LOADI  R0, BALL_X
    LOAD   R1, R0           ; R1 = BX

    ; Ball past left edge → P2 scores
    LOADI  R0, 0
    CMP    R1, R0
    JL     P2_SCORES

    ; Ball past right edge → P1 scores
    LOADI  R0, SW
    CMP    R1, R0
    JG     P1_SCORES
    RET

P1_SCORES:
    LOADI  R0, SCORE1
    LOAD   R1, R0
    LOADI  R2, 1
    ADD    R1, R2
    STORE  R0, R1
    CALL   CHECK_WIN
    CALL   RESET_BALL
    RET

P2_SCORES:
    LOADI  R0, SCORE2
    LOAD   R1, R0
    LOADI  R2, 1
    ADD    R1, R2
    STORE  R0, R1
    CALL   CHECK_WIN
    CALL   RESET_BALL
    RET

; ============================================================
;  CHECK_WIN  -- if anyone has WIN_SCORE, do a victory flash
;               then reset scores and ball
; ============================================================
CHECK_WIN:
    LOADI  R0, WIN_SCORE
    LOADI  R1, SCORE1
    LOAD   R1, R1
    CMP    R1, R0
    JZ     DO_WIN

    LOADI  R1, SCORE2
    LOAD   R1, R1
    CMP    R1, R0
    JZ     DO_WIN
    RET

DO_WIN:
    ; Flash screen 6 times with COL_WIN then black
    LOADI  R7, 6
WIN_FLASH_LOOP:
    CLS    COL_WIN
    ; GPU flip
    LOADI  R0, 3
    LOADI  R1, 0xFF10
    STORE  R1, R0
    WAITVBLANK
    CLS    COL_BG
    LOADI  R0, 3
    STORE  R1, R0
    WAITVBLANK
    DEC    R7
    JNZ    WIN_FLASH_LOOP

    ; Reset scores
    LOADI  R0, 0
    LOADI  R1, SCORE1
    STORE  R1, R0
    LOADI  R1, SCORE2
    STORE  R1, R0

    CALL   RESET_BALL
    RET

; ============================================================
;  DRAW_FRAME
;  Draw:  background → net → paddles → ball → flip
; ============================================================
DRAW_FRAME:
    ; --- Clear back-buffer ---
    CLS    COL_BG

    ; --- Dotted centre net ---
    ; Draw vertical dots every 4 pixels from top to bottom
    LOADI  R5, 0            ; Y counter
    LOADI  R6, SW / 2       ; net X = 128
NET_LOOP:
    ; draw 2px dot
    RECT   R6, R5, 2, 2, COL_NET
    ; skip 4 pixels (gap)
    LOADI  R0, 6
    ADD    R5, R0
    LOADI  R0, SH
    CMP    R5, R0
    JL     NET_LOOP

    ; --- Paddle 1 ---
    LOADI  R0, PAD1_Y
    LOAD   R1, R0            ; R1 = P1Y
    RECT   PAD1_X, R1, PAD_W, PAD_H, COL_PAD1

    ; --- Paddle 2 ---
    LOADI  R0, PAD2_Y
    LOAD   R1, R0            ; R1 = P2Y
    RECT   PAD2_X, R1, PAD_W, PAD_H, COL_PAD2

    ; --- Ball ---
    LOADI  R0, BALL_X
    LOAD   R1, R0
    LOADI  R0, BALL_Y
    LOAD   R2, R0
    RECT   R1, R2, BALL_W, BALL_H, COL_BALL

    ; --- Score digits (simple 3×5 pixel digits) ---
    ; P1 score left of centre
    LOADI  R0, SCORE1
    LOAD   R0, R0
    LOADI  R1, SW / 2 - 20
    LOADI  R2, 4
    CALL   DRAW_DIGIT        ; R0=digit, R1=X, R2=Y, colour = COL_SCORE

    ; P2 score right of centre
    LOADI  R0, SCORE2
    LOAD   R0, R0
    LOADI  R1, SW / 2 + 14
    LOADI  R2, 4
    CALL   DRAW_DIGIT

    ; --- GPU flip (command 3) ---
    LOADI  R0, 3
    LOADI  R1, 0xFF10
    STORE  R1, R0

    RET

; ============================================================
;  DRAW_DIGIT  --  draw a single decimal digit 0-9
;  R0 = digit value (0-9)
;  R1 = X position
;  R2 = Y position
;  Uses a jump table into 10 inline rect sequences.
;  Each digit rendered as a 5×7 block (two 3×1 bars + sides).
;  Colour = COL_SCORE throughout.
; ============================================================
DRAW_DIGIT:
    ; jump table: DIGIT_0 .. DIGIT_9
    ; index = R0 * 2  → add to base
    PUSH   R0
    PUSH   R1
    PUSH   R2

    ; Compute jump target: DIGIT_TABLE + R0 * 2
    LOADI  R3, DIGIT_TABLE
    LOADI  R4, 2
    MUL    R0, R4            ; R0 = offset in words (each entry is one word = address)
    ; The table stores 16-bit addresses
    ADD    R3, R0
    LOAD   R3, R3            ; R3 = address of digit draw routine
    ; We can't indirect-jump directly; use CALL via SP trick:
    ; Push return address, then jump to R3
    ; GMC-16 has no indirect CALL, so we use self-modification or a chain.
    ; Instead: use a compare chain (simpler, works within spec).

    POP    R2
    POP    R1
    POP    R0

    ; Compare chain
    LOADI  R7, 0
    CMP    R0, R7
    JZ     DIGIT_0
    LOADI  R7, 1
    CMP    R0, R7
    JZ     DIGIT_1
    LOADI  R7, 2
    CMP    R0, R7
    JZ     DIGIT_2
    LOADI  R7, 3
    CMP    R0, R7
    JZ     DIGIT_3
    LOADI  R7, 4
    CMP    R0, R7
    JZ     DIGIT_4
    LOADI  R7, 5
    CMP    R0, R7
    JZ     DIGIT_5
    LOADI  R7, 6
    CMP    R0, R7
    JZ     DIGIT_6
    LOADI  R7, 7
    CMP    R0, R7
    JZ     DIGIT_7
    LOADI  R7, 8
    CMP    R0, R7
    JZ     DIGIT_8
    JMP    DIGIT_9           ; else 9

; Each digit is drawn as a series of RECTs.
; All use R1=X, R2=Y as top-left origin.
; Width of digit cell = 5, height = 7.
; Segments:
;   TOP    = rect(X,   Y,   5, 1, c)
;   MID    = rect(X,   Y+3, 5, 1, c)
;   BOT    = rect(X,   Y+6, 5, 1, c)
;   TL     = rect(X,   Y+1, 1, 2, c)   top-left vertical
;   TR     = rect(X+4, Y+1, 1, 2, c)   top-right vertical
;   BL     = rect(X,   Y+4, 1, 2, c)   bottom-left vertical
;   BR     = rect(X+4, Y+4, 1, 2, c)   bottom-right vertical
;
; R3..R6 used as scratch here (callee must save R5/R6 if needed --
; caller already saved them via PUSH).

; Helper macros expressed as inline labels:

DIGIT_0:
    ; TOP MID(no) BOT  TL TR BL BR
    RECT   R1, R2,       5, 1, COL_SCORE   ; top
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE   ; bot
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R1, R3,       1, 5, COL_SCORE   ; left
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R3,       1, 5, COL_SCORE   ; right
    RET

DIGIT_1:
    ; Only right side vertical, top dot
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R2,       1, 7, COL_SCORE
    RET

DIGIT_2:
    ; TOP TR MID BL BOT
    RECT   R1, R2,       5, 1, COL_SCORE   ; top
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE   ; mid
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE   ; bot
    LOADI  R3, 1
    ADD    R3, R2
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R3,       1, 2, COL_SCORE   ; TR
    LOADI  R3, 4
    ADD    R3, R2
    RECT   R1, R3,       1, 2, COL_SCORE   ; BL
    RET

DIGIT_3:
    ; TOP TR MID BR BOT
    RECT   R1, R2,       5, 1, COL_SCORE
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R4, 4
    ADD    R4, R1
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R4, R3,       1, 5, COL_SCORE   ; full right side
    RET

DIGIT_4:
    ; TL TR MID BR
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R1, R3,       1, 2, COL_SCORE   ; TL
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R3,       1, 5, COL_SCORE   ; full TR+BR
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE   ; mid
    RET

DIGIT_5:
    ; TOP TL MID BR BOT
    RECT   R1, R2,       5, 1, COL_SCORE
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R1, R3,       1, 2, COL_SCORE   ; TL
    LOADI  R4, 4
    ADD    R4, R1
    LOADI  R3, 4
    ADD    R3, R2
    RECT   R4, R3,       1, 2, COL_SCORE   ; BR
    RET

DIGIT_6:
    ; TOP TL MID BL BR BOT
    RECT   R1, R2,       5, 1, COL_SCORE
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R1, R3,       1, 5, COL_SCORE   ; full left
    LOADI  R4, 4
    ADD    R4, R1
    LOADI  R3, 4
    ADD    R3, R2
    RECT   R4, R3,       1, 2, COL_SCORE   ; BR only
    RET

DIGIT_7:
    ; TOP TR (straight down right)
    RECT   R1, R2,       5, 1, COL_SCORE
    LOADI  R4, 4
    ADD    R4, R1
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R4, R3,       1, 6, COL_SCORE
    RET

DIGIT_8:
    ; All segments
    RECT   R1, R2,       5, 1, COL_SCORE
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R1, R3,       1, 5, COL_SCORE   ; full left
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R3,       1, 5, COL_SCORE   ; full right
    RET

DIGIT_9:
    ; TOP TL TR MID BR BOT
    RECT   R1, R2,       5, 1, COL_SCORE
    LOADI  R3, 3
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 6
    ADD    R3, R2
    RECT   R1, R3,       5, 1, COL_SCORE
    LOADI  R3, 1
    ADD    R3, R2
    RECT   R1, R3,       1, 2, COL_SCORE   ; TL
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R3,       1, 5, COL_SCORE   ; full right
    RET

; ---- Unused table reference (kept for documentation) -------
DIGIT_TABLE:
    ; Would hold addresses if indirect jump were available.
    ; Not used at runtime; compare chain used instead.

    HALT