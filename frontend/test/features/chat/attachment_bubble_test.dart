import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/src/features/chat/application/services/downloaded_file_opener.dart';
import 'package:frontend/src/features/chat/application/services/open_chat_attachment.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/connection_status.dart';
import 'package:frontend/src/features/chat/domain/entities/cost_usage.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';
import 'package:frontend/src/features/chat/presentation/widgets/attachment_bubble.dart';
import 'package:frontend/src/presentation/theme/app_theme.dart';
import 'package:provider/provider.dart';

void main() {
  testWidgets(
      'open button delegates attachment download and opening to use case',
      (tester) async {
    final repo = _AttachmentRepo();
    final opener = _FakeDownloadedFileOpener();
    addTearDown(repo.close);

    await _pumpAttachment(
      tester,
      repo: repo,
      opener: opener,
      child: const AttachmentBubble(name: 'report.pdf', fileId: 'file-42'),
    );

    await tester.tap(find.text('Open'));
    await tester.pump();

    expect(repo.downloadedFileIds, ['file-42']);
    expect(opener.requests, hasLength(1));
    expect(opener.requests.single.suggestedName, 'report.pdf');
    expect(opener.requests.single.bytes, [7, 8, 9]);
    expect(opener.requests.single.namespace, isNull);
  });

  testWidgets('open button reports attachment open failures', (tester) async {
    final repo = _AttachmentRepo();
    final opener = _FakeDownloadedFileOpener(throwOnOpen: true);
    addTearDown(repo.close);

    await _pumpAttachment(
      tester,
      repo: repo,
      opener: opener,
      child: const AttachmentBubble(name: 'report.pdf', fileId: 'file-42'),
    );

    await tester.tap(find.text('Open'));
    await tester.pump();

    expect(find.textContaining('Open attachment failed'), findsOneWidget);
    expect(repo.downloadedFileIds, ['file-42']);
  });

  testWidgets('open button reports missing attachment file id', (tester) async {
    final repo = _AttachmentRepo();
    final opener = _FakeDownloadedFileOpener();
    addTearDown(repo.close);

    await _pumpAttachment(
      tester,
      repo: repo,
      opener: opener,
      child: const AttachmentBubble(name: 'report.pdf', fileId: ''),
    );

    await tester.tap(find.text('Open'));
    await tester.pump();

    expect(find.textContaining('Open attachment failed'), findsOneWidget);
    expect(repo.downloadedFileIds, isEmpty);
    expect(opener.requests, isEmpty);
  });
}

Future<void> _pumpAttachment(
  WidgetTester tester, {
  required _AttachmentRepo repo,
  required DownloadedFileOpener opener,
  required Widget child,
}) async {
  await tester.pumpWidget(
    MultiProvider(
      providers: [
        Provider<OpenChatAttachment>(
          create: (_) => OpenChatAttachment(repo: repo, opener: opener),
        ),
      ],
      child: MaterialApp(
        theme: _testTheme(),
        home: Scaffold(body: child),
      ),
    ),
  );
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

class _AttachmentRepo implements ChatRepository {
  final downloadedFileIds = <String>[];
  final _messages = StreamController<ChatMessage>.broadcast();
  final _usage = StreamController<CostUsage>.broadcast();
  final _running = StreamController<bool>.broadcast();
  final _connection = StreamController<ConnectionStatus>.broadcast();

  Future<void> close() async {
    await _messages.close();
    await _usage.close();
    await _running.close();
    await _connection.close();
  }

  @override
  Future<List<int>> downloadFile(String id) async {
    downloadedFileIds.add(id);
    return <int>[7, 8, 9];
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
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

class _OpenRequest {
  final String suggestedName;
  final List<int> bytes;
  final String? namespace;

  const _OpenRequest({
    required this.suggestedName,
    required this.bytes,
    required this.namespace,
  });
}

class _FakeDownloadedFileOpener implements DownloadedFileOpener {
  final bool throwOnOpen;
  final requests = <_OpenRequest>[];

  _FakeDownloadedFileOpener({this.throwOnOpen = false});

  @override
  Future<OpenedDownloadedFile> openBytes({
    required String suggestedName,
    required List<int> bytes,
    String? namespace,
  }) async {
    requests.add(
      _OpenRequest(
        suggestedName: suggestedName,
        bytes: List<int>.of(bytes),
        namespace: namespace,
      ),
    );
    if (throwOnOpen) {
      throw const DownloadedFileOpenException('open failed');
    }
    return const OpenedDownloadedFile(path: '/tmp/opened');
  }
}
