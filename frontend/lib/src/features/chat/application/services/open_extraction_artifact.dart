import 'package:frontend/src/features/chat/application/services/downloaded_file_opener.dart';
import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';

class OpenExtractionArtifact {
  final ChatRepository _repo;
  final DownloadedFileOpener _opener;

  const OpenExtractionArtifact({
    required ChatRepository repo,
    required DownloadedFileOpener opener,
  })  : _repo = repo,
        _opener = opener;

  Future<OpenedDownloadedFile> call(ExtractionArtifact artifact) async {
    final bytes = await _repo.downloadExtractionArtifact(artifact.id);
    return _opener.openBytes(
      suggestedName: artifact.filename,
      bytes: bytes,
      namespace: artifact.id,
    );
  }
}
