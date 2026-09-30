# Eiltn

Eiltn is a small systems-flavored language that does not run your program
line by line. Instead, the compiler turns the whole program into a graph of
**Eiltn Info Nodes (EINs)**, and the runtime dispatches every node whose
inputs are ready **all at once, in waves**, across CPU worker threads.

A conventional interpreter asks "what is the next line?" all the time.
Eiltn asks "which nodes are ready right now?" and fires every one of them
simultaneously, then collects the results, unlocks the next wave, and
repeats until the graph drains. Output effects (`out`, `err`) retire in
program order, so runs stay deterministic even though computation does not.

The toolchain is written in Python and can be compiled to a single
executable with PyInstaller.

```
source.eil        the program, must begin with the #bin/ header
    |
    v
[EIN builder]     every statement and expression becomes nodes
    |
    v
program.ein       packed little-endian node graph (the EIN binary)
    |
    v
[RAM loader]      validates the stream, builds dispatch tables
    |
    v
[dispatcher]      fires ready nodes in waves across CPU worker threads
    |
    v
result
```

## Quickstart

```sh
python3 -m eiltn run examples/hello.eil        # build nodes and dispatch
python3 -m eiltn build examples/fib.eil        # emit the ein binary
python3 -m eiltn run examples/fib.ein          # load binary into RAM and dispatch
python3 -m eiltn dis examples/fib.ein          # disassemble the node tape
python3 -m eiltn run -s examples/fizzbuzz.eil  # dispatch statistics on stderr
python3 -m unittest discover -s tests          # run the test suite
```

`python3 -m eiltn` also works after `pip install .`, which installs the
`eiltn` command.

## The language

A program is a set of functions. Execution starts at `main`. There are two
kinds of values: 64-bit signed machine words and strings.

```eil
#bin/ threads=4

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
    out r
    let t1 = clock()
    out t1 - t0
}
```

### The #bin/ header

Every source file begins with `#bin/`. It marks the binary section of the
program and can carry build attributes:

```
#bin/
#bin/ threads=4
```

That is the only comment-like element in the language. There are no other
comments and no emojis in Eiltn source. Comments are a fiction of
line-by-line languages; in Eiltn the unit of meaning is the node, and the
`#bin/` line is where the node stream is defined to begin.

### Statements

| statement        | meaning                                          |
|------------------|--------------------------------------------------|
| `let name = e`   | bind a new name (once per function)              |
| `set name = e`   | assign an existing name                          |
| `out e`          | print value + newline to stdout                  |
| `err e`          | print value + newline to stderr                  |
| `if c {} else {}`| branch; `else if` chains work                    |
| `while c {}`     | loop                                             |
| `return e`       | return from function (word or nothing)           |
| `f(a, b)`        | call for effect                                  |

### Operators

Words are 64-bit signed with wraparound (`0x7FFFFFFFFFFFFFFF + 1` is
`-9223372036854775808`). Division truncates toward zero, `%` takes the
sign of the dividend, shifts mask the count to 6 bits, `>>` is arithmetic.

```
*  /  %         arithmetic
+  -            arithmetic, + concatenates two strings
<< >>           shifts
<  <=  >  >=    ordering (words with words, strings with strings)
== !=           equality (mixed word/string compare unequal)
&  |  ^         bitwise and, or, xor
and or not      logic on truthiness, yields 1 or 0
-  ~            negate, bitwise complement
```

Literals: `42`, `0xFF`, `0b1011_0001`, `1_000_000`, `"text"` with escapes
`\n \t \r \0 \\ \" \xNN`. Literals may be written unsigned up to
`0xFFFFFFFFFFFFFFFF` and wrap into signed words.

### Natives

```
clock()   monotonic nanosecond counter
len(s)    string length
ord(s)    first character code
chr(n)    character from code
str(x)    to string
num(s)    parse word from string
abs(x)    absolute value
hex(x)    to 0x-prefixed hex string (two's complement view)
```

### Types

There are no type annotations. Values are machine words or strings at
runtime; mixing them in arithmetic is an `EIN fault`:

```
EIN fault: in fn main at ADD (line 15): type fault: + expects two words or two strings
```

## EIN: the node model

The builder lowers every expression and statement into nodes. A node is a
micro-operation with explicit input edges. For example, `let t = a + b`
in a function becomes:

```
LOAD   r1 <- m0
LOAD   r2 <- m1
ADD    r3 <- r1, r2
STORE  m2 <- r3
```

Nodes carry dependency edges so the dispatcher knows exactly which nodes
can fire together. Within a block, the graph is a DAG:

- a node depends on the nodes producing its register operands
- a `STORE` depends on earlier loads/stores of the same cell
  (war/waw ordering)
- effect nodes (`OUT`, `ERR`, natives such as `clock`) chain in program
  order so output stays deterministic
- `CALL` nodes chain only through their data, so independent calls fire
  in the same wave, in parallel

The dispatcher runs the block by repeatedly firing every ready node at
once. Blocks whose waves contain independent calls are dispatched across
worker threads; all other blocks run a pre-bound linear plan that is as
fast as the graph allows. Both paths produce identical results.

### User functions are pure nodes

`fn` calls compile to `CALL` nodes and run concurrently when their
arguments are ready. Input and output (`out`, `err`, `clock`) are sequenced
against each other in program order. That is why `examples/parfib.eil`
times itself by placing `out r` between the two clock reads: the second
clock node cannot fire until the print that depends on `fib` has retired.

## The .ein binary

`eiltn build` packs the node graph into a compact little-endian format that
the loader reads straight into RAM:

```
offset  field
0       magic "EILN"
4       version u8, flags u8, threads u16, entry u16, func count u32
14      name (u8 length + bytes)
        const pool: u32 count, then tagged entries (i64 or length-prefixed utf-8)
        functions: name, arity u8, cells u16, regs u16, block count u32
          blocks: u32 instruction count, then instructions
            instruction: op u8, dst u16, operand count u8,
                         operands (kind u8 + value u16), line u16,
                         op-specific aux (jump/branch targets, cell, fn idx)
```

The loader validates every opcode, operand kind, index and branch target
before the program runs. `eiltn dis` prints the tape back out:

```
.b1:
  0000  LOAD   r4 <- m3                                   @8
  0001  LOAD   r5 <- m0                                   @8
  0002  LT     r6 <- r4, r5                               @8
  0003  BR     r6 ? .b2 : .b3                             @8
```

## Building an executable

```sh
./build.sh
```

This uses PyInstaller to produce a single `dist/eiltn` executable. On
systems where the shared libpython needed by PyInstaller is not installed,
the script automatically falls back to `make-pyz.sh`, which produces
`eiltn.pyz`, a single-file executable that runs anywhere Python 3.8+ exists:

```sh
./eiltn.pyz run examples/hello.eil
```

## Performance

The dispatcher binds every block to a flat plan of closures once, then
reuses it for the whole run, so steady-state execution avoids re-decoding
nodes. A 1,000,000-iteration summing loop (`examples/bench.eil`) runs in
about 2.3 seconds on one core at roughly 180 ns per node, and independent
calls dispatch concurrently across threads. CPython's GIL still serializes
pure-python node work; the wave architecture is what keeps runs correct
while allowing effects like I/O to overlap.

## Layout

```
eiltn/           the toolchain
  lexer.py       tokenizer, enforces the #bin/ rule
  parser.py      grammar
  syntax.py      AST
  builder.py     AST to EIN node graph
  ein.py         node opcodes and program structures
  binfmt.py      .ein packer and RAM loader
  dispatcher.py  wave scheduler and fault handling
  plan.py        per-block closure plans
  ops.py         word and native operations
  disasm.py      node tape disassembler
  cli.py         run / build / dis / --version
examples/        hello, fib, parfib, bits, fizzbuzz, words, bench
tests/           48 tests: lexer, builder, engine, binary, cli
```

## Design rules

1. A program is a graph, not a list of lines.
2. Everything that can fire at once, fires at once.
3. Effects retire in program order, so output is deterministic.
4. Words are words: 64 bits, wraparound, no silent promotion.
5. No comments, no emojis. The node stream starts at `#bin/` and nothing
   else stands between the programmer and the machine.
