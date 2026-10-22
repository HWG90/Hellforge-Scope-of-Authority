`tables_test.c` checks `mod/src/tables.c` without the game: it plants a HellForge-style copy of the Wieldable table in
its own memory, then finds it, claims a free record and refuses one that is not empty. `NOHINT=1` times a full memory
sweep over 1 GB of ballast.

    F:/Hellforge/tools/zig/zig.exe cc -std=c11 -target x86_64-windows-gnu -O2 -I F:/Hellforge/app/sdk tables_test.c ../mod/src/tables.c -o tables_test.exe
