import 'package:flutter/material.dart';
import 'package:flutter_mobx/flutter_mobx.dart';
import 'package:provider/provider.dart';

import 'package:frontend/src/features/chat/application/services/open_extraction_artifact.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/entities/document_chunk.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_capture.dart';
import 'package:frontend/src/features/chat/presentation/widgets/sidebar_formatters.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';

typedef OpenMemoryCapture = void Function(
  BuildContext context,
  MemoryCapture capture,
);

void showMemoryEvidenceViewer(
  BuildContext context,
  ChatStore store, {
  required OpenMemoryCapture onOpenCapture,
}) {
  showDialog<void>(
    context: context,
    builder: (_) => _MemoryEvidenceViewerDialog(
      store: store,
      onOpenCapture: onOpenCapture,
    ),
  );
}

enum _EvidenceViewerFilter { all, captures, files, running, issues }

enum _EvidenceViewerRange { scope, thread }

class _MemoryEvidenceViewerDialog extends StatefulWidget {
  final ChatStore store;
  final OpenMemoryCapture onOpenCapture;

  const _MemoryEvidenceViewerDialog({
    required this.store,
    required this.onOpenCapture,
  });

  @override
  State<_MemoryEvidenceViewerDialog> createState() =>
      _MemoryEvidenceViewerDialogState();
}

class _MemoryEvidenceViewerDialogState
    extends State<_MemoryEvidenceViewerDialog> {
  _EvidenceViewerFilter _filter = _EvidenceViewerFilter.all;
  _EvidenceViewerRange _range = _EvidenceViewerRange.scope;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Dialog(
      key: const ValueKey('memory_evidence_viewer_dialog'),
      insetPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 20),
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 980, maxHeight: 760),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(18, 16, 18, 14),
          child: Observer(
            builder: (_) {
              final rangeCaptures = _rangeCaptures(widget.store.memoryCaptures);
              final rangeJobs = _rangeJobs(widget.store.assetExtractions);
              final captures = _filterCaptures(rangeCaptures);
              final jobs = _filterJobs(rangeJobs);
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(
                        Icons.manage_search_outlined,
                        size: 21,
                        color: scheme.primary,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              'Memory evidence',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.w700),
                            ),
                            Text(
                              '${widget.store.activeMemoryScopeExternalRef} - ${widget.store.activeChatId}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: Theme.of(context)
                                  .textTheme
                                  .labelSmall
                                  ?.copyWith(color: scheme.onSurfaceVariant),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        key: const ValueKey('memory_evidence_refresh_button'),
                        tooltip: 'Refresh evidence',
                        onPressed: () {
                          widget.store.refreshMemoryCaptures();
                          widget.store.refreshAssetExtractions();
                        },
                        icon: const Icon(Icons.refresh, size: 20),
                      ),
                      IconButton(
                        tooltip: 'Close',
                        onPressed: () => Navigator.of(context).pop(),
                        icon: const Icon(Icons.close, size: 20),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 6,
                    children: [
                      for (final range in _EvidenceViewerRange.values)
                        ChoiceChip(
                          key: ValueKey('memory_evidence_range_${range.name}'),
                          selected: _range == range,
                          label: Text(_rangeLabel(range)),
                          avatar: Icon(_rangeIcon(range), size: 16),
                          onSelected: (_) => setState(() => _range = range),
                        ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Wrap(
                      spacing: 8,
                      children: [
                        for (final filter in _EvidenceViewerFilter.values)
                          ChoiceChip(
                            key: ValueKey(
                                'memory_evidence_filter_${filter.name}'),
                            selected: _filter == filter,
                            label: Text(_filterLabel(filter)),
                            avatar: Icon(_filterIcon(filter), size: 16),
                            onSelected: (_) => setState(() => _filter = filter),
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 10),
                  _EvidenceCountsBar(
                    captures: rangeCaptures.length,
                    files: rangeJobs.length,
                    visible: captures.length + jobs.length,
                  ),
                  const SizedBox(height: 10),
                  Expanded(
                    child: LayoutBuilder(
                      builder: (context, constraints) {
                        final twoColumn = constraints.maxWidth >= 760 &&
                            _filter == _EvidenceViewerFilter.all;
                        if (captures.isEmpty && jobs.isEmpty) {
                          return const _EvidenceViewerEmpty();
                        }
                        if (twoColumn) {
                          return Row(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Expanded(
                                child: _EvidenceCaptureList(
                                  captures: captures,
                                  onOpenCapture: widget.onOpenCapture,
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(child: _EvidenceFileList(jobs: jobs)),
                            ],
                          );
                        }
                        return ListView(
                          children: [
                            if (captures.isNotEmpty)
                              _EvidenceCaptureList(
                                captures: captures,
                                onOpenCapture: widget.onOpenCapture,
                              ),
                            if (captures.isNotEmpty && jobs.isNotEmpty)
                              const SizedBox(height: 12),
                            if (jobs.isNotEmpty) _EvidenceFileList(jobs: jobs),
                          ],
                        );
                      },
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  List<MemoryCapture> _rangeCaptures(Iterable<MemoryCapture> captures) {
    return captures.where((capture) {
      return switch (_range) {
        _EvidenceViewerRange.scope => true,
        _EvidenceViewerRange.thread => _belongsToActiveThread(capture.threadId),
      };
    }).toList(growable: false);
  }

  List<AssetExtractionJob> _rangeJobs(Iterable<AssetExtractionJob> jobs) {
    return jobs.where((job) {
      return switch (_range) {
        _EvidenceViewerRange.scope => true,
        _EvidenceViewerRange.thread => _belongsToActiveThread(job.threadId),
      };
    }).toList(growable: false);
  }

  bool _belongsToActiveThread(String? threadId) {
    final normalized = threadId?.trim();
    return normalized == null ||
        normalized.isEmpty ||
        normalized == widget.store.activeChatId;
  }

  List<MemoryCapture> _filterCaptures(Iterable<MemoryCapture> captures) {
    return captures.where((capture) {
      return switch (_filter) {
        _EvidenceViewerFilter.all => true,
        _EvidenceViewerFilter.captures => true,
        _EvidenceViewerFilter.files => false,
        _EvidenceViewerFilter.running =>
          capture.consolidationStatus == 'running',
        _EvidenceViewerFilter.issues => capture.lastErrorCode != null ||
            capture.consolidationStatus == 'dead',
      };
    }).toList(growable: false);
  }

  List<AssetExtractionJob> _filterJobs(Iterable<AssetExtractionJob> jobs) {
    return jobs.where((job) {
      return switch (_filter) {
        _EvidenceViewerFilter.all => true,
        _EvidenceViewerFilter.captures => false,
        _EvidenceViewerFilter.files => true,
        _EvidenceViewerFilter.running => job.isRunning,
        _EvidenceViewerFilter.issues => job.isFailed,
      };
    }).toList(growable: false);
  }
}

class _EvidenceCountsBar extends StatelessWidget {
  final int captures;
  final int files;
  final int visible;

  const _EvidenceCountsBar({
    required this.captures,
    required this.files,
    required this.visible,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Wrap(
      spacing: 8,
      runSpacing: 6,
      children: [
        _CountPill(label: 'Visible', value: visible, color: scheme.primary),
        _CountPill(
          label: 'Captures',
          value: captures,
          color: Colors.green.shade700,
        ),
        _CountPill(label: 'Files', value: files, color: Colors.blue.shade700),
      ],
    );
  }
}

class _CountPill extends StatelessWidget {
  final String label;
  final int value;
  final Color color;

  const _CountPill({
    required this.label,
    required this.value,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.35)),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Text(
        '$label $value',
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

class _EvidenceCaptureList extends StatelessWidget {
  final List<MemoryCapture> captures;
  final OpenMemoryCapture onOpenCapture;

  const _EvidenceCaptureList({
    required this.captures,
    required this.onOpenCapture,
  });

  @override
  Widget build(BuildContext context) {
    return _ViewerSection(
      title: 'Saved captures',
      child: Column(
        children: [
          for (final capture in captures)
            _EvidenceCaptureTile(
              key: ValueKey(
                  'memory_evidence_capture_${sidebarKeyPart(capture.id)}'),
              capture: capture,
              onOpenCapture: onOpenCapture,
            ),
        ],
      ),
    );
  }
}

class _EvidenceFileList extends StatelessWidget {
  final List<AssetExtractionJob> jobs;

  const _EvidenceFileList({required this.jobs});

  @override
  Widget build(BuildContext context) {
    return _ViewerSection(
      title: 'File evidence',
      child: Column(
        children: [
          for (final job in jobs)
            _EvidenceExtractionTile(
              key: ValueKey(
                  'memory_evidence_extraction_${sidebarKeyPart(job.id)}'),
              job: job,
            ),
        ],
      ),
    );
  }
}

class _ViewerSection extends StatelessWidget {
  final String title;
  final Widget child;

  const _ViewerSection({required this.title, required this.child});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: Theme.of(context)
              .textTheme
              .labelMedium
              ?.copyWith(fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 6),
        child,
      ],
    );
  }
}

class _EvidenceCaptureTile extends StatelessWidget {
  final MemoryCapture capture;
  final OpenMemoryCapture onOpenCapture;

  const _EvidenceCaptureTile({
    super.key,
    required this.capture,
    required this.onOpenCapture,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return _ViewerTile(
      leading: Icons.history_edu_outlined,
      title: capture.preview.isEmpty
          ? shortStorageId(capture.id)
          : capture.preview,
      subtitle:
          '${capture.consolidationStatus.replaceAll('_', ' ')} - ${capture.dataClassification}',
      status: capture.status,
      statusColor: _captureStatusColor(capture, scheme),
      trailing: IconButton(
        tooltip: 'Open capture',
        onPressed: () => onOpenCapture(context, capture),
        icon: const Icon(Icons.open_in_new, size: 18),
      ),
      body: capture.evidenceRefs.isEmpty
          ? null
          : Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final ref in capture.evidenceRefs.take(8))
                  _ViewerSourceRefChip(ref: ref),
              ],
            ),
    );
  }
}

class _EvidenceExtractionTile extends StatelessWidget {
  final AssetExtractionJob job;

  const _EvidenceExtractionTile({super.key, required this.job});

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return _ViewerTile(
      leading: Icons.auto_awesome_motion_outlined,
      title: _extractionTitle(job),
      subtitle:
          '${job.status.replaceAll('_', ' ')} - ${job.parserName ?? job.parserProfile}',
      status: job.progress.message,
      statusColor: _extractionStatusColor(job, scheme),
      trailing: job.canRetry
          ? IconButton(
              key: ValueKey('memory_evidence_retry_${sidebarKeyPart(job.id)}'),
              tooltip: 'Retry extraction',
              onPressed: () =>
                  context.read<ChatStore?>()?.retryAssetExtraction(job),
              icon: const Icon(Icons.refresh, size: 18),
            )
          : null,
      body: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (job.progress.percent > 0 && !job.progress.terminal) ...[
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(value: job.progress.percent / 100),
            ),
            const SizedBox(height: 8),
          ],
          if (job.artifacts.isNotEmpty)
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final artifact in job.artifacts.take(8))
                  _ViewerArtifactChip(artifact: artifact),
              ],
            ),
          if (job.hasDocuments) ...[
            const SizedBox(height: 8),
            _ExtractionSourceRefsPreview(job: job),
          ],
          if (job.safeErrorMessage != null) ...[
            const SizedBox(height: 8),
            Text(
              job.safeErrorMessage!,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: scheme.error),
            ),
          ],
        ],
      ),
    );
  }
}

class _ExtractionSourceRefsPreview extends StatelessWidget {
  final AssetExtractionJob job;

  const _ExtractionSourceRefsPreview({required this.job});

  @override
  Widget build(BuildContext context) {
    final store = context.read<ChatStore?>();
    if (store == null) return const SizedBox.shrink();
    return FutureBuilder<List<DocumentChunk>>(
      future: store.loadAssetExtractionEvidence(job),
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const SizedBox(
            height: 18,
            width: 18,
            child: CircularProgressIndicator(strokeWidth: 2),
          );
        }
        final refs = [
          for (final chunk in snapshot.data ?? const <DocumentChunk>[])
            ...chunk.sourceRefs,
        ];
        if (refs.isEmpty) return const SizedBox.shrink();
        return Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            for (final ref in refs.take(8)) _ViewerSourceRefChip(ref: ref),
          ],
        );
      },
    );
  }
}

class _ViewerArtifactChip extends StatelessWidget {
  final ExtractionArtifact artifact;

  const _ViewerArtifactChip({required this.artifact});

  @override
  Widget build(BuildContext context) {
    return ActionChip(
      key: ValueKey('memory_evidence_artifact_${sidebarKeyPart(artifact.id)}'),
      visualDensity: VisualDensity.compact,
      avatar: const Icon(Icons.description_outlined, size: 16),
      label: Text(
        artifact.artifactType.replaceAll('_', ' '),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
      tooltip: artifact.filename,
      onPressed: () => _openEvidenceArtifact(context, artifact),
    );
  }
}

class _ViewerTile extends StatelessWidget {
  final IconData leading;
  final String title;
  final String subtitle;
  final String status;
  final Color statusColor;
  final Widget? trailing;
  final Widget? body;

  const _ViewerTile({
    required this.leading,
    required this.title,
    required this.subtitle,
    required this.status,
    required this.statusColor,
    this.trailing,
    this.body,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: DecoratedBox(
        decoration: BoxDecoration(
          border: Border.all(color: context.themeColors.surfaceBorder),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(10, 9, 8, 9),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(leading, size: 18, color: scheme.onSurfaceVariant),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context)
                              .textTheme
                              .bodyMedium
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        Text(
                          subtitle,
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
                  const SizedBox(width: 8),
                  _StatusPill(text: status, color: statusColor),
                  if (trailing != null) trailing!,
                ],
              ),
              if (body != null) ...[
                const SizedBox(height: 8),
                body!,
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _StatusPill extends StatelessWidget {
  final String text;
  final Color color;

  const _StatusPill({required this.text, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(maxWidth: 150),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        border: Border.all(color: color.withValues(alpha: 0.45)),
        borderRadius: BorderRadius.circular(7),
      ),
      child: Text(
        text.replaceAll('_', ' '),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w800,
            ),
      ),
    );
  }
}

class _ViewerSourceRefChip extends StatelessWidget {
  final DocumentSourceRef ref;

  const _ViewerSourceRefChip({required this.ref});

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
    if (ref.hasBBox) return 'BBox';
    return ref.kind ?? ref.sourceType;
  }
}

class _EvidenceViewerEmpty extends StatelessWidget {
  const _EvidenceViewerEmpty();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Text(
        'No evidence for this filter',
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
      ),
    );
  }
}

String _rangeLabel(_EvidenceViewerRange range) {
  return switch (range) {
    _EvidenceViewerRange.scope => 'Scope',
    _EvidenceViewerRange.thread => 'This thread',
  };
}

IconData _rangeIcon(_EvidenceViewerRange range) {
  return switch (range) {
    _EvidenceViewerRange.scope => Icons.account_tree_outlined,
    _EvidenceViewerRange.thread => Icons.forum_outlined,
  };
}

String _filterLabel(_EvidenceViewerFilter filter) {
  return switch (filter) {
    _EvidenceViewerFilter.all => 'All',
    _EvidenceViewerFilter.captures => 'Captures',
    _EvidenceViewerFilter.files => 'Files',
    _EvidenceViewerFilter.running => 'Running',
    _EvidenceViewerFilter.issues => 'Issues',
  };
}

IconData _filterIcon(_EvidenceViewerFilter filter) {
  return switch (filter) {
    _EvidenceViewerFilter.all => Icons.all_inbox_outlined,
    _EvidenceViewerFilter.captures => Icons.history_edu_outlined,
    _EvidenceViewerFilter.files => Icons.attach_file,
    _EvidenceViewerFilter.running => Icons.sync,
    _EvidenceViewerFilter.issues => Icons.error_outline,
  };
}

Color _captureStatusColor(MemoryCapture capture, ColorScheme scheme) {
  return switch (capture.consolidationStatus) {
    'consolidated' => Colors.green.shade700,
    'dead' => scheme.error,
    'running' => scheme.primary,
    'retry_pending' => Colors.orange.shade700,
    _ => scheme.onSurfaceVariant,
  };
}

Color _extractionStatusColor(AssetExtractionJob job, ColorScheme scheme) {
  if (job.isSucceeded) return Colors.green.shade700;
  if (job.isFailed) return scheme.error;
  if (job.isRunning) return scheme.primary;
  return scheme.onSurfaceVariant;
}

String _extractionTitle(AssetExtractionJob job) {
  final filename = job.metadata['filename'];
  if (filename is String && filename.trim().isNotEmpty) return filename.trim();
  return shortStorageId(job.assetId);
}

Future<void> _openEvidenceArtifact(
  BuildContext context,
  ExtractionArtifact artifact,
) async {
  final openArtifact = context.read<OpenExtractionArtifact?>();
  if (openArtifact == null) return;
  try {
    await openArtifact(artifact);
  } catch (e) {
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Open extraction artifact failed: $e')),
    );
  }
}
