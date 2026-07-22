/* Framework-free unit tests: run with `node tests/js/apply.test.js`. */
const assert = require("node:assert");
const path = require("node:path");

const { applyAIOperations } = require(
  path.join(__dirname, "../../static/editor/editor-ai.js")
);

function baseState() {
  return {
    document: {
      body: {
        children: [
          {
            type: "element",
            tag: "section",
            attributes: { class: ["hero"] },
            children: [
              { type: "element", tag: "h1", attributes: {}, children: [
                { type: "text", value: "Viejo" },
              ] },
              { type: "element", tag: "p", attributes: {}, children: [
                { type: "text", value: "desc" },
              ] },
            ],
          },
          { type: "element", tag: "footer", attributes: {}, children: [] },
        ],
      },
    },
    styles: { variables: {}, rules: [] },
  };
}

// set_text
(() => {
  const next = applyAIOperations(baseState(), [
    { action: "set_text", path: [0, 0, 0], value: "Nuevo" },
  ]);
  assert.strictEqual(next.document.body.children[0].children[0].children[0].value, "Nuevo");
})();

// does not mutate the input
(() => {
  const original = baseState();
  applyAIOperations(original, [{ action: "set_text", path: [0, 0, 0], value: "X" }]);
  assert.strictEqual(original.document.body.children[0].children[0].children[0].value, "Viejo");
})();

// set_attribute + set_style_variable
(() => {
  const next = applyAIOperations(baseState(), [
    { action: "set_attribute", path: [0], attribute: "class", value: ["hero", "big"] },
    { action: "set_style_variable", name: "--color-primary", value: "#0f0" },
  ]);
  assert.deepStrictEqual(next.document.body.children[0].attributes.class, ["hero", "big"]);
  assert.strictEqual(next.styles.variables["--color-primary"], "#0f0");
})();

// add_node
(() => {
  const node = { type: "element", tag: "span", attributes: {}, children: [] };
  const next = applyAIOperations(baseState(), [
    { action: "add_node", parent_path: [1], index: 0, node },
  ]);
  assert.strictEqual(next.document.body.children[1].children[0].tag, "span");
})();

// move_node (footer before hero)
(() => {
  const next = applyAIOperations(baseState(), [
    { action: "move_node", source_path: [1], target_path: [0], position: "before" },
  ]);
  assert.strictEqual(next.document.body.children[0].tag, "footer");
  assert.strictEqual(next.document.body.children[1].tag, "section");
})();

// move_node cycle prevention
(() => {
  assert.throws(() =>
    applyAIOperations(baseState(), [
      { action: "move_node", source_path: [0], target_path: [0, 0], position: "inside" },
    ])
  );
})();

// delete_node
(() => {
  const next = applyAIOperations(baseState(), [{ action: "delete_node", path: [1] }]);
  assert.strictEqual(next.document.body.children.length, 1);
})();

console.log("applyAIOperations: all assertions passed");
