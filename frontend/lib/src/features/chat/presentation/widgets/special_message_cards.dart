import 'package:flutter/material.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:provider/provider.dart';

class ApprovalCard extends StatelessWidget {
  final dynamic message;

  const ApprovalCard({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final meta = (message.meta ?? const {}) as Map;
    final jobId = (meta['jobId'] ?? '').toString();
    final approvalId = (meta['approvalId'] ?? '').toString();
    final risk = (meta['risk'] ?? '').toString();
    final toolName = (meta['toolName'] ?? '').toString();
    final summary = (message.text ?? '').toString();
    final store = context.read<ChatStore?>();

    Future<void> respond(bool approved) async {
      if (store == null || jobId.isEmpty || approvalId.isEmpty) return;
      await store.respondApproval(
        messageId: message.id.toString(),
        jobId: jobId,
        approvalId: approvalId,
        approved: approved,
      );
    }

    final colorScheme = Theme.of(context).colorScheme;
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.86,
        ),
        decoration: BoxDecoration(
          color: colorScheme.errorContainer.withValues(alpha: 0.42),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: colorScheme.error.withValues(alpha: 0.35)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.security, size: 18, color: colorScheme.error),
                const SizedBox(width: 8),
                Flexible(
                  child: Text(
                    summary,
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          color: colorScheme.onErrorContainer,
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                if (toolName.isNotEmpty)
                  _ApprovalPill(icon: Icons.build, text: toolName),
                if (risk.isNotEmpty)
                  _ApprovalPill(icon: Icons.warning_amber, text: risk),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                FilledButton.icon(
                  onPressed: () => respond(true),
                  icon: const Icon(Icons.check, size: 16),
                  label: const Text('Approve'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => respond(false),
                  icon: const Icon(Icons.close, size: 16),
                  label: const Text('Deny'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _ApprovalPill extends StatelessWidget {
  final IconData icon;
  final String text;

  const _ApprovalPill({required this.icon, required this.text});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
      decoration: BoxDecoration(
        color: colorScheme.surface.withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: colorScheme.outline.withValues(alpha: 0.25)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 13, color: colorScheme.onSurfaceVariant),
          const SizedBox(width: 4),
          Text(text, style: Theme.of(context).textTheme.labelSmall),
        ],
      ),
    );
  }
}

class LinkSuggestionsCard extends StatefulWidget {
  final ChatMessage message;
  final ChatStore store;

  const LinkSuggestionsCard({
    super.key,
    required this.message,
    required this.store,
  });

  @override
  State<LinkSuggestionsCard> createState() => _LinkSuggestionsCardState();
}

class _LinkSuggestionsCardState extends State<LinkSuggestionsCard> {
  final Set<String> _selected = {};
  bool _saving = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final rawCandidates = widget.message.meta?['candidates'];
    final candidates = rawCandidates is List
        ? rawCandidates
            .whereType<Map>()
            .map((item) => item.map((k, v) => MapEntry(k.toString(), v)))
            .toList(growable: false)
        : const <Map<String, dynamic>>[];

    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.all(12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.88,
        ),
        decoration: BoxDecoration(
          color: colorScheme.surfaceContainerLow,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: colorScheme.outlineVariant),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                Icon(Icons.hub_outlined, size: 18, color: colorScheme.primary),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    widget.message.text ?? 'Saved.',
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ),
                if (_saving)
                  const SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
              ],
            ),
            if (candidates.isNotEmpty) ...[
              const SizedBox(height: 10),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final candidate in candidates)
                    _candidateChip(context, candidate),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _candidateChip(BuildContext context, Map<String, dynamic> candidate) {
    final id = '${candidate['target_type']}:${candidate['target_id']}';
    final label = candidate['label']?.toString() ?? 'context';
    final tier = candidate['tier']?.toString() ?? 'possible';
    final score = candidate['score']?.toString() ?? '';
    final selected = _selected.contains(id);
    return Tooltip(
      message: _reasons(candidate),
      child: FilterChip(
        key: ValueKey('context_link_chip_$id'),
        selected: selected,
        avatar: Icon(_iconFor(candidate['target_type']?.toString()), size: 16),
        label: Text(score.isEmpty ? label : '$label $score'),
        onSelected: _saving || selected
            ? null
            : (_) async {
                setState(() => _saving = true);
                try {
                  await widget.store.acceptLinkSuggestion(
                    widget.message,
                    candidate,
                  );
                  if (mounted) setState(() => _selected.add(id));
                } finally {
                  if (mounted) setState(() => _saving = false);
                }
              },
        side: BorderSide(
          color: tier == 'likely'
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.outlineVariant,
        ),
      ),
    );
  }

  String _reasons(Map<String, dynamic> candidate) {
    final reasons = candidate['reasons'];
    if (reasons is List && reasons.isNotEmpty) {
      return reasons.map((item) => item.toString()).join(', ');
    }
    return candidate['preview']?.toString() ?? '';
  }

  IconData _iconFor(String? type) {
    return switch (type) {
      'fact' => Icons.psychology_alt_outlined,
      'capture' => Icons.history_outlined,
      'asset' => Icons.attach_file,
      'suggestion' => Icons.rate_review_outlined,
      'thread' => Icons.forum_outlined,
      _ => Icons.label_outline,
    };
  }
}

class SystemChip extends StatelessWidget {
  final String text;
  final bool isError;

  const SystemChip({super.key, required this.text, this.isError = false});

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final fgColor = isError ? colorScheme.error : colorScheme.onSurfaceVariant;
    final bgColor = isError
        ? colorScheme.error.withValues(alpha: 0.08)
        : colorScheme.onSurfaceVariant.withValues(alpha: 0.08);
    final borderColor = isError
        ? colorScheme.error.withValues(alpha: 0.2)
        : colorScheme.onSurfaceVariant.withValues(alpha: 0.15);
    final icon = isError ? Icons.error_outline : Icons.info_outline;

    return Center(
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: bgColor,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: borderColor),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 13, color: fgColor),
            const SizedBox(width: 5),
            Flexible(
              child: Text(
                text,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: fgColor,
                      fontStyle: FontStyle.italic,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
