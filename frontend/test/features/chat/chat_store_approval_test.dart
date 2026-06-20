import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';
import 'package:frontend/src/features/chat/domain/entities/cost_usage.dart';
import 'package:frontend/src/features/chat/domain/entities/document_chunk.dart';
import 'package:frontend/src/features/chat/domain/entities/extraction_capabilities.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_browser.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_capture.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_operations_console.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_scope.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_suggestion.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/domain/repositories/extraction_capability_provider.dart';

void main() {
  group('ChatStore approvals', () {
    late _FakeChatRepository repo;

    setUp(() {
      repo = _FakeChatRepository();
    });

    tearDown(() async {
      await repo.close();
    });

    test('removes approval messages for completed job', () async {
      final store = ChatStore(repo, null);

      repo.emitMessage(_approvalMessage('approval-1', 'job-1'));
      await pumpEventQueue();

      expect(store.messages.where((m) => m.kind == 'approval'), hasLength(1));

      repo.emitMessage(
        ChatMessage(
          id: 'control-1',
          role: 'assistant',
          ts: DateTime.now(),
          kind: 'control',
          meta: const {'removeApprovalsForJobId': 'job-1'},
        ),
      );
      await pumpEventQueue();

      expect(store.messages.where((m) => m.kind == 'approval'), isEmpty);
    });

    test('marks stale approval response as unavailable', () async {
      final store = ChatStore(repo, null);
      repo.respondApprovalResult = false;

      repo.emitMessage(_approvalMessage('approval-1', 'job-1'));
      await pumpEventQueue();

      await store.respondApproval(
        messageId: 'approval-1',
        jobId: 'job-1',
        approvalId: 'safety-1',
        approved: true,
      );

      expect(store.messages.where((m) => m.kind == 'approval'), isEmpty);
      expect(store.messages.last.text, 'Approval is no longer active.');
      expect(store.messages.last.meta?['isError'], true);
    });

    test('records accepted approval response', () async {
      final store = ChatStore(repo, null);
      repo.respondApprovalResult = true;

      repo.emitMessage(_approvalMessage('approval-1', 'job-1'));
      await pumpEventQueue();

      await store.respondApproval(
        messageId: 'approval-1',
        jobId: 'job-1',
        approvalId: 'safety-1',
        approved: false,
      );

      expect(store.messages.where((m) => m.kind == 'approval'), isEmpty);
      expect(store.messages.last.text, 'Denied tool request.');
      expect(store.messages.last.meta, isNull);
    });

    test('creates new chats inside the selected memory scope', () async {
      final store = ChatStore(repo, null);

      store.createNewChat(memoryScopeExternalRef: 'sales-crm');

      expect(store.activeMemoryScopeExternalRef, 'sales-crm');
      expect(repo.activeMemoryScopeExternalRef, 'sales-crm');
      expect(store.sessions.first.memoryScopeExternalRef, 'sales-crm');
    });

    test('migrates thread metadata when a memory scope ref changes', () async {
      final store = ChatStore(repo, null);
      await store.refreshMemoryScopes();
      store.createNewChat(memoryScopeExternalRef: 'sales-crm');
      final scope = store.memoryScopes.firstWhere(
        (item) => item.externalRef == 'sales-crm',
      );

      await store.updateMemoryScope(
        scope,
        externalRef: 'sales-platform',
        name: 'Sales Platform',
      );

      expect(store.activeMemoryScopeExternalRef, 'sales-platform');
      expect(repo.activeMemoryScopeExternalRef, 'sales-platform');
      expect(store.sessions.first.memoryScopeExternalRef, 'sales-platform');
      expect(
        store.memoryScopes.any((item) => item.externalRef == 'sales-platform'),
        true,
      );
    });

    test(
      'renames local fallback memory scopes without merging empty ids',
      () async {
        final store = ChatStore(repo, null);
        store.createNewChat(memoryScopeExternalRef: 'local-alpha');
        store.createNewChat(memoryScopeExternalRef: 'local-beta');
        final alpha = store.memoryScopes.firstWhere(
          (item) => item.externalRef == 'local-alpha',
        );

        await store.updateMemoryScope(
          alpha,
          externalRef: 'local-alpha-renamed',
          name: 'Local Alpha Renamed',
        );

        expect(store.activeMemoryScopeExternalRef, 'local-beta');
        expect(repo.activeMemoryScopeExternalRef, 'local-beta');
        expect(
          store.memoryScopes.map((item) => item.externalRef),
          containsAll(['local-alpha-renamed', 'local-beta']),
        );
        expect(
          store.memoryScopes.any((item) => item.externalRef == 'local-alpha'),
          false,
        );
        expect(
          store.sessions.any(
            (session) =>
                session.memoryScopeExternalRef == 'local-alpha-renamed',
          ),
          true,
        );
      },
    );

    test(
      'deleting active memory scope switches to a remaining thread',
      () async {
        final store = ChatStore(repo, null);
        await store.refreshMemoryScopes();
        final defaultChatId = store.sessions.first.id;
        store.createNewChat(memoryScopeExternalRef: 'sales-crm');
        final sales = store.memoryScopes.firstWhere(
          (item) => item.externalRef == 'sales-crm',
        );

        await store.deleteMemoryScope(sales);

        expect(store.activeMemoryScopeExternalRef, 'default');
        expect(repo.activeMemoryScopeExternalRef, 'default');
        expect(store.activeChatId, defaultChatId);
        expect(
          store.sessions.any(
            (session) => session.memoryScopeExternalRef == 'sales-crm',
          ),
          false,
        );
        expect(
          store.memoryScopes.any((item) => item.externalRef == 'sales-crm'),
          false,
        );
      },
    );

    test('reviews context link suggestions from the active scope', () async {
      final store = ChatStore(repo, null);
      repo.contextLinkSuggestions = [_suggestion('ctxlinksug-1')];

      await store.refreshContextLinkSuggestions();

      expect(store.contextLinkSuggestions.single.id, 'ctxlinksug-1');

      await store.reviewContextLinkSuggestion(
        store.contextLinkSuggestions.single,
        approve: true,
      );

      expect(repo.reviewedSuggestions, ['ctxlinksug-1:approve']);
      expect(
        repo.reviewedSuggestionReasons['ctxlinksug-1'],
        'approved by user from review queue',
      );
      expect(store.contextLinkSuggestions, isEmpty);
    });

    test('rejects context link suggestions from the active scope', () async {
      final store = ChatStore(repo, null);
      repo.contextLinkSuggestions = [_suggestion('ctxlinksug-1')];

      await store.refreshContextLinkSuggestions();
      await store.reviewContextLinkSuggestion(
        store.contextLinkSuggestions.single,
        approve: false,
      );

      expect(repo.reviewedSuggestions, ['ctxlinksug-1:reject']);
      expect(
        repo.reviewedSuggestionReasons['ctxlinksug-1'],
        'rejected by user from review queue',
      );
      expect(store.contextLinkSuggestions, isEmpty);
      expect(store.contextLinkSuggestionError.value, isNull);
    });

    test('refreshes pending context links from repository after review',
        () async {
      final store = ChatStore(repo, null);
      repo.contextLinkSuggestions = [_suggestion('ctxlinksug-1')];
      repo.postReviewContextLinkSuggestions = [_suggestion('ctxlinksug-2')];

      await store.refreshContextLinkSuggestions();
      final listCallsBeforeReview = repo.listContextLinkSuggestionCalls;
      await store.reviewContextLinkSuggestion(
        store.contextLinkSuggestions.single,
        approve: true,
      );

      expect(repo.reviewedSuggestions, ['ctxlinksug-1:approve']);
      expect(repo.listContextLinkSuggestionCalls,
          greaterThan(listCallsBeforeReview));
      expect(store.contextLinkSuggestions.map((item) => item.id),
          ['ctxlinksug-2']);
    });

    test('refreshes pending memory suggestions from repository', () async {
      final store = ChatStore(repo, null);
      repo.memorySuggestions = [_memorySuggestion('sug-duplicate')];

      await store.refreshMemorySuggestions();

      expect(repo.listMemorySuggestionCalls, 1);
      expect(store.memorySuggestions.single.id, 'sug-duplicate');
      expect(store.memorySuggestions.single.canResolveDuplicate, true);
    });

    test('resolves duplicate memory suggestion through repository', () async {
      final store = ChatStore(repo, null);
      repo.memorySuggestions = [_memorySuggestion('sug-duplicate')];

      await store.refreshMemorySuggestions();
      final ok = await store.resolveDuplicateMemorySuggestion(
        store.memorySuggestions.single,
        action: 'keep_separate_fact',
      );

      expect(ok, true);
      expect(repo.reviewedMemorySuggestions, [
        'sug-duplicate:keep_separate_fact',
      ]);
      expect(
        repo.reviewedMemorySuggestionReasons['sug-duplicate'],
        'resolved duplicate memory from review queue',
      );
      expect(store.memorySuggestions, isEmpty);
      expect(store.memorySuggestionError.value, isNull);
    });

    test('approves pending suggestion with target override', () async {
      final store = ChatStore(repo, null);
      repo.contextLinkSuggestions = [_suggestion('ctxlinksug-1')];

      await store.refreshContextLinkSuggestions();
      final ok = await store.approveContextLinkSuggestionWithOverride(
        store.contextLinkSuggestions.single,
        targetType: 'anchor',
        targetId: 'anchor-alex',
        relationType: 'mentions',
        confidence: 'medium',
        reason: 'Alex is the correct target',
      );

      expect(ok, true);
      expect(repo.createdContextLinks, isEmpty);
      expect(repo.reviewedSuggestions, ['ctxlinksug-1:approve']);
      expect(
        repo.reviewedSuggestionReasons['ctxlinksug-1'],
        'approved by user with target override',
      );
      expect(repo.reviewedSuggestionOverrides['ctxlinksug-1'], {
        'target_type': 'anchor',
        'target_id': 'anchor-alex',
        'relation_type': 'mentions',
        'confidence': 'medium',
        'link_reason': 'Alex is the correct target',
      });
      expect(
        store.contextLinkSuggestions,
        isEmpty,
      );
      expect(store.contextLinkSuggestionError.value, isNull);
    });

    test('keeps suggestion visible when target override review fails',
        () async {
      final store = ChatStore(repo, null);
      repo.contextLinkSuggestions = [_suggestion('ctxlinksug-1')];
      repo.failReviewContextLink = true;

      await store.refreshContextLinkSuggestions();
      final ok = await store.approveContextLinkSuggestionWithOverride(
        store.contextLinkSuggestions.single,
        targetType: 'anchor',
        targetId: 'anchor-alex',
        relationType: 'mentions',
        confidence: 'medium',
        reason: 'Alex is the correct target',
      );

      expect(ok, false);
      expect(repo.createdContextLinks, isEmpty);
      expect(repo.reviewedSuggestions, isEmpty);
      expect(store.contextLinkSuggestions.single.id, 'ctxlinksug-1');
      expect(
        store.contextLinkSuggestionError.value,
        contains('Target override review failed'),
      );
    });

    test('refreshes extraction capabilities through optional provider',
        () async {
      final capabilityProvider = _FakeExtractionCapabilityProvider();
      final store = ChatStore(
        repo,
        null,
        extractionCapabilities: capabilityProvider,
      );

      await store.refreshExtractionCapabilities();

      expect(capabilityProvider.calls, 1);
      expect(
        store.extractionCapabilities.value
            ?.provider('openai_transcription')
            ?.status,
        'blocked',
      );
      expect(store.extractionCapabilitiesError.value, isNull);
    });
  });
}

ChatMessage _approvalMessage(String id, String jobId) {
  return ChatMessage(
    id: id,
    role: 'system',
    ts: DateTime.now(),
    kind: 'approval',
    text: 'Tool approval required',
    meta: {'jobId': jobId, 'approvalId': 'safety-1'},
  );
}

class _FakeChatRepository implements ChatRepository {
  final _messages = StreamController<ChatMessage>.broadcast();
  final _usage = StreamController<CostUsage>.broadcast();
  final _running = StreamController<bool>.broadcast();
  final _connection = StreamController<ConnectionStatus>.broadcast();

  bool respondApprovalResult = true;
  String activeMemoryScopeExternalRef = 'default';
  bool failCreateContextLink = false;
  bool failReviewContextLink = false;
  bool failResolveMemorySuggestion = false;
  final Map<String, MemoryScope> scopesByRef = {
    'default': _scope('scope-default', 'default', 'Default'),
    'sales-crm': _scope('scope-sales-crm', 'sales-crm', 'Sales CRM'),
  };
  List<MemoryContextLinkSuggestion> contextLinkSuggestions = const [];
  List<MemoryContextLinkSuggestion>? postReviewContextLinkSuggestions;
  List<MemorySuggestion> memorySuggestions = const [];
  List<MemorySuggestion>? postReviewMemorySuggestions;
  int listContextLinkSuggestionCalls = 0;
  int listMemorySuggestionCalls = 0;
  final reviewedSuggestions = <String>[];
  final reviewedMemorySuggestions = <String>[];
  final reviewedSuggestionReasons = <String, String?>{};
  final reviewedMemorySuggestionReasons = <String, String?>{};
  final reviewedSuggestionOverrides = <String, Map<String, String>>{};
  final createdContextLinks = <Map<String, String>>[];
  final assetExtractions = <AssetExtractionJob>[];
  int _assetSeq = 0;
  int _extractionSeq = 0;

  void emitMessage(ChatMessage message) {
    _messages.add(message);
  }

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
  Future<String> runTask({required String task}) async => 'job-1';

  @override
  Future<bool> respondApproval({
    required String jobId,
    required String approvalId,
    required bool approved,
  }) async {
    return respondApprovalResult;
  }

  @override
  Future<void> cancelJob(String jobId) async {}

  @override
  Future<void> cancelCurrentJob() async {}

  @override
  void setActiveChat(String chatId) {}

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
    final current = scopesByRef.values.firstWhere(
      (item) => item.id == memoryScopeId,
    );
    scopesByRef.remove(current.externalRef);
    final updated = current.copyWith(
      externalRef: externalRef ?? current.externalRef,
      name: name ?? current.name,
      updatedAt: DateTime.now(),
    );
    scopesByRef[updated.externalRef] = updated;
    return updated;
  }

  @override
  Future<void> deleteMemoryScope(String memoryScopeId) async {
    scopesByRef.removeWhere((_, item) => item.id == memoryScopeId);
  }

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
    if (failCreateContextLink) {
      throw StateError('simulated create link failure');
    }
    createdContextLinks.add({
      'source_type': sourceType,
      'source_id': sourceId,
      'target_type': targetType,
      'target_id': targetId,
      'relation_type': relationType,
      'confidence': confidence,
      'reason': reason,
    });
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
    final job = _assetExtractionJob(
      id: 'extract-${++_extractionSeq}',
      assetId: assetId,
      status: 'succeeded',
    );
    assetExtractions.insert(0, job);
    onProgress?.call(bytes.length, bytes.length);
    return assetId;
  }

  @override
  Future<List<int>> downloadFile(String id) async => <int>[];

  @override
  Future<List<AssetExtractionJob>> listAssetExtractions({
    String? status,
    int limit = 50,
  }) async {
    return assetExtractions
        .where((job) => status == null || job.status == status)
        .take(limit)
        .toList(growable: false);
  }

  @override
  Future<AssetExtractionJob> getAssetExtraction(String jobId) async {
    return assetExtractions.firstWhere(
      (job) => job.id == jobId,
      orElse: () => throw StateError('Asset extraction not found: $jobId'),
    );
  }

  @override
  Future<AssetExtractionJob> retryAssetExtraction(String jobId) async {
    final current = await getAssetExtraction(jobId);
    final updated = _assetExtractionJob(
      id: current.id,
      assetId: current.assetId,
      status: 'pending',
      attemptCount: current.attemptCount + 1,
    );
    _replaceAssetExtraction(updated);
    return updated;
  }

  @override
  Future<AssetExtractionJob> cancelAssetExtraction(String jobId) async {
    final current = await getAssetExtraction(jobId);
    final updated = _assetExtractionJob(
      id: current.id,
      assetId: current.assetId,
      status: 'canceled',
      attemptCount: current.attemptCount,
    );
    _replaceAssetExtraction(updated);
    return updated;
  }

  void _replaceAssetExtraction(AssetExtractionJob updated) {
    final index = assetExtractions.indexWhere((job) => job.id == updated.id);
    if (index == -1) {
      assetExtractions.insert(0, updated);
      return;
    }
    assetExtractions[index] = updated;
  }

  @override
  Future<MemoryOperationsConsole> getOperationsConsole({int limit = 50}) async {
    return MemoryOperationsConsole(
      generatedAt: DateTime.now(),
      scope: const <String, dynamic>{},
      extractionStatusCounts: _statusCounts(assetExtractions),
      linkSuggestionStatusCounts: {
        'pending':
            contextLinkSuggestions.where((item) => item.isPending).length,
      },
      extractionJobs: assetExtractions.take(limit).toList(growable: false),
      contextLinkSuggestions: contextLinkSuggestions.take(limit).toList(),
      diagnostics: const <String, dynamic>{},
    );
  }

  @override
  Future<MemoryBrowserSnapshot> getMemoryBrowser({int limit = 50}) async {
    return MemoryBrowserSnapshot.empty();
  }

  @override
  Future<MemoryBrowserAnchor> createMemoryAnchor({
    required String kind,
    required String label,
    List<String> aliases = const <String>[],
    String? description,
  }) async {
    return MemoryBrowserAnchor.fromMap({
      'id': 'anchor-fake',
      'space_id': 'space-1',
      'memory_scope_id': 'scope-1',
      'kind': kind,
      'normalized_key': label.toLowerCase(),
      'label': label,
      'aliases': aliases,
      'description': description,
      'status': 'active',
      'metadata': <String, dynamic>{},
      'created_at': '2026-06-14T10:00:00Z',
      'updated_at': '2026-06-14T10:00:00Z',
    });
  }

  @override
  Future<MemoryBrowserAnchor> updateMemoryAnchor({
    required String anchorId,
    required String label,
    List<String> aliases = const <String>[],
    String? description,
  }) async {
    return MemoryBrowserAnchor.fromMap({
      'id': anchorId,
      'space_id': 'space-1',
      'memory_scope_id': 'scope-1',
      'kind': 'person',
      'normalized_key': label.toLowerCase(),
      'label': label,
      'aliases': aliases,
      'description': description,
      'status': 'active',
      'metadata': <String, dynamic>{},
      'created_at': '2026-06-14T10:00:00Z',
      'updated_at': '2026-06-14T10:05:00Z',
    });
  }

  @override
  Future<void> deleteMemoryAnchor({
    required String anchorId,
    String reason = 'manual delete',
  }) async {}

  @override
  Future<List<MemoryAnchorMergeSuggestion>> listMemoryAnchorMergeSuggestions({
    int limit = 50,
  }) async {
    return const <MemoryAnchorMergeSuggestion>[];
  }

  @override
  Future<MemoryBrowserAnchor> mergeMemoryAnchors({
    required String sourceAnchorId,
    required String targetAnchorId,
    required String reason,
  }) async {
    return MemoryBrowserAnchor.fromMap({
      'id': targetAnchorId,
      'space_id': 'space-1',
      'memory_scope_id': 'scope-1',
      'kind': 'person',
      'normalized_key': targetAnchorId,
      'label': targetAnchorId,
      'aliases': const <String>[],
      'description': null,
      'status': 'active',
      'metadata': <String, dynamic>{},
      'created_at': '2026-06-14T10:00:00Z',
      'updated_at': '2026-06-14T10:05:00Z',
    });
  }

  @override
  Future<MemoryBrowserAnchor> splitMemoryAnchor({
    required String anchorId,
    required String alias,
    String? newLabel,
    String reason = 'manual split',
  }) async {
    return MemoryBrowserAnchor.fromMap({
      'id': 'anchor-split',
      'space_id': 'space-1',
      'memory_scope_id': 'scope-1',
      'kind': 'person',
      'normalized_key': (newLabel ?? alias).toLowerCase(),
      'label': newLabel ?? alias,
      'aliases': const <String>[],
      'description': null,
      'status': 'active',
      'metadata': <String, dynamic>{},
      'created_at': '2026-06-14T10:00:00Z',
      'updated_at': '2026-06-14T10:05:00Z',
    });
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
    return const <MemoryCapture>[];
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
    listContextLinkSuggestionCalls += 1;
    return contextLinkSuggestions;
  }

  @override
  Future<MemoryContextLinkSuggestion> reviewContextLinkSuggestion({
    required String suggestionId,
    required String action,
    String? reason,
    String? targetType,
    String? targetId,
    String? relationType,
    String? confidence,
    String? linkReason,
  }) async {
    if (failReviewContextLink) {
      throw StateError('simulated review failure');
    }
    reviewedSuggestions.add('$suggestionId:$action');
    reviewedSuggestionReasons[suggestionId] = reason;
    reviewedSuggestionOverrides[suggestionId] = {
      if (targetType != null) 'target_type': targetType,
      if (targetId != null) 'target_id': targetId,
      if (relationType != null) 'relation_type': relationType,
      if (confidence != null) 'confidence': confidence,
      if (linkReason != null) 'link_reason': linkReason,
    };
    final suggestion = contextLinkSuggestions.firstWhere(
      (item) => item.id == suggestionId,
    );
    contextLinkSuggestions = postReviewContextLinkSuggestions ??
        contextLinkSuggestions
            .where((item) => item.id != suggestionId)
            .toList(growable: false);
    postReviewContextLinkSuggestions = null;
    return MemoryContextLinkSuggestion.fromMap({
      'id': suggestion.id,
      'space_id': suggestion.spaceId,
      'memory_scope_id': suggestion.memoryScopeId,
      'source_type': suggestion.sourceType,
      'source_id': suggestion.sourceId,
      'target_type': targetType ?? suggestion.targetType,
      'target_id': targetId ?? suggestion.targetId,
      'relation_type': relationType ?? suggestion.relationType,
      'confidence': confidence ?? suggestion.confidence,
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

  @override
  Future<List<MemoryContextLinkSuggestion>> reviewContextLinkSuggestionsBatch({
    required List<String> suggestionIds,
    required String action,
    String? reason,
  }) async {
    final reviewed = <MemoryContextLinkSuggestion>[];
    for (final suggestionId in suggestionIds) {
      reviewed.add(
        await reviewContextLinkSuggestion(
          suggestionId: suggestionId,
          action: action,
          reason: reason,
        ),
      );
    }
    return reviewed;
  }

  @override
  Future<List<MemorySuggestion>> listMemorySuggestions({
    String status = 'pending',
    int limit = 50,
  }) async {
    listMemorySuggestionCalls += 1;
    return memorySuggestions;
  }

  @override
  Future<MemorySuggestion> resolveDuplicateMemorySuggestion({
    required String suggestionId,
    required String action,
    String? reason,
    bool force = false,
  }) async {
    if (failResolveMemorySuggestion) {
      throw StateError('simulated memory review failure');
    }
    reviewedMemorySuggestions.add('$suggestionId:$action');
    reviewedMemorySuggestionReasons[suggestionId] = reason;
    final suggestion = memorySuggestions.firstWhere(
      (item) => item.id == suggestionId,
    );
    memorySuggestions = postReviewMemorySuggestions ??
        memorySuggestions
            .where((item) => item.id != suggestionId)
            .toList(growable: false);
    postReviewMemorySuggestions = null;
    return MemorySuggestion.fromMap({
      'id': suggestion.id,
      'space_id': suggestion.spaceId,
      'memory_scope_id': suggestion.memoryScopeId,
      'candidate_text': suggestion.candidateText,
      'kind': suggestion.kind,
      'operation': suggestion.operation,
      'status': 'approved',
      'confidence': suggestion.confidence,
      'trust_level': suggestion.trustLevel,
      'safe_reason': suggestion.safeReason,
      'target_fact_id': suggestion.targetFactId,
      'target_fact_version': suggestion.targetFactVersion,
      'review_kind': suggestion.reviewKind,
      'review_actionable': false,
      'available_review_actions': suggestion.availableReviewActions,
      'review_resolution_options': [
        for (final option in suggestion.reviewResolutionOptions)
          {
            'id': option.id,
            'review_action': option.reviewAction,
            'effect': option.effect,
            'availability': option.availability,
            'resolution_action': option.resolutionAction,
          },
      ],
      'review_payload': suggestion.reviewPayload,
      'created_at': suggestion.createdAt.toIso8601String(),
      'updated_at': DateTime.now().toIso8601String(),
      'reviewed_at': DateTime.now().toIso8601String(),
      'review_reason': reason,
    });
  }
}

class _FakeExtractionCapabilityProvider
    implements ExtractionCapabilityProvider {
  var calls = 0;

  @override
  Future<ExtractionCapabilities> getExtractionCapabilities() async {
    calls += 1;
    return ExtractionCapabilities.fromMap({
      'enabled': true,
      'default_profile': 'standard_local',
      'providers': {
        'openai_transcription': {
          'kind': 'asr',
          'installed': true,
          'configured': false,
          'enabled': false,
          'status': 'blocked',
          'reason': 'missing api key',
        },
      },
      'degraded_components': [
        {
          'component_type': 'provider',
          'name': 'openai_transcription',
          'status': 'blocked',
          'reason': 'missing api key',
        },
      ],
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

AssetExtractionJob _assetExtractionJob({
  required String id,
  required String assetId,
  required String status,
  int attemptCount = 1,
}) {
  final now = DateTime.now().toIso8601String();
  final succeeded = status == 'succeeded';
  return AssetExtractionJob.fromMap({
    'id': id,
    'asset_id': assetId,
    'space_id': 'space-1',
    'memory_scope_id': 'scope-default',
    'thread_id': null,
    'parser_profile': 'standard_local',
    'parser_config_hash': 'fake-parser-config',
    'source_sha256_hex': 'fake-source-sha',
    'status': status,
    'attempt_count': attemptCount,
    'parser_name': succeeded ? 'fake_text_parser' : null,
    'parser_version': succeeded ? '1' : null,
    'model_version': null,
    'result_document_ids': succeeded ? ['doc-$assetId'] : const <String>[],
    'artifacts': const <Map<String, dynamic>>[],
    'metadata': const <String, dynamic>{},
    'progress': {
      'stage': status,
      'percent': succeeded ? 100 : 0,
      'message': 'Extraction $status',
      'terminal': status != 'pending' && status != 'running',
    },
    'execution': const <String, dynamic>{},
    'usage': const <String, dynamic>{},
    'created_at': now,
    'updated_at': now,
    'started_at': status == 'pending' ? null : now,
    'finished_at': status == 'pending' || status == 'running' ? null : now,
  });
}

Map<String, int> _statusCounts(Iterable<dynamic> items) {
  final counts = <String, int>{};
  for (final item in items) {
    final status = item.status.toString();
    counts[status] = (counts[status] ?? 0) + 1;
  }
  return counts;
}

MemoryContextLinkSuggestion _suggestion(String id) {
  final now = DateTime.now();
  return MemoryContextLinkSuggestion(
    id: id,
    spaceId: 'space-1',
    memoryScopeId: 'scope-default',
    sourceType: 'capture',
    sourceId: 'capture-1',
    targetType: 'fact',
    targetId: 'fact-1',
    relationType: 'related_to',
    confidence: 'high',
    reason: 'matching text',
    score: 88,
    status: 'pending',
    metadata: const {
      'target_label': 'Q3 roadmap',
      'target_preview': 'Alex confirmed Q3 rollout.',
    },
    createdAt: now,
    updatedAt: now,
  );
}

MemorySuggestion _memorySuggestion(String id) {
  final now = DateTime.now();
  return MemorySuggestion.fromMap({
    'id': id,
    'space_id': 'space-1',
    'memory_scope_id': 'scope-default',
    'candidate_text': 'Docs retrieval should use Qdrant vectors.',
    'kind': 'note',
    'operation': 'review',
    'status': 'pending',
    'confidence': 'medium',
    'trust_level': 'medium',
    'safe_reason': 'candidate matches an active fact',
    'target_fact_id': 'fact-1',
    'target_fact_version': 1,
    'review_kind': 'duplicate_fact_merge',
    'review_actionable': true,
    'available_review_actions': [
      'approve',
      'reject',
      'expire',
      'resolve_duplicate',
    ],
    'review_resolution_options': [
      {
        'id': 'merge_source_refs',
        'review_action': 'resolve_duplicate',
        'effect': 'merge_source_refs_into_existing_fact',
        'availability': 'available',
        'resolution_action': 'merge_source_refs',
      },
      {
        'id': 'keep_separate_fact',
        'review_action': 'resolve_duplicate',
        'effect': 'create_new_fact_keep_existing_fact',
        'availability': 'available',
        'resolution_action': 'keep_separate_fact',
      },
    ],
    'review_payload': {
      'review_kind': 'duplicate_fact_merge',
      'recommended_action': 'merge_source_refs_into_existing_fact',
      'default_resolution': 'merge_or_keep_separate_after_review',
    },
    'created_at': now.toIso8601String(),
    'updated_at': now.toIso8601String(),
  });
}
