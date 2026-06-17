import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/app/debug/marionette_e2e_extensions.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';
import 'package:frontend/src/features/chat/domain/entities/cost_usage.dart';
import 'package:frontend/src/features/chat/domain/entities/document_chunk.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_browser.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_capture.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_operations_console.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_scope.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';

void main() {
  group('MemoStackMarionetteE2eCommandHandler', () {
    late _FakeChatRepository repo;
    late ChatStore store;
    late MemoStackMarionetteE2eCommandHandler handler;

    setUp(() {
      repo = _FakeChatRepository();
      store = ChatStore(repo, null);
      handler = MemoStackMarionetteE2eCommandHandler(() => store);
    });

    tearDown(() async {
      store.dispose();
      await repo.close();
    });

    test('submits a capture into the requested scope and thread', () async {
      final result = await handler.submitCapture({
        'memoryScopeExternalRef': 'project-atlas',
        'memoryScopeName': 'Project Atlas',
        'threadTitle': 'Alex follow-up',
        'text': 'Alex asked to connect the launch note with Project Atlas.',
      });

      expect(result['activeMemoryScopeExternalRef'], 'project-atlas');
      expect(result['captureCount'], 1);
      expect(result['pendingLinkSuggestionCount'], 1);
      expect(result['operationsPendingLinkSuggestionCount'], 1);
      expect(result['latestCapture'], isA<Map<String, dynamic>>());
      expect(
        (result['latestCapture'] as Map<String, dynamic>)['preview'],
        contains('Alex asked'),
      );
      expect(
        (result['activeThread'] as Map<String, dynamic>)['title'],
        'Alex follow-up',
      );
      expect(repo.lastTask, contains('Project Atlas'));
    });

    test('submits an attachment capture with asset evidence', () async {
      final result = await handler.submitAttachmentCapture({
        'memoryScopeExternalRef': 'project-atlas',
        'memoryScopeName': 'Project Atlas',
        'threadTitle': 'Attachment evidence',
        'filename': 'launch-note.txt',
        'mime': 'text/plain',
        'content': 'Attachment content for Project Atlas launch evidence.',
        'text': 'Attachment note for Project Atlas launch.',
      });

      expect(result['uploadedAssetIds'], ['file-1']);
      expect(result['captureCount'], 1);
      expect(result['assetExtractionCount'], 1);
      expect(repo.lastTask, contains('Attachment note'));
      expect(repo.pendingUploads, isEmpty);

      final latestCapture = result['latestCapture'] as Map<String, dynamic>;
      expect(latestCapture['assetIds'], contains('file-1'));

      final extractions = result['assetExtractions'] as List<dynamic>;
      final extraction = extractions.single as Map<String, dynamic>;
      expect(extraction['assetId'], 'file-1');
      expect(extraction['threadId'], store.activeChatId);
      expect(extraction['status'], 'succeeded');
      expect(extraction['parserName'], 'fake_text_parser');
      expect(extraction['progressPercent'], 100);
      expect(extraction['resultDocumentIds'], ['doc-file-1']);
      expect(extraction['artifactTypes'], contains('markdown'));
    });

    test('reviews the first pending link suggestion', () async {
      await handler.submitCapture({
        'text': 'Alex confirmed the Project Atlas launch timing.',
      });

      final result = await handler.reviewFirstPendingLinkSuggestion({
        'approve': 'false',
      });

      expect(result['reviewed'], true);
      expect(result['reviewAction'], 'reject');
      expect(result['pendingLinkSuggestionCount'], 0);
      expect(repo.reviewedSuggestions, ['ctxlinksug-1:reject']);
      expect(
        repo.reviewedSuggestionReasons['ctxlinksug-1'],
        'rejected by user from review queue',
      );
    });

    test('reviews a pending link suggestion by target filter', () async {
      await handler.submitCapture({
        'text': 'Alex confirmed the Project Atlas launch timing.',
      });
      repo.contextLinkSuggestions = [
        _suggestion(
          'ctxlinksug-other',
          sourceId: 'capture-1',
          targetId: 'anchor-other',
        ),
        _suggestion(
          'ctxlinksug-project',
          sourceId: 'capture-1',
          targetId: 'anchor-project-atlas',
        ),
      ];

      final result = await handler.reviewFirstPendingLinkSuggestion({
        'approve': 'true',
        'targetId': 'anchor-project-atlas',
      });

      expect(result['reviewed'], true);
      expect(result['reviewedSuggestionId'], 'ctxlinksug-project');
      expect(result['reviewedTargetId'], 'anchor-project-atlas');
      expect(repo.reviewedSuggestions, ['ctxlinksug-project:approve']);
      expect(repo.contextLinkSuggestions.single.id, 'ctxlinksug-other');
    });

    test('does not review pending link suggestions outside target filter',
        () async {
      await handler.submitCapture({
        'text': 'Alex confirmed the Project Atlas launch timing.',
      });

      final result = await handler.reviewFirstPendingLinkSuggestion({
        'approve': 'true',
        'targetId': 'anchor-missing',
      });

      expect(result['reviewed'], false);
      expect(repo.reviewedSuggestions, isEmpty);
      expect(repo.contextLinkSuggestions.single.id, 'ctxlinksug-1');
    });

    test('creates a manual context link from a pending suggestion', () async {
      await handler.submitCapture({
        'text': 'Alex confirmed the Project Atlas launch timing.',
      });

      final result = await handler.createManualContextLinkFromSuggestion({
        'suggestionTargetId': 'anchor-project-atlas',
        'targetType': 'anchor',
        'targetId': 'anchor-manual-project',
        'relationType': 'supports',
        'confidence': 'medium',
        'reason': 'manual override',
      });

      expect(result['manualLinked'], true);
      expect(result['manualLinkSuggestionId'], 'ctxlinksug-1');
      expect(result['manualLinkTargetId'], 'anchor-manual-project');
      expect(result['pendingLinkSuggestionCount'], 0);
      expect(result['memoryBrowserContextLinkCount'], 1);
      expect(repo.createdContextLinks, [
        {
          'source_type': 'capture',
          'source_id': 'capture-1',
          'target_type': 'anchor',
          'target_id': 'anchor-manual-project',
          'relation_type': 'supports',
          'confidence': 'medium',
          'reason': 'manual override',
        },
      ]);
      expect(repo.reviewedSuggestions, ['ctxlinksug-1:reject']);
      expect(
        repo.reviewedSuggestionReasons['ctxlinksug-1'],
        'replaced by manual link',
      );
    });

    test('drives memory anchor lifecycle for live e2e checks', () async {
      var result = await handler.createMemoryAnchor({
        'memoryScopeExternalRef': 'project-atlas',
        'memoryScopeName': 'Project Atlas',
        'kind': 'person',
        'label': 'Alex Key',
        'aliases': 'Alex, AK',
        'description': 'Launch stakeholder',
      });

      expect(result['memoryBrowserAnchorCount'], 1);
      expect(result['pendingAnchorMergeSuggestionCount'], 0);
      final created = result['anchor'] as Map<String, dynamic>;
      expect(created['label'], 'Alex Key');
      expect(created['aliases'], ['Alex', 'AK']);

      result = await handler.updateMemoryAnchor({
        'anchorId': created['id'] as String,
        'label': 'Alex Key',
        'aliases': 'Alex, Sasha, AK',
        'description': 'Launch and memory stakeholder',
      });

      final updated = result['anchor'] as Map<String, dynamic>;
      expect(updated['description'], 'Launch and memory stakeholder');
      expect(updated['aliases'], ['Alex', 'Sasha', 'AK']);

      result = await handler.splitMemoryAnchorAlias({
        'anchorId': created['id'] as String,
        'alias': 'AK',
        'newLabel': 'Alex Krasnov',
      });

      expect(result['memoryBrowserAnchorCount'], 2);
      final split = result['splitAnchor'] as Map<String, dynamic>;
      expect(split['label'], 'Alex Krasnov');

      repo.anchorMergeSuggestions = [
        _mergeSuggestion(
          repo.anchors.firstWhere((anchor) => anchor.id == split['id']),
          repo.anchors.firstWhere((anchor) => anchor.id == created['id']),
        ),
      ];

      result = await handler.mergeFirstAnchorSuggestion({});

      expect(result['merged'], true);
      expect(result['memoryBrowserAnchorCount'], 1);
      expect(result['pendingAnchorMergeSuggestionCount'], 0);

      result = await handler.deleteMemoryAnchor({
        'label': 'Alex Key',
        'reason': 'cleanup after e2e',
      });

      expect(result['deletedAnchorLabel'], 'Alex Key');
      expect(result['memoryBrowserAnchorCount'], 0);
    });
  });
}

class _FakeChatRepository implements ChatRepository {
  final _messages = StreamController<ChatMessage>.broadcast(sync: true);
  final _usage = StreamController<CostUsage>.broadcast(sync: true);
  final _running = StreamController<bool>.broadcast(sync: true);
  final _connection = StreamController<ConnectionStatus>.broadcast(sync: true);

  final Map<String, MemoryScope> scopesByRef = {
    'default': _scope('scope-default', 'default', 'Default'),
  };
  final List<MemoryCapture> captures = <MemoryCapture>[];
  final List<MemoryBrowserAnchor> anchors = <MemoryBrowserAnchor>[];
  final List<MemoryContextLink> contextLinks = <MemoryContextLink>[];
  final List<Map<String, String?>> pendingUploads = <Map<String, String?>>[];
  final List<AssetExtractionJob> extractions = <AssetExtractionJob>[];
  List<MemoryContextLinkSuggestion> contextLinkSuggestions = const [];
  List<MemoryAnchorMergeSuggestion> anchorMergeSuggestions = const [];
  final List<String> reviewedSuggestions = <String>[];
  final Map<String, String?> reviewedSuggestionReasons = <String, String?>{};
  final List<Map<String, String>> createdContextLinks = <Map<String, String>>[];
  String activeMemoryScopeExternalRef = 'default';
  String? activeChatId;
  String? lastTask;
  int _captureSeq = 0;
  int _anchorSeq = 0;
  int _contextLinkSeq = 0;
  int _assetSeq = 0;
  int _extractionSeq = 0;

  Future<void> close() async {
    await _messages.close();
    await _usage.close();
    await _running.close();
    await _connection.close();
  }

  @override
  Stream<ChatMessage> messages() => _messages.stream;

  @override
  Stream<CostUsage> usage() => _usage.stream;

  @override
  Stream<bool> running() => _running.stream;

  @override
  Stream<ConnectionStatus> connectionStatus() => _connection.stream;

  @override
  Future<String> createSession({String? provider}) async => 'session-1';

  @override
  Future<String> runTask({required String task}) async {
    lastTask = task;
    _running.add(true);
    _messages.add(
      ChatMessage(
        id: 'msg-user-${_captureSeq + 1}',
        role: 'user',
        ts: DateTime.now(),
        kind: 'text',
        text: task,
      ),
    );
    final captureId = 'capture-${++_captureSeq}';
    final assetIds = pendingUploads
        .map((item) => item['fileId'])
        .whereType<String>()
        .toList(growable: false);
    captures.insert(
      0,
      _capture(
        id: captureId,
        memoryScopeId:
            scopesByRef[activeMemoryScopeExternalRef]?.id ?? 'scope-default',
        threadId: activeChatId,
        preview: task,
        assetIds: assetIds,
      ),
    );
    pendingUploads.clear();
    contextLinkSuggestions = [
      _suggestion('ctxlinksug-1', sourceId: captureId),
    ];
    _messages.add(
      ChatMessage(
        id: 'msg-links-$_captureSeq',
        role: 'assistant',
        ts: DateTime.now(),
        kind: 'link_suggestions',
        text: 'Saved. Select related contexts to link.',
        meta: {
          'sourceType': 'capture',
          'sourceId': captureId,
          'candidates': const <Map<String, dynamic>>[],
        },
      ),
    );
    _running.add(false);
    return 'job-$_captureSeq';
  }

  @override
  Future<bool> respondApproval({
    required String jobId,
    required String approvalId,
    required bool approved,
  }) async {
    return true;
  }

  @override
  Future<void> cancelJob(String jobId) async {}

  @override
  Future<void> cancelCurrentJob() async {}

  @override
  void setActiveChat(String chatId) {
    activeChatId = chatId;
  }

  @override
  void setActiveMemoryScopeExternalRef(String externalRef) {
    activeMemoryScopeExternalRef =
        externalRef.trim().isEmpty ? 'default' : externalRef.trim();
  }

  @override
  String currentMemoryScopeExternalRef() => activeMemoryScopeExternalRef;

  @override
  Future<List<MemoryScope>> listMemoryScopes() async {
    return scopesByRef.values.toList(growable: false);
  }

  @override
  Future<MemoryScope> createMemoryScope({
    required String externalRef,
    required String name,
  }) async {
    final scope = _scope('scope-$externalRef', externalRef, name);
    scopesByRef[externalRef] = scope;
    return scope;
  }

  @override
  Future<MemoryScope> updateMemoryScope({
    required String memoryScopeId,
    String? externalRef,
    String? name,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteMemoryScope(String memoryScopeId) async {}

  @override
  Future<void> createContextLink({
    required String sourceType,
    required String sourceId,
    required String targetType,
    required String targetId,
    required String relationType,
    required String confidence,
    required String reason,
  }) async {
    createdContextLinks.add({
      'source_type': sourceType,
      'source_id': sourceId,
      'target_type': targetType,
      'target_id': targetId,
      'relation_type': relationType,
      'confidence': confidence,
      'reason': reason,
    });
    contextLinks.add(
      _contextLink(
        id: 'ctxlink-${++_contextLinkSeq}',
        memoryScopeId:
            scopesByRef[activeMemoryScopeExternalRef]?.id ?? 'scope-default',
        sourceType: sourceType,
        sourceId: sourceId,
        targetType: targetType,
        targetId: targetId,
        relationType: relationType,
        confidence: confidence,
        reason: reason,
      ),
    );
  }

  @override
  Future<String> uploadFile(
    String name,
    List<int> bytes, {
    String? mime,
    void Function(int sent, int total)? onProgress,
    void Function(void Function())? onCreateCancel,
    String? previewBase64,
    String? batchId,
    int? batchSize,
    int? batchIndex,
  }) async {
    final assetId = 'file-${++_assetSeq}';
    final extractionId = 'extract-${++_extractionSeq}';
    onProgress?.call(bytes.length, bytes.length);
    pendingUploads.add({
      'fileId': assetId,
      'name': name,
      'mime': mime,
      'extractionId': extractionId,
      'extractionStatus': 'succeeded',
    });
    extractions.insert(
      0,
      _extractionJob(
        id: extractionId,
        assetId: assetId,
        memoryScopeId:
            scopesByRef[activeMemoryScopeExternalRef]?.id ?? 'scope-default',
        threadId: activeChatId,
        filename: name,
      ),
    );
    return assetId;
  }

  @override
  Future<List<int>> downloadFile(String id) async => <int>[];

  @override
  Future<List<AssetExtractionJob>> listAssetExtractions({
    String? status,
    int limit = 50,
  }) async {
    final filtered = status == null
        ? extractions
        : extractions.where((job) => job.status == status).toList();
    return filtered.take(limit).toList(growable: false);
  }

  @override
  Future<AssetExtractionJob> getAssetExtraction(String jobId) async {
    return extractions.firstWhere((job) => job.id == jobId);
  }

  @override
  Future<AssetExtractionJob> retryAssetExtraction(String jobId) async {
    throw UnimplementedError();
  }

  @override
  Future<AssetExtractionJob> cancelAssetExtraction(String jobId) async {
    throw UnimplementedError();
  }

  @override
  Future<MemoryOperationsConsole> getOperationsConsole({int limit = 50}) async {
    return MemoryOperationsConsole(
      generatedAt: DateTime.now(),
      scope: {
        'external_ref': activeMemoryScopeExternalRef,
      },
      extractionStatusCounts: const <String, int>{},
      linkSuggestionStatusCounts: {
        'pending':
            contextLinkSuggestions.where((item) => item.isPending).length,
      },
      extractionJobs: extractions.take(limit).toList(growable: false),
      contextLinkSuggestions: contextLinkSuggestions.take(limit).toList(),
      diagnostics: const <String, dynamic>{},
    );
  }

  @override
  Future<MemoryBrowserSnapshot> getMemoryBrowser({int limit = 50}) async {
    return MemoryBrowserSnapshot(
      generatedAt: DateTime.now(),
      memoryScope: scopesByRef[activeMemoryScopeExternalRef],
      threads: const <MemoryBrowserThread>[],
      captures: captures.take(limit).toList(growable: false),
      assets: const <MemoryBrowserAsset>[],
      anchors: anchors.take(limit).toList(growable: false),
      contextLinks: contextLinks.take(limit).toList(growable: false),
      contextLinkSuggestions:
          contextLinkSuggestions.take(limit).toList(growable: false),
      stats: {
        'captures': captures.length,
        'anchors': anchors.length,
      },
      diagnostics: const <String, dynamic>{},
    );
  }

  @override
  Future<MemoryBrowserAnchor> createMemoryAnchor({
    required String kind,
    required String label,
    List<String> aliases = const <String>[],
    String? description,
  }) async {
    final scope =
        scopesByRef[activeMemoryScopeExternalRef] ?? scopesByRef.values.first;
    final anchor = _browserAnchor(
      id: 'anchor-${++_anchorSeq}',
      memoryScopeId: scope.id,
      kind: kind,
      label: label,
      aliases: aliases,
      description: description,
    );
    anchors.add(anchor);
    return anchor;
  }

  @override
  Future<MemoryBrowserAnchor> updateMemoryAnchor({
    required String anchorId,
    required String label,
    List<String> aliases = const <String>[],
    String? description,
  }) async {
    final index = anchors.indexWhere((anchor) => anchor.id == anchorId);
    if (index == -1) {
      throw StateError('Anchor not found: $anchorId');
    }
    final current = anchors[index];
    final updated = _browserAnchor(
      id: current.id,
      memoryScopeId: current.memoryScopeId,
      kind: current.kind,
      label: label,
      aliases: aliases,
      description: description,
      createdAt: current.createdAt,
      updatedAt: DateTime.now(),
    );
    anchors[index] = updated;
    return updated;
  }

  @override
  Future<void> deleteMemoryAnchor({
    required String anchorId,
    String reason = 'manual delete',
  }) async {
    anchors.removeWhere((anchor) => anchor.id == anchorId);
    anchorMergeSuggestions = anchorMergeSuggestions
        .where(
          (suggestion) =>
              suggestion.sourceAnchor.id != anchorId &&
              suggestion.targetAnchor.id != anchorId,
        )
        .toList(growable: false);
  }

  @override
  Future<List<MemoryAnchorMergeSuggestion>> listMemoryAnchorMergeSuggestions({
    int limit = 50,
  }) async {
    return anchorMergeSuggestions.take(limit).toList(growable: false);
  }

  @override
  Future<MemoryBrowserAnchor> mergeMemoryAnchors({
    required String sourceAnchorId,
    required String targetAnchorId,
    required String reason,
  }) async {
    final sourceIndex =
        anchors.indexWhere((anchor) => anchor.id == sourceAnchorId);
    final targetIndex =
        anchors.indexWhere((anchor) => anchor.id == targetAnchorId);
    if (sourceIndex == -1 || targetIndex == -1) {
      throw StateError('Merge anchors not found');
    }
    final source = anchors[sourceIndex];
    final target = anchors[targetIndex];
    final mergedAliases = <String>{
      ...target.aliases,
      source.label,
      ...source.aliases,
    }.where((item) => item != target.label).toList(growable: false);
    final merged = _browserAnchor(
      id: target.id,
      memoryScopeId: target.memoryScopeId,
      kind: target.kind,
      label: target.label,
      aliases: mergedAliases,
      description: target.description,
      createdAt: target.createdAt,
      updatedAt: DateTime.now(),
    );
    anchors[targetIndex] = merged;
    anchors.removeWhere((anchor) => anchor.id == sourceAnchorId);
    anchorMergeSuggestions = anchorMergeSuggestions
        .where(
          (suggestion) =>
              suggestion.sourceAnchor.id != sourceAnchorId &&
              suggestion.targetAnchor.id != sourceAnchorId,
        )
        .toList(growable: false);
    return merged;
  }

  @override
  Future<MemoryBrowserAnchor> splitMemoryAnchor({
    required String anchorId,
    required String alias,
    String? newLabel,
    String reason = 'manual split',
  }) async {
    final index = anchors.indexWhere((anchor) => anchor.id == anchorId);
    if (index == -1) {
      throw StateError('Anchor not found: $anchorId');
    }
    final source = anchors[index];
    final updatedSource = _browserAnchor(
      id: source.id,
      memoryScopeId: source.memoryScopeId,
      kind: source.kind,
      label: source.label,
      aliases: source.aliases.where((item) => item != alias).toList(),
      description: source.description,
      createdAt: source.createdAt,
      updatedAt: DateTime.now(),
    );
    final split = _browserAnchor(
      id: 'anchor-${++_anchorSeq}',
      memoryScopeId: source.memoryScopeId,
      kind: source.kind,
      label: newLabel ?? alias,
      aliases: const <String>[],
      description: null,
    );
    anchors[index] = updatedSource;
    anchors.add(split);
    return split;
  }

  @override
  Future<void> backfillMemoryAnchors({int limitPerSource = 100}) async {}

  @override
  Future<List<int>> downloadExtractionArtifact(String artifactId) async {
    return <int>[];
  }

  @override
  Future<List<DocumentChunk>> listDocumentChunks(String documentId) async {
    return const <DocumentChunk>[];
  }

  @override
  Future<List<MemoryCapture>> listMemoryCaptures({int limit = 50}) async {
    return captures.take(limit).toList(growable: false);
  }

  @override
  Future<List<MemoryContextLink>> listContextLinks({
    required String sourceType,
    required String sourceId,
    int limit = 50,
  }) async {
    return contextLinks
        .where(
          (link) => link.sourceType == sourceType && link.sourceId == sourceId,
        )
        .take(limit)
        .toList(growable: false);
  }

  @override
  Future<List<MemoryContextLinkSuggestion>> listContextLinkSuggestions({
    String status = 'pending',
    int limit = 50,
  }) async {
    return contextLinkSuggestions.take(limit).toList(growable: false);
  }

  @override
  Future<MemoryContextLinkSuggestion> reviewContextLinkSuggestion({
    required String suggestionId,
    required String action,
    String? reason,
  }) async {
    reviewedSuggestions.add('$suggestionId:$action');
    reviewedSuggestionReasons[suggestionId] = reason;
    final suggestion = contextLinkSuggestions.firstWhere(
      (item) => item.id == suggestionId,
    );
    contextLinkSuggestions = contextLinkSuggestions
        .where((item) => item.id != suggestionId)
        .toList(growable: false);
    return MemoryContextLinkSuggestion.fromMap({
      'id': suggestion.id,
      'space_id': suggestion.spaceId,
      'memory_scope_id': suggestion.memoryScopeId,
      'source_type': suggestion.sourceType,
      'source_id': suggestion.sourceId,
      'target_type': suggestion.targetType,
      'target_id': suggestion.targetId,
      'relation_type': suggestion.relationType,
      'confidence': suggestion.confidence,
      'reason': suggestion.reason,
      'score': suggestion.score,
      'status': action == 'approve' ? 'approved' : 'rejected',
      'metadata': suggestion.metadata,
      'created_at': suggestion.createdAt.toIso8601String(),
      'updated_at': DateTime.now().toIso8601String(),
      'reviewed_at': DateTime.now().toIso8601String(),
      'review_reason': reason,
    });
  }
}

MemoryScope _scope(String id, String externalRef, String name) {
  final now = DateTime.now();
  return MemoryScope(
    id: id,
    spaceId: 'space-1',
    externalRef: externalRef,
    name: name,
    status: 'active',
    createdAt: now,
    updatedAt: now,
  );
}

MemoryCapture _capture({
  required String id,
  required String memoryScopeId,
  required String? threadId,
  required String preview,
  List<String> assetIds = const <String>[],
}) {
  final now = DateTime.now();
  return MemoryCapture(
    id: id,
    spaceId: 'space-1',
    memoryScopeId: memoryScopeId,
    threadId: threadId,
    sourceAgent: 'user',
    sourceKind: 'manual',
    eventType: 'Capture',
    actorRole: 'user',
    textPreview: preview,
    status: 'accepted',
    consolidationStatus: 'pending',
    trustLevel: 'medium',
    sourceAuthority: 'user',
    sensitivity: 'medium',
    dataClassification: 'internal',
    evidenceRefs: assetIds.map(_assetRef).toList(growable: false),
    metadata: assetIds.isEmpty
        ? const <String, dynamic>{}
        : <String, dynamic>{'asset_ids': assetIds},
    createdAt: now,
    updatedAt: now,
    occurredAt: now,
    lastErrorCode: null,
  );
}

DocumentSourceRef _assetRef(String assetId) {
  return DocumentSourceRef(
    sourceType: 'asset',
    sourceId: assetId,
    assetId: assetId,
    kind: null,
    pageNumber: null,
    timeStartMs: null,
    timeEndMs: null,
    charStart: null,
    charEnd: null,
    chunkCharStart: null,
    chunkCharEnd: null,
    bbox: const <double>[],
    confidence: null,
    providerSource: null,
    quotePreview: null,
    raw: {
      'source_type': 'asset',
      'source_id': assetId,
      'asset_id': assetId,
    },
  );
}

AssetExtractionJob _extractionJob({
  required String id,
  required String assetId,
  required String memoryScopeId,
  required String? threadId,
  required String filename,
}) {
  final now = DateTime.now().toIso8601String();
  return AssetExtractionJob.fromMap({
    'id': id,
    'asset_id': assetId,
    'space_id': 'space-1',
    'memory_scope_id': memoryScopeId,
    'thread_id': threadId,
    'parser_profile': 'standard_local',
    'parser_config_hash': 'fake-parser-config',
    'source_sha256_hex': 'fake-source-sha',
    'status': 'succeeded',
    'attempt_count': 1,
    'parser_name': 'fake_text_parser',
    'parser_version': '1',
    'model_version': null,
    'result_document_ids': ['doc-$assetId'],
    'artifacts': [
      {
        'id': 'artifact-$assetId-markdown',
        'job_id': id,
        'asset_id': assetId,
        'artifact_type': 'markdown',
        'storage_backend': 'memory',
        'storage_key': 'artifacts/$assetId/extracted.md',
        'sha256_hex': 'fake-artifact-sha',
        'byte_size': 64,
        'metadata': {'filename': '$filename.md'},
        'created_at': now,
      },
    ],
    'metadata': {'filename': filename},
    'progress': {
      'stage': 'succeeded',
      'percent': 100,
      'message': 'Extraction complete',
      'terminal': true,
    },
    'execution': const <String, dynamic>{},
    'usage': const <String, dynamic>{},
    'created_at': now,
    'updated_at': now,
    'started_at': now,
    'finished_at': now,
  });
}

MemoryContextLink _contextLink({
  required String id,
  required String memoryScopeId,
  required String sourceType,
  required String sourceId,
  required String targetType,
  required String targetId,
  required String relationType,
  required String confidence,
  required String reason,
}) {
  final now = DateTime.now().toIso8601String();
  return MemoryContextLink.fromMap({
    'id': id,
    'space_id': 'space-1',
    'memory_scope_id': memoryScopeId,
    'source_type': sourceType,
    'source_id': sourceId,
    'target_type': targetType,
    'target_id': targetId,
    'relation_type': relationType,
    'confidence': confidence,
    'reason': reason,
    'status': 'active',
    'metadata': {'target_label': targetId},
    'created_at': now,
    'updated_at': now,
  });
}

MemoryContextLinkSuggestion _suggestion(
  String id, {
  required String sourceId,
  String targetId = 'anchor-project-atlas',
}) {
  final now = DateTime.now();
  return MemoryContextLinkSuggestion(
    id: id,
    spaceId: 'space-1',
    memoryScopeId: 'scope-default',
    sourceType: 'capture',
    sourceId: sourceId,
    targetType: 'anchor',
    targetId: targetId,
    relationType: 'related_to',
    confidence: 'high',
    reason: 'matched Project Atlas and Alex',
    score: 91,
    status: 'pending',
    metadata: const {
      'anchor_kind': 'project',
      'target_label': 'Project Atlas',
      'target_preview': 'Project Atlas launch context',
    },
    createdAt: now,
    updatedAt: now,
  );
}

MemoryBrowserAnchor _browserAnchor({
  required String id,
  required String memoryScopeId,
  required String kind,
  required String label,
  List<String> aliases = const <String>[],
  String? description,
  DateTime? createdAt,
  DateTime? updatedAt,
}) {
  final now = DateTime.now();
  return MemoryBrowserAnchor(
    id: id,
    spaceId: 'space-1',
    memoryScopeId: memoryScopeId,
    kind: kind,
    normalizedKey: label.trim().toLowerCase(),
    label: label,
    aliases: aliases,
    description: description,
    status: 'active',
    metadata: const <String, dynamic>{},
    createdAt: createdAt ?? now,
    updatedAt: updatedAt ?? now,
  );
}

MemoryAnchorMergeSuggestion _mergeSuggestion(
  MemoryBrowserAnchor source,
  MemoryBrowserAnchor target,
) {
  return MemoryAnchorMergeSuggestion(
    sourceAnchor: source,
    targetAnchor: target,
    confidence: 'high',
    score: 0.92,
    reasons: const <String>[
      'same person alias',
      'recently split from the same source',
    ],
    metadata: const <String, dynamic>{},
  );
}
