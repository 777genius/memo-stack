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
  List<MemoryContextLinkSuggestion> contextLinkSuggestions = const [];
  final List<String> reviewedSuggestions = <String>[];
  final Map<String, String?> reviewedSuggestionReasons = <String, String?>{};
  String activeMemoryScopeExternalRef = 'default';
  String? activeChatId;
  String? lastTask;
  int _captureSeq = 0;

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
    captures.insert(
      0,
      _capture(
        id: captureId,
        memoryScopeId:
            scopesByRef[activeMemoryScopeExternalRef]?.id ?? 'scope-default',
        threadId: activeChatId,
        preview: task,
      ),
    );
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
  }) async {}

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
    return 'file-1';
  }

  @override
  Future<List<int>> downloadFile(String id) async => <int>[];

  @override
  Future<List<AssetExtractionJob>> listAssetExtractions({
    String? status,
    int limit = 50,
  }) async {
    return const <AssetExtractionJob>[];
  }

  @override
  Future<AssetExtractionJob> getAssetExtraction(String jobId) async {
    throw UnimplementedError();
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
      extractionJobs: const <AssetExtractionJob>[],
      contextLinkSuggestions: contextLinkSuggestions.take(limit).toList(),
      diagnostics: const <String, dynamic>{},
    );
  }

  @override
  Future<MemoryBrowserSnapshot> getMemoryBrowser({int limit = 50}) async {
    return MemoryBrowserSnapshot.empty();
  }

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
    return const <MemoryContextLink>[];
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
    evidenceRefs: const <DocumentSourceRef>[],
    metadata: const <String, dynamic>{},
    createdAt: now,
    updatedAt: now,
    occurredAt: now,
    lastErrorCode: null,
  );
}

MemoryContextLinkSuggestion _suggestion(String id, {required String sourceId}) {
  final now = DateTime.now();
  return MemoryContextLinkSuggestion(
    id: id,
    spaceId: 'space-1',
    memoryScopeId: 'scope-default',
    sourceType: 'capture',
    sourceId: sourceId,
    targetType: 'anchor',
    targetId: 'anchor-project-atlas',
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
