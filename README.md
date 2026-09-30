# Eiltn

Eiltn is a systems-flavored language that does not run your program line by
line. The compiler lowers the whole program into a graph of **Eiltn Info
Nodes (EINs)**, and the runtime dispatches every node whose inputs are ready
**at once, in waves**, across CPU worker threads. A tiered **JIT** compiles
each block into a flat executable plan the first time it runs, so loops are
fast as hell: a 10,000 iteration loop runs in milliseconds.

The toolchain is written in Python and shipped as a real executable built
with PyInstaller. You do not run it via python; you download `eiltn` and run:

```
eiltn file.eil
```

```
file.eil          the program
    |
    v
[EIN builder]     every statement and expression lowers into nodes
    |
    v
EIN graph         packed node stream (also cacheable as a .ein binary)
    |
    v
[RAM loader]      validates the stream, builds dispatch tables
    |
    v
[JIT]             each block compiles once into a flat plan
    |
    v
[dispatcher]      ready nodes fire in waves across CPU worker threads
    |
    v
result
```

## The language

A program is a set of functions. Execution starts at `main`. Values are
64-bit signed machine words, doubles, and strings.

```eil
$ the classic

fn fib(n) {
    if n < 2 {
        return n
    }
    let a = fib(n - 1)
    let b = fib(n - 2)
    return a + b
}

fn main() {
    let t0 = clock()
    let r = fib(20)
    out.printf("fib(20) = %d\n", r)
    let t1 = clock()
    out.printf("nanos: %d\n", t1 - t0)
}
```

Run it: `eiltn parfib.eil` (add `-t 4` to spread call waves over 4 threads).

### Comments

```eil
$ this is a line comment

-$
this is a multi line comment
it can span as many lines as you want
$-
```

Comments are stripped before the EIN graph is built. They never reach the
machine.

### Variables

```eil
let x = 5        $ bind a new name (once per function)
set x = x + 1    $ assign an existing name
```

Types are runtime values: words (`42`, `0xFF`, `0b1010_0001`), floats
(`3.14`, `1e3`), strings (`"text\n"`), and booleans (`true`, `false`,
which are `1` and `0`). Mixing ints and floats promotes to float; mixing
numbers with strings in arithmetic is an `EIN fault`.

### Printing

```eil
println("plain line")          $ stdout, newline appended
out.println("explicit")        $ same thing
err.println("to stderr")
out.printf("%s scored %d (%.1f%%)\n", name, n, pct)
err.printf("failed at %d\n", line)
```

`printf` uses C-style format specifiers: `%d %i %f %s %x %X %c %%` plus
widths and precisions like `%5d` and `%.2f`.

### Control flow

```eil
if x < 5 { ... } else if x < 10 { ... } else { ... }

while i < n { ... }

for let i = 0; i < n; i = i + 1 { ... }
for i = 0; i < n; i = i + 1 { ... }     $ reuse an outer variable
for ;; { ... }                          $ infinite, leave with return or break

break          $ leave the innermost loop
return v       $ return from a function
```

`for` and `while` are deliberately sequential (each iteration depends on
the last), and they run on the JIT path: compiled once to a flat plan,
then executed at roughly a hundred nanoseconds per node.

### Operators

Words are 64-bit signed with wraparound (`0x7FFFFFFFFFFFFFFF + 1` is
`-9223372036854775808`). `/` on two ints truncates toward zero; any float
makes it float division. `%` takes the sign of the dividend. Shifts mask
the count to 6 bits; `>>` is arithmetic.

```
*  /  %         arithmetic
+  -            arithmetic; + also concatenates two strings
<< >>           shifts
<  <=  >  >=    ordering (numbers together, strings together)
== !=           equality
&  |  ^         bitwise and, or, xor
and or not      logic on truthiness, yields 1 or 0
-  ~            negate, bitwise complement
```

### Builtins

About 36 builtins ship with the runtime. None of them exist in the EIN
graph under their own names: `println` becomes an `out` node, `printf`
becomes a `printf` node, `min`/`max` become compare-plus-select node
pairs, and the rest become native trap nodes the CPU-facing dispatcher
executes.

| math    | strings        | conversion | system  |
|---------|----------------|------------|---------|
| sqrt    | len            | str        | clock   |
| pow     | substr(s,i,j)  | num        | argc    |
| floor   | upper / lower  | int        | argv(i) |
| ceil    | trim           | float      | exit(c) |
| round   | contains(s,x)  | hex        | rand    |
| sin / cos / tan | index(s,x) | bin  | randint(lo,hi) |
| log / exp | replace(s,a,b) | ord    |         |
| abs / fmod | repeat(s,n)  | chr        |         |
| min / max | reverse       |            |         |

### Faults

Runtime errors are EIN faults and name the node and line:

```
EIN fault: in fn main at DIV (line 7): division by zero
```

## EIN: the node model

The builder lowers every expression and statement into nodes: a
micro-operation with explicit input edges. `let t = a + b` becomes:

```
LOAD   r1 <- m0
LOAD   r2 <- m1
ADD    r3 <- r1, r2
STORE  m2 <- r3
```

Dependency edges tell the dispatcher which nodes can fire together:

- a node depends on the nodes producing its register inputs
- a `STORE` orders against earlier loads/stores of the same cell
- effect nodes (`out`, `err`, `printf`, natives like `clock`) chain in
  program order so output is deterministic
- `CALL` nodes chain only through their data, so independent calls fire
  in the same wave, in parallel

That is why `parfib.eil` times itself by printing between two clock reads:
the second clock node cannot fire until the print that depends on `fib`
has retired.

### The JIT

The dispatcher JITs every block: the first time a block runs, its node
tape is compiled into a flat plan (a single callable with the node
semantics baked in, one mapped source line per node for fault reporting),
exec'd once and cached. Every later execution of that block runs the
compiled plan with no re-decoding. Blocks whose waves contain independent
calls dispatch across worker threads instead. Both paths produce identical
results.

## The .ein binary

EIN is the internal node format, not a file type you have to care about.
`eiltn build` can still cache a compiled graph as a `.ein` binary, and
`eiltn file.ein` loads it straight into RAM:

```
eiltn build file.eil        $ produces file.ein
eiltn file.ein              $ load and dispatch
eiltn dis file.ein          $ disassemble the node tape
```

## CLI

```
eiltn file.eil              $ run a program
eiltn file.eil -t 4         $ 4 worker threads for parallel call waves
eiltn file.eil one two      $ program arguments: argc(), argv(0), ...
eiltn run -s file.eil       $ print dispatch statistics to stderr
eiltn build file.eil        $ compile to a .ein binary
eiltn dis file.eil          $ dump the node tape
eiltn --version
```

## Getting the executable

Do not run eiltn via python. Download the PyInstaller executable from the
releases page (`eiltn-linux-x64`, `eiltn-macos-arm64`,
`eiltn-windows-x64.exe`), mark it executable, and run `eiltn file.eil`.

To build it yourself:

```sh
./build.sh
```

`build.sh` uses PyInstaller (`eiltn.spec`) to produce a single executable
in `dist/`. If the shared libpython PyInstaller needs is not installed,
it falls back to `make-pyz.sh`, which produces a single-file `eiltn.pyz`.

## Layout

```
eiltn/             the toolchain (every file starts with #!/usr/bin/python3)
  lexer.py         tokenizer: $ and -$ $- comments, words, floats
  parser.py        grammar
  syntax.py        AST
  builder.py       AST to EIN node lowering
  ein.py           node opcodes, natives table
  binfmt.py        .ein packer and validating RAM loader
  dispatcher.py    wave scheduler, jit cache, fault mapping
  jit.py           block-to-plan jit compiler (+ closure fallback)
  ops.py           word/float/string semantics and the native traps
  disasm.py        node tape disassembler
  cli.py           eiltn file.eil / build / dis
examples/          12 programs, one per feature
tests/             88 tests
.github/workflows  builds the pyinstaller executables on push, releases on tags
```

## Design rules

1. A program is a node graph, not a list of lines.
2. Everything that can fire at once, fires at once.
3. Loops are sequential by nature and run on the jit path, fast as hell.
4. Effects retire in program order, so output is deterministic.
5. Builtins live in the source language only; the machine sees EIN.
6. Words are words: 64 bits, wraparound, floats are doubles.
