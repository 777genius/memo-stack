class OpenedDownloadedFile {
  final String path;

  const OpenedDownloadedFile({required this.path});
}

class DownloadedFileOpenException implements Exception {
  final String message;

  const DownloadedFileOpenException(this.message);

  @override
  String toString() => message;
}

abstract class DownloadedFileOpener {
  Future<OpenedDownloadedFile> openBytes({
    required String suggestedName,
    required List<int> bytes,
    String? namespace,
  });
}
