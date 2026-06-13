import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';

class PlatformAttachmentFilePicker implements AttachmentFilePicker {
  const PlatformAttachmentFilePicker();

  @override
  Future<List<AttachmentUploadDraft>> pickFiles() async {
    final result = await FilePicker.platform.pickFiles(
      withData: true,
      allowMultiple: true,
      type: FileType.any,
    );
    if (result == null || result.files.isEmpty) return const [];

    final drafts = <AttachmentUploadDraft>[];
    for (final file in result.files) {
      final bytes = await _readBytes(file);
      if (bytes == null) continue;
      drafts.add(
        AttachmentUploadDraft.file(
          name: file.name,
          bytes: bytes,
          source: AttachmentUploadSource.filePicker,
        ),
      );
    }
    return drafts;
  }

  Future<Uint8List?> _readBytes(PlatformFile file) async {
    if (file.bytes != null) {
      return Uint8List.fromList(file.bytes!);
    }
    final path = file.path;
    if (kIsWeb || path == null || path.isEmpty) return null;
    try {
      final localFile = File(path);
      if (!await localFile.exists()) return null;
      return await localFile.readAsBytes();
    } catch (_) {
      return null;
    }
  }
}
