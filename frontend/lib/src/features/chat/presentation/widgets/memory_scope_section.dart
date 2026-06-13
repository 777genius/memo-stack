import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_session.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_scope.dart';
import 'package:frontend/src/features/chat/presentation/widgets/chat_thread_item.dart';
import 'package:frontend/src/features/chat/presentation/widgets/extraction_status_panel.dart';
import 'package:frontend/src/features/chat/presentation/widgets/memory_history_panel.dart';
import 'package:frontend/src/features/chat/presentation/widgets/memory_scope_dialogs.dart';
import 'package:frontend/src/features/chat/presentation/widgets/sidebar_formatters.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';

class MemoryScopeSection extends StatelessWidget {
  final MemoryScope scope;
  final List<ChatSession> sessions;
  final String activeChatId;
  final String activeScopeRef;
  final void Function()? onChatTapped;

  const MemoryScopeSection({
    super.key,
    required this.scope,
    required this.sessions,
    required this.activeChatId,
    required this.activeScopeRef,
    required this.onChatTapped,
  });

  @override
  Widget build(BuildContext context) {
    final store = context.read<ChatStore?>();
    final active = activeScopeRef == scope.externalRef;
    return DecoratedBox(
      key: ValueKey('memory_scope_group_${sidebarKeyPart(scope.externalRef)}'),
      decoration: BoxDecoration(
        border: Border(
          top: BorderSide(color: context.themeColors.surfaceBorder),
        ),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: active || sessions.isNotEmpty,
          tilePadding: const EdgeInsets.only(left: 12, right: 4),
          childrenPadding: const EdgeInsets.only(bottom: 4),
          title: InkWell(
            onTap: () => store?.setActiveMemoryScope(scope.externalRef),
            child: _ScopeTitle(
              scope: scope,
              sessionsCount: sessions.length,
              active: active,
            ),
          ),
          trailing: _ScopeActions(
            scope: scope,
            onChatTapped: onChatTapped,
          ),
          children: [
            if (active) const MemoryHistoryPanel(),
            if (active) const ExtractionStatusPanel(),
            if (sessions.isEmpty)
              const _EmptyScopeMessage()
            else
              for (final session in sessions)
                ChatThreadItem(
                  key: ValueKey('chat_thread_${sidebarKeyPart(session.id)}'),
                  session: session,
                  isActive: session.id == activeChatId,
                  onTap: () {
                    store?.setActiveChat(session.id);
                    onChatTapped?.call();
                  },
                  onRename: (newTitle) =>
                      store?.renameChat(session.id, newTitle),
                  onDelete: () => store?.removeChat(session.id),
                ),
          ],
        ),
      ),
    );
  }
}

class _ScopeTitle extends StatelessWidget {
  final MemoryScope scope;
  final int sessionsCount;
  final bool active;

  const _ScopeTitle({
    required this.scope,
    required this.sessionsCount,
    required this.active,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            scope.name,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  fontWeight: active ? FontWeight.w700 : FontWeight.w600,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
          ),
          const SizedBox(height: 2),
          Text(
            '${scope.externalRef} - $sessionsCount threads',
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
        ],
      ),
    );
  }
}

class _ScopeActions extends StatelessWidget {
  final MemoryScope scope;
  final void Function()? onChatTapped;

  const _ScopeActions({
    required this.scope,
    required this.onChatTapped,
  });

  @override
  Widget build(BuildContext context) {
    final store = context.read<ChatStore?>();
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        IconButton(
          key: ValueKey(
            'memory_scope_new_chat_${sidebarKeyPart(scope.externalRef)}',
          ),
          tooltip: 'New thread in ${scope.name}',
          visualDensity: VisualDensity.compact,
          onPressed: () {
            store?.createNewChat(memoryScopeExternalRef: scope.externalRef);
            onChatTapped?.call();
          },
          icon: Icon(
            Icons.add_comment_outlined,
            size: 18,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        PopupMenuButton<String>(
          key: ValueKey(
            'memory_scope_menu_${sidebarKeyPart(scope.externalRef)}',
          ),
          tooltip: 'Memory scope actions',
          onSelected: (value) async {
            if (value == 'edit') {
              await showMemoryScopeDialog(context, scope: scope);
            } else if (value == 'delete') {
              await confirmDeleteMemoryScope(context, scope);
            }
          },
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'edit', child: Text('Edit')),
            PopupMenuItem(value: 'delete', child: Text('Delete')),
          ],
          icon: Icon(
            Icons.more_horiz,
            size: 18,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }
}

class _EmptyScopeMessage extends StatelessWidget {
  const _EmptyScopeMessage();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 2, 16, 10),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(
          'No threads yet',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ),
    );
  }
}
