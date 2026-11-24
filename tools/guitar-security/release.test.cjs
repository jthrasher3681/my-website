'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const publicRoot = path.join(__dirname, '../../guitar');

test('the public course contains only encrypted delivery files, never editable lesson sources', () => {
 const allowed = ['.gitignore', 'README.md', 'index.html', 'sw.js', 'lock.js', 'lock.css', 'crypto.js',
  'course.enc.json', 'manifest.webmanifest', 'icon.svg', 'icon-192.png', 'icon-512.png'];
 const actual = fs.readdirSync(publicRoot).filter(name => name !== '_qa');
 assert.deepEqual(actual.sort(), allowed.sort());
 const bundle = JSON.parse(fs.readFileSync(path.join(publicRoot, 'course.enc.json'), 'utf8'));
 assert.equal(bundle.format, 'guitar-studio-encrypted');
 assert.equal(typeof bundle.ciphertext, 'string');
 assert.ok(!Object.hasOwn(bundle, 'files'), 'Plaintext source must not be an envelope field');
 assert.ok(!Object.hasOwn(bundle, 'password'), 'Password must not be an envelope field');
});

test('the lock shell, worker and encrypted bundle agree on the deployed version', () => {
 const bundle = JSON.parse(fs.readFileSync(path.join(publicRoot, 'course.enc.json'), 'utf8'));
 const html = fs.readFileSync(path.join(publicRoot, 'index.html'), 'utf8');
 for (const file of ['lock.js', 'sw.js']) {
  const code = fs.readFileSync(path.join(publicRoot, file), 'utf8');
  assert.equal(/const RELEASE = '([^']+)'/.exec(code)[1], bundle.release, file);
 }
 const assets = [...html.matchAll(/(?:src|href)="\.\/([^"?]+)\?v=([^"]+)"/g)];
 assert.deepEqual(assets.map(match => match[1]).sort(), ['crypto.js','lock.css','lock.js']);
 assert.ok(assets.every(match => match[2] === bundle.release));
 assert.match(html, /form-action 'none'/);
 assert.match(html, /<form[^>]+method="post"/);
 assert.doesNotMatch(html, /name="password"/);
 assert.doesNotMatch(html, /(?:src|href)="[^"\n]*(?:lessons\.js|studio\.js|ui\.js|studio\.css)/);
});
