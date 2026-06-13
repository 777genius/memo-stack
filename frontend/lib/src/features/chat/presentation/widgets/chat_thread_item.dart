import 'package:flutter/material.dart';

import 'package:frontend/src/features/chat/domain/entities/chat_session.dart';

class ChatThreadItem extends StatefulWidget {
  final ChatSession session;
  final bool isActive;
  final VoidCallback onTap;
  final void Function(String) onRename;
  final VoidCallback onDelete;

  const ChatThreadItem({
    super.key,
    required this.session,
    required this.isActive,
    required this.onTap,
    required this.onRename,
    required this.onDelete,
  });

  @override
  State<ChatThreadItem> createState() => _ChatThreadItemState();
}

class _ChatThreadItemState extends State<ChatThreadItem> {
  bool _isHovered = false;

  @override
  Widget build(BuildContext context) {
    final session = widget.session;
    return MouseRegion(
      onEnter: (_) => setState(() => _isHovered = true),
      onExit: (_) => setState(() => _isHovered = false),
      child: Material(
        color: widget.isActive
            ? Theme.of(context).colorScheme.primary.withValues(alpha: 0.08)
            : Colors.transparent,
        child: InkWell(
          onTap: widget.onTap,
          child: Padding(
            padding: const EdgeInsets.only(
              left: 20,
              right: 8,
              top: 8,
              bottom: 8,
            ),
            child: Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        session.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                              color: Theme.of(context).colorScheme.onSurface,
                              fontWeight:
                                  widget.isActive ? FontWeight.w600 : null,
                            ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        (session.lastMessageText ?? '').isEmpty
                            ? '-'
                            : session.lastMessageText!,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context)
                                  .colorScheme
                                  .onSurfaceVariant,
                            ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                if (!_isHovered) _ThreadUsage(session: session),
                if (_isHovered) ...[
                  IconButton(
                    tooltip: 'Rename',
                    visualDensity: VisualDensity.compact,
                    onPressed: () => _rename(context),
                    icon: Icon(
                      Icons.edit,
                      size: 18,
                      color: Theme.of(context).colorScheme.onSurface,
                    ),
                  ),
                  IconButton(
                    tooltip: 'Delete',
                    visualDensity: VisualDensity.compact,
                    onPressed: () => _delete(context),
                    icon: Icon(
                      Icons.delete_outline,
                      size: 18,
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _rename(BuildContext context) async {
    final title = await showDialog<String>(
      context: context,
      builder: (_) => _RenameThreadDialog(initialTitle: widget.session.title),
    );
    if (title != null && title.isNotEmpty) widget.onRename(title);
  }

  Future<void> _delete(BuildContext context) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          title: const Text('Delete thread?'),
          content: const Text('This cannot be undone.'),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(false),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(true),
              child: const Text('Delete'),
            ),
          ],
        );
      },
    );
    if (ok == true) widget.onDelete();
  }
}

class _RenameThreadDialog extends StatefulWidget {
  final String initialTitle;

  const _RenameThreadDialog({required this.initialTitle});

  @override
  State<_RenameThreadDialog> createState() => _RenameThreadDialogState();
}

class _RenameThreadDialogState extends State<_RenameThreadDialog> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.initialTitle);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Rename thread'),
      content: TextField(
        controller: _controller,
        autofocus: true,
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(
          onPressed: () => Navigator.of(context).pop(_controller.text.trim()),
          child: const Text('Save'),
        ),
      ],
    );
  }
}

class _ThreadUsage extends StatelessWidget {
  final ChatSession session;

  const _ThreadUsage({required this.session});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Text(
          '\$${session.totalUsd.toStringAsFixed(4)}',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
        Text(
          '${session.totalInputTokens + session.totalOutputTokens} tok',
          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
        ),
      ],
    );
  }
}
