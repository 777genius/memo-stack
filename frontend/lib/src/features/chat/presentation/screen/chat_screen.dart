import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_mobx/flutter_mobx.dart';
import 'package:provider/provider.dart';

import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_service.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';
import 'package:frontend/src/features/chat/presentation/screen/chat_list_overlay_screen.dart';
import 'package:frontend/src/features/chat/presentation/widgets/capture_review_dock.dart';
import 'package:frontend/src/features/chat/presentation/widgets/chat_input_composer.dart';
import 'package:frontend/src/features/chat/presentation/widgets/chat_list_sidebar.dart';
import 'package:frontend/src/features/chat/presentation/widgets/chat_messages_list.dart';
import 'package:frontend/src/features/chat/presentation/widgets/upload_overlay.dart';
import 'package:frontend/src/features/usage/presentation/usage_screen.dart';
import 'package:frontend/src/presentation/stores/theme_store.dart';
import 'package:frontend/src/presentation/settings/settings_screen.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';
import 'package:frontend/src/presentation/utils/drop_target.dart';
import 'package:frontend/src/presentation/overlay/window_mode_service.dart';

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  /// Preserves ChatInputComposer state (incl. TextEditingController)
  /// across overlay/normal mode switches that change the widget tree structure.
  final _inputKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final store = context.read<ChatStore?>();
      store?.init();
    });
  }

  @override
  Widget build(BuildContext context) {
    final wms = context.read<WindowModeService>();

    return ListenableBuilder(
      listenable: wms,
      builder: (context, _) {
        final isOverlay = wms.isOverlay;
        return _buildScreen(context, isOverlay: isOverlay);
      },
    );
  }

  Widget _buildScreen(BuildContext context, {required bool isOverlay}) {
    final isMacOS = !kIsWeb && defaultTargetPlatform == TargetPlatform.macOS;
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgAlpha = isDark ? 0.47 : 0.2;

    return Scaffold(
      backgroundColor: Colors.transparent,
      appBar: _buildAppBar(
        context,
        isOverlay: isOverlay,
        isMacOS: isMacOS,
        bgAlpha: bgAlpha,
      ),
      body: _buildBody(context, isOverlay: isOverlay, bgAlpha: bgAlpha),
    );
  }

  PreferredSizeWidget _buildAppBar(
    BuildContext context, {
    required bool isOverlay,
    required bool isMacOS,
    required double bgAlpha,
  }) {
    // In overlay mode: compact bar, no traffic light padding, expand button
    // In normal mode: full bar with sidebar padding and all actions
    final titleSpacing = isOverlay ? 12.0 : (isMacOS ? 78.0 : 16.0);
    final toolbarHeight = isOverlay ? 36.0 : (isMacOS ? 38.0 : kToolbarHeight);

    return AppBar(
      backgroundColor: Theme.of(
        context,
      ).colorScheme.surface.withValues(alpha: bgAlpha),
      surfaceTintColor: Colors.transparent,
      toolbarHeight: toolbarHeight,
      titleSpacing: titleSpacing,
      title: _AppBarTitle(isOverlay: isOverlay),
      actions: _buildActions(context, isOverlay: isOverlay),
    );
  }

  List<Widget> _buildActions(BuildContext context, {required bool isOverlay}) {
    final wms = context.read<WindowModeService>();

    if (isOverlay) {
      return [
        IconButton(
          tooltip: 'Minimize',
          onPressed: () => wms.minimizeWindow(),
          icon: const Icon(Icons.remove, size: 16),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
        ),
        IconButton(
          tooltip: 'Expand (Cmd+Shift+O)',
          onPressed: () => wms.exitOverlay(),
          icon: const Icon(Icons.open_in_full, size: 16),
          padding: EdgeInsets.zero,
          constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
        ),
        const SizedBox(width: 8),
      ];
    }

    // Normal mode: all actions
    return [
      IconButton(
        tooltip: 'Compact overlay (Cmd+Shift+O)',
        onPressed: () => wms.enterOverlay(),
        icon: const Icon(Icons.picture_in_picture_alt, size: 20),
      ),
      IconButton(
        tooltip: 'Toggle theme',
        onPressed: () {
          final ts = context.read<ThemeStore?>();
          if (ts == null) return;
          ts.toggleUsing(context);
        },
        icon: const Icon(Icons.brightness_6),
      ),
      IconButton(
        tooltip: 'Settings',
        onPressed: () {
          Navigator.of(
            context,
          ).push(MaterialPageRoute(builder: (_) => const SettingsScreen()));
        },
        icon: const Icon(Icons.settings),
      ),
      const SizedBox(width: 12),
      Observer(
        builder: (_) {
          final running = context.watch<ChatStore?>()?.running ?? false;
          return running
              ? const Padding(
                  padding: EdgeInsets.only(right: 12),
                  child: SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                )
              : const SizedBox.shrink();
        },
      ),
    ];
  }

  Widget _buildBody(
    BuildContext context, {
    required bool isOverlay,
    required double bgAlpha,
  }) {
    final chatArea = Container(
      color: Theme.of(context).colorScheme.surface.withValues(alpha: bgAlpha),
      child: UploadOverlay(
        child: _ChatDropArea(
          child: Column(
            children: [
              Observer(
                builder: (_) {
                  final store = context.read<ChatStore?>();
                  final error = store?.connectionError;
                  if (error != null) {
                    return _ConnectionErrorBanner(error: error);
                  }
                  return const SizedBox.shrink();
                },
              ),
              const Expanded(child: ChatMessagesList()),
              const CaptureReviewDock(),
              ChatInputComposer(key: _inputKey),
            ],
          ),
        ),
      ),
    );

    return LayoutBuilder(
      builder: (context, constraints) {
        final showSidebar = !isOverlay && constraints.maxWidth >= 680;
        if (!showSidebar) {
          return chatArea;
        }

        return Row(
          children: [
            ChatListSidebar(
              onCreateChat: () {
                final s = context.read<ChatStore?>();
                s?.createNewChat();
              },
              onOpenUsage: () {
                Navigator.of(
                  context,
                ).push(MaterialPageRoute(builder: (_) => const UsageScreen()));
              },
            ),
            Expanded(child: chatArea),
          ],
        );
      },
    );
  }
}

/// AppBar title — adapts to overlay mode.
class _AppBarTitle extends StatelessWidget {
  final bool isOverlay;

  const _AppBarTitle({required this.isOverlay});

  @override
  Widget build(BuildContext context) {
    return Observer(
      builder: (_) {
        final storeWatch = context.watch<ChatStore?>();
        final u = storeWatch?.usage;
        final totalUsd = storeWatch?.totalUsd ?? 0.0;
        final tin = storeWatch?.totalInputTokens ?? 0;
        final tout = storeWatch?.totalOutputTokens ?? 0;
        final conn = storeWatch?.connection ?? ConnectionStatus.connecting;

        final statusDot = _StatusDot(connection: conn);

        final statusTooltip = Tooltip(
          message: switch (conn) {
            ConnectionStatus.connected => 'Connected',
            ConnectionStatus.connecting => 'Connecting...',
            ConnectionStatus.disconnected => 'Disconnected',
            ConnectionStatus.offline => 'Offline',
            ConnectionStatus.error => 'Connection error',
          },
          child: statusDot,
        );

        // In overlay mode: title + status + chat buttons
        if (isOverlay) {
          return Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              statusTooltip,
              const SizedBox(width: 6),
              Text(
                'Infinity Context',
                style: Theme.of(
                  context,
                ).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w700),
              ),
              // Show running indicator inline in overlay
              Observer(
                builder: (_) {
                  final running = context.watch<ChatStore?>()?.running ?? false;
                  if (!running) return const SizedBox.shrink();
                  return const Padding(
                    padding: EdgeInsets.only(left: 8),
                    child: SizedBox(
                      width: 12,
                      height: 12,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  );
                },
              ),
              const SizedBox(width: 8),
              IconButton(
                key: const ValueKey('chat_scopes_threads_button'),
                tooltip: 'Scopes & threads',
                onPressed: () {
                  Navigator.of(context).push(
                    MaterialPageRoute(
                      builder: (_) => const ChatListOverlayScreen(),
                    ),
                  );
                },
                icon: Icon(
                  Icons.menu,
                  size: 16,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
              ),
              IconButton(
                key: const ValueKey('chat_new_thread_button'),
                tooltip: 'New thread',
                onPressed: () {
                  final s = context.read<ChatStore?>();
                  s?.createNewChat();
                },
                icon: Icon(
                  Icons.add,
                  size: 16,
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
                padding: EdgeInsets.zero,
                constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
              ),
            ],
          );
        }

        // Normal mode: full title with usage
        final usageLine = (u == null || (tin + tout) == 0)
            ? null
            : 'in=${u.inputTokens} out=${u.outputTokens}'
                '  \u03A3tokens=${tin + tout}'
                '  \$${u.totalUsd.toStringAsFixed(4)}'
                ' (\u03A3 \$${totalUsd.toStringAsFixed(4)})';

        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Flexible(
                  child: Text(
                    'Infinity Context',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurface,
                          fontWeight: FontWeight.w700,
                        ),
                  ),
                ),
                const SizedBox(width: 8),
                statusTooltip,
              ],
            ),
            if (usageLine != null)
              Text(
                usageLine,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
              ),
          ],
        );
      },
    );
  }
}

/// Connection status dot — reused in both modes.
class _StatusDot extends StatelessWidget {
  final ConnectionStatus connection;

  const _StatusDot({required this.connection});

  @override
  Widget build(BuildContext context) {
    switch (connection) {
      case ConnectionStatus.connected:
        return Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: context.themeColors.actionGreenBorder,
            shape: BoxShape.circle,
          ),
        );
      case ConnectionStatus.offline:
      case ConnectionStatus.error:
        return Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(
            color: Theme.of(context).colorScheme.error,
            shape: BoxShape.circle,
          ),
        );
      case ConnectionStatus.disconnected:
      case ConnectionStatus.connecting:
        return const SizedBox(
          width: 12,
          height: 12,
          child: CircularProgressIndicator(strokeWidth: 2),
        );
    }
  }
}

class _ChatDropArea extends StatefulWidget {
  final Widget child;
  const _ChatDropArea({required this.child});

  @override
  State<_ChatDropArea> createState() => _ChatDropAreaState();
}

class _ChatDropAreaState extends State<_ChatDropArea> {
  bool _dragging = false;

  @override
  Widget build(BuildContext context) {
    final overlayColor = Theme.of(
      context,
    ).colorScheme.primary.withValues(alpha: 0.08);
    return Stack(
      children: [
        DropTarget(
          onDragEntered: (_) => setState(() => _dragging = true),
          onDragExited: (_) => setState(() => _dragging = false),
          onDragDone: (details) async {
            setState(() => _dragging = false);
            if (!mounted) return;
            final upload = context.read<AttachmentUploadService?>();
            if (upload == null) return;
            final store = context.read<UploadStore?>();
            final chatStore = context.read<ChatStore?>();
            final drafts = <AttachmentUploadDraft>[];
            for (final file in details.files) {
              try {
                final data = await file.readAsBytes();
                final name = file.name.isNotEmpty ? file.name : 'file.bin';
                drafts.add(
                  AttachmentUploadDraft.file(
                    name: name,
                    bytes: data,
                    source: AttachmentUploadSource.drop,
                  ),
                );
              } catch (_) {}
            }
            if (!mounted || drafts.isEmpty) return;
            final uploaded = await upload.uploadAll(drafts, progress: store);
            if (!mounted || uploaded.isEmpty) return;
            await chatStore?.sendTask('');
          },
          child: widget.child,
        ),
        if (_dragging)
          Positioned.fill(
            child: IgnorePointer(
              child: Container(
                color: overlayColor,
                alignment: Alignment.center,
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    vertical: 12,
                    horizontal: 16,
                  ),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: Theme.of(
                        context,
                      ).colorScheme.primary.withValues(alpha: 0.3),
                    ),
                  ),
                  child: Text(
                    'Drop files to attach',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _ConnectionErrorBanner extends StatelessWidget {
  final String? error;
  const _ConnectionErrorBanner({this.error});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final errorText = error ?? 'Cannot connect to backend server';

    return ConstrainedBox(
      constraints: const BoxConstraints(maxHeight: 156),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        color: colorScheme.errorContainer,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Icon(
                Icons.error_outline,
                size: 18,
                color: colorScheme.onErrorContainer,
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: SingleChildScrollView(
                child: SelectableText(
                  errorText,
                  style: TextStyle(
                    fontSize: 12,
                    color: colorScheme.onErrorContainer,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            IconButton(
              tooltip: 'Copy error',
              onPressed: () {
                Clipboard.setData(ClipboardData(text: errorText));
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text('Error copied'),
                    duration: Duration(seconds: 1),
                  ),
                );
              },
              icon: Icon(
                Icons.copy,
                size: 16,
                color: colorScheme.onErrorContainer,
              ),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
            ),
            IconButton(
              tooltip: 'Retry connection',
              onPressed: () {
                final store = context.read<ChatStore?>();
                store?.init();
              },
              icon: Icon(
                Icons.refresh,
                size: 18,
                color: colorScheme.onErrorContainer,
              ),
              padding: EdgeInsets.zero,
              constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
            ),
          ],
        ),
      ),
    );
  }
}
