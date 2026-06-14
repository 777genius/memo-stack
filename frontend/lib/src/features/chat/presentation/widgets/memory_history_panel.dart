import 'package:flutter/material.dart';
import 'package:flutter_mobx/flutter_mobx.dart';
import 'package:provider/provider.dart';

import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/document_chunk.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_capture.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';
import 'package:frontend/src/features/chat/presentation/widgets/memory_evidence_viewer_dialog.dart';
import 'package:frontend/src/features/chat/presentation/widgets/sidebar_formatters.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';

class MemoryHistoryPanel extends StatelessWidget {
  const MemoryHistoryPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final store = context.read<ChatStore?>();
    if (store == null) return const SizedBox.shrink();
    return Observer(
      builder: (_) {
        final captures = store.memoryCaptures.take(5).toList(growable: false);
        return Container(
          key: const ValueKey('memory_history_panel'),
          margin: const EdgeInsets.fromLTRB(14, 0, 12, 8),
          padding: const EdgeInsets.fromLTRB(10, 8, 8, 8),
          decoration: BoxDecoration(
            border: Border.all(color: context.themeColors.surfaceBorder),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.history_edu_outlined,
                    size: 16,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      'Saved memory',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            fontWeight: FontWeight.w700,
                            color: Theme.of(context).colorScheme.onSurface,
                          ),
                    ),
                  ),
                  if (store.memoryCapturesLoading)
                    const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  else ...[
                    IconButton(
                      key: const ValueKey('memory_evidence_viewer_button'),
                      tooltip: 'Open memory evidence',
                      visualDensity: VisualDensity.compact,
                      onPressed: () => showMemoryEvidenceViewer(
                        context,
                        store,
                        onOpenCapture: _showCaptureDialog,
                      ),
                      icon: Icon(
                        Icons.manage_search_outlined,
                        size: 18,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    IconButton(
                      key: const ValueKey('memory_history_refresh_button'),
                      tooltip: 'Refresh saved memory',
                      visualDensity: VisualDensity.compact,
                      onPressed: store.refreshMemoryCaptures,
                      icon: Icon(
                        Icons.refresh,
                        size: 18,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ],
              ),
              if (store.memoryCaptureError != null)
                Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Text(
                    store.memoryCaptureError!,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.error,
                        ),
                  ),
                )
              else if (captures.isEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 4, bottom: 2),
                  child: Text(
                    'No saved captures yet',
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                )
              else
                for (final capture in captures)
                  _MemoryCaptureRow(capture: capture),
            ],
          ),
        );
      },
    );
  }
}

class _MemoryCaptureRow extends StatelessWidget {
  final MemoryCapture capture;

  const _MemoryCaptureRow({required this.capture});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: _statusColor(capture.consolidationStatus, scheme),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  capture.preview.isEmpty
                      ? shortStorageId(capture.id)
                      : capture.preview,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall?.copyWith(
                        fontWeight: FontWeight.w600,
                        color: scheme.onSurface,
                      ),
                ),
                Text(
                  _captureSubtitle(capture),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                ),
              ],
            ),
          ),
          IconButton(
            key: ValueKey('memory_capture_open_${sidebarKeyPart(capture.id)}'),
            tooltip: 'View saved memory',
            visualDensity: VisualDensity.compact,
            onPressed: () => _showCaptureDialog(context, capture),
            icon: Icon(
              Icons.open_in_new,
              size: 17,
              color: scheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }

  Color _statusColor(String status, ColorScheme scheme) {
    return switch (status) {
      'consolidated' => Colors.green.shade600,
      'dead' => scheme.error,
      'running' => scheme.primary,
      'retry_pending' => Colors.orange.shade700,
      _ => scheme.onSurfaceVariant,
    };
  }

  String _captureSubtitle(MemoryCapture capture) {
    final parts = <String>[
      capture.consolidationStatus.replaceAll('_', ' '),
      capture.dataClassification,
    ];
    if (capture.assetIds.isNotEmpty) {
      parts.add('${capture.assetIds.length} files');
    }
    if (capture.evidenceRefs.isNotEmpty) {
      parts.add('${capture.evidenceRefs.length} refs');
    }
    return parts.join(' - ');
  }
}

void _showCaptureDialog(BuildContext context, MemoryCapture capture) {
  final store = context.read<ChatStore?>();
  if (store == null) return;
  final linksFuture = store.loadCaptureContextLinks(capture);
  showDialog<void>(
    context: context,
    builder: (_) => _MemoryCaptureDialog(
      capture: capture,
      linksFuture: linksFuture,
    ),
  );
}

class _MemoryCaptureDialog extends StatelessWidget {
  final MemoryCapture capture;
  final Future<List<MemoryContextLink>> linksFuture;

  const _MemoryCaptureDialog({
    required this.capture,
    required this.linksFuture,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Dialog(
      key: const ValueKey('memory_capture_detail_dialog'),
      insetPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 760, maxHeight: 680),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(
                    Icons.history_edu_outlined,
                    size: 20,
                    color: scheme.primary,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Saved memory',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                  IconButton(
                    tooltip: 'Close',
                    onPressed: () => Navigator.of(context).pop(),
                    icon: const Icon(Icons.close, size: 20),
                  ),
                ],
              ),
              Text(
                '${capture.consolidationStatus.replaceAll('_', ' ')} - ${capture.eventType}',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
              ),
              const SizedBox(height: 12),
              Expanded(
                child: ListView(
                  children: [
                    _DetailSection(
                      title: 'Capture',
                      child: Text(
                        capture.preview,
                        style: Theme.of(context).textTheme.bodyMedium,
                      ),
                    ),
                    const SizedBox(height: 10),
                    _DetailSection(
                      title: 'Evidence',
                      child: capture.evidenceRefs.isEmpty
                          ? const Text('No evidence refs')
                          : Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: [
                                for (final ref in capture.evidenceRefs.take(12))
                                  _SourceRefChip(ref: ref),
                              ],
                            ),
                    ),
                    const SizedBox(height: 10),
                    _DetailSection(
                      title: 'Linked context',
                      child: FutureBuilder<List<MemoryContextLink>>(
                        future: linksFuture,
                        builder: (context, snapshot) {
                          if (snapshot.connectionState !=
                              ConnectionState.done) {
                            return const SizedBox(
                              height: 28,
                              child: Align(
                                alignment: Alignment.centerLeft,
                                child: SizedBox(
                                  width: 18,
                                  height: 18,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                ),
                              ),
                            );
                          }
                          if (snapshot.hasError) {
                            return Text(
                              'Links unavailable: ${snapshot.error}',
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall
                                  ?.copyWith(
                                    color: scheme.error,
                                  ),
                            );
                          }
                          final links =
                              snapshot.data ?? const <MemoryContextLink>[];
                          if (links.isEmpty) {
                            return const Text('No linked context yet');
                          }
                          return Column(
                            children: [
                              for (final link in links.take(12))
                                _ContextLinkRow(link: link),
                            ],
                          );
                        },
                      ),
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

class _DetailSection extends StatelessWidget {
  final String title;
  final Widget child;

  const _DetailSection({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        border: Border.all(color: context.themeColors.surfaceBorder),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  fontWeight: FontWeight.w700,
                ),
          ),
          const SizedBox(height: 6),
          child,
        ],
      ),
    );
  }
}

class _SourceRefChip extends StatelessWidget {
  final DocumentSourceRef ref;

  const _SourceRefChip({required this.ref});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest.withValues(alpha: 0.55),
        borderRadius: BorderRadius.circular(7),
        border: Border.all(color: context.themeColors.surfaceBorder),
      ),
      child: Text(
        _label(ref),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: scheme.onSurfaceVariant,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }

  String _label(DocumentSourceRef ref) {
    if (ref.sourceType == 'asset') {
      return 'File ${shortStorageId(ref.sourceId)}';
    }
    if (ref.hasPage) return 'Page ${ref.pageNumber}';
    if (ref.hasTime) return 'Time ref';
    return ref.kind ?? ref.sourceType;
  }
}

class _ContextLinkRow extends StatelessWidget {
  final MemoryContextLink link;

  const _ContextLinkRow({required this.link});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Row(
        children: [
          Icon(Icons.link, size: 14, color: scheme.onSurfaceVariant),
          const SizedBox(width: 6),
          Expanded(
            child: Text(
              '${link.targetLabel} - ${link.reason}',
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ),
          const SizedBox(width: 6),
          Text(
            link.confidence,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: scheme.onSurfaceVariant,
                  fontWeight: FontWeight.w700,
                ),
          ),
        ],
      ),
    );
  }
}
