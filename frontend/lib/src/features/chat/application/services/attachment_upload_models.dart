import 'dart:typed_data';

enum AttachmentUploadSource {
  clipboard,
  filePicker,
  drop,
}

class AttachmentUploadDraft {
  final String name;
  final Uint8List bytes;
  final String? mime;
  final bool isImage;
  final AttachmentUploadSource source;

  const AttachmentUploadDraft({
    required this.name,
    required this.bytes,
    required this.isImage,
    required this.source,
    this.mime,
  });

  factory AttachmentUploadDraft.file({
    required String name,
    required List<int> bytes,
    String? mime,
    AttachmentUploadSource source = AttachmentUploadSource.filePicker,
  }) {
    return AttachmentUploadDraft(
      name: _safeName(name),
      bytes: Uint8List.fromList(bytes),
      mime: mime,
      isImage: _isImageName(name) || _isImageMime(mime),
      source: source,
    );
  }

  factory AttachmentUploadDraft.clipboardImage({
    required List<int> bytes,
    String name = 'clipboard.png',
  }) {
    return AttachmentUploadDraft(
      name: _safeName(name),
      bytes: Uint8List.fromList(bytes),
      mime: 'image/png',
      isImage: true,
      source: AttachmentUploadSource.clipboard,
    );
  }
}

abstract class AttachmentUploadProgress {
  void start(
    String name,
    int total, {
    void Function()? onCancel,
    List<int>? previewBytes,
    String? analysisLabel,
    bool analysisDegraded = false,
  });

  void progress(String name, int sent, int total);

  void fail(String name, String message);

  void complete(String name);
}

abstract class AttachmentFilePicker {
  Future<List<AttachmentUploadDraft>> pickFiles();
}

abstract class ClipboardAttachmentReader {
  Future<AttachmentUploadDraft?> readImage();
}

String _safeName(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? 'file.bin' : trimmed;
}

bool _isImageName(String name) {
  final lower = name.toLowerCase();
  return lower.endsWith('.png') ||
      lower.endsWith('.jpg') ||
      lower.endsWith('.jpeg') ||
      lower.endsWith('.webp') ||
      lower.endsWith('.gif') ||
      lower.endsWith('.bmp');
}

bool _isImageMime(String? mime) {
  final lower = mime?.trim().toLowerCase();
  return lower != null && lower.startsWith('image/');
}
