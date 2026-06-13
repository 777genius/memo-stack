import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:pasteboard/pasteboard.dart';

class PasteboardClipboardAttachmentReader implements ClipboardAttachmentReader {
  const PasteboardClipboardAttachmentReader();

  @override
  Future<AttachmentUploadDraft?> readImage() async {
    try {
      final imageBytes = await Pasteboard.image;
      if (imageBytes == null || imageBytes.isEmpty) return null;
      return AttachmentUploadDraft.clipboardImage(bytes: imageBytes);
    } catch (_) {
      return null;
    }
  }
}
