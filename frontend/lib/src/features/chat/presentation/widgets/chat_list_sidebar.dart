import 'package:flutter/material.dart';
import 'package:flutter_mobx/flutter_mobx.dart';
import 'package:provider/provider.dart';

import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_scope.dart';
import 'package:frontend/src/features/chat/presentation/widgets/memory_scope_dialogs.dart';
import 'package:frontend/src/features/chat/presentation/widgets/memory_scope_section.dart';
import 'package:frontend/src/features/chat/presentation/widgets/scope_error_banner.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';

export 'package:frontend/src/features/chat/presentation/widgets/memory_scope_dialogs.dart'
    show showMemoryScopeDialog;

class ChatListSidebar extends StatelessWidget {
  final void Function()? onCreateChat;
  final void Function()? onOpenUsage;
  final void Function()? onChatTapped;
  final double? width;
  final bool showHeader;
  final bool showBorder;

  const ChatListSidebar({
    super.key,
    this.onCreateChat,
    this.onOpenUsage,
    this.onChatTapped,
    this.width,
    this.showHeader = true,
    this.showBorder = true,
  });

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final bgAlpha = isDark ? 0.47 : 0.2;
    return Container(
      width: width ?? 300,
      decoration: showBorder
          ? BoxDecoration(
              color: Theme.of(
                context,
              ).colorScheme.surface.withValues(alpha: bgAlpha),
              border: Border(
                right: BorderSide(color: context.themeColors.surfaceBorder),
              ),
            )
          : null,
      child: Column(
        children: [
          if (showHeader)
            _SidebarHeader(
              onCreateChat: onCreateChat,
              onOpenUsage: onOpenUsage,
            ),
          Expanded(
            child: Observer(
              builder: (_) {
                final store = context.read<ChatStore?>();
                if (store == null) return const SizedBox.shrink();
                final scopes = _orderedScopes(store);
                return ListView.builder(
                  key: const ValueKey('memory_scope_sidebar_list'),
                  itemCount:
                      scopes.length + (store.memoryScopeError == null ? 0 : 1),
                  itemBuilder: (ctx, index) {
                    if (index == 0 && store.memoryScopeError != null) {
                      return ScopeErrorBanner(
                        message: store.memoryScopeError!,
                      );
                    }
                    final offset =
                        store.memoryScopeError == null ? index : index - 1;
                    final scope = scopes[offset];
                    final sessions = store.sessions
                        .where(
                          (item) =>
                              item.memoryScopeExternalRef == scope.externalRef,
                        )
                        .toList(growable: false);
                    return MemoryScopeSection(
                      scope: scope,
                      sessions: sessions,
                      activeChatId: store.activeChatId,
                      activeScopeRef: store.activeMemoryScopeExternalRef,
                      onChatTapped: onChatTapped,
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  List<MemoryScope> _orderedScopes(ChatStore store) {
    final byRef = <String, MemoryScope>{};
    for (final scope in store.memoryScopes) {
      byRef[scope.externalRef] = scope;
    }
    for (final session in store.sessions) {
      byRef.putIfAbsent(
        session.memoryScopeExternalRef,
        () => MemoryScope.local(externalRef: session.memoryScopeExternalRef),
      );
    }
    byRef.putIfAbsent(
      'default',
      () => MemoryScope.local(externalRef: 'default'),
    );
    final scopes = byRef.values.toList();
    scopes.sort((a, b) {
      if (a.externalRef == store.activeMemoryScopeExternalRef) return -1;
      if (b.externalRef == store.activeMemoryScopeExternalRef) return 1;
      return b.updatedAt.compareTo(a.updatedAt);
    });
    return scopes;
  }
}

class _SidebarHeader extends StatelessWidget {
  final void Function()? onCreateChat;
  final void Function()? onOpenUsage;

  const _SidebarHeader({required this.onCreateChat, required this.onOpenUsage});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          Expanded(
            child: Text(
              'Memory scopes',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: Theme.of(context).colorScheme.onSurface,
                    fontWeight: FontWeight.w600,
                  ),
            ),
          ),
          IconButton(
            key: const ValueKey('memory_scope_create_button'),
            tooltip: 'New memory scope',
            onPressed: () => showMemoryScopeDialog(context),
            icon: Icon(
              Icons.create_new_folder_outlined,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          IconButton(
            key: const ValueKey('chat_create_button'),
            tooltip: 'New thread',
            onPressed: onCreateChat,
            icon: Icon(
              Icons.add,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
          IconButton(
            tooltip: 'Usage',
            onPressed: onOpenUsage,
            icon: Icon(
              Icons.bar_chart_outlined,
              color: Theme.of(context).colorScheme.onSurface,
            ),
          ),
        ],
      ),
    );
  }
}
