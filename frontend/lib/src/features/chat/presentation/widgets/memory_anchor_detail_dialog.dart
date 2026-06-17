import 'package:flutter/material.dart';

import 'package:frontend/src/features/chat/domain/entities/memory_browser.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';
import 'package:frontend/src/features/chat/presentation/widgets/sidebar_formatters.dart';

class MemoryAnchorDetailDialog extends StatelessWidget {
  final MemoryBrowserAnchor anchor;
  final MemoryBrowserSnapshot snapshot;

  const MemoryAnchorDetailDialog({
    super.key,
    required this.anchor,
    required this.snapshot,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final links = snapshot.contextLinks
        .where((link) => _linkTouchesAnchor(link, anchor.id))
        .toList(growable: false);
    final suggestions = snapshot.contextLinkSuggestions
        .where((suggestion) => _suggestionTouchesAnchor(suggestion, anchor.id))
        .toList(growable: false);
    final evidence = _relatedEvidence(anchor, snapshot, links, suggestions);
    final aliases = anchor.aliasesLabel;
    return Dialog(
      key:
          ValueKey('memory_browser_anchor_dialog_${sidebarKeyPart(anchor.id)}'),
      insetPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720, maxHeight: 680),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(
                    _anchorIcon(anchor.kind),
                    size: 22,
                    color: scheme.primary,
                  ),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          anchor.label,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context)
                              .textTheme
                              .titleMedium
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        Text(
                          '${anchor.kind} anchor - ${anchor.status}',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style:
                              Theme.of(context).textTheme.labelSmall?.copyWith(
                                    color: scheme.onSurfaceVariant,
                                  ),
                        ),
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Close',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close, size: 20),
                  ),
                ],
              ),
              const SizedBox(height: 10),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  _AnchorChip(label: 'key: ${anchor.normalizedKey}'),
                  if (aliases.isNotEmpty)
                    _AnchorChip(label: 'aliases: $aliases'),
                  _AnchorChip(
                    label: 'updated: ${_timeLabel(anchor.updatedAt)}',
                  ),
                  if (_metadataText(anchor, 'creation_source') != null)
                    _AnchorChip(
                      label:
                          'source: ${_metadataText(anchor, 'creation_source')}',
                    ),
                  if (_metadataText(anchor, 'canonical_key') != null)
                    _AnchorChip(
                      label:
                          'canonical: ${_metadataText(anchor, 'canonical_key')}',
                    ),
                  if (_metadataText(anchor, 'merged_into_anchor_id') != null)
                    _AnchorChip(
                      label:
                          'merged into: ${shortStorageId(_metadataText(anchor, 'merged_into_anchor_id')!)}',
                    ),
                  if (_metadataText(anchor, 'split_from_anchor_id') != null)
                    _AnchorChip(
                      label:
                          'split from: ${shortStorageId(_metadataText(anchor, 'split_from_anchor_id')!)}',
                    ),
                ],
              ),
              if (anchor.description != null) ...[
                const SizedBox(height: 10),
                Text(
                  anchor.description!,
                  maxLines: 4,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
              const SizedBox(height: 14),
              Expanded(
                child: ListView(
                  children: [
                    _AnchorDialogSection(
                      title: 'Accepted relations',
                      empty: 'No accepted relations for this anchor',
                      children: [
                        for (final link in links)
                          _AnchorRelationRow(
                            title:
                                '${_endpointLabel(link.sourceType, link.sourceId, snapshot)} -> ${_endpointLabel(link.targetType, link.targetId, snapshot)}',
                            subtitle:
                                '${link.relationType} - ${link.confidence} - ${link.reason}',
                            status: link.status,
                          ),
                      ],
                    ),
                    _AnchorDialogSection(
                      title: 'Pending suggestions',
                      empty: 'No pending suggestions for this anchor',
                      children: [
                        for (final suggestion
                            in suggestions.where((item) => item.isPending))
                          _AnchorRelationRow(
                            title:
                                '${_endpointLabel(suggestion.sourceType, suggestion.sourceId, snapshot)} -> ${suggestion.targetLabel}',
                            subtitle:
                                '${suggestion.relationType} - ${suggestion.score.toStringAsFixed(0)} - ${suggestion.reason}',
                            status: suggestion.status,
                          ),
                      ],
                    ),
                    _AnchorDialogSection(
                      title: 'Related evidence',
                      empty: 'No linked evidence in this snapshot',
                      children: evidence
                          .map(
                            (item) => _AnchorRelationRow(
                              title: item.title,
                              subtitle: item.subtitle,
                              status: item.status,
                            ),
                          )
                          .toList(growable: false),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AnchorDialogSection extends StatelessWidget {
  final String title;
  final String empty;
  final List<Widget> children;

  const _AnchorDialogSection({
    required this.title,
    required this.empty,
    required this.children,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.labelLarge?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 6),
          if (children.isEmpty)
            Text(
              empty,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            )
          else
            ...children,
        ],
      ),
    );
  }
}

class _AnchorRelationRow extends StatelessWidget {
  final String title;
  final String subtitle;
  final String status;

  const _AnchorRelationRow({
    required this.title,
    required this.subtitle,
    required this.status,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      margin: const EdgeInsets.only(bottom: 7),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      decoration: BoxDecoration(
        border: Border.all(color: scheme.outlineVariant),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          _StatusPill(status: status),
        ],
      ),
    );
  }
}

class _AnchorChip extends StatelessWidget {
  final String label;

  const _AnchorChip({required this.label});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.62),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        label,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  final String status;

  const _StatusPill({required this.status});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final active =
        status == 'active' || status == 'stored' || status == 'accepted';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: active
            ? scheme.primaryContainer.withValues(alpha: 0.68)
            : scheme.surfaceContainerHighest.withValues(alpha: 0.68),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Text(
        status,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color:
                  active ? scheme.onPrimaryContainer : scheme.onSurfaceVariant,
              fontWeight: FontWeight.w600,
            ),
      ),
    );
  }
}

class _AnchorEvidenceItem {
  final String title;
  final String subtitle;
  final String status;

  const _AnchorEvidenceItem({
    required this.title,
    required this.subtitle,
    required this.status,
  });
}

List<_AnchorEvidenceItem> _relatedEvidence(
  MemoryBrowserAnchor anchor,
  MemoryBrowserSnapshot snapshot,
  List<MemoryContextLink> links,
  List<MemoryContextLinkSuggestion> suggestions,
) {
  final ids = <String>{};
  for (final link in links) {
    _collectRelatedEvidenceId(ids, link.sourceType, link.sourceId);
    _collectRelatedEvidenceId(ids, link.targetType, link.targetId);
  }
  for (final suggestion in suggestions) {
    _collectRelatedEvidenceId(ids, suggestion.sourceType, suggestion.sourceId);
    _collectRelatedEvidenceId(ids, suggestion.targetType, suggestion.targetId);
  }
  ids.remove('anchor:${anchor.id}');
  return [
    for (final capture in snapshot.captures)
      if (ids.contains('capture:${capture.id}'))
        _AnchorEvidenceItem(
          title: capture.preview,
          subtitle:
              'capture - ${capture.eventType} - ${_timeLabel(capture.updatedAt)}',
          status: capture.status,
        ),
    for (final asset in snapshot.assets)
      if (ids.contains('asset:${asset.id}'))
        _AnchorEvidenceItem(
          title: asset.filename,
          subtitle: 'file - ${asset.contentType} - ${asset.shortSize}',
          status: asset.status,
        ),
    for (final thread in snapshot.threads)
      if (ids.contains('thread:${thread.id}'))
        _AnchorEvidenceItem(
          title: thread.externalRef,
          subtitle: 'thread - ${_timeLabel(thread.updatedAt)}',
          status: thread.status,
        ),
  ];
}

void _collectRelatedEvidenceId(Set<String> ids, String type, String id) {
  if (type == 'capture' || type == 'asset' || type == 'thread') {
    ids.add('$type:$id');
  }
}

bool _linkTouchesAnchor(MemoryContextLink link, String anchorId) {
  return (link.sourceType == 'anchor' && link.sourceId == anchorId) ||
      (link.targetType == 'anchor' && link.targetId == anchorId);
}

bool _suggestionTouchesAnchor(
  MemoryContextLinkSuggestion suggestion,
  String anchorId,
) {
  return (suggestion.sourceType == 'anchor' &&
          suggestion.sourceId == anchorId) ||
      (suggestion.targetType == 'anchor' && suggestion.targetId == anchorId);
}

String _endpointLabel(String type, String id, MemoryBrowserSnapshot snapshot) {
  if (type == 'anchor') {
    for (final item in snapshot.anchors) {
      if (item.id == id) return '${item.kind}: ${item.label}';
    }
    return 'anchor ${shortStorageId(id)}';
  }
  if (type == 'capture') {
    for (final item in snapshot.captures) {
      if (item.id == id) return item.preview;
    }
    return 'capture ${shortStorageId(id)}';
  }
  if (type == 'asset') {
    for (final item in snapshot.assets) {
      if (item.id == id) return item.filename;
    }
    return 'asset ${shortStorageId(id)}';
  }
  if (type == 'thread') {
    for (final item in snapshot.threads) {
      if (item.id == id) return item.externalRef;
    }
    return 'thread ${shortStorageId(id)}';
  }
  return '$type ${shortStorageId(id)}';
}

String? _metadataText(MemoryBrowserAnchor anchor, String key) {
  final value = anchor.metadata[key]?.toString().trim();
  return value == null || value.isEmpty ? null : value;
}

IconData _anchorIcon(String kind) {
  return switch (kind) {
    'person' => Icons.person_outline,
    'event' => Icons.event_outlined,
    'project' => Icons.work_outline,
    _ => Icons.hub_outlined,
  };
}

String _timeLabel(DateTime value) {
  final local = value.toLocal();
  return '${local.year.toString().padLeft(4, '0')}-'
      '${local.month.toString().padLeft(2, '0')}-'
      '${local.day.toString().padLeft(2, '0')} '
      '${local.hour.toString().padLeft(2, '0')}:'
      '${local.minute.toString().padLeft(2, '0')}';
}
