(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory(require("node:crypto").webcrypto);
  } else {
    root.GuitarCrypto = factory(root.crypto);
  }
})(globalThis, function (crypto) {
  "use strict";

  const ITERATIONS = 600000;
  const MAX_BYTES = 16 * 1024 * 1024;
  const MAX_FILES = 2048;
  const RUNTIME_FILES = ["index.html", "studio.css", "lessons.js", "studio.js", "ui.js"];
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

  function requireValue(condition, message) {
    if (!condition) throw new Error(message);
  }

  function record(value) {
    return value !== null && typeof value === "object" &&
      (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
  }

  function exactFields(value, fields) {
    return record(value) && Object.keys(value).length === fields.length &&
      fields.every((field) => Object.prototype.hasOwnProperty.call(value, field));
  }

  function validRelease(value) {
    return typeof value === "string" && value.length <= 17 && /^\d{1,5}\.\d{1,5}\.\d{1,5}$/.test(value);
  }

  function validPath(path) {
    return path.length > 0 && path.length <= 512 && path.split("/").every((part) =>
      part.length > 0 && part.length <= 255 && !part.startsWith(".") &&
      !/[. ]$/.test(part) && !/[\\<>:"|?*\u0000-\u001f\u007f]/.test(part) &&
      !/^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)/i.test(part) &&
      !["__proto__", "prototype", "constructor"].includes(part)
    );
  }

  function validBase64(value, maxBytes) {
    if (typeof value !== "string" || value.length > 4 * Math.ceil(maxBytes / 3) ||
        value.length % 4 !== 0 || /[^A-Za-z0-9+/=]/.test(value)) return false;
    const padding = value.endsWith("==") ? 2 : Number(value.endsWith("="));
    const bodyLength = value.length - padding;
    if (value.indexOf("=") !== (padding ? bodyLength : -1) ||
        value.length / 4 * 3 - padding > maxBytes) return false;
    const last = alphabet.indexOf(value[bodyLength - 1]);
    return padding === 0 || (last >= 0 && (last & (padding === 2 ? 15 : 3)) === 0);
  }

  function base64(bytes) {
    let binary = "";
    for (let offset = 0; offset < bytes.length; offset += 16384) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 16384));
    }
    return btoa(binary);
  }

  function bytesFrom64(value) {
    const binary = atob(value);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < bytes.length; i++) bytes[i] = binary.charCodeAt(i);
    return bytes;
  }

  function validatePayload(payload, release) {
    requireValue(exactFields(payload, ["format", "schema", "release", "files"]) &&
      payload.format === "guitar-studio-source" && payload.schema === 1 &&
      payload.release === release && record(payload.files), "Invalid course payload.");
    const files = Object.entries(payload.files);
    requireValue(files.length <= MAX_FILES, "Too many course files.");
    for (const [path, file] of files) {
      requireValue(validPath(path) && exactFields(file, ["encoding", "content"]) &&
        typeof file.content === "string" && file.content.length <= MAX_BYTES &&
        (file.encoding === "utf8" || (file.encoding === "base64" && validBase64(file.content, MAX_BYTES))),
        "Invalid course file.");
    }
    for (const name of RUNTIME_FILES) {
      requireValue(Object.prototype.hasOwnProperty.call(payload.files, name) &&
        payload.files[name].encoding === "utf8", "Required course file missing or invalid.");
    }
  }

  function additionalData(header) {
    // Encode fields in protocol order independently of the envelope's JSON key order.
    return new TextEncoder().encode(JSON.stringify([
      header.format, header.schema, header.release, header.iterations, header.salt, header.iv
    ]));
  }

  async function keyFor(password, salt, usage) {
    requireValue(typeof password === "string" && password.length > 0 && password.length <= 1024,
      "Invalid password length.");
    const passwordBytes = new TextEncoder().encode(password);
    let material;
    try {
      material = await crypto.subtle.importKey("raw", passwordBytes, "PBKDF2", false, ["deriveKey"]);
    } finally {
      passwordBytes.fill(0);
    }
    return crypto.subtle.deriveKey({ name: "PBKDF2", hash: "SHA-256", salt, iterations: ITERATIONS },
      material, { name: "AES-GCM", length: 256 }, false, [usage]);
  }

  function cipher(header, iv) {
    return { name: "AES-GCM", iv, additionalData: additionalData(header), tagLength: 128 };
  }

  async function encrypt(payload, password, release) {
    requireValue(validRelease(release), "Invalid release.");
    validatePayload(payload, release);
    const plaintext = new TextEncoder().encode(JSON.stringify(payload));
    try {
      requireValue(plaintext.length <= MAX_BYTES, "Course payload is too large.");
      const salt = crypto.getRandomValues(new Uint8Array(16));
      const iv = crypto.getRandomValues(new Uint8Array(12));
      const header = { format: "guitar-studio-encrypted", schema: 1, release, iterations: ITERATIONS,
        salt: base64(salt), iv: base64(iv) };
      const key = await keyFor(password, salt, "encrypt");
      const ciphertext = await crypto.subtle.encrypt(cipher(header, iv), key, plaintext);
      return { ...header, ciphertext: base64(new Uint8Array(ciphertext)) };
    } finally {
      plaintext.fill(0);
    }
  }

  async function decrypt(envelope, password) {
    requireValue(exactFields(envelope, ["format", "schema", "release", "iterations", "salt", "iv", "ciphertext"]) &&
      envelope.format === "guitar-studio-encrypted" && envelope.schema === 1 && validRelease(envelope.release) &&
      envelope.iterations === ITERATIONS && validBase64(envelope.salt, 16) && envelope.salt.length === 24 &&
      envelope.salt.endsWith("==") && validBase64(envelope.iv, 12) && envelope.iv.length === 16 &&
      !envelope.iv.includes("=") && validBase64(envelope.ciphertext, MAX_BYTES + 16) &&
      envelope.ciphertext.length >= 24, "Invalid encrypted course.");
    const salt = bytesFrom64(envelope.salt);
    const iv = bytesFrom64(envelope.iv);
    const ciphertext = bytesFrom64(envelope.ciphertext);
    requireValue(ciphertext.length > 16, "Invalid encrypted course.");
    const key = await keyFor(password, salt, "decrypt");
    const plaintext = new Uint8Array(await crypto.subtle.decrypt(cipher(envelope, iv), key, ciphertext));
    try {
      const payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(plaintext));
      validatePayload(payload, envelope.release);
      return payload;
    } finally {
      plaintext.fill(0);
    }
  }

  return Object.freeze({ encrypt, decrypt });
});
