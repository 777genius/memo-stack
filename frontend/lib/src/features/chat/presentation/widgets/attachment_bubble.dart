import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:frontend/src/features/chat/application/services/open_chat_attachment.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';

class AttachmentBubble extends StatelessWidget {
  final String name;
  final String fileId;
  final bool isUser;
  final String? previewBase64;
  const AttachmentBubble(
      {super.key,
      required this.name,
      required this.fileId,
      this.isUser = true,
      this.previewBase64});

  @override
  Widget build(BuildContext context) {
    final previewBytes = _decodePreview(previewBase64);
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: LayoutBuilder(
        builder: (context, constraints) {
          final width = constraints.maxWidth.isFinite
              ? constraints.maxWidth * 0.82
              : 420.0;
          return ConstrainedBox(
            constraints: BoxConstraints(maxWidth: width.clamp(220.0, 520.0)),
            child: Container(
              margin: const EdgeInsets.symmetric(vertical: 6),
              padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 14),
              decoration: BoxDecoration(
                color: isUser
                    ? context.themeColors.userBubbleBg
                    : context.themeColors.assistantBubbleBg,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (previewBytes != null)
                    ClipRRect(
                      borderRadius: BorderRadius.circular(6),
                      child: Image.memory(
                        previewBytes,
                        width: 32,
                        height: 32,
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _fallbackIcon(context),
                      ),
                    )
                  else
                    _fallbackIcon(context),
                  const SizedBox(width: 8),
                  Flexible(
                    child: Text(
                      name,
                      overflow: TextOverflow.ellipsis,
                      style: isUser
                          ? context.theme
                              .style((t) => t.body, (c) => c.userBubbleFg)
                          : context.theme.style(
                              (t) => t.body,
                              (c) => c.assistantBubbleFg,
                            ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  TextButton(
                    onPressed: () async {
                      final openAttachment =
                          context.read<OpenChatAttachment?>();
                      if (openAttachment == null) return;
                      try {
                        await openAttachment(fileId: fileId, filename: name);
                      } catch (e) {
                        if (!context.mounted) return;
                        ScaffoldMessenger.of(context).showSnackBar(
                          SnackBar(content: Text('Open attachment failed: $e')),
                        );
                      }
                    },
                    style: TextButton.styleFrom(
                      foregroundColor: isUser
                          ? context.themeColors.userBubbleFg.withValues(
                              alpha: 0.9,
                            )
                          : context.themeColors.assistantBubbleFg,
                    ),
                    child: const Text('Open'),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _fallbackIcon(BuildContext context) {
    return Icon(
      Icons.attach_file,
      color: isUser
          ? context.themeColors.userBubbleFg
          : context.themeColors.assistantBubbleFg,
      size: 18,
    );
  }

  Uint8List? _decodePreview(String? value) {
    if (value == null || value.isEmpty) return null;
    try {
      return const Base64Decoder().convert(value);
    } on FormatException {
      return null;
    }
  }
}
