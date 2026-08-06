import * as os from 'node:os';
import * as path from 'node:path';

/**
 * Enables V8's on-disk compile cache, which stores the compiled bytecode of every module so
 * subsequent starts skip parsing and compiling them again.
 *
 * This is the closest Node.js analogue of the AOTCache used by the `*-leyden` runtimes: it caches
 * compilation work to shorten startup. Like AOTCache, it does **not** improve steady-state
 * throughput — V8 still JITs the hot paths at runtime.
 *
 * Must be imported before anything else in main.ts: the cache only covers modules loaded after
 * this call, and CommonJS evaluates requires in order.
 *
 * Measurement caveat: the first start populates a cold cache and sees no benefit (it pays a small
 * write cost instead); later starts reuse it. Benchmarks that average several iterations therefore
 * mix one cold start with several warm ones.
 *
 * Set NODE_COMPILE_CACHE_DISABLED=true to turn it off, or NODE_COMPILE_CACHE=<dir> to relocate it
 * (Node honours that variable on its own, without this module).
 */
if (process.env.NODE_COMPILE_CACHE_DISABLED !== 'true') {
  // Resolved dynamically because `enableCompileCache` only exists on Node >= 22.8 and is not in
  // every @types/node release; a missing function must not break the build or the boot.
  const nodeModule = require('node:module');

  if (typeof nodeModule.enableCompileCache === 'function') {
    const dir = process.env.NODE_COMPILE_CACHE || path.join(os.tmpdir(), 'nodejs-compile-cache');

    try {
      nodeModule.enableCompileCache(dir);
    }
    catch {
      // Unsupported platform or unwritable directory - not fatal, we just start without it.
    }
  }
}
