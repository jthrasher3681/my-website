"use strict";

const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const path = require("node:path");
const os = require("node:os");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
const { execFile } = require("node:child_process");
const { promisify } = require("node:util");
const execute = promisify(execFile);
const api = require("../../guitar/crypto.js");

const release = "1.2.0";
const password = "fixture-only passphrase 🎸";
const runtime = ["index.html", "studio.css", "lessons.js", "studio.js", "ui.js"];
const payload = {
  format: "guitar-studio-source", schema: 1, release,
  files: Object.fromEntries(runtime.map((name) => [name, { encoding: "utf8", content: "Private fixture " + name }]))
};
const cls = path.join(__dirname, "build.cjs");
let envelope;
let scratch;

before(async () => {
  envelope = await api.encrypt(payload, password, release);
  scratch = await fs.mkdtemp(path.join(os.tmpdir(), "guitar-security-test-"));
});
after(async () => {
  if (scratch) await fs.rm(scratch, { recursive: true, force: true });
});

test("browser global decrypts Node-sealed data with reordered header fields", async () => {
  const context = vm.createContext({ crypto: webcrypto, TextEncoder, TextDecoder, atob, btoa, password });
  vm.runInContext(await fs.readFile(path.resolve(__dirname, "../../guitar/crypto.js"), "utf8"), context);
  const shuffled = Object.fromEntries(Object.entries(envelope).reverse());
  context.wire = JSON.stringify(shuffled);
  const decoded = await vm.runInContext("GuitarCrypto.decrypt(JSON.parse(wire), password)", context);
  assert.deepEqual(JSON.parse(JSON.stringify(decoded)), payload);
  const fresh = await api.encrypt(payload, password, release);
  assert.notEqual(fresh.salt, envelope.salt);
  assert.notEqual(fresh.iv, envelope.iv);
  assert.notEqual(fresh.ciphertext, envelope.ciphertext);
  assert.equal(envelope.iterations, 600000);
  assert.equal(Buffer.from(envelope.salt, "base64").length, 16);
  assert.equal(Buffer.from(envelope.iv, "base64").length, 12);
  assert.ok(!JSON.stringify(envelope).includes("Private fixture"));
  assert.ok(!JSON.stringify(envelope).includes(password));
});

test("wrong password, valid-looking changed metadata, and modified ciphertext fail authentication", async () => {
  const changed = Buffer.from(envelope.ciphertext, "base64");
  changed[0] ^= 1;
  for (const [message, candidate] of [
    [envelope, password + "x"],
    [{ ...envelope, release: "1.3.0" }, password],
    [{ ...envelope, ciphertext: changed.toString("base64") }, password]
  ]) await assert.rejects(api.decrypt(message, candidate), { name: "OperationError" });
});

test("malformed envelope fields and out-of-policy parameters are rejected before key derivation", async () => {
  for (const change of [
    { format: "other" }, { schema: 2 }, { iterations: 999999999 }, { iterations: 1 },
    { release: "x" }, { salt: "AAAA" }, { iv: "AAAAAAAAAAAAAAA=" }, { ciphertext: "a==x" },
    { ciphertext: "A".repeat(24 * 1024 * 1024) }, { extra: true }
  ]) await assert.rejects(api.decrypt({ ...envelope, ...change }, ""), /Invalid encrypted course/);
});

test("only safe paths and valid runtime files may be sealed", async () => {
  const file = { encoding: "utf8", content: "fixture" };
  for (const name of ["../escape", "/absolute", "dir/../escape", ".private", "dir\\escape", "dir/CON.txt"]) {
    await assert.rejects(api.encrypt({ ...payload, files: { ...payload.files, [name]: file } }, password, release),
      /Invalid course file/);
  }
  const files = { ...payload.files };
  delete files["ui.js"];
  await assert.rejects(api.encrypt({ ...payload, files }, password, release), /Required course file/);
  await assert.rejects(api.encrypt({ ...payload, release: "1.3.0" }, password, release), /Invalid course payload/);
});

async function authenticatedFixture(privatePayload) {
  const encoder = new TextEncoder();
  const salt = Buffer.from(envelope.salt, "base64");
  const iv = webcrypto.getRandomValues(new Uint8Array(12));
  const header = { ...envelope, iv: Buffer.from(iv).toString("base64") };
  const additionalData = encoder.encode(JSON.stringify([
    header.format, header.schema, header.release, header.iterations, header.salt, header.iv
  ]));
  const material = await webcrypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveKey"]);
  const key = await webcrypto.subtle.deriveKey({ name: "PBKDF2", salt, hash: "SHA-256", iterations: 600000 },
    material, { name: "AES-GCM", length: 256 }, false, ["encrypt"]);
  const encrypted = await webcrypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData, tagLength: 128 },
    key, encoder.encode(JSON.stringify(privatePayload)));
  return { ...header, ciphertext: Buffer.from(encrypted).toString("base64") };
}

test("authenticated payload must match the release and include UTF-8 runtime files", async () => {
  const mismatch = await authenticatedFixture({ ...payload, release: "1.2.1" });
  await assert.rejects(api.decrypt(mismatch, password), /Invalid course payload/);
  const altered = { ...payload, files: { ...payload.files, "ui.js": { encoding: "base64", content: "AA==" } } };
  await assert.rejects(api.decrypt(await authenticatedFixture(altered), password), /Required course file/);
});

test("CLI privately restores the editable tree byte-for-byte and refuses unsafe writes", async () => {
  const source = path.join(scratch, "source");
  const bundle = path.join(scratch, "course.json");
  const key = path.join(scratch, "password");
  const extracted = path.join(scratch, "restored");
  await fs.mkdir(path.join(source, "docs"), { recursive: true });
  const fixtures = Object.fromEntries(runtime.map((file) => [file, Buffer.from("\ufeff🎸\r\n" + file)]));
  fixtures["docs/photo.jpg"] = Buffer.from([0xff, 0xd8, 0x00, 0x80, 0xff, 0xd9]);
  for (const [name, bytes] of Object.entries(fixtures)) await fs.writeFile(path.join(source, name), bytes);
  await fs.writeFile(path.join(source, ".local"), "excluded");
  await fs.symlink(path.join(source, "index.html"), path.join(source, "linked"));
  const common = ["--release", release];
  const seal = ["seal", "--source", source, "--output", bundle, ...common];
  const unpackArgs = ["unpack", "--source", bundle, "--output", extracted, ...common, "--password-file", key];
  const sealed = await execute(process.execPath, [cls, ...seal, "--generate-password", key]);
  assert.equal(sealed.stdout + sealed.stderr, "");
  assert.equal((await fs.stat(key)).mode & 0o777, 0o600);
  const wrongKey = path.join(scratch, "wrong-key");
  await fs.writeFile(wrongKey, "wrong fixture password");
  await assert.rejects(execute(process.execPath, [cls, ...unpackArgs.slice(0, -1), wrongKey]));
  await assert.rejects(fs.access(extracted), { code: "ENOENT" });
  await execute(process.execPath, [cls, ...unpackArgs]);
  assert.equal((await fs.stat(extracted)).mode & 0o777, 0o700);
  for (const [name, expected] of Object.entries(fixtures)) {
    assert.deepEqual(await fs.readFile(path.join(extracted, name)), expected);
  }
  for (const omitted of [".local", "linked"]) await assert.rejects(fs.access(path.join(extracted, omitted)), { code: "ENOENT" });
  await assert.rejects(execute(process.execPath, [cls, ...unpackArgs]), /already exists/);
  await assert.rejects(execute(process.execPath, [cls, ...seal, "--password-file", key]), /already exists/);
  const publicTarget = path.join(__dirname, "invalid-public-extraction-" + process.pid);
  await assert.rejects(execute(process.execPath, [cls, "unpack", "--source", bundle, "--output", publicTarget,
    ...common, "--password-file", key]), /outside the public site/);
});
