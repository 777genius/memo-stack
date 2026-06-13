import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:frontend/src/features/chat/application/services/image_attachment_preprocessor.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';

class AttachmentUploadService {
  static const int defaultMaxBytes = 25 * 1024 * 1024;
  static const int inlinePreviewMaxBytes = 2 * 1024 * 1024;

  final ChatRepository _repo;
  final int _maxBytes;

  const AttachmentUploadService({
    required ChatRepository repo,
    int maxBytes = defaultMaxBytes,
  })  : _repo = repo,
        _maxBytes = maxBytes;

  Future<List<String>> uploadAll(
    List<AttachmentUploadDraft> drafts, {
    AttachmentUploadProgress? progress,
  }) async {
    if (drafts.isEmpty) return const [];
    final batchId = DateTime.now().microsecondsSinceEpoch.toString();
    final total = drafts.length;
    final uploaded = <String>[];

    for (var index = 0; index < drafts.length; index += 1) {
      final draft = drafts[index];
      final result = await _prepare(draft);
      final bytes = result.bytes;
      if (bytes.length > _maxBytes) {
        progress?.start(draft.name, bytes.length);
        progress?.fail(draft.name, 'too large');
        continue;
      }

      var canceled = false;
      void Function()? cancelNetwork;
      progress?.start(
        draft.name,
        bytes.length,
        onCancel: () {
          canceled = true;
          cancelNetwork?.call();
        },
        previewBytes: bytes.length > inlinePreviewMaxBytes ? null : bytes,
      );

      try {
        final fileId = await _repo.uploadFile(
          draft.name,
          bytes,
          mime: result.mime,
          onProgress: (sent, totalBytes) {
            if (!canceled) progress?.progress(draft.name, sent, totalBytes);
          },
          onCreateCancel: (fn) {
            cancelNetwork = fn;
          },
          previewBase64: result.previewBase64,
          batchId: batchId,
          batchSize: total,
          batchIndex: index + 1,
        );
        uploaded.add(fileId);
        progress?.complete(draft.name);
      } catch (error) {
        if (!canceled) {
          progress?.fail(draft.name, error.toString());
        }
      }
    }

    return uploaded;
  }

  Future<_PreparedAttachment> _prepare(AttachmentUploadDraft draft) async {
    if (!draft.isImage) {
      return _PreparedAttachment(
        bytes: draft.bytes,
        mime: draft.mime ?? 'application/octet-stream',
      );
    }

    final compressed = await compressIfNeeded(draft.bytes);
    return _PreparedAttachment(
      bytes: compressed.bytes,
      mime: compressed.mime,
      previewBase64: await makePreviewBase64(compressed.bytes),
    );
  }
}

class _PreparedAttachment {
  final List<int> bytes;
  final String mime;
  final String? previewBase64;

  const _PreparedAttachment({
    required this.bytes,
    required this.mime,
    this.previewBase64,
  });
}
