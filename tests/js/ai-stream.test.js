/* Unit tests for the shared SSE parser used by editor and wizard. */
const assert = require("node:assert");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(
  path.join(__dirname, "../../static/shared/ai-stream.js"),
  "utf8",
);
const context = {
  window: {},
  TextDecoder,
  TextEncoder,
};
vm.runInNewContext(source, context);
const { consume, parseSseBlock } = context.window.AIStream;

assert.deepStrictEqual(JSON.parse(JSON.stringify(parseSseBlock('event: done\ndata: {"ok":true}'))), {
  event: "done",
  data: { ok: true },
});
assert.strictEqual(parseSseBlock("event: reasoning\ndata: not-json"), null);

(async () => {
  const chunks = [
    "event: reasoning\ndata: {\"text\":\"Primera. ",
    "\"}\n\n",
    "event: reasoning\ndata: {\"text\":\"Segunda.\"}\n\n",
    "event: done\ndata: {\"value\":42}",
  ].map((value) => new TextEncoder().encode(value));
  let index = 0;
  const reasoning = [];
  const result = await consume(
    {
      body: {
        getReader() {
          return {
            async read() {
              if (index >= chunks.length) return { done: true };
              return { done: false, value: chunks[index++] };
            },
          };
        },
      },
    },
    (text) => reasoning.push(text),
  );

  assert.deepStrictEqual(reasoning, ["Primera. ", "Primera. Segunda."]);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(result)), { done: { value: 42 }, error: null });
  console.log("AIStream: all assertions passed");
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
