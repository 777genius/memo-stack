import 'dart:convert';
import 'dart:io';

import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:path_provider/path_provider.dart';

extension ChatMessageCacheMapExt on ChatMessage {
  Map<String, dynamic> toCacheMap({String? screenshotDir}) {
    String? imagePath;
    if (imageBase64 != null &&
        imageBase64!.isNotEmpty &&
        screenshotDir != null) {
      try {
        final file = File('$screenshotDir/$id.jpg');
        file.parent.createSync(recursive: true);
        file.writeAsBytesSync(base64Decode(imageBase64!));
        imagePath = file.path;
      } catch (_) {}
    }

    return {
      'id': id,
      'role': role,
      'chatId': chatId,
      'kind': kind,
      'text': text,
      if (imagePath != null) 'imagePath': imagePath,
      if (meta != null) 'meta': meta,
      'ts': ts.toIso8601String(),
    };
  }
}

class ChatMessageCacheMapper {
  static ChatMessage fromCacheMap(Map map) {
    String? imageBase64;
    final imagePath = map['imagePath'] as String?;
    if (imagePath != null && imagePath.isNotEmpty) {
      try {
        final file = File(imagePath);
        if (file.existsSync()) {
          imageBase64 = base64Encode(file.readAsBytesSync());
        }
      } catch (_) {}
    }

    return ChatMessage(
      id: (map['id'] as String?) ?? '',
      role: (map['role'] as String?) ?? 'assistant',
      chatId: map['chatId'] as String?,
      kind: map['kind'] as String?,
      text: map['text'] as String?,
      imageBase64: imageBase64,
      meta: (map['meta'] as Map?)?.cast<String, dynamic>(),
      ts: DateTime.tryParse((map['ts'] as String?) ?? '') ?? DateTime.now(),
    );
  }

  static void deleteScreenshot(Map map) {
    final imagePath = map['imagePath'] as String?;
    if (imagePath != null && imagePath.isNotEmpty) {
      try {
        final file = File(imagePath);
        if (file.existsSync()) file.deleteSync();
      } catch (_) {}
    }
  }
}

Future<String> getScreenshotDir() async {
  final dir = await getApplicationSupportDirectory();
  return '${dir.path}/screenshots';
}
