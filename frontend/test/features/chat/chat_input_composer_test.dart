import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_models.dart';
import 'package:frontend/src/features/chat/application/services/attachment_upload_service.dart';
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
import 'package:frontend/src/features/chat/domain/entities/memory_suggestion.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/presentation/widgets/chat_input_composer.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('idle primary action sends when controller already has text', (
    tester,
  ) async {
    final repo = _RecordingChatRepository();
    final store = ChatStore(repo, null);
    addTearDown(store.dispose);
    addTearDown(repo.close);

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          Provider<ChatRepository>.value(value: repo),
          Provider<ChatStore>.value(value: store),
        ],
        child: MaterialApp(
          theme: ThemeData(splashFactory: InkRipple.splashFactory),
          home: const Scaffold(body: ChatInputComposer()),
        ),
      ),
    );

    expect(
      find.byKey(const ValueKey('quick_capture_save_target_strip')),
      findsOneWidget,
    );
    expect(find.text('Default'), findsOneWidget);
    expect(find.text('Thread 1'), findsOneWidget);
    expect(
      find.byKey(const ValueKey('quick_capture_primary_action_button')),
      findsOneWidget,
    );

    final textField = tester.widget<TextField>(
      find.byKey(const ValueKey('quick_capture_input')),
    );
    textField.controller!.text = 'Captured from stale controller';

    await tester.tap(
      find.byKey(const ValueKey('quick_capture_primary_action_button')),
    );
    await tester.pump();

    expect(repo.sentTasks, ['Captured from stale controller']);
    expect(textField.controller!.text, isEmpty);
  });

  testWidgets('file picker upload creates a file-only capture', (
    tester,
  ) async {
    final repo = _RecordingChatRepository();
    final picker = _RecordingAttachmentFilePicker([
      AttachmentUploadDraft.file(
        name: 'atlas-note.txt',
        bytes: [65, 116, 108, 97, 115],
        mime: 'text/plain',
      ),
    ]);
    final store = ChatStore(repo, null);
    addTearDown(store.dispose);
    addTearDown(repo.close);

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          Provider<ChatRepository>.value(value: repo),
          Provider<ChatStore>.value(value: store),
          Provider<AttachmentFilePicker>.value(value: picker),
          Provider<AttachmentUploadService>.value(
            value: AttachmentUploadService(repo: repo),
          ),
        ],
        child: MaterialApp(
          theme: ThemeData(splashFactory: InkRipple.splashFactory),
          home: const Scaffold(body: ChatInputComposer()),
        ),
      ),
    );

    await tester.tap(find.byKey(const ValueKey('quick_capture_attach_button')));
    await tester.pumpAndSettle();

    expect(picker.pickCalls, 1);
    expect(repo.uploadedNames, ['atlas-note.txt']);
    expect(repo.sentTasks, ['']);
    expect(store.assetExtractions.map((job) => job.id), ['extract-1']);
  });

  testWidgets('file picker upload saves current text as capture note', (
    tester,
  ) async {
    final repo = _RecordingChatRepository();
    final picker = _RecordingAttachmentFilePicker([
      AttachmentUploadDraft.file(
        name: 'atlas-screenshot-note.txt',
        bytes: [65, 108, 101, 120],
        mime: 'text/plain',
      ),
    ]);
    final store = ChatStore(repo, null);
    addTearDown(store.dispose);
    addTearDown(repo.close);

    await tester.pumpWidget(
      MultiProvider(
        providers: [
          Provider<ChatRepository>.value(value: repo),
          Provider<ChatStore>.value(value: store),
          Provider<AttachmentFilePicker>.value(value: picker),
          Provider<AttachmentUploadService>.value(
            value: AttachmentUploadService(repo: repo),
          ),
        ],
        child: MaterialApp(
          theme: ThemeData(splashFactory: InkRipple.splashFactory),
          home: const Scaffold(body: ChatInputComposer()),
        ),
      ),
    );

    await tester.enterText(
      find.byKey(const ValueKey('quick_capture_input')),
      'Screenshot from Alex call',
    );
    await tester.tap(find.byKey(const ValueKey('quick_capture_attach_button')));
    await tester.pumpAndSettle();

    expect(repo.uploadedNames, ['atlas-screenshot-note.txt']);
    expect(repo.sentTasks, ['Screenshot from Alex call']);
    final textField = tester.widget<TextField>(
      find.byKey(const ValueKey('quick_capture_input')),
    );
    expect(textField.controller!.text, isEmpty);
  });

  test('attachment with dedupe suggestion refreshes review data', () async {
    final repo = _RecordingChatRepository();
    final store = ChatStore(repo, null);
    addTearDown(store.dispose);
    addTearDown(repo.close);

    repo.emitMessage(ChatMessage(
      id: 'msg-asset-dedupe',
      role: 'user',
      ts: DateTime.now(),
      kind: 'attachment',
      text: 'shared-note.txt',
      meta: const {
        'fileId': 'asset-duplicate',
        'contextLinkSuggestionId': 'ctxlinksug-duplicate',
      },
    ));
    await Future<void>.delayed(Duration.zero);

    expect(repo.operationsConsoleCalls, 1);
    expect(repo.contextLinkSuggestionCalls, 1);
  });
}

class _RecordingAttachmentFilePicker implements AttachmentFilePicker {
  final List<AttachmentUploadDraft> drafts;
  int pickCalls = 0;

  _RecordingAttachmentFilePicker(this.drafts);

  @override
  Future<List<AttachmentUploadDraft>> pickFiles() async {
    pickCalls += 1;
    return drafts;
  }
}

class _RecordingChatRepository implements ChatRepository {
  final sentTasks = <String>[];
  final uploadedNames = <String>[];
  final assetExtractions = <AssetExtractionJob>[];
  int operationsConsoleCalls = 0;
  int contextLinkSuggestionCalls = 0;
  final _messages = StreamController<ChatMessage>.broadcast();
  final _usage = StreamController<CostUsage>.broadcast();
  final _running = StreamController<bool>.broadcast();
  final _connection = StreamController<ConnectionStatus>.broadcast();
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

  void emitMessage(ChatMessage message) {
    _messages.add(message);
  }

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
    sentTasks.add(task);
    return 'job-1';
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
  void setActiveChat(String chatId) {}

  @override
  void setActiveMemoryScopeExternalRef(String externalRef) {}

  @override
  String currentMemoryScopeExternalRef() => 'default';

  @override
  Future<List<MemoryScope>> listMemoryScopes() async {
    return [_scope()];
  }

  @override
  Future<MemoryScope> createMemoryScope({
    required String externalRef,
    required String name,
  }) async {
    return _scope(externalRef: externalRef, name: name);
  }

  @override
  Future<MemoryScope> updateMemoryScope({
    required String memoryScopeId,
    String? externalRef,
    String? name,
  }) async {
    return _scope(id: memoryScopeId, externalRef: externalRef, name: name);
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
    uploadedNames.add(name);
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
    operationsConsoleCalls += 1;
    return MemoryOperationsConsole(
      generatedAt: DateTime.now(),
      scope: const <String, dynamic>{},
      extractionStatusCounts: _statusCounts(assetExtractions),
      linkSuggestionStatusCounts: const <String, int>{},
      extractionJobs: assetExtractions.take(limit).toList(growable: false),
      contextLinkSuggestions: const <MemoryContextLinkSuggestion>[],
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
    contextLinkSuggestionCalls += 1;
    return const <MemoryContextLinkSuggestion>[];
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
    return _suggestion(
      suggestionId,
      status: action == 'approve' ? 'approved' : 'rejected',
      reviewReason: reason,
    );
  }

  @override
  Future<List<MemoryContextLinkSuggestion>> reviewContextLinkSuggestionsBatch({
    required List<String> suggestionIds,
    required String action,
    String? reason,
  }) async {
    return [
      for (final suggestionId in suggestionIds)
        await reviewContextLinkSuggestion(
          suggestionId: suggestionId,
          action: action,
          reason: reason,
        ),
    ];
  }

  @override
  Future<List<MemorySuggestion>> listMemorySuggestions({
    String status = 'pending',
    int limit = 50,
  }) async {
    return const <MemorySuggestion>[];
  }

  @override
  Future<MemorySuggestion> resolveDuplicateMemorySuggestion({
    required String suggestionId,
    required String action,
    String? reason,
    bool force = false,
  }) async {
    throw UnimplementedError();
  }
}

MemoryScope _scope({String? id, String? externalRef, String? name}) {
  final now = DateTime.now();
  return MemoryScope(
    id: id ?? 'scope-default',
    spaceId: 'space-1',
    externalRef: externalRef ?? 'default',
    name: name ?? 'Default',
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

MemoryContextLinkSuggestion _suggestion(
  String id, {
  required String status,
  String? reviewReason,
}) {
  final now = DateTime.now();
  return MemoryContextLinkSuggestion.fromMap({
    'id': id,
    'space_id': 'space-1',
    'memory_scope_id': 'scope-default',
    'source_type': 'capture',
    'source_id': 'capture-1',
    'target_type': 'fact',
    'target_id': 'fact-1',
    'relation_type': 'related_to',
    'confidence': 'medium',
    'reason': 'test suggestion',
    'score': 50,
    'status': status,
    'metadata': const <String, dynamic>{},
    'created_at': now.toIso8601String(),
    'updated_at': now.toIso8601String(),
    'reviewed_at': now.toIso8601String(),
    'review_reason': reviewReason,
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
