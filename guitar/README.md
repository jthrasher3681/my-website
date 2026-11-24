# Guitar Practice Studio — protected release

The course at https://jthrashercompanies.com/guitar/ requires a password. Version 1.4.0 contains 62 lessons across ten subjects, including a complete 24-lesson Travis Picking pathway with 72 progressive studies and the existing six-lesson Knopfler Fingerstyle section. The new path starts at `#lesson-39` and displays its own lesson numbers 1–24. Existing lesson links, the password and the local progress format remain compatible.

## Published files

Only the password screen, its scripts/styles, public app icons/manifest and `course.enc.json` are published in this directory. The entire editable course—including HTML, curriculum, player, styles, tests and reference screenshot—is inside the encrypted bundle. The browser decrypts it in memory after a correct password, then loads the lesson application in the same origin. No password, decryption key or decrypted course is written to browser storage by the app. The existing notes, completion and practice settings remain in the existing localStorage entry; they are not encrypted.

Encryption uses AES-256-GCM with a fresh 12-byte IV and a key derived using PBKDF2-SHA-256 (600,000 iterations, fresh 16-byte salt). All envelope metadata is authenticated. A generated password has 192 bits of randomness. Keep it in a password manager. There is no password-reset account or recovery service.

This is encrypted static delivery, not server-side account authentication. It restricts opening the currently published course without its password. Earlier course versions were public, including their Git history, and already downloaded copies cannot be recalled. A password holder can save or share decrypted material. A compromised host can change the unlock code. This design does not promise revocation of offline copies or per-person access control.

## Locking and offline access

Opening or reloading the page asks for the password. **Lock course** stops playback and reloads the locked screen. Returning through back/forward history reloads it too. While an unlocked tab stays open, it remains available until locked or reloaded.

The service worker stores only the lock screen, public shell files and encrypted bundle. Offline unlocking works after one complete online installation. The first protected release activates immediately, removes that installation's former plaintext course caches and reloads older open course tabs when they reconnect and receive the new worker. Unrelated applications and their caches are untouched. Devices that remain offline can still hold the earlier public course. Subsequent protected updates use the existing Update course control.

## Editing or changing the password

Keep plaintext source and password files outside the repository and any served directory. Never commit them. The source can be restored from the encrypted bundle with the current password:

```sh
node tools/guitar-security/build.cjs unpack \
  --source guitar/course.enc.json \
  --output /private/path/guitar-source \
  --password-file /private/path/course-password.txt \
  --release 1.4.0
```

The output must not exist. Edit and test that private source. To seal it, use a new output path:

```sh
node tools/guitar-security/build.cjs seal \
  --source /private/path/guitar-source \
  --output /private/path/course-next.enc.json \
  --password-file /private/path/course-password.txt \
  --release 1.4.1
```

To generate a different password for a new release, replace `--password-file` with `--generate-password /private/path/new-password.txt`. The tool creates a new 0600 file; it never prints the password. A strong generated password is recommended because a downloadable encrypted bundle permits offline password guessing.

For every release, update the version together in the private lessons.js/index.html, public lock.js/sw.js, shell asset query strings and the envelope. Then replace the public encrypted bundle with the freshly sealed file. Keep `FIRST_LOCKED_RELEASE` at 1.2.0; later releases should not force-reload an active practice session. Do not republish old plaintext files. Password rotation protects the new bundle; it cannot revoke an old cached release/password or copied lessons.

## Verification

From the repository root:

```sh
node --test tools/guitar-security/*.test.cjs
```

From the restored private source:

```sh
node --test tests/*.test.cjs
```

Verify browser unlocking, wrong-password rejection, direct old-asset 404 responses, retained progress, playback, Lock course, back/forward restoration, update migration and offline unlocking. Keep the service worker scoped to `/guitar/`. The homepage, other apps, domain and hosting settings remain unchanged.
