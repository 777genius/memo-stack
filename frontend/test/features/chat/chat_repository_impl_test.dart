import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/data/datasources/backend_rest_client.dart';
import 'package:frontend/src/features/chat/data/repositories/chat_repository_impl.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';

void main() {
  group('ChatRepositoryImpl', () {
    test(
        'shows backend error message and keeps connection when server responds',
        () async {
      final rest = _PolicyBlockedRestClient(asJsonString: true);
      final repo = ChatRepositoryImpl(rest);
      final messages = <String>[];
      final statuses = <ConnectionStatus>[];
      final messageSub = repo.messages().listen((message) {
        if (message.text != null) {
          messages.add(message.text!);
        }
      });
      final statusSub = repo.connectionStatus().listen(statuses.add);

      await expectLater(
        repo.runTask(task: 'Save CRM onboarding screenshot note'),
        throwsA(isA<DioException>()),
      );
      await pumpEventQueue();

      expect(messages,
          contains('Capture failed: Capture writes are disabled by policy'));
      expect(statuses.last, ConnectionStatus.connected);

      await messageSub.cancel();
      await statusSub.cancel();
      await repo.dispose();
    });

    test('shows backend error message from map response bodies', () async {
      final rest = _PolicyBlockedRestClient(asJsonString: false);
      final repo = ChatRepositoryImpl(rest);
      final messages = <String>[];
      final messageSub = repo.messages().listen((message) {
        if (message.text != null) {
          messages.add(message.text!);
        }
      });

      await expectLater(
        repo.runTask(task: 'Save CRM onboarding screenshot note'),
        throwsA(isA<DioException>()),
      );
      await pumpEventQueue();

      expect(messages,
          contains('Capture failed: Capture writes are disabled by policy'));

      await messageSub.cancel();
      await repo.dispose();
    });

    test('uploadFile requests extraction and emits extraction metadata',
        () async {
      final rest = _UploadRecordingRestClient();
      final repo = ChatRepositoryImpl(rest);
      final messages = <Map<String, dynamic>>[];
      final sub = repo.messages().listen((message) {
        if (message.kind == 'attachment') {
          messages.add(message.meta ?? const <String, dynamic>{});
        }
      });

      final assetId = await repo.uploadFile(
        'notes.txt',
        [1, 2, 3],
        mime: 'text/plain',
      );
      await pumpEventQueue();

      expect(assetId, 'asset-1');
      expect(rest.extractAttempts, [true]);
      expect(messages.single['extractionId'], 'extract-1');
      expect(messages.single['extractionStatus'], 'pending');

      await sub.cancel();
      await repo.dispose();
    });

    test('uploadFile falls back when extraction is disabled', () async {
      final rest = _ExtractionDisabledRestClient();
      final repo = ChatRepositoryImpl(rest);

      final assetId = await repo.uploadFile('notes.txt', [1, 2, 3]);

      expect(assetId, 'asset-fallback');
      expect(rest.extractAttempts, [true, false]);

      await repo.dispose();
    });

    test('listAssetExtractions hydrates artifacts for succeeded jobs',
        () async {
      final rest = _ExtractionListRestClient();
      final repo = ChatRepositoryImpl(rest);

      final jobs = await repo.listAssetExtractions();

      expect(jobs.single.id, 'extract-1');
      expect(jobs.single.artifacts.single.id, 'artifact-1');
      expect(rest.detailCalls, ['extract-1']);

      await repo.dispose();
    });

    test('listDocumentChunks parses source refs', () async {
      final rest = _DocumentChunksRestClient();
      final repo = ChatRepositoryImpl(rest);

      final chunks = await repo.listDocumentChunks('doc-1');

      expect(chunks.single.id, 'chunk-1');
      expect(chunks.single.sourceRefs.single.pageNumber, 3);
      expect(chunks.single.sourceRefs.single.timeStartMs, 1200);
      expect(chunks.single.sourceRefs.single.quotePreview, 'Decision quote');

      await repo.dispose();
    });

    test('lists memory captures and context links', () async {
      final rest = _MemoryHistoryRestClient();
      final repo = ChatRepositoryImpl(rest);

      final captures = await repo.listMemoryCaptures();
      final links = await repo.listContextLinks(
        sourceType: 'capture',
        sourceId: 'capture-1',
      );

      expect(captures.single.id, 'capture-1');
      expect(captures.single.assetIds, ['asset-1']);
      expect(captures.single.preview, contains('Alex confirmed'));
      expect(links.single.targetLabel, 'Q3 roadmap');
      expect(links.single.confidence, 'high');

      await repo.dispose();
    });

    test('keeps saved capture when link suggestions fail softly', () async {
      final rest = _SuggestionFailingRestClient();
      final repo = ChatRepositoryImpl(rest);
      final messages = <String>[];
      final sub = repo.messages().listen((message) {
        if (message.text != null) {
          messages.add(message.text!);
        }
      });

      await repo.uploadFile('report.pdf', [1, 2, 3]);
      await repo.runTask(task: 'Alex sent updated capture notes');
      await repo.runTask(task: 'Second note');
      await pumpEventQueue();

      expect(messages,
          contains('Saved. Related context suggestions unavailable.'));
      expect(
        messages.where((item) => item.startsWith('Capture failed')),
        isEmpty,
      );
      expect(rest.captureAssetIds, [
        ['asset-1'],
        <String>[],
      ]);
      expect(rest.suggestPersistValues, [true, true]);

      await sub.cancel();
      await repo.dispose();
    });
  });
}

class _MemoryHistoryRestClient extends BackendRestClient {
  @override
  Future<List<Map<String, dynamic>>> listCaptures({
    required String spaceSlug,
    required String memoryScopeExternalRef,
    String? status,
    String? consolidationStatus,
    int limit = 50,
  }) async {
    return [
      {
        'id': 'capture-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'thread_id': 'thread-1',
        'source_agent': 'memo-stack-frontend',
        'source_kind': 'manual',
        'event_type': 'QuickCapture',
        'actor_role': 'user',
        'text_preview': 'Alex confirmed Q3 rollout after product review.',
        'status': 'accepted',
        'consolidation_status': 'pending',
        'trust_level': 'medium',
        'source_authority': 'user_statement',
        'sensitivity': 'medium',
        'data_classification': 'internal',
        'evidence_refs': [
          {'source_type': 'asset', 'source_id': 'asset-1'},
        ],
        'metadata': {
          'asset_ids': ['asset-1'],
        },
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
        'occurred_at': '2026-06-13T00:00:00Z',
      },
    ];
  }

  @override
  Future<List<Map<String, dynamic>>> listContextLinks({
    required String spaceSlug,
    required String memoryScopeExternalRef,
    required String sourceType,
    required String sourceId,
    String status = 'active',
    int limit = 50,
  }) async {
    return [
      {
        'id': 'link-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'source_type': sourceType,
        'source_id': sourceId,
        'target_type': 'thread',
        'target_id': 'thread-1',
        'relation_type': 'related_to',
        'confidence': 'high',
        'reason': 'selected by user',
        'status': status,
        'metadata': {'target_label': 'Q3 roadmap'},
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      },
    ];
  }
}

class _DocumentChunksRestClient extends BackendRestClient {
  @override
  Future<List<Map<String, dynamic>>> listDocumentChunks(
    String documentId, {
    int limit = 100,
  }) async {
    return [
      {
        'id': 'chunk-1',
        'document_id': documentId,
        'text': 'Decision quote from source',
        'kind': 'document_section',
        'sequence': 0,
        'status': 'active',
        'classification': 'internal',
        'source_refs': [
          {
            'source_type': 'asset_extraction',
            'source_id': 'extract-1',
            'page_number': 3,
            'time_start_ms': 1200,
            'quote_preview': 'Decision quote',
          },
        ],
        'metadata': <String, dynamic>{},
      },
    ];
  }
}

class _ExtractionListRestClient extends BackendRestClient {
  final List<String> detailCalls = <String>[];

  @override
  Future<Map<String, dynamic>> healthz() async => {'status': 'ok'};

  @override
  Future<List<Map<String, dynamic>>> listAssetExtractions({
    required String spaceSlug,
    required String memoryScopeExternalRef,
    String? threadExternalRef,
    String? status,
    int limit = 50,
  }) async {
    return [
      {
        'id': 'extract-1',
        'asset_id': 'asset-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'succeeded',
        'attempt_count': 1,
        'result_document_ids': ['doc-1'],
        'metadata': <String, dynamic>{},
        'created_at': '2026-06-12T00:00:00Z',
        'updated_at': '2026-06-12T00:00:01Z',
      },
    ];
  }

  @override
  Future<Map<String, dynamic>> getAssetExtraction(String jobId) async {
    detailCalls.add(jobId);
    return {
      'id': jobId,
      'asset_id': 'asset-1',
      'space_id': 'space-1',
      'memory_scope_id': 'scope-1',
      'parser_profile': 'standard_local',
      'parser_config_hash': 'hash',
      'source_sha256_hex': 'sha',
      'status': 'succeeded',
      'attempt_count': 1,
      'result_document_ids': ['doc-1'],
      'artifacts': [
        {
          'id': 'artifact-1',
          'job_id': jobId,
          'asset_id': 'asset-1',
          'artifact_type': 'markdown',
          'storage_backend': 'local',
          'storage_key': 'artifact.md',
          'sha256_hex': 'sha',
          'byte_size': 12,
          'metadata': {'filename': 'extracted.md'},
          'created_at': '2026-06-12T00:00:02Z',
        },
      ],
      'metadata': <String, dynamic>{},
      'created_at': '2026-06-12T00:00:00Z',
      'updated_at': '2026-06-12T00:00:01Z',
    };
  }
}

class _UploadRecordingRestClient extends BackendRestClient {
  final List<bool> extractAttempts = <bool>[];

  @override
  Future<Map<String, dynamic>> uploadBytes(
    String name,
    List<int> bytes, {
    required String spaceSlug,
    required String memoryScopeExternalRef,
    String? threadExternalRef,
    String? mime,
    bool extract = false,
    String? parserProfile,
    void Function(int, int)? onProgress,
    void Function(void Function())? onCreateCancel,
  }) async {
    extractAttempts.add(extract);
    return {
      'id': 'asset-1',
      'extraction': {
        'id': 'extract-1',
        'status': 'pending',
      },
    };
  }
}

class _SuggestionFailingRestClient extends BackendRestClient {
  int uploadCount = 0;
  int captureCount = 0;
  final captureAssetIds = <List<String>>[];
  final suggestPersistValues = <bool>[];

  @override
  Future<Map<String, dynamic>> uploadBytes(
    String name,
    List<int> bytes, {
    required String spaceSlug,
    required String memoryScopeExternalRef,
    String? threadExternalRef,
    String? mime,
    bool extract = false,
    String? parserProfile,
    void Function(int, int)? onProgress,
    void Function(void Function())? onCreateCancel,
  }) async {
    uploadCount += 1;
    return {'id': 'asset-$uploadCount'};
  }

  @override
  Future<Map<String, dynamic>> createCapture({
    required String spaceSlug,
    required String memoryScopeExternalRef,
    required String threadExternalRef,
    required String text,
    required List<String> assetIds,
  }) async {
    captureCount += 1;
    captureAssetIds.add(List<String>.of(assetIds));
    return {'id': 'capture-$captureCount'};
  }

  @override
  Future<List<Map<String, dynamic>>> suggestLinks({
    required String spaceSlug,
    required String memoryScopeExternalRef,
    required String threadExternalRef,
    required String text,
    required String sourceType,
    required String sourceId,
    bool persist = false,
  }) async {
    suggestPersistValues.add(persist);
    throw DioException(
      requestOptions: RequestOptions(path: '/v1/link-suggestions'),
      type: DioExceptionType.connectionError,
      error: 'offline',
    );
  }
}

class _ExtractionDisabledRestClient extends BackendRestClient {
  final List<bool> extractAttempts = <bool>[];

  @override
  Future<Map<String, dynamic>> uploadBytes(
    String name,
    List<int> bytes, {
    required String spaceSlug,
    required String memoryScopeExternalRef,
    String? threadExternalRef,
    String? mime,
    bool extract = false,
    String? parserProfile,
    void Function(int, int)? onProgress,
    void Function(void Function())? onCreateCancel,
  }) async {
    extractAttempts.add(extract);
    if (extract) {
      final payload = {
        'error': {
          'code': 'memory.validation_error',
          'message': 'Asset extraction is disabled',
          'retryable': false,
        },
      };
      throw DioException(
        requestOptions: RequestOptions(path: '/v1/assets'),
        response: Response<dynamic>(
          requestOptions: RequestOptions(path: '/v1/assets'),
          statusCode: 422,
          data: payload,
        ),
        type: DioExceptionType.badResponse,
      );
    }
    return {'id': 'asset-fallback'};
  }
}

class _PolicyBlockedRestClient extends BackendRestClient {
  final bool asJsonString;

  _PolicyBlockedRestClient({required this.asJsonString});

  @override
  Future<Map<String, dynamic>> createCapture({
    required String spaceSlug,
    required String memoryScopeExternalRef,
    required String threadExternalRef,
    required String text,
    required List<String> assetIds,
  }) async {
    final payload = {
      'error': {
        'code': 'memory.policy_blocked',
        'message': 'Capture writes are disabled by policy',
        'retryable': false,
      },
    };
    throw DioException(
      requestOptions: RequestOptions(path: '/v1/captures'),
      response: Response<dynamic>(
        requestOptions: RequestOptions(path: '/v1/captures'),
        statusCode: 422,
        data: asJsonString ? jsonEncode(payload) : payload,
      ),
      type: DioExceptionType.badResponse,
    );
  }
}
