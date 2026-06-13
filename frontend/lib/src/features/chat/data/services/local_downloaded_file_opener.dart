import 'dart:io';

import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

import 'package:frontend/src/features/chat/application/services/downloaded_file_opener.dart';

class LocalDownloadedFileOpener implements DownloadedFileOpener {
  @override
  Future<OpenedDownloadedFile> openBytes({
    required String suggestedName,
    required List<int> bytes,
    String? namespace,
  }) async {
    final dir = await getTemporaryDirectory();
    final filename = _safeFileName(suggestedName);
    final prefix = _safeFileName(namespace ?? '');
    final path = prefix.isEmpty
        ? '${dir.path}/$filename'
        : '${dir.path}/${prefix}_$filename';
    final file = await File(path).writeAsBytes(bytes, flush: true);
    final result = await OpenFilex.open(file.path);
    if (result.type != ResultType.done) {
      final message = result.message.trim().isEmpty
          ? 'File opener failed: ${result.type.name}'
          : result.message.trim();
      throw DownloadedFileOpenException(message);
    }
    return OpenedDownloadedFile(path: file.path);
  }

  String _safeFileName(String name) {
    final safe = name
        .trim()
        .replaceAll(RegExp(r'[^a-zA-Z0-9._-]+'), '_')
        .replaceAll(RegExp(r'_+'), '_')
        .replaceAll(RegExp(r'^[_\\.]+|[_\\.]+$'), '');
    return safe.isEmpty ? 'download.bin' : safe;
  }
}
