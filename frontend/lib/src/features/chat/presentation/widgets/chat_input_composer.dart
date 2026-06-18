import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'package:flutter_mobx/flutter_mobx.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_service.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/presentation/widgets/upload_overlay.dart';

class ChatInputComposer extends StatefulWidget {
  const ChatInputComposer({super.key});

  @override
  State<ChatInputComposer> createState() => _ChatInputComposerState();
}

class _ChatInputComposerState extends State<ChatInputComposer> {
  final controller = TextEditingController();
  final focusNode = FocusNode();
  bool hasText = false;

  /// Pending clipboard images (attached but not yet sent).
  final List<AttachmentUploadDraft> _pendingImages = [];

  @override
  void initState() {
    super.initState();
    controller.addListener(_onTextChanged);
  }

  void _onTextChanged() {
    final newHasText = controller.text.trim().isNotEmpty;
    if (newHasText != hasText) {
      setState(() {
        hasText = newHasText;
      });
    }
  }

  @override
  void dispose() {
    controller.removeListener(_onTextChanged);
    controller.dispose();
    focusNode.dispose();
    super.dispose();
  }

  bool get _hasTextNow => controller.text.trim().isNotEmpty;
  bool get _hasContent => _hasTextNow || _pendingImages.isNotEmpty;

  // ── Clipboard paste ──

  Future<void> _handlePaste() async {
    final reader = context.read<ClipboardAttachmentReader?>();
    // Check if clipboard has text — if so, let TextField handle it
    try {
      final textData = await Clipboard.getData(Clipboard.kTextPlain);
      if (textData != null &&
          textData.text != null &&
          textData.text!.isNotEmpty) {
        return;
      }
    } catch (_) {}

    if (!mounted) return;
    final image = await reader?.readImage();
    if (!mounted || image == null) return;
    setState(() {
      _pendingImages.add(image);
    });
    focusNode.requestFocus();
  }

  void _removeImage(int index) {
    setState(() {
      _pendingImages.removeAt(index);
    });
  }

  // ── Upload pending images ──

  Future<int> _uploadPendingImages() async {
    if (_pendingImages.isEmpty) return 0;
    final upload = context.read<AttachmentUploadService?>();
    if (upload == null) return 0;
    final store = context.read<UploadStore?>();
    final images = List<AttachmentUploadDraft>.from(_pendingImages);
    setState(() {
      _pendingImages.clear();
    });
    final uploaded = await upload.uploadAll(images, progress: store);
    return uploaded.length;
  }

  // ── Send ──

  Future<void> _sendMessage() async {
    final txt = controller.text.trim();
    final store = context.read<ChatStore?>();
    if (store == null) return;
    if (store.running) return;
    if (txt.isEmpty && _pendingImages.isEmpty) return;

    // Upload pending images first
    final uploadedImages = await _uploadPendingImages();
    if (!mounted) return;

    if (txt.isNotEmpty || uploadedImages > 0) {
      try {
        await store.sendTask(txt);
        controller.clear();
      } catch (_) {
        // The repository emits a visible error message. Keep the draft for retry.
      }
    }
    focusNode.requestFocus();
  }

  Future<void> _stopGeneration() async {
    final repo = context.read<ChatStore?>()?.repo;
    await repo?.cancelCurrentJob();
  }

  Future<void> _handleIdlePrimaryAction() async {
    if (_hasContent) {
      await _sendMessage();
      return;
    }
    await launchUrl(Uri.parse('https://voicetext.site/'));
  }

  // ── File picker ──

  Future<void> _pickFiles() async {
    final picker = context.read<AttachmentFilePicker?>();
    final upload = context.read<AttachmentUploadService?>();
    if (picker == null || upload == null) return;
    List<AttachmentUploadDraft> drafts;
    try {
      drafts = await picker.pickFiles();
    } catch (e) {
      debugPrint('FilePicker error: $e');
      return;
    }
    if (!mounted) return;
    if (drafts.isEmpty) return;
    final store = context.read<UploadStore?>();
    final uploaded = await upload.uploadAll(drafts, progress: store);
    if (!mounted || uploaded.isEmpty) return;
    final chatStore = context.read<ChatStore?>();
    if (chatStore == null || chatStore.running) return;
    final text = controller.text.trim();
    try {
      await chatStore.sendTask(text);
      controller.clear();
    } catch (_) {
      // The repository emits a visible error message. Keep the draft for retry.
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Observer(
              builder: (_) {
                final store = context.read<ChatStore?>();
                if (store == null) return const SizedBox.shrink();
                return _SaveTargetStrip(
                  scopeName: _activeScopeName(store),
                  threadTitle: _activeThreadTitle(store),
                );
              },
            ),

            // ── Pending image previews ──
            if (_pendingImages.isNotEmpty)
              Container(
                height: 72,
                margin: const EdgeInsets.only(bottom: 8),
                child: ListView.separated(
                  scrollDirection: Axis.horizontal,
                  itemCount: _pendingImages.length,
                  separatorBuilder: (_, __) => const SizedBox(width: 8),
                  itemBuilder: (context, i) {
                    return Stack(
                      clipBehavior: Clip.none,
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(12),
                          child: Image.memory(
                            _pendingImages[i].bytes,
                            width: 64,
                            height: 64,
                            fit: BoxFit.cover,
                            errorBuilder: (_, __, ___) => Container(
                              width: 64,
                              height: 64,
                              alignment: Alignment.center,
                              color: colorScheme.surfaceContainerHighest,
                              child: Icon(
                                Icons.image_not_supported_outlined,
                                color: colorScheme.onSurfaceVariant,
                              ),
                            ),
                          ),
                        ),
                        Positioned(
                          top: -6,
                          right: -6,
                          child: GestureDetector(
                            onTap: () => _removeImage(i),
                            child: Container(
                              width: 20,
                              height: 20,
                              decoration: BoxDecoration(
                                color: colorScheme.error,
                                shape: BoxShape.circle,
                              ),
                              child: const Icon(
                                Icons.close,
                                size: 14,
                                color: Colors.white,
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),

            // ── Input bar ──
            Container(
              decoration: BoxDecoration(
                color: colorScheme.surface,
                borderRadius: BorderRadius.circular(28),
                border: Border.all(
                  color: colorScheme.outline.withValues(alpha: 0.2),
                  width: 1,
                ),
                boxShadow: [
                  BoxShadow(
                    color: colorScheme.shadow.withValues(alpha: 0.05),
                    blurRadius: 10,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final isNarrow = constraints.maxWidth < 200;
                  return Row(
                    crossAxisAlignment: CrossAxisAlignment.center,
                    children: [
                      // Attach file button — hide when too narrow
                      if (!isNarrow)
                        Padding(
                          padding: const EdgeInsets.only(left: 4, right: 4),
                          child: IconButton(
                            key: const ValueKey('quick_capture_attach_button'),
                            onPressed: _pickFiles,
                            icon: Icon(
                              Icons.add_circle,
                              color: colorScheme.onSurfaceVariant,
                            ),
                            tooltip: 'Attach file',
                          ),
                        ),

                      // Text input with paste interception and Enter/Shift+Enter handling
                      Expanded(
                        child: Padding(
                          padding: const EdgeInsets.symmetric(vertical: 0),
                          child: Focus(
                            onKeyEvent: (node, event) {
                              if (event is! KeyDownEvent) {
                                return KeyEventResult.ignored;
                              }
                              // Intercept Cmd+V / Ctrl+V for image paste
                              if (event.logicalKey == LogicalKeyboardKey.keyV &&
                                  (HardwareKeyboard.instance.isMetaPressed ||
                                      HardwareKeyboard
                                          .instance.isControlPressed)) {
                                _handlePaste();
                                return KeyEventResult
                                    .ignored; // let TextField paste text too
                              }
                              // Enter = send (consume event), Shift+Enter = newline (pass through)
                              if (event.logicalKey ==
                                      LogicalKeyboardKey.enter &&
                                  !HardwareKeyboard.instance.isShiftPressed) {
                                _sendMessage();
                                return KeyEventResult
                                    .handled; // prevent newline insertion
                              }
                              return KeyEventResult.ignored;
                            },
                            child: TextField(
                              key: const ValueKey('quick_capture_input'),
                              controller: controller,
                              focusNode: focusNode,
                              minLines: 1,
                              maxLines: 5,
                              textInputAction: TextInputAction.newline,
                              decoration: InputDecoration(
                                hintText: 'Save a note, screenshot, or file...',
                                hintStyle: TextStyle(
                                  color: colorScheme.onSurfaceVariant
                                      .withValues(alpha: 0.6),
                                ),
                                border: InputBorder.none,
                                contentPadding: const EdgeInsets.symmetric(
                                  vertical: 10,
                                ),
                              ),
                              style: TextStyle(
                                color: colorScheme.onSurface,
                                fontSize: 16,
                              ),
                            ),
                          ),
                        ),
                      ),

                      // Right side buttons
                      Padding(
                        padding: const EdgeInsets.only(left: 4, right: 4),
                        child: Observer(
                          builder: (_) {
                            final store = context.read<ChatStore?>();
                            final isRunning = store?.running ?? false;
                            if (isRunning) {
                              return IconButton(
                                key: const ValueKey(
                                  'quick_capture_stop_button',
                                ),
                                onPressed: _stopGeneration,
                                icon: Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: colorScheme.error,
                                    shape: BoxShape.circle,
                                  ),
                                  child: const Icon(
                                    Icons.stop_rounded,
                                    color: Colors.white,
                                    size: 20,
                                  ),
                                ),
                                tooltip: 'Stop saving',
                              );
                            } else if (_hasContent) {
                              return Tooltip(
                                message: 'Save memory',
                                child: IconButton(
                                  key: const ValueKey(
                                    'quick_capture_send_button',
                                  ),
                                  onPressed: _sendMessage,
                                  icon: Container(
                                    padding: const EdgeInsets.all(8),
                                    decoration: BoxDecoration(
                                      color: colorScheme.primary,
                                      shape: BoxShape.circle,
                                    ),
                                    child: Icon(
                                      Icons.arrow_upward_rounded,
                                      color: colorScheme.onPrimary,
                                      size: 20,
                                    ),
                                  ),
                                ),
                              );
                            } else {
                              return IconButton(
                                key: const ValueKey(
                                  'quick_capture_primary_action_button',
                                ),
                                onPressed: _handleIdlePrimaryAction,
                                icon: Icon(
                                  Icons.mic_none_outlined,
                                  color: colorScheme.onSurfaceVariant,
                                ),
                                tooltip: 'Voice input',
                              );
                            }
                          },
                        ),
                      ),
                    ],
                  );
                },
              ),
            ),

            // ── Hotkey hint when agent is running ──
            Observer(
              builder: (_) {
                final store = context.read<ChatStore?>();
                if (store?.running ?? false) {
                  return Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      'Press Ctrl+Esc to stop the agent (works globally)',
                      style: TextStyle(
                        fontSize: 11,
                        color: colorScheme.onSurfaceVariant.withValues(
                          alpha: 0.5,
                        ),
                      ),
                    ),
                  );
                }
                return const SizedBox.shrink();
              },
            ),
          ],
        ),
      ),
    );
  }
}

class _SaveTargetStrip extends StatelessWidget {
  final String scopeName;
  final String threadTitle;

  const _SaveTargetStrip({
    required this.scopeName,
    required this.threadTitle,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Wrap(
          key: const ValueKey('quick_capture_save_target_strip'),
          spacing: 6,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Icon(
              Icons.save_alt_rounded,
              size: 14,
              color: colorScheme.onSurfaceVariant,
            ),
            Text(
              'Save target',
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w600,
                  ),
            ),
            _SaveTargetChip(
              key: const ValueKey('quick_capture_scope_chip'),
              icon: Icons.folder_outlined,
              text: scopeName,
              tooltip: 'Memory scope: $scopeName',
            ),
            _SaveTargetChip(
              key: const ValueKey('quick_capture_thread_chip'),
              icon: Icons.forum_outlined,
              text: threadTitle,
              tooltip: 'Thread: $threadTitle',
            ),
          ],
        ),
      ),
    );
  }
}

String _activeScopeName(ChatStore store) {
  final activeRef = store.activeMemoryScopeExternalRef;
  for (final scope in store.memoryScopes) {
    if (scope.externalRef == activeRef) return scope.name;
  }
  return activeRef;
}

String _activeThreadTitle(ChatStore store) {
  final activeChatId = store.activeChatId;
  for (final session in store.sessions) {
    if (session.id == activeChatId) return session.title;
  }
  return 'New thread';
}

class _SaveTargetChip extends StatelessWidget {
  final IconData icon;
  final String text;
  final String tooltip;

  const _SaveTargetChip({
    super.key,
    required this.icon,
    required this.text,
    required this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Tooltip(
      message: tooltip,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 180),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.68),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: colorScheme.outlineVariant),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: colorScheme.onSurfaceVariant),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                text,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color: colorScheme.onSurface,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
