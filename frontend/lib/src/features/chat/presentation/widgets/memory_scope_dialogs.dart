import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_scope.dart';

Future<void> showMemoryScopeDialog(
  BuildContext context, {
  MemoryScope? scope,
}) async {
  final store = context.read<ChatStore?>();
  if (store == null) return;
  final isEdit = scope != null;
  final input = await showDialog<_MemoryScopeDialogInput>(
    context: context,
    builder: (ctx) => _MemoryScopeDialog(scope: scope),
  );
  if (input == null) return;

  final result = isEdit
      ? await store.updateMemoryScope(
          scope,
          externalRef: input.externalRef,
          name: input.name,
        )
      : await store.createMemoryScope(
          externalRef: input.externalRef,
          name: input.name,
        );
  if (result == null && context.mounted) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(store.memoryScopeError ?? 'Memory scope failed'),
      ),
    );
  }
}

class _MemoryScopeDialogInput {
  final String externalRef;
  final String name;

  const _MemoryScopeDialogInput({
    required this.externalRef,
    required this.name,
  });
}

class _MemoryScopeDialog extends StatefulWidget {
  final MemoryScope? scope;

  const _MemoryScopeDialog({required this.scope});

  @override
  State<_MemoryScopeDialog> createState() => _MemoryScopeDialogState();
}

class _MemoryScopeDialogState extends State<_MemoryScopeDialog> {
  late final TextEditingController _nameController;
  late final TextEditingController _refController;

  @override
  void initState() {
    super.initState();
    _nameController = TextEditingController(text: widget.scope?.name ?? '');
    _refController = TextEditingController(
      text: widget.scope?.externalRef ?? '',
    );
  }

  @override
  void dispose() {
    _nameController.dispose();
    _refController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isEdit = widget.scope != null;
    return AlertDialog(
      title: Text(isEdit ? 'Edit memory scope' : 'New memory scope'),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              key: const ValueKey('memory_scope_name_field'),
              controller: _nameController,
              autofocus: true,
              decoration: const InputDecoration(labelText: 'Name'),
            ),
            const SizedBox(height: 12),
            TextField(
              key: const ValueKey('memory_scope_ref_field'),
              controller: _refController,
              decoration: const InputDecoration(labelText: 'Reference'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const ValueKey('memory_scope_save_button'),
          onPressed: () {
            final ref = _refController.text.trim().isEmpty
                ? 'default'
                : _refController.text.trim();
            final name = _nameController.text.trim().isEmpty
                ? ref
                : _nameController.text.trim();
            Navigator.of(context).pop(
              _MemoryScopeDialogInput(externalRef: ref, name: name),
            );
          },
          child: const Text('Save'),
        ),
      ],
    );
  }
}

Future<void> confirmDeleteMemoryScope(
  BuildContext context,
  MemoryScope scope,
) async {
  final store = context.read<ChatStore?>();
  if (store == null) return;
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) {
      return AlertDialog(
        title: Text('Delete ${scope.name}?'),
        content: const Text(
          'Local threads in this scope will be removed from the sidebar. Stored server memory is not erased.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            key: const ValueKey('memory_scope_delete_confirm_button'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Delete'),
          ),
        ],
      );
    },
  );
  if (ok == true) {
    await store.deleteMemoryScope(scope);
  }
}
