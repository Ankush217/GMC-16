; ============================================================
;  PONG for GMC.py v7
;  Controls:
;    Player 1: Z up, X down
;    Player 2: CPU
;  First to 9 wins.
; ============================================================

; ---- Controller bits ---------------------------------------
BTN_UP      EQU 0x01
BTN_DOWN    EQU 0x02
BTN_LEFT    EQU 0x04
BTN_RIGHT   EQU 0x08
BTN_A       EQU 0x10
BTN_B       EQU 0x20

; ---- Screen -------------------------------------------------
SW          EQU SCREEN_W
SH          EQU SCREEN_H

; ---- Geometry ----------------------------------------------
PAD_W       EQU 4
PAD_H       EQU 20
PAD_SPEED   EQU 3
PAD1_X      EQU 8
PAD2_X      EQU SW - 12

BALL_W      EQU 4
BALL_H      EQU 4

WIN_SCORE   EQU 9

; ---- Colors -------------------------------------------------
COL_BG      EQU 0x0000
COL_NET     EQU 0x3186
COL_P1      EQU 0x07FF
COL_P2      EQU 0xF81F
COL_BALL    EQU 0xFFE0
COL_SCORE1  EQU 0x07E0
COL_SCORE2  EQU 0xFBE0
COL_WIN1    EQU 0x07FF
COL_WIN2    EQU 0xF81F

; ---- RAM layout --------------------------------------------
PAD1_Y      EQU 0x0000
PAD2_Y      EQU 0x0002
BALL_X      EQU 0x0004
BALL_Y      EQU 0x0006
BALL_VX     EQU 0x0008
BALL_VY     EQU 0x000A
SCORE1      EQU 0x000C
SCORE2      EQU 0x000E
SERVE_DIR   EQU 0x0010    ; +1 or -1
WINNER      EQU 0x0012    ; 0, 1, 2

; ============================================================
;  Entry
; ============================================================
START:
    CALL INIT

MAIN_LOOP:
    INPUT  R7
    CALL   MOVE_PADDLES
    CALL   MOVE_BALL
    CALL   CHECK_SCORE
    CALL   DRAW_FRAME
    CALL   FLIP_FRAME
    WAITVBLANK
    JMP    MAIN_LOOP

; ============================================================
;  Init
; ============================================================
INIT:
    LOADI  R0, (SH - PAD_H) / 2
    LOADI  R1, PAD1_Y
    STORE  R0, R1
    LOADI  R1, PAD2_Y
    STORE  R0, R1

    LOADI  R0, 0
    LOADI  R1, SCORE1
    STORE  R0, R1
    LOADI  R1, SCORE2
    STORE  R0, R1
    LOADI  R1, WINNER
    STORE  R0, R1

    LOADI  R0, 1
    LOADI  R1, SERVE_DIR
    STORE  R0, R1

    CALL   RESET_BALL
    RET

; ============================================================
;  Reset Ball
; ============================================================
RESET_BALL:
    LOADI  R0, (SW - BALL_W) / 2
    LOADI  R1, BALL_X
    STORE  R0, R1

    LOADI  R0, (SH - BALL_H) / 2
    LOADI  R1, BALL_Y
    STORE  R0, R1

    LOADI  R1, SERVE_DIR
    LOAD   R2, R1
    LOADI  R3, 0
    CMP    R2, R3
    JL     RESET_BALL_LEFT

    LOADI  R0, 2
    LOADI  R1, BALL_VX
    STORE  R0, R1
    JMP    RESET_BALL_VY

RESET_BALL_LEFT:
    LOADI  R0, 0xFFFE
    LOADI  R1, BALL_VX
    STORE  R0, R1

RESET_BALL_VY:
    RAND   R0
    LOADI  R1, 1
    AND    R0, R1
    CMP    R0, R1
    JZ     RESET_BALL_VY_POS
    LOADI  R0, 0xFFFF
    JMP    RESET_BALL_VY_STORE

RESET_BALL_VY_POS:
    LOADI  R0, 1

RESET_BALL_VY_STORE:
    LOADI  R1, BALL_VY
    STORE  R0, R1
    RET

; ============================================================
;  Paddle movement
;  R7 = current controller state
; ============================================================
MOVE_PADDLES:
    ; Player 1 uses A/B
    LOADI  R0, PAD1_Y
    LOAD   R1, R0

    LOADI  R2, BTN_A
    AND    R2, R7
    JZ     P1_CHECK_DOWN
    LOADI  R3, PAD_SPEED
    SUB    R1, R3
    LOADI  R3, 0
    CMP    R1, R3
    JL     P1_TOP
    JMP    P1_STORE

P1_TOP:
    LOADI  R1, 0
    JMP    P1_STORE

P1_CHECK_DOWN:
    LOADI  R2, BTN_B
    AND    R2, R7
    JZ     P1_STORE
    LOADI  R3, PAD_SPEED
    ADD    R1, R3
    LOADI  R3, SH - PAD_H
    CMP    R1, R3
    JG     P1_BOTTOM
    JMP    P1_STORE

P1_BOTTOM:
    LOADI  R1, SH - PAD_H

P1_STORE:
    LOADI  R0, PAD1_Y
    STORE  R1, R0

    ; Player 2 AI tracks the ball with a small dead zone.
    LOADI  R0, PAD2_Y
    LOAD   R1, R0
    LOADI  R0, BALL_Y
    LOAD   R2, R0
    LOADI  R3, BALL_H / 2
    ADD    R2, R3             ; ball center Y

    LOADI  R3, PAD_H / 2
    ADD    R3, R1             ; paddle center Y

    LOADI  R4, 3
    SUB    R2, R4             ; upper bound of dead zone
    CMP    R3, R2
    JL     P2_MOVE_DOWN

    LOADI  R0, BALL_Y
    LOAD   R2, R0
    LOADI  R4, BALL_H / 2
    ADD    R2, R4
    LOADI  R4, 3
    ADD    R2, R4             ; lower bound of dead zone
    CMP    R3, R2
    JG     P2_MOVE_UP
    JMP    P2_STORE

P2_MOVE_UP:
    LOADI  R3, PAD_SPEED
    SUB    R1, R3
    LOADI  R3, 0
    CMP    R1, R3
    JL     P2_TOP
    JMP    P2_STORE

P2_TOP:
    LOADI  R1, 0
    JMP    P2_STORE

P2_MOVE_DOWN:
    LOADI  R3, PAD_SPEED
    ADD    R1, R3
    LOADI  R3, SH - PAD_H
    CMP    R1, R3
    JG     P2_BOTTOM
    JMP    P2_STORE

P2_BOTTOM:
    LOADI  R1, SH - PAD_H

P2_STORE:
    LOADI  R0, PAD2_Y
    STORE  R1, R0
    RET

; ============================================================
;  Ball movement and paddle collisions
; ============================================================
MOVE_BALL:
    LOADI  R0, BALL_X
    LOAD   R1, R0
    LOADI  R0, BALL_Y
    LOAD   R2, R0
    LOADI  R0, BALL_VX
    LOAD   R3, R0
    LOADI  R0, BALL_VY
    LOAD   R4, R0

    ADD    R1, R3
    ADD    R2, R4

    ; Top / bottom bounce
    LOADI  R0, 0
    CMP    R2, R0
    JL     BALL_HIT_TOP

    LOADI  R0, SH - BALL_H
    CMP    R2, R0
    JG     BALL_HIT_BOTTOM
    JMP    CHECK_P1_HIT

BALL_HIT_TOP:
    LOADI  R2, 0
    NEG    R4
    JMP    CHECK_P1_HIT

BALL_HIT_BOTTOM:
    LOADI  R2, SH - BALL_H
    NEG    R4

CHECK_P1_HIT:
    ; Only when moving left
    LOADI  R0, 0
    CMP    R3, R0
    JG     CHECK_P2_HIT

    ; Past paddle face?
    LOADI  R0, PAD1_X + PAD_W
    CMP    R1, R0
    JG     CHECK_P2_HIT

    ; Vertical overlap test
    LOADI  R0, PAD1_Y
    LOAD   R5, R0
    LOADI  R6, PAD_H + BALL_H
    ADD    R6, R5
    CMP    R2, R6
    JG     CHECK_P2_HIT

    LOADI  R6, BALL_H
    SUB    R5, R6
    CMP    R2, R5
    JL     CHECK_P2_HIT

    LOADI  R1, PAD1_X + PAD_W
    NEG    R3

CHECK_P2_HIT:
    ; Only when moving right
    LOADI  R0, 0
    CMP    R3, R0
    JL     SAVE_BALL

    LOADI  R0, PAD2_X - BALL_W
    CMP    R1, R0
    JL     SAVE_BALL

    LOADI  R0, PAD2_Y
    LOAD   R5, R0
    LOADI  R6, PAD_H + BALL_H
    ADD    R6, R5
    CMP    R2, R6
    JG     SAVE_BALL

    LOADI  R6, BALL_H
    SUB    R5, R6
    CMP    R2, R5
    JL     SAVE_BALL

    LOADI  R1, PAD2_X - BALL_W
    NEG    R3

SAVE_BALL:
    LOADI  R0, BALL_X
    STORE  R1, R0
    LOADI  R0, BALL_Y
    STORE  R2, R0
    LOADI  R0, BALL_VX
    STORE  R3, R0
    LOADI  R0, BALL_VY
    STORE  R4, R0
    RET

; ============================================================
;  Scoring and win handling
; ============================================================
CHECK_SCORE:
    LOADI  R0, BALL_X
    LOAD   R1, R0

    LOADI  R0, 0
    CMP    R1, R0
    JL     POINT_P2

    LOADI  R0, SW - BALL_W
    CMP    R1, R0
    JG     POINT_P1
    RET

POINT_P1:
    LOADI  R0, SCORE1
    LOAD   R1, R0
    LOADI  R2, 1
    ADD    R1, R2
    STORE  R1, R0
    LOADI  R0, 0xFFFF
    LOADI  R2, SERVE_DIR
    STORE  R0, R2
    LOADI  R0, 1
    LOADI  R2, WINNER
    STORE  R0, R2
    CALL   CHECK_WIN
    CALL   RESET_BALL
    RET

POINT_P2:
    LOADI  R0, SCORE2
    LOAD   R1, R0
    LOADI  R2, 1
    ADD    R1, R2
    STORE  R1, R0
    LOADI  R0, 1
    LOADI  R2, SERVE_DIR
    STORE  R0, R2
    LOADI  R0, 2
    LOADI  R2, WINNER
    STORE  R0, R2
    CALL   CHECK_WIN
    CALL   RESET_BALL
    RET

CHECK_WIN:
    LOADI  R0, SCORE1
    LOAD   R1, R0
    LOADI  R2, WIN_SCORE
    CMP    R1, R2
    JZ     WIN_SEQUENCE

    LOADI  R0, SCORE2
    LOAD   R1, R0
    CMP    R1, R2
    JZ     WIN_SEQUENCE
    RET

WIN_SEQUENCE:
    LOADI  R6, 18

WIN_FLASH_LOOP:
    LOADI  R0, WINNER
    LOAD   R1, R0
    LOADI  R2, 1
    CMP    R1, R2
    JZ     FLASH_P1

    CLS    COL_WIN2
    JMP    FLASH_DONE

FLASH_P1:
    CLS    COL_WIN1

FLASH_DONE:
    CALL   FLIP_FRAME
    WAITVBLANK
    DEC    R6
    JNZ    WIN_FLASH_LOOP

    LOADI  R0, 0
    LOADI  R1, SCORE1
    STORE  R0, R1
    LOADI  R1, SCORE2
    STORE  R0, R1
    LOADI  R1, WINNER
    STORE  R0, R1
    LOADI  R0, 1
    LOADI  R1, SERVE_DIR
    STORE  R0, R1
    RET

; ============================================================
;  Drawing
; ============================================================
DRAW_FRAME:
    CLS    COL_BG

    ; Center net
    LOADI  R5, 0
    LOADI  R6, SW / 2 - 1

NET_LOOP:
    RECT   R6, R5, 2, 4, COL_NET
    LOADI  R0, 8
    ADD    R5, R0
    LOADI  R0, SH
    CMP    R5, R0
    JL     NET_LOOP

    ; Paddles
    LOADI  R0, PAD1_Y
    LOAD   R1, R0
    RECT   PAD1_X, R1, PAD_W, PAD_H, COL_P1

    LOADI  R0, PAD2_Y
    LOAD   R1, R0
    RECT   PAD2_X, R1, PAD_W, PAD_H, COL_P2

    ; Ball
    LOADI  R0, BALL_X
    LOAD   R1, R0
    LOADI  R0, BALL_Y
    LOAD   R2, R0
    RECT   R1, R2, BALL_W, BALL_H, COL_BALL

    ; Score digits
    LOADI  R0, SCORE1
    LOAD   R0, R0
    LOADI  R1, SW / 2 - 24
    LOADI  R2, 8
    LOADI  R3, COL_SCORE1
    CALL   DRAW_DIGIT

    LOADI  R0, SCORE2
    LOAD   R0, R0
    LOADI  R1, SW / 2 + 16
    LOADI  R2, 8
    LOADI  R3, COL_SCORE2
    CALL   DRAW_DIGIT
    RET

DRAW_DIGIT:
    ; R0=digit, R1=x, R2=y, R3=color
    LOADI  R4, 0
    CMP    R0, R4
    JZ     DIGIT_0
    LOADI  R4, 1
    CMP    R0, R4
    JZ     DIGIT_1
    LOADI  R4, 2
    CMP    R0, R4
    JZ     DIGIT_2
    LOADI  R4, 3
    CMP    R0, R4
    JZ     DIGIT_3
    LOADI  R4, 4
    CMP    R0, R4
    JZ     DIGIT_4
    LOADI  R4, 5
    CMP    R0, R4
    JZ     DIGIT_5
    LOADI  R4, 6
    CMP    R0, R4
    JZ     DIGIT_6
    LOADI  R4, 7
    CMP    R0, R4
    JZ     DIGIT_7
    LOADI  R4, 8
    CMP    R0, R4
    JZ     DIGIT_8
    JMP    DIGIT_9

DIGIT_0:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R1, R4, 1, 5, R3
    LOADI  R5, 4
    ADD    R5, R1
    RECT   R5, R4, 1, 5, R3
    RET

DIGIT_1:
    LOADI  R4, 4
    ADD    R4, R1
    RECT   R4, R2, 1, 7, R3
    RET

DIGIT_2:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 1
    ADD    R4, R2
    LOADI  R5, 4
    ADD    R5, R1
    RECT   R5, R4, 1, 2, R3
    LOADI  R4, 4
    ADD    R4, R2
    RECT   R1, R4, 1, 2, R3
    RET

DIGIT_3:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R5, 4
    ADD    R5, R1
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R5, R4, 1, 5, R3
    RET

DIGIT_4:
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R1, R4, 1, 2, R3
    LOADI  R5, 4
    ADD    R5, R1
    RECT   R5, R4, 1, 5, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    RET

DIGIT_5:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R1, R4, 1, 2, R3
    LOADI  R5, 4
    ADD    R5, R1
    LOADI  R4, 4
    ADD    R4, R2
    RECT   R5, R4, 1, 2, R3
    RET

DIGIT_6:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R1, R4, 1, 5, R3
    LOADI  R5, 4
    ADD    R5, R1
    LOADI  R4, 4
    ADD    R4, R2
    RECT   R5, R4, 1, 2, R3
    RET

DIGIT_7:
    RECT   R1, R2, 5, 1, R3
    LOADI  R5, 4
    ADD    R5, R1
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R5, R4, 1, 6, R3
    RET

DIGIT_8:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R1, R4, 1, 5, R3
    LOADI  R5, 4
    ADD    R5, R1
    RECT   R5, R4, 1, 5, R3
    RET

DIGIT_9:
    RECT   R1, R2, 5, 1, R3
    LOADI  R4, 3
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 6
    ADD    R4, R2
    RECT   R1, R4, 5, 1, R3
    LOADI  R4, 1
    ADD    R4, R2
    RECT   R1, R4, 1, 2, R3
    LOADI  R5, 4
    ADD    R5, R1
    RECT   R5, R4, 1, 5, R3
    RET

FLIP_FRAME:
    LOADI  R0, 3
    LOADI  R1, 0xFF10
    STORE  R0, R1
    RET
