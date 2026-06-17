import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';
import 'package:frontend/src/features/chat/domain/entities/cost_usage.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_browser.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/presentation/widgets/memory_browser_tab.dart';
import 'package:mobx/mobx.dart';

void main() {
  testWidgets('memory browser renders sections and filters results', (
    tester,
  ) async {
    await tester.binding.setSurfaceSize(const Size(700, 700));
    addTearDown(() => tester.binding.setSurfaceSize(null));

    final repo = _BrowserRepo(snapshot: _snapshot());
    final store = ChatStore(repo, null);
    addTearDown(store.dispose);
    addTearDown(repo.close);

    runInAction(() {
      store.memoryBrowser.value = repo.snapshot;
    });

    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox(
            width: 610,
            height: 620,
            child: MemoryBrowserTab(store: store),
          ),
        ),
      ),
    );

    expect(find.text('Threads 1'), findsWidgets);
    expect(find.text('Captures 1'), findsWidgets);
    expect(find.text('Files 1'), findsWidgets);
    expect(find.text('Anchors 1'), findsWidgets);
    expect(find.text('Relations 3'), findsOneWidget);
    expect(find.text('alex-call'), findsOneWidget);
    expect(find.text('atlas.png'), findsOneWidget);
    expect(find.text('Alex'), findsWidgets);
    expect(find.text('capture -> fact'), findsOneWidget);

    await tester
        .tap(find.byKey(const ValueKey('memory_browser_anchor_anchor_1')));
    await tester.pumpAndSettle();

    expect(
      find.byKey(const ValueKey('memory_browser_anchor_dialog_anchor_1')),
      findsOneWidget,
    );
    expect(find.text('person anchor - active'), findsOneWidget);
    expect(find.text('key: alex'), findsOneWidget);
    expect(find.text('aliases: A. Carter'), findsOneWidget);
    expect(find.text('source: rule'), findsOneWidget);
    expect(find.textContaining('Stable contact from Atlas captures'),
        findsOneWidget);
    expect(
      find.textContaining(
        'Screenshot from Alex about Project Atlas memory. -> person: Alex',
      ),
      findsOneWidget,
    );
    expect(find.textContaining('matched person'), findsWidgets);
    expect(find.text('Related evidence'), findsOneWidget);
    expect(find.textContaining('capture - QuickCapture'), findsWidgets);

    await tester.tap(find.byTooltip('Close'));
    await tester.pumpAndSettle();

    await tester
        .tap(find.byKey(const ValueKey('memory_browser_add_anchor_button')));
    await tester.pumpAndSettle();

    expect(find.byKey(const ValueKey('memory_anchor_form_dialog')),
        findsOneWidget);
    await tester.enterText(
      find.byKey(const ValueKey('memory_anchor_label_field')),
      'Jordan',
    );
    await tester.enterText(
      find.byKey(const ValueKey('memory_anchor_aliases_field')),
      'J, Jordan',
    );
    await tester.enterText(
      find.byKey(const ValueKey('memory_anchor_description_field')),
      'Design partner',
    );
    await tester.tap(find.byKey(const ValueKey('memory_anchor_save_button')));
    await tester.pumpAndSettle();

    expect(repo.createdAnchors.single.kind, 'person');
    expect(repo.createdAnchors.single.label, 'Jordan');
    expect(repo.createdAnchors.single.aliases, ['J']);
    expect(repo.createdAnchors.single.description, 'Design partner');

    await tester.tap(
      find.byKey(const ValueKey('memory_browser_backfill_anchors_button')),
    );
    await tester.pumpAndSettle();

    expect(repo.backfillRequests, [100]);

    await tester
        .tap(find.byKey(const ValueKey('memory_browser_filter_anchors')));
    await tester.pumpAndSettle();

    expect(find.text('Anchors 1'), findsWidgets);
    expect(find.text('Alex'), findsOneWidget);
    expect(find.text('atlas.png'), findsNothing);

    await tester.tap(find.byKey(const ValueKey('memory_browser_filter_all')));
    await tester.enterText(
      find.byKey(const ValueKey('memory_browser_search_field')),
      'png',
    );
    await tester.pumpAndSettle();

    expect(find.text('Files 1'), findsWidgets);
    expect(find.text('atlas.png'), findsOneWidget);
    expect(find.text('Alex'), findsNothing);
  });
}

class _BrowserRepo implements ChatRepository {
  final MemoryBrowserSnapshot snapshot;
  final createdAnchors = <_CreatedAnchor>[];
  final backfillRequests = <int>[];
  final _messages = StreamController<ChatMessage>.broadcast();
  final _usage = StreamController<CostUsage>.broadcast();
  final _running = StreamController<bool>.broadcast();
  final _connection = StreamController<ConnectionStatus>.broadcast();

  _BrowserRepo({required this.snapshot});

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
  String currentMemoryScopeExternalRef() => 'project-atlas';

  @override
  void setActiveChat(String chatId) {}

  @override
  void setActiveMemoryScopeExternalRef(String externalRef) {}

  @override
  Future<MemoryBrowserSnapshot> getMemoryBrowser({int limit = 50}) async {
    return snapshot;
  }

  @override
  Future<MemoryBrowserAnchor> createMemoryAnchor({
    required String kind,
    required String label,
    List<String> aliases = const <String>[],
    String? description,
  }) async {
    createdAnchors.add(
      _CreatedAnchor(
        kind: kind,
        label: label,
        aliases: aliases,
        description: description,
      ),
    );
    return MemoryBrowserAnchor.fromMap({
      'id': 'anchor-created',
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
  Future<void> backfillMemoryAnchors({int limitPerSource = 100}) async {
    backfillRequests.add(limitPerSource);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _CreatedAnchor {
  final String kind;
  final String label;
  final List<String> aliases;
  final String? description;

  const _CreatedAnchor({
    required this.kind,
    required this.label,
    required this.aliases,
    required this.description,
  });
}

MemoryBrowserSnapshot _snapshot() {
  return MemoryBrowserSnapshot.fromMap({
    'generated_at': '2026-06-14T10:00:00Z',
    'memory_scope': {
      'id': 'scope-1',
      'space_id': 'space-1',
      'external_ref': 'project-atlas',
      'name': 'Project Atlas',
      'status': 'active',
      'created_at': '2026-06-14T09:00:00Z',
      'updated_at': '2026-06-14T10:00:00Z',
    },
    'threads': [
      {
        'id': 'thread-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'external_ref': 'alex-call',
        'status': 'active',
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
      },
    ],
    'captures': [
      {
        'id': 'capture-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'thread_id': 'thread-1',
        'source_agent': 'memo',
        'source_kind': 'manual',
        'event_type': 'QuickCapture',
        'actor_role': 'user',
        'text_preview': 'Screenshot from Alex about Project Atlas memory.',
        'status': 'accepted',
        'consolidation_status': 'pending',
        'trust_level': 'medium',
        'source_authority': 'user_statement',
        'sensitivity': 'medium',
        'data_classification': 'internal',
        'evidence_refs': <Map<String, dynamic>>[],
        'metadata': <String, dynamic>{},
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
        'occurred_at': '2026-06-14T09:30:00Z',
      },
    ],
    'assets': [
      {
        'id': 'asset-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'thread_id': 'thread-1',
        'filename': 'atlas.png',
        'content_type': 'image/png',
        'byte_size': 2048,
        'status': 'stored',
        'classification': 'internal',
        'metadata': <String, dynamic>{},
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
      },
    ],
    'anchors': [
      {
        'id': 'anchor-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'kind': 'person',
        'normalized_key': 'alex',
        'label': 'Alex',
        'aliases': ['Alex', 'A. Carter'],
        'description': 'Stable contact from Atlas captures.',
        'status': 'active',
        'metadata': {
          'creation_source': 'rule',
          'canonical_key': 'alex',
        },
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
      },
    ],
    'context_links': [
      {
        'id': 'link-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'source_type': 'capture',
        'source_id': 'capture-1',
        'target_type': 'fact',
        'target_id': 'fact-1',
        'relation_type': 'related_to',
        'confidence': 'high',
        'reason': 'same project',
        'status': 'active',
        'metadata': <String, dynamic>{},
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
      },
      {
        'id': 'link-2',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'source_type': 'capture',
        'source_id': 'capture-1',
        'target_type': 'anchor',
        'target_id': 'anchor-1',
        'relation_type': 'mentions',
        'confidence': 'high',
        'reason': 'matched person',
        'status': 'active',
        'metadata': {'target_label': 'Alex'},
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
      },
    ],
    'context_link_suggestions': [
      {
        'id': 'suggestion-1',
        'space_id': 'space-1',
        'memory_scope_id': 'scope-1',
        'source_type': 'capture',
        'source_id': 'capture-1',
        'target_type': 'anchor',
        'target_id': 'anchor-1',
        'relation_type': 'mentions',
        'confidence': 'medium',
        'reason': 'matched person',
        'score': 82,
        'status': 'pending',
        'metadata': {'target_label': 'Alex'},
        'created_at': '2026-06-14T09:00:00Z',
        'updated_at': '2026-06-14T10:00:00Z',
      },
    ],
    'stats': {
      'threads': 1,
      'captures': 1,
      'assets': 1,
      'anchors': 1,
      'context_links': 2,
      'context_link_suggestions': 1,
    },
    'diagnostics': {'browser_version': 'memory-browser-v1'},
  });
}
