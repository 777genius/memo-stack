import 'package:flutter/material.dart';

import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';

enum ContextLinkEndpoint { source, target }

void showContextLinkEndpointDialog(
  BuildContext context,
  MemoryContextLinkSuggestion suggestion, {
  required ContextLinkEndpoint endpoint,
}) {
  showDialog<void>(
    context: context,
    requestFocus: true,
    traversalEdgeBehavior: TraversalEdgeBehavior.closedLoop,
    builder: (_) => _ContextLinkEndpointDialog(
      suggestion: suggestion,
      endpoint: endpoint,
    ),
  );
}

class _ContextLinkEndpointDialog extends StatelessWidget {
  final MemoryContextLinkSuggestion suggestion;
  final ContextLinkEndpoint endpoint;

  const _ContextLinkEndpointDialog({
    required this.suggestion,
    required this.endpoint,
  });

  @override
  Widget build(BuildContext context) {
    final metadata = _boundedMetadataRows(suggestion.metadata);
    return AlertDialog(
      key: const ValueKey('context_link_endpoint_dialog'),
      title: Row(
        children: [
          Icon(_icon, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(_title)),
        ],
      ),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 560, maxHeight: 560),
        child: SingleChildScrollView(
          key: ValueKey('context_link_endpoint_${endpoint.name}_details'),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              _EndpointRow(label: 'Label', value: _label),
              _EndpointRow(label: 'Type', value: _type),
              _EndpointRow(label: 'Id', value: _id),
              _EndpointRow(label: 'Relation', value: suggestion.relationType),
              _EndpointRow(label: 'Confidence', value: suggestion.confidence),
              _EndpointRow(
                label: 'Score',
                value: suggestion.score.toStringAsFixed(0),
              ),
              _EndpointRow(label: 'Status', value: suggestion.status),
              _EndpointRow(label: 'Reason', value: suggestion.reason),
              _EndpointRow(label: 'Preview', value: _preview),
              if (suggestion.reviewReason != null)
                _EndpointRow(label: 'Review', value: suggestion.reviewReason!),
              if (metadata.isNotEmpty) ...[
                const SizedBox(height: 8),
                Text(
                  'Metadata',
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6,
                  runSpacing: 6,
                  children: [
                    for (final row in metadata)
                      Chip(
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                        visualDensity: VisualDensity.compact,
                        label: Text(row),
                      ),
                  ],
                ),
              ],
            ],
          ),
        ),
      ),
      actions: [
        TextButton(
          key: const ValueKey('context_link_endpoint_close_button'),
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }

  String get _title => endpoint == ContextLinkEndpoint.source
      ? 'Source evidence'
      : 'Target memory';

  IconData get _icon => endpoint == ContextLinkEndpoint.source
      ? Icons.input_outlined
      : Icons.output_outlined;

  String get _type => endpoint == ContextLinkEndpoint.source
      ? suggestion.sourceType
      : suggestion.targetTypeLabel;

  String get _id => endpoint == ContextLinkEndpoint.source
      ? suggestion.sourceId
      : suggestion.targetId;

  String get _label {
    if (endpoint == ContextLinkEndpoint.target) return suggestion.targetLabel;
    final label = suggestion.metadata['source_label']?.toString().trim();
    if (label != null && label.isNotEmpty) return label;
    return '${suggestion.sourceType} ${suggestion.sourceId}';
  }

  String get _preview {
    if (endpoint == ContextLinkEndpoint.target) return suggestion.targetPreview;
    for (final key in const [
      'source_preview',
      'source_excerpt',
      'source_text',
    ]) {
      final value = suggestion.metadata[key]?.toString().trim();
      if (value != null && value.isNotEmpty) return _cap(value, 400);
    }
    return suggestion.reason;
  }
}

class _EndpointRow extends StatelessWidget {
  final String label;
  final String value;

  const _EndpointRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 7),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
          ),
          Text(
            value,
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }
}

List<String> _boundedMetadataRows(Map<String, dynamic> metadata) {
  final rows = metadata.entries
      .where((entry) => entry.value != null)
      .map((entry) => MapEntry(entry.key.trim(), entry.value))
      .where((entry) => entry.key.isNotEmpty)
      .toList(growable: false)
    ..sort((a, b) => a.key.compareTo(b.key));
  return rows
      .take(8)
      .map((entry) => '${entry.key}: ${_compactValue(entry.value)}')
      .toList(growable: false);
}

String _compactValue(Object? value) {
  if (value is List) {
    return _cap(
      value.map((item) => item?.toString() ?? '').take(6).join(', '),
      120,
    );
  }
  if (value is Map) {
    return _cap(
      value.entries
          .map((entry) => '${entry.key}: ${entry.value}')
          .take(4)
          .join(', '),
      120,
    );
  }
  return _cap(value?.toString() ?? '', 120);
}

String _cap(String value, int limit) {
  if (value.length <= limit) return value;
  return '${value.substring(0, limit - 3)}...';
}
