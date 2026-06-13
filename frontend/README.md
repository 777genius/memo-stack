Memo Stack Frontend
===================

Flutter desktop/web client for quick memory capture.

The default flow is intentionally simple:

- open a chat-like capture screen;
- type a note or attach screenshots/files;
- save the input through Memo Stack REST APIs;
- show suggested related context as selectable chips;
- let the user link one capture to several existing facts, captures, suggestions or assets.

Backend
-------

Default local backend:

```bash
http://127.0.0.1:7788
```

Expected API surface:

- `GET /healthz`
- `POST /v1/assets`
- `GET /v1/assets/{asset_id}/download`
- `POST /v1/captures`
- `POST /v1/link-suggestions`
- `POST /v1/context-links`

Run
---

```bash
flutter pub get
flutter run -d macos
```

Verify
------

```bash
flutter analyze
flutter test
flutter build macos --debug
```

Notes
-----

- The UI stores server host, port, token, space slug and memory scope ref in local encrypted storage.
- Files are uploaded as raw asset bytes, not multipart form data.
- Context chips are suggestions only. The user explicitly confirms links before they are persisted.
