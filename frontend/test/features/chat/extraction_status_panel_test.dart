import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';
import 'package:frontend/src/features/chat/domain/entities/cost_usage.dart';
import 'package:frontend/src/features/chat/domain/entities/document_chunk.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_capture.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/presentation/widgets/extraction_status_panel.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';
import 'package:mobx/mobx.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets('shows determinate extraction progress and media quota',
      (tester) async {
    final repo = _PanelRepo();
    final store = ChatStore(
      repo,
      null,
      assetExtractionPollInterval: const Duration(minutes: 5),
    );
    addTearDown(store.dispose);
    addTearDown(repo.close);

    store.assetExtractions = ObservableList.of([
      AssetExtractionJob.fromMap({
        'id': 'extract-1',
        'asset_id': 'asset-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'running',
        'attempt_count': 1,
        'result_document_ids': <String>[],
        'artifacts': <Map<String, dynamic>>[],
        'metadata': <String, dynamic>{},
        'progress': {
          'stage': 'extracting_content',
          'percent': 45,
          'message': 'Extracting searchable content',
          'terminal': false,
        },
        'usage': {
          'plan_tier': 'free',
          'media_analysis_seconds_requested': 7200,
          'media_analysis_seconds_limit': 36000,
        },
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      }),
    ]);

    await tester.pumpWidget(
      Provider<ChatStore>.value(
        value: store,
        child: MaterialApp(
          theme: _testTheme(),
          home: const Scaffold(body: ExtractionStatusPanel()),
        ),
      ),
    );

    expect(find.text('Running 45% - standard_local'), findsOneWidget);
    expect(find.text('Extracting searchable content'), findsOneWidget);
    expect(find.text('Media quota: 2h of 10h'), findsOneWidget);
    final progress = tester.widget<LinearProgressIndicator>(
      find.byKey(const ValueKey('asset_extraction_progress_extract_1')),
    );
    expect(progress.value, 0.45);
  });

  testWidgets('shows reconciled media quota after extraction completes',
      (tester) async {
    final repo = _PanelRepo();
    final store = ChatStore(
      repo,
      null,
      assetExtractionPollInterval: const Duration(minutes: 5),
    );
    addTearDown(store.dispose);
    addTearDown(repo.close);

    store.assetExtractions = ObservableList.of([
      AssetExtractionJob.fromMap({
        'id': 'extract-1',
        'asset_id': 'asset-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'succeeded',
        'attempt_count': 1,
        'parser_name': 'media_metadata',
        'result_document_ids': ['doc-1'],
        'artifacts': <Map<String, dynamic>>[],
        'metadata': {
          'normalized_content_type': 'audio/wav',
          'duration_seconds': 1,
        },
        'progress': <String, dynamic>{},
        'usage': {
          'plan_tier': 'free',
          'media_analysis_seconds_requested': 600,
          'media_analysis_seconds_actual': 1,
          'media_analysis_seconds_delta': -599,
          'media_analysis_seconds_final': 1,
          'media_analysis_seconds_limit': 36000,
          'reconciled': true,
        },
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      }),
    ]);

    await tester.pumpWidget(
      Provider<ChatStore>.value(
        value: store,
        child: MaterialApp(
          theme: _testTheme(),
          home: const Scaffold(body: ExtractionStatusPanel()),
        ),
      ),
    );

    expect(
      find.text('Media quota: 1m final of 10h (10m reserved)'),
      findsOneWidget,
    );
  });

  testWidgets('shows compact extraction evidence summaries', (tester) async {
    final repo = _PanelRepo();
    final store = ChatStore(
      repo,
      null,
      assetExtractionPollInterval: const Duration(minutes: 5),
    );
    addTearDown(store.dispose);
    addTearDown(repo.close);

    store.assetExtractions = ObservableList.of([
      AssetExtractionJob.fromMap({
        'id': 'extract-pdf',
        'asset_id': 'asset-pdf',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'succeeded',
        'attempt_count': 1,
        'parser_name': 'pypdf_text',
        'result_document_ids': ['doc-1'],
        'artifacts': <Map<String, dynamic>>[],
        'metadata': {
          'normalized_content_type': 'application/pdf',
          'page_count': 1,
        },
        'progress': <String, dynamic>{},
        'usage': <String, dynamic>{},
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      }),
      AssetExtractionJob.fromMap({
        'id': 'extract-image',
        'asset_id': 'asset-image',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'succeeded',
        'attempt_count': 1,
        'parser_name': 'image_metadata',
        'result_document_ids': ['doc-2'],
        'artifacts': <Map<String, dynamic>>[],
        'metadata': {
          'normalized_content_type': 'image/png',
          'image_width': 120,
          'image_height': 40,
        },
        'progress': <String, dynamic>{},
        'usage': <String, dynamic>{},
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      }),
      AssetExtractionJob.fromMap({
        'id': 'extract-transcript',
        'asset_id': 'asset-transcript',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'succeeded',
        'attempt_count': 1,
        'parser_name': 'timed_text_transcript',
        'result_document_ids': ['doc-3'],
        'artifacts': <Map<String, dynamic>>[],
        'metadata': {
          'normalized_content_type': 'application/x-subrip',
          'segment_count': 2,
        },
        'progress': <String, dynamic>{},
        'usage': <String, dynamic>{},
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      }),
    ]);

    await tester.pumpWidget(
      Provider<ChatStore>.value(
        value: store,
        child: MaterialApp(
          theme: _testTheme(),
          home: const Scaffold(body: ExtractionStatusPanel()),
        ),
      ),
    );

    expect(find.text('PDF: 1 page - 1 docs - 0 artifacts'), findsOneWidget);
    expect(find.text('Image: 120x40 - 1 docs - 0 artifacts'), findsOneWidget);
    expect(
      find.text('Transcript: 2 segments - 1 docs - 0 artifacts'),
      findsOneWidget,
    );
  });

  testWidgets('opens extraction evidence dialog with source refs',
      (tester) async {
    final repo = _PanelRepo();
    repo.chunksByDocumentId['doc-1'] = [
      DocumentChunk.fromMap({
        'id': 'chunk-1',
        'document_id': 'doc-1',
        'text': 'Alex confirmed the Q3 rollout decision in the call.',
        'kind': 'document_section',
        'sequence': 0,
        'status': 'active',
        'classification': 'internal',
        'source_refs': [
          {
            'source_type': 'asset_extraction',
            'source_id': 'extract-1',
            'asset_id': 'asset-1',
            'kind': 'transcript_segment',
            'page_number': 2,
            'time_start_ms': 1000,
            'time_end_ms': 3000,
            'quote_preview': 'Alex confirmed the Q3 rollout decision',
          },
        ],
        'metadata': <String, dynamic>{},
      }),
    ];
    final store = ChatStore(
      repo,
      null,
      assetExtractionPollInterval: const Duration(minutes: 5),
    );
    addTearDown(store.dispose);
    addTearDown(repo.close);

    store.assetExtractions = ObservableList.of([
      AssetExtractionJob.fromMap({
        'id': 'extract-1',
        'asset_id': 'asset-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'parser_profile': 'standard_local',
        'parser_config_hash': 'hash',
        'source_sha256_hex': 'sha',
        'status': 'succeeded',
        'attempt_count': 1,
        'parser_name': 'timed_text_transcript',
        'result_document_ids': ['doc-1'],
        'artifacts': <Map<String, dynamic>>[],
        'metadata': {'filename': 'alex-call.srt'},
        'progress': <String, dynamic>{},
        'usage': <String, dynamic>{},
        'created_at': '2026-06-13T00:00:00Z',
        'updated_at': '2026-06-13T00:01:00Z',
      }),
    ]);

    await tester.pumpWidget(
      Provider<ChatStore>.value(
        value: store,
        child: MaterialApp(
          theme: _testTheme(),
          home: const Scaffold(body: ExtractionStatusPanel()),
        ),
      ),
    );

    await tester
        .tap(find.byKey(const ValueKey('asset_extraction_evidence_extract_1')));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('asset_extraction_evidence_dialog')),
        findsOneWidget);
    expect(find.text('Evidence'), findsOneWidget);
    expect(find.text('alex-call.srt - 1 docs'), findsOneWidget);
    expect(
      find.text('Alex confirmed the Q3 rollout decision in the call.'),
      findsOneWidget,
    );
    expect(find.text('Page 2 00:01-00:03'), findsOneWidget);
  });
}

ThemeData _testTheme() {
  return ThemeData(
    useMaterial3: true,
    extensions: [
      const AppThemeColors(
        userBubbleBg: Color(0xFF1565C0),
        userBubbleFg: Colors.white,
        assistantBubbleBg: Color(0xFFF3F4F6),
        assistantBubbleFg: Color(0xFF111827),
        surfaceBorder: Color(0xFFE5E7EB),
        usageBorder: Color(0xFFFFB74D),
        usageFill: Color(0xFFFFF3E0),
        actionTealBorder: Color(0xFF26A69A),
        actionTealFill: Color(0xFFE0F2F1),
        actionIndigoBorder: Color(0xFF5C6BC0),
        actionIndigoFill: Color(0xFFE8EAF6),
        actionPurpleBorder: Color(0xFF9575CD),
        actionPurpleFill: Color(0xFFF3E5F5),
        actionBlueGreyBorder: Color(0xFF78909C),
        actionBlueGreyFill: Color(0xFFECEFF1),
        actionGreenBorder: Color(0xFF66BB6A),
        actionGreenFill: Color(0xFFE8F5E9),
        actionOrangeBorder: Color(0xFFFFA726),
        actionOrangeFill: Color(0xFFFFF3E0),
      ),
      const AppThemeStyles(
        body: TextStyle(fontSize: 14, height: 1.35),
        bodySmall: TextStyle(fontSize: 12, height: 1.30),
        caption: TextStyle(fontSize: 11, height: 1.25),
        labelSmall: TextStyle(
          fontSize: 10,
          height: 1.20,
          fontWeight: FontWeight.w600,
        ),
      ),
    ],
  );
}

class _PanelRepo implements ChatRepository {
  final _messages = StreamController<ChatMessage>.broadcast();
  final _usage = StreamController<CostUsage>.broadcast();
  final _running = StreamController<bool>.broadcast();
  final _connection = StreamController<ConnectionStatus>.broadcast();
  final chunksByDocumentId = <String, List<DocumentChunk>>{};

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
  String currentMemoryScopeExternalRef() => 'default';

  @override
  void setActiveChat(String chatId) {}

  @override
  void setActiveMemoryScopeExternalRef(String externalRef) {}

  @override
  Future<List<DocumentChunk>> listDocumentChunks(String documentId) async {
    return chunksByDocumentId[documentId] ?? const <DocumentChunk>[];
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
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}
