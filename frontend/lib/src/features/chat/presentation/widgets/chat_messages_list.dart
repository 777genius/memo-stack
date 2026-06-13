import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
// removed duplicate provider import
import 'package:frontend/src/features/chat/presentation/widgets/action_messages.dart';
import 'package:frontend/src/features/chat/presentation/widgets/attachment_bubble.dart';
import 'package:frontend/src/features/chat/presentation/widgets/lightbox_viewer.dart';
import 'package:frontend/src/features/chat/presentation/widgets/album_bubble.dart';
import 'package:frontend/src/features/chat/presentation/widgets/special_message_cards.dart';
import 'package:flutter_mobx/flutter_mobx.dart';
import 'package:provider/provider.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';
import 'package:frontend/src/presentation/widgets/markdown/markdown_message.dart';

class ChatMessagesList extends StatefulWidget {
  const ChatMessagesList({super.key});

  @override
  State<ChatMessagesList> createState() => _ChatMessagesListState();
}

class _ChatMessagesListState extends State<ChatMessagesList> {
  final ScrollController _ctrl = ScrollController();
  bool _atBottom = true;
  int _lastLen = 0;
  String? _lastChatId;

  @override
  void initState() {
    super.initState();
    _ctrl.addListener(_onScroll);
  }

  @override
  void dispose() {
    _ctrl.removeListener(_onScroll);
    _ctrl.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_ctrl.hasClients) return;
    final pos = _ctrl.position;
    final bool atBottomNow = pos.pixels >= (pos.maxScrollExtent - 24);
    _atBottom = atBottomNow;
  }

  void _scrollToBottom() {
    if (!_ctrl.hasClients) return;
    final target = _ctrl.position.maxScrollExtent;
    _ctrl.animateTo(
      target,
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOut,
    );
    // Re-check after animation — maxScrollExtent may have changed during layout
    Future.delayed(const Duration(milliseconds: 250), () {
      if (!mounted || !_ctrl.hasClients) return;
      if (_ctrl.position.pixels < _ctrl.position.maxScrollExtent - 1) {
        _ctrl.jumpTo(_ctrl.position.maxScrollExtent);
      }
    });
  }

  void _jumpToBottom() {
    if (!_ctrl.hasClients) return;
    _ctrl.jumpTo(_ctrl.position.maxScrollExtent);
    // Layout may still settle — verify in next frame
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_ctrl.hasClients) return;
      if (_ctrl.position.pixels < _ctrl.position.maxScrollExtent - 1) {
        _ctrl.jumpTo(_ctrl.position.maxScrollExtent);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Observer(
      builder: (_) {
        final store = context.read<ChatStore?>();
        final len = store?.messages.length ?? 0;
        final chatId = store?.activeChatId;

        // Chat switched — always jump to bottom
        final chatSwitched = chatId != _lastChatId;
        if (chatSwitched) {
          _lastChatId = chatId;
          _atBottom = true;
        }

        // автопрокрутка: при смене чата — jump, при новых сообщениях — animate
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (!mounted) return;
          if (chatSwitched) {
            _jumpToBottom();
          } else if (_atBottom && _lastLen != len) {
            _scrollToBottom();
          }
          _lastLen = len;
        });

        // Group consecutive action messages for compact display
        final groups = groupChatMessages(store!.messages);

        return ListView.builder(
          controller: _ctrl,
          padding: const EdgeInsets.all(12),
          itemCount: groups.length,
          itemBuilder: (_, i) {
            final group = groups[i];
            // Peek at next group to attach usage badge to current message
            final nextUsage = (i + 1 < groups.length &&
                    groups[i + 1].length == 1 &&
                    groups[i + 1].first.kind == 'usage')
                ? groups[i + 1].first
                : null;

            if (group.length > 1) {
              return _withUsageBadge(ActionGroup(actions: group), nextUsage);
            }
            final m = group.first;
            if (m.kind == 'attachment_album') {
              final list = (m.meta?['items'] as List?)?.cast<Map>() ?? const [];
              final items = list
                  .map(
                    (e) => e.map(
                      (k, v) => MapEntry(k.toString(), v?.toString() ?? ''),
                    ),
                  )
                  .toList();
              return AlbumBubble(items: items, isUser: m.role == 'user');
            }
            if (m.kind == 'attachment') {
              final name = (m.meta?['name'] as String?) ?? (m.text ?? 'file');
              final fileId = (m.meta?['fileId'] as String?) ?? '';
              final preview = (m.meta?['previewBase64'] as String?);
              return AttachmentBubble(
                name: name,
                fileId: fileId,
                isUser: m.role == 'user',
                previewBase64: preview,
              );
            }
            if (m.kind == 'screenshot' &&
                m.imageBase64 != null &&
                m.imageBase64!.isNotEmpty) {
              final screenshot = GestureDetector(
                onTap: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) =>
                          LightboxViewer(base64Images: [m.imageBase64!]),
                    ),
                  );
                },
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: SizedBox(
                    width: 50,
                    height: 50,
                    child: FittedBox(
                      fit: BoxFit.cover,
                      child: Image.memory(
                        const Base64Decoder().convert(m.imageBase64!),
                        gaplessPlayback: true,
                      ),
                    ),
                  ),
                ),
              );
              return _withUsageBadge(
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: screenshot,
                ),
                nextUsage,
              );
            }
            if (m.kind == 'usage') {
              // Skip — already attached as badge to previous message
              if (i > 0) {
                final prevGroup = groups[i - 1];
                final prevKind = prevGroup.length == 1
                    ? prevGroup.first.kind
                    : 'action_group';
                if (prevKind != 'usage') {
                  return const SizedBox.shrink();
                }
              }
              // Orphan usage (no previous message) — show standalone
              return Align(
                alignment: Alignment.centerRight,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: _UsageBadge(
                    meta: m.meta ?? const {},
                    useInfoColor: true,
                  ),
                ),
              );
            }
            if (m.kind == 'approval') {
              return ApprovalCard(message: m);
            }
            if (m.kind == 'link_suggestions') {
              return LinkSuggestionsCard(message: m, store: store);
            }
            if (m.kind == 'action') {
              return ActionMessage(message: m);
            }
            if (m.kind == 'thought') {
              final isThinking = (m.meta?['thinking'] as bool?) == true;
              if (isThinking) {
                final maxBubbleWidth = MediaQuery.of(context).size.width * 0.88;
                final bubble = Container(
                  margin: const EdgeInsets.symmetric(vertical: 6),
                  padding: const EdgeInsets.symmetric(
                    vertical: 8,
                    horizontal: 10,
                  ),
                  constraints: BoxConstraints(maxWidth: maxBubbleWidth),
                  decoration: BoxDecoration(
                    color: context.themeColors.assistantBubbleBg,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: context.themeColors.surfaceBorder,
                    ),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        crossAxisAlignment: CrossAxisAlignment.center,
                        children: [
                          Icon(
                            Icons.psychology,
                            size: 14,
                            color: context.themeColors.assistantBubbleFg,
                          ),
                          const SizedBox(width: 6),
                          Flexible(
                            child: Text(
                              m.text ?? '',
                              softWrap: true,
                              style: context.theme.style(
                                (t) => t.bodySmall,
                                (c) => c.assistantBubbleFg,
                              ),
                            ),
                          ),
                          const SizedBox(width: 6),
                          SizedBox(
                            width: 12,
                            height: 12,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: context.themeColors.assistantBubbleFg,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(999),
                        child: LinearProgressIndicator(
                          key: const ValueKey('memory_save_progress_bar'),
                          minHeight: 3,
                          backgroundColor: context.themeColors.surfaceBorder,
                          color: Theme.of(context).colorScheme.primary,
                        ),
                      ),
                    ],
                  ),
                );
                return _withUsageBadge(bubble, nextUsage);
              }
              // Completed thought: render with markdown
              final maxBubbleWidth = MediaQuery.of(context).size.width * 0.85;
              final bubble = IntrinsicWidth(
                child: Container(
                  margin: const EdgeInsets.symmetric(vertical: 6),
                  padding: const EdgeInsets.symmetric(
                    vertical: 8,
                    horizontal: 10,
                  ),
                  constraints: BoxConstraints(maxWidth: maxBubbleWidth),
                  decoration: BoxDecoration(
                    color: context.themeColors.assistantBubbleBg,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                      color: context.themeColors.surfaceBorder,
                    ),
                  ),
                  child: (m.text != null && m.text!.isNotEmpty)
                      ? MarkdownMessage(text: m.text!)
                      : const SizedBox.shrink(),
                ),
              );
              if (m.text == null || m.text!.isEmpty) {
                return _withUsageBadge(bubble, nextUsage);
              }
              return _withUsageBadge(bubble, nextUsage, copyText: m.text);
            }
            if (m.kind == 'system') {
              return SystemChip(
                text: m.text ?? '',
                isError: m.meta?['isError'] == true,
              );
            }
            final bubble = _MessageBubble(
              role: m.role,
              text: m.text ?? '',
              ts: m.ts,
            );
            final align =
                m.role == 'user' ? Alignment.centerRight : Alignment.centerLeft;
            if ((m.text ?? '').isEmpty) {
              return _withUsageBadge(bubble, nextUsage, alignment: align);
            }
            return _withUsageBadge(
              bubble,
              nextUsage,
              copyText: m.text,
              alignment: align,
            );
          },
        );
      },
    );
  }
}

/// Wraps a message widget with usage $ badge and optional copy button in top-right corner.
class _MessageOverlay extends StatefulWidget {
  final Widget child;
  final dynamic usageMsg;
  final String? copyText;
  final Alignment alignment;
  const _MessageOverlay({
    required this.child,
    this.usageMsg,
    this.copyText,
    this.alignment = Alignment.centerLeft,
  });

  @override
  State<_MessageOverlay> createState() => _MessageOverlayState();
}

class _MessageOverlayState extends State<_MessageOverlay> {
  bool _hovered = false;
  bool _copied = false;

  void _copy() {
    if (widget.copyText == null) return;
    Clipboard.setData(ClipboardData(text: widget.copyText!));
    setState(() => _copied = true);
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) setState(() => _copied = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final hasUsage = widget.usageMsg != null;
    final hasCopy = widget.copyText != null && widget.copyText!.isNotEmpty;
    if (!hasUsage && !hasCopy) {
      return Align(alignment: widget.alignment, child: widget.child);
    }

    final showButtons = _hovered && (hasUsage || hasCopy);

    return Align(
      alignment: widget.alignment,
      child: MouseRegion(
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: Stack(
          clipBehavior: Clip.none,
          children: [
            widget.child,
            if (showButtons)
              // Use LayoutBuilder to find child's actual rendered bounds
              Positioned.fill(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    return Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Positioned(
                          right: -12,
                          top: 2,
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              if (hasUsage)
                                _UsageBadge(
                                  meta: widget.usageMsg.meta ?? const {},
                                  useInfoColor: true,
                                ),
                              if (_hovered && hasCopy) ...[
                                if (hasUsage) const SizedBox(height: 4),
                                GestureDetector(
                                  onTap: _copy,
                                  child: Container(
                                    padding: const EdgeInsets.all(4),
                                    decoration: BoxDecoration(
                                      color: Theme.of(context)
                                          .colorScheme
                                          .surface
                                          .withValues(alpha: 0.9),
                                      borderRadius: BorderRadius.circular(6),
                                      border: Border.all(
                                        color: Theme.of(context)
                                            .colorScheme
                                            .outline
                                            .withValues(alpha: 0.2),
                                      ),
                                    ),
                                    child: Icon(
                                      _copied ? Icons.check : Icons.copy,
                                      size: 13,
                                      color: _copied
                                          ? Colors.green
                                          : Theme.of(
                                              context,
                                            ).colorScheme.onSurfaceVariant,
                                    ),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }
}

Widget _withUsageBadge(
  Widget child,
  dynamic usageMsg, {
  String? copyText,
  Alignment alignment = Alignment.centerLeft,
}) {
  if (usageMsg == null && (copyText == null || copyText.isEmpty)) {
    return Align(alignment: alignment, child: child);
  }
  return _MessageOverlay(
    usageMsg: usageMsg,
    copyText: copyText,
    alignment: alignment,
    child: child,
  );
}

class _MessageBubble extends StatelessWidget {
  final String role;
  final String text;
  final DateTime ts;
  const _MessageBubble({
    required this.role,
    required this.text,
    required this.ts,
  });

  bool get isUser => role == 'user';

  @override
  Widget build(BuildContext context) {
    final timeStr =
        '${ts.hour.toString().padLeft(2, '0')}:${ts.minute.toString().padLeft(2, '0')}';
    final timeColor = isUser
        ? Colors.white.withValues(alpha: 0.6)
        : Theme.of(context).colorScheme.onSurfaceVariant.withValues(alpha: 0.5);
    final timeStyle = TextStyle(fontSize: 10, color: timeColor);

    if (isUser) {
      // User messages: plain text with inline timestamp (original layout)
      final textStyle = context.theme.style(
        (t) => t.body,
        (c) => c.userBubbleFg,
      );
      const timePadding = '              ';
      return Container(
        margin: const EdgeInsets.symmetric(vertical: 6),
        padding: const EdgeInsets.fromLTRB(12, 8, 8, 5),
        decoration: BoxDecoration(
          color: context.themeColors.userBubbleBg,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Stack(
          children: [
            Text.rich(
              TextSpan(
                children: [
                  TextSpan(text: text, style: textStyle),
                  TextSpan(
                    text: timePadding,
                    style: textStyle.copyWith(color: const Color(0x00000000)),
                  ),
                ],
              ),
            ),
            Positioned(
              right: 0,
              bottom: 0,
              child: Text(timeStr, style: timeStyle),
            ),
          ],
        ),
      );
    }

    // Assistant messages: markdown rendering
    return Container(
      margin: const EdgeInsets.symmetric(vertical: 6),
      padding: const EdgeInsets.fromLTRB(12, 8, 8, 5),
      decoration: BoxDecoration(
        color: context.themeColors.assistantBubbleBg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          MarkdownMessage(text: text),
          Align(
            alignment: Alignment.bottomRight,
            child: Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Text(timeStr, style: timeStyle),
            ),
          ),
        ],
      ),
    );
  }
}

class _UsageBadge extends StatelessWidget {
  final Map<String, dynamic> meta;
  final bool useInfoColor;
  const _UsageBadge({required this.meta, this.useInfoColor = false});

  @override
  Widget build(BuildContext context) {
    final inTok = meta['inputTokens'] ?? 0;
    final outTok = meta['outputTokens'] ?? 0;
    final inUsd = (meta['inputUsd'] as num?)?.toDouble() ?? 0.0;
    final outUsd = (meta['outputUsd'] as num?)?.toDouble() ?? 0.0;
    final stepUsd = (meta['totalUsd'] as num?)?.toDouble() ?? (inUsd + outUsd);
    final stepTok = (inTok is int ? inTok : 0) + (outTok is int ? outTok : 0);

    // Accumulated totals from ChatStore
    final store = context.read<ChatStore?>();
    final accumTok =
        (store?.totalInputTokens ?? 0) + (store?.totalOutputTokens ?? 0);
    final accumUsd = store?.totalUsd ?? 0.0;

    final borderColor = useInfoColor
        ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.5)
        : context.themeColors.usageBorder.withValues(alpha: 0.4);
    final fillColor = useInfoColor
        ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.12)
        : context.themeColors.usageFill.withValues(alpha: 0.6);
    final iconColor = useInfoColor
        ? Theme.of(context).colorScheme.primary
        : context.themeColors.usageBorder;

    return Tooltip(
      richMessage: TextSpan(
        style: const TextStyle(fontSize: 12, height: 1.5),
        children: [
          const TextSpan(
            text: 'Input:  ',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          TextSpan(text: '$inTok tokens  \$${inUsd.toStringAsFixed(6)}\n'),
          const TextSpan(
            text: 'Output: ',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          TextSpan(text: '$outTok tokens  \$${outUsd.toStringAsFixed(6)}\n'),
          const TextSpan(
            text: 'Step:   ',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          TextSpan(text: '$stepTok tokens  \$${stepUsd.toStringAsFixed(6)}\n'),
          const TextSpan(
            text: 'Total:  ',
            style: TextStyle(fontWeight: FontWeight.w600),
          ),
          TextSpan(text: '$accumTok tokens  \$${accumUsd.toStringAsFixed(4)}'),
        ],
      ),
      waitDuration: const Duration(milliseconds: 200),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 3),
        decoration: BoxDecoration(
          color: fillColor,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: borderColor),
        ),
        child: Icon(Icons.attach_money, size: 13, color: iconColor),
      ),
    );
  }
}
