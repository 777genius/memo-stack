import 'package:flutter/material.dart';

typedef MemoryAnchorSubmit = Future<bool> Function({
  required String kind,
  required String label,
  List<String> aliases,
  String? description,
});

class MemoryAnchorFormDialog extends StatefulWidget {
  final MemoryAnchorSubmit onSubmit;

  const MemoryAnchorFormDialog({
    super.key,
    required this.onSubmit,
  });

  @override
  State<MemoryAnchorFormDialog> createState() => _MemoryAnchorFormDialogState();
}

class _MemoryAnchorFormDialogState extends State<MemoryAnchorFormDialog> {
  final _label = TextEditingController();
  final _aliases = TextEditingController();
  final _description = TextEditingController();
  String _kind = 'person';
  bool _saving = false;

  @override
  void dispose() {
    _label.dispose();
    _aliases.dispose();
    _description.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const ValueKey('memory_anchor_form_dialog'),
      title: const Text('Add anchor'),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 420),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              key: const ValueKey('memory_anchor_kind_field'),
              initialValue: _kind,
              decoration: const InputDecoration(
                labelText: 'Kind',
                border: OutlineInputBorder(),
              ),
              items: const [
                DropdownMenuItem(value: 'person', child: Text('Person')),
                DropdownMenuItem(value: 'event', child: Text('Event')),
                DropdownMenuItem(value: 'project', child: Text('Project')),
              ],
              onChanged: _saving
                  ? null
                  : (value) => setState(() => _kind = value ?? 'person'),
            ),
            const SizedBox(height: 10),
            TextField(
              key: const ValueKey('memory_anchor_label_field'),
              controller: _label,
              enabled: !_saving,
              autofocus: true,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Label',
                hintText: 'Alex, Project Atlas, Monday call',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              key: const ValueKey('memory_anchor_aliases_field'),
              controller: _aliases,
              enabled: !_saving,
              textInputAction: TextInputAction.next,
              decoration: const InputDecoration(
                labelText: 'Aliases',
                hintText: 'comma separated',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 10),
            TextField(
              key: const ValueKey('memory_anchor_description_field'),
              controller: _description,
              enabled: !_saving,
              maxLines: 3,
              decoration: const InputDecoration(
                labelText: 'Description',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _saving ? null : () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const ValueKey('memory_anchor_save_button'),
          onPressed: _saving ? null : _submit,
          child: _saving
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Save'),
        ),
      ],
    );
  }

  Future<void> _submit() async {
    setState(() => _saving = true);
    final ok = await widget.onSubmit(
      kind: _kind,
      label: _label.text,
      aliases: _aliases.text
          .split(',')
          .map((item) => item.trim())
          .where((item) => item.isNotEmpty)
          .toList(growable: false),
      description: _description.text,
    );
    if (!mounted) return;
    if (ok) {
      Navigator.of(context).pop(true);
      return;
    }
    setState(() => _saving = false);
  }
}
