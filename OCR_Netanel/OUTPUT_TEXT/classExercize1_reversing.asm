include 'C:\assembly\fasm\include\win32a.inc'

format PE console
entry start

section '.data' data readable writeable
    x db 1

section '.text' code readable executable
; ======================================
	
start:
	mov [x], 0x8
	mov 
	
; ====================================

	push	0
	call	[ExitProcess]


section '.idata' import data readable
    library kernel32, 'kernel32.dll'
    import kernel32, ExitProcess, 'ExitProcess'