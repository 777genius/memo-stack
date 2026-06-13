import 'package:frontend/src/features/chat/application/services/downloaded_file_opener.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';

class OpenChatAttachment {
  final ChatRepository _repo;
  final DownloadedFileOpener _opener;

  const OpenChatAttachment({
    required ChatRepository repo,
    required DownloadedFileOpener opener,
  })  : _repo = repo,
        _opener = opener;

  Future<OpenedDownloadedFile> call({
    required String fileId,
    required String filename,
  }) async {
    final id = fileId.trim();
    if (id.isEmpty) {
      throw ArgumentError.value(
          fileId, 'fileId', 'Attachment file id is required');
    }
    final safeFilename =
        filename.trim().isEmpty ? 'attachment.bin' : filename.trim();
    final bytes = await _repo.downloadFile(id);
    return _opener.openBytes(suggestedName: safeFilename, bytes: bytes);
  }
}
