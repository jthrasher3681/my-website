#!/usr/bin/env node
"use strict";

const fs = require("node:fs/promises");
const { constants } = require("node:fs");
const path = require("node:path");
const { randomBytes } = require("node:crypto");
const { encrypt, decrypt } = require("../../guitar/crypto.js");

const MAX_SOURCE = 16 * 1024 * 1024;
const MAX_ENVELOPE = 4 * Math.ceil((MAX_SOURCE + 16) / 3) + 4096;
const PUBLIC_SITE = path.resolve(__dirname, "../..");
const usage = "Usage: node build.cjs <seal|unpack> --source PATH --output NEW_PATH " +
  "--release X.Y.Z (--password-file PRIVATE_PATH | --generate-password NEW_PRIVATE_PATH)";

function args(argv) {
  const [command, ...rest] = argv;
  const options = Object.create(null);
  const known = ["--source", "--output", "--release", "--password-file", "--generate-password"];
  if (!["seal", "unpack"].includes(command) || rest.length % 2) throw new Error(usage);
  for (let i = 0; i < rest.length; i += 2) {
    const [name, value] = rest.slice(i, i + 2);
    if (!known.includes(name) || options[name] || !value || value.startsWith("--")) throw new Error(usage);
    options[name] = value;
  }
  if (!options["--source"] || !options["--output"] || !/^\d{1,5}\.\d{1,5}\.\d{1,5}$/.test(options["--release"]) ||
      Boolean(options["--password-file"]) === Boolean(options["--generate-password"]) ||
      (command === "unpack" && options["--generate-password"])) throw new Error(usage);
  return { command, options };
}

function within(directory, target) {
  const relative = path.relative(directory, target);
  return relative === "" || (!path.isAbsolute(relative) && relative !== ".." && !relative.startsWith(".." + path.sep));
}

async function newPath(input) {
  const absolute = path.resolve(input);
  const target = path.join(await fs.realpath(path.dirname(absolute)), path.basename(absolute));
  try {
    await fs.lstat(target);
  } catch (error) {
    if (error.code === "ENOENT") return target;
    throw error;
  }
  throw new Error("Output already exists. Choose a new path.");
}

async function readRegularFile(file, limit) {
  const handle = await fs.open(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || stat.size > limit) throw new Error("Input file is invalid or too large.");
    const bytes = await handle.readFile();
    if (bytes.length > limit) throw new Error("Input file grew beyond the size limit.");
    return bytes;
  } finally {
    await handle.close();
  }
}

function encodeFile(bytes) {
  try {
    const content = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes);
    if (!content.includes("\0")) return { encoding: "utf8", content };
  } catch (error) {
    if (error.code !== "ERR_ENCODING_INVALID_ENCODED_DATA") throw error;
  }
  return { encoding: "base64", content: bytes.toString("base64") };
}

async function collect(source, release) {
  const files = Object.create(null);
  let remaining = MAX_SOURCE;
  let count = 0;
  async function walk(directory, prefix) {
    const entries = await fs.readdir(directory, { withFileTypes: true });
    entries.sort((a, b) => a.name.localeCompare(b.name));
    for (const entry of entries) {
      if (entry.name.startsWith(".") || entry.isSymbolicLink()) continue;
      const name = prefix + entry.name;
      if (name.length > 512) throw new Error("Course path is too long.");
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        await walk(file, name + "/");
      } else if (entry.isFile()) {
        if (++count > 2048) throw new Error("Too many course files.");
        const bytes = await readRegularFile(file, remaining);
        remaining -= bytes.length;
        files[name] = encodeFile(bytes);
      }
    }
  }
  await walk(source, "");
  return { format: "guitar-studio-source", schema: 1, release, files };
}

async function writeEnvelope(file, envelope) {
  const temp = await fs.mkdtemp(path.join(path.dirname(file), ".guitar-seal-"));
  try {
    const staged = path.join(temp, "bundle");
    await fs.writeFile(staged, JSON.stringify(envelope) + "\n", { flag: "wx", mode: 0o600 });
    // A same-filesystem hard link publishes a complete file and atomically refuses overwrites.
    await fs.link(staged, file);
  } finally {
    await fs.rm(temp, { recursive: true, force: true });
  }
}

async function unpack(output, payload) {
  await fs.mkdir(output, { mode: 0o700 });
  try {
    for (const [name, file] of Object.entries(payload.files)) {
      const target = path.resolve(output, name);
      if (!within(output, target) || target === output) throw new Error("Invalid extraction path.");
      await fs.mkdir(path.dirname(target), { recursive: true, mode: 0o700 });
      await fs.writeFile(target, file.content, { encoding: file.encoding, flag: "wx", mode: 0o600 });
    }
  } catch (error) {
    await fs.rm(output, { recursive: true, force: true });
    throw error;
  }
}

async function main(argv) {
  const { command, options } = args(argv);
  const site = await fs.realpath(PUBLIC_SITE);
  const input = options["--source"];
  const inputStat = await fs.lstat(input);
  if (!(command === "seal" ? inputStat.isDirectory() : inputStat.isFile())) throw new Error("Invalid source.");
  const source = await fs.realpath(input);
  const output = await newPath(options["--output"]);
  const release = options["--release"];
  if (command === "seal" && within(source, output)) throw new Error("Keep the encrypted output outside the source.");
  if (command === "unpack" && within(site, output)) throw new Error("Extract private source outside the public site.");

  const generate = options["--generate-password"];
  const keyPath = generate ? await newPath(generate) : await fs.realpath(options["--password-file"]);
  if (within(site, keyPath) || (command === "seal" && within(source, keyPath)) || keyPath === output) {
    throw new Error("Keep the password file outside the site, source directory, and output.");
  }
  let password;
  if (generate) {
    password = randomBytes(24).toString("base64url");
    await fs.writeFile(keyPath, password + "\n", { mode: 0o600, flag: "wx" });
  } else {
    if ((await fs.lstat(options["--password-file"])).isSymbolicLink()) throw new Error("Choose a regular password file.");
    const bytes = await readRegularFile(keyPath, 4098);
    try {
      password = new TextDecoder("utf-8", { fatal: true, ignoreBOM: true }).decode(bytes).replace(/\r?\n$/, "");
    } finally {
      bytes.fill(0);
    }
  }
  if (!password.length || password.length > 1024 || /[\r\n]/.test(password)) throw new Error("Invalid password file.");
  if (command === "seal") {
    const payload = await collect(source, release);
    await writeEnvelope(output, await encrypt(payload, password, release));
  } else {
    const bytes = await readRegularFile(source, MAX_ENVELOPE);
    const envelope = JSON.parse(bytes.toString("utf8"));
    if (envelope?.release !== release) throw new Error("Release does not match.");
    await unpack(output, await decrypt(envelope, password));
  }
}

if (require.main === module) {
  main(process.argv.slice(2)).catch((error) => {
    // Parser errors may quote snippets of a supplied file. Keep all file contents out of logs.
    process.stderr.write((error instanceof SyntaxError ? "Invalid input JSON." : error.message) + "\n");
    process.exitCode = 1;
  });
}
