import 'dart:async';
import 'dart:convert';
import 'dart:io';

Future<void> main() async {
  final config = MarionetteAnchorLifecycleConfig.fromEnv(Platform.environment);
  final runner = MarionetteAnchorLifecycleRunner(config);
  await runner.run();
}

class MarionetteAnchorLifecycleConfig {
  final String flutterBin;
  final String device;
  final String backendHost;
  final String backendPort;
  final String serviceToken;
  final String spaceSlug;
  final String scopeRef;
  final Uri? vmServiceUri;
  final bool keepAppRunning;
  final Duration startupTimeout;
  final Duration callTimeout;

  const MarionetteAnchorLifecycleConfig({
    required this.flutterBin,
    required this.device,
    required this.backendHost,
    required this.backendPort,
    required this.serviceToken,
    required this.spaceSlug,
    required this.scopeRef,
    required this.vmServiceUri,
    required this.keepAppRunning,
    required this.startupTimeout,
    required this.callTimeout,
  });

  factory MarionetteAnchorLifecycleConfig.fromEnv(
    Map<String, String> env,
  ) {
    final runId = env['MEMO_STACK_E2E_RUN_ID'] ??
        DateTime.now().millisecondsSinceEpoch.toString();
    final vmServiceValue = _env(env, 'MEMO_STACK_E2E_VM_SERVICE_URI');
    return MarionetteAnchorLifecycleConfig(
      flutterBin: _env(env, 'FLUTTER_BIN') ??
          _env(env, 'FLUTTER') ??
          _defaultFlutterBin(),
      device: _env(env, 'MEMO_STACK_E2E_DEVICE') ?? 'macos',
      backendHost: _env(env, 'MEMO_STACK_BACKEND_HOST') ?? '127.0.0.1',
      backendPort: _env(env, 'MEMO_STACK_BACKEND_PORT') ?? '7788',
      serviceToken: _env(env, 'MEMO_STACK_SERVICE_TOKEN') ?? 'local-dev-token',
      spaceSlug: _env(env, 'MEMO_STACK_SPACE_SLUG') ?? 'marionette-anchor-e2e',
      scopeRef: _env(env, 'MEMO_STACK_MEMORY_SCOPE_EXTERNAL_REF') ??
          'marionette-anchor-e2e-$runId',
      vmServiceUri:
          vmServiceValue == null ? null : _parseWebSocketUri(vmServiceValue),
      keepAppRunning: _truthy(env['MEMO_STACK_E2E_KEEP_APP_RUNNING']),
      startupTimeout: Duration(
        seconds:
            int.tryParse(env['MEMO_STACK_E2E_STARTUP_TIMEOUT'] ?? '') ?? 120,
      ),
      callTimeout: Duration(
        seconds: int.tryParse(env['MEMO_STACK_E2E_CALL_TIMEOUT'] ?? '') ?? 30,
      ),
    );
  }
}

class MarionetteAnchorLifecycleRunner {
  final MarionetteAnchorLifecycleConfig config;

  MarionetteAnchorLifecycleRunner(this.config);

  Future<void> run() async {
    final startedApp =
        config.vmServiceUri == null ? await _startFlutterApp(config) : null;
    final vmServiceUri = startedApp?.vmServiceUri ?? config.vmServiceUri!;
    VmServiceClient? client;
    MemoStackExtensionClient? memoStack;
    final runMarker = _runMarker(config.scopeRef);

    try {
      _log('connecting to VM service at $vmServiceUri');
      client = await VmServiceClient.connect(vmServiceUri, config.callTimeout);
      memoStack = MemoStackExtensionClient(client, config.callTimeout);
      await memoStack.init();

      final state = await memoStack.waitUntilReady();
      _expect(
        state['connection'] == 'connected',
        'frontend did not report backend connection',
      );

      await memoStack.call(
        'memoStack.createMemoryScope',
        {
          'externalRef': config.scopeRef,
          'name': 'Marionette Anchor E2E $runMarker',
        },
      );

      await _runCaptureLinkingFlow(memoStack, runMarker);
      await _runAttachmentCaptureFlow(memoStack, runMarker);
      final anchorBaselineState =
          await memoStack.call('memoStack.e2eState', {});
      final anchorBaseline =
          _int(anchorBaselineState['memoryBrowserAnchorCount']);
      final created = await memoStack.call(
        'memoStack.createMemoryAnchor',
        {
          'memoryScopeExternalRef': config.scopeRef,
          'kind': 'person',
          'label': 'Alex Script $runMarker',
          'aliases': 'Alex Script, AS-$runMarker',
          'description': 'Created by automated Marionette anchor lifecycle e2e',
        },
      );
      final targetAnchorId = _field(_map(created['anchor']), 'id');
      _expect(
        _int(created['memoryBrowserAnchorCount']) == anchorBaseline + 1,
        'create anchor did not add exactly one browser anchor',
      );
      _log('created anchor $targetAnchorId');

      final updated = await memoStack.call(
        'memoStack.updateMemoryAnchor',
        {
          'anchorId': targetAnchorId,
          'label': 'Alex Script $runMarker Updated',
          'aliases': 'Alex Script, AS-$runMarker, Alex Demo',
          'description': 'Updated by automated Marionette anchor lifecycle e2e',
        },
      );
      _expect(
        _field(_map(updated['anchor']), 'label').endsWith('Updated'),
        'update anchor did not return updated label',
      );

      final split = await memoStack.call(
        'memoStack.splitMemoryAnchorAlias',
        {
          'anchorId': targetAnchorId,
          'alias': 'AS-$runMarker',
          'newLabel': 'Alex Script Split $runMarker',
          'reason': 'automated Marionette anchor lifecycle e2e split',
        },
      );
      final splitAnchorId = _field(_map(split['splitAnchor']), 'id');
      _expect(
        _int(split['memoryBrowserAnchorCount']) == anchorBaseline + 2,
        'split alias did not produce the expected second anchor',
      );
      _log('split alias into anchor $splitAnchorId');

      final duplicate = await memoStack.call(
        'memoStack.createMemoryAnchor',
        {
          'memoryScopeExternalRef': config.scopeRef,
          'kind': 'person',
          'label': 'Alex Script Demo $runMarker',
          'aliases': 'Alex Demo, Alex Script',
          'description': 'Possible duplicate for automated merge e2e',
        },
      );
      final duplicateAnchorId = _field(_map(duplicate['anchor']), 'id');
      _log('created duplicate candidate $duplicateAnchorId');

      var reviewState = duplicate;
      if (_int(reviewState['pendingAnchorMergeSuggestionCount']) == 0) {
        reviewState = await memoStack.call(
          'memoStack.backfillMemoryAnchors',
          {'limitPerSource': '25'},
        );
      }
      _expect(
        _int(reviewState['pendingAnchorMergeSuggestionCount']) > 0,
        'backend did not produce an anchor merge suggestion',
      );

      var merged = await memoStack.call(
        'memoStack.mergeFirstAnchorSuggestion',
        {
          'sourceAnchorId': duplicateAnchorId,
          'targetAnchorId': targetAnchorId,
        },
      );
      if (merged['merged'] != true) {
        merged = await memoStack.call(
          'memoStack.mergeFirstAnchorSuggestion',
          {
            'sourceAnchorId': targetAnchorId,
            'targetAnchorId': duplicateAnchorId,
          },
        );
      }
      _expect(merged['merged'] == true, 'merge suggestion was not applied');
      final mergedSourceAnchorId = _field(merged, 'mergedSourceAnchorId');
      final mergedTargetAnchorId = _field(merged, 'mergedTargetAnchorId');
      final anchorsAfterMerge =
          _list(merged['memoryBrowserAnchors']).map(_map).toList();
      _expect(
        anchorsAfterMerge
            .every((anchor) => _field(anchor, 'id') != mergedSourceAnchorId),
        'merged source anchor is still visible in memory browser',
      );
      _expect(
        anchorsAfterMerge
            .any((anchor) => _field(anchor, 'id') == mergedTargetAnchorId),
        'merged target anchor is not visible in memory browser',
      );
      _log(
        'merged $mergedSourceAnchorId into $mergedTargetAnchorId '
        'with ${merged['pendingAnchorMergeSuggestionCount']} suggestions left',
      );

      await _cleanupRunAnchors(memoStack, runMarker);
      final cleanState = await memoStack.call('memoStack.e2eState', {});
      final remaining = _anchorsWithMarker(cleanState, runMarker);
      _expect(
        remaining.isEmpty,
        'cleanup left ${remaining.length} test anchors in memory browser',
      );

      _log('anchor lifecycle e2e passed');
    } finally {
      if (memoStack != null) {
        await _bestEffortCleanup(memoStack, runMarker);
      }
      await client?.close();
      if (startedApp != null && !config.keepAppRunning) {
        await startedApp.stop();
      }
    }
  }

  Future<void> _runCaptureLinkingFlow(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final target = await memoStack.call(
      'memoStack.createMemoryAnchor',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'kind': 'project',
        'label': 'Project Capture Target $runMarker',
        'aliases': 'Capture Target $runMarker, Project Link $runMarker',
        'description': 'Target anchor for automated capture linking e2e',
      },
    );
    final targetAnchorId = _field(_map(target['anchor']), 'id');
    _log('created capture link target $targetAnchorId');

    final captured = await memoStack.call(
      'memoStack.submitCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Capture Link Thread $runMarker',
        'text': 'Alex confirmed Project Capture Target $runMarker should be '
            'linked to the onboarding screenshot note.',
      },
    );
    _expect(
      _int(captured['captureCount']) > 0,
      'submitCapture did not create a visible memory capture',
    );
    _expect(
      _field(_map(captured['latestCapture']), 'preview').contains(runMarker),
      'latest capture does not contain the run marker',
    );

    final pending = await _waitForPendingContextLinkSuggestion(
      memoStack,
      targetAnchorId: targetAnchorId,
    );
    _expect(
      _int(pending['pendingLinkSuggestionCount']) > 0,
      'capture did not produce a pending context-link suggestion',
    );
    _log(
      'capture produced ${pending['pendingLinkSuggestionCount']} '
      'context-link suggestions',
    );

    final reviewed = await memoStack.call(
      'memoStack.reviewFirstPendingLinkSuggestion',
      {
        'approve': 'true',
        'targetId': targetAnchorId,
      },
    );
    _expect(
        reviewed['reviewed'] == true, 'no context-link suggestion reviewed');
    _expect(
      reviewed['reviewedTargetId'] == targetAnchorId,
      'reviewed suggestion target did not match the capture target anchor',
    );
    final linked = await _waitForContextLinkCount(memoStack);
    _expect(
      _int(linked['memoryBrowserContextLinkCount']) > 0,
      'approved context-link suggestion did not create a visible link',
    );
    _log(
      'approved context-link suggestion ${reviewed['reviewedSuggestionId']} '
      'for capture flow',
    );
  }

  Future<void> _runAttachmentCaptureFlow(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final captured = await memoStack.call(
      'memoStack.submitAttachmentCapture',
      {
        'memoryScopeExternalRef': config.scopeRef,
        'threadTitle': 'Attachment Capture Thread $runMarker',
        'filename': 'attachment-$runMarker.txt',
        'mime': 'text/plain',
        'content': 'Attachment E2E $runMarker: Alex attached file evidence '
            'for Project Capture Target $runMarker.',
        'text': 'Attachment capture $runMarker should preserve file evidence.',
      },
    );
    final uploadedAssetIds =
        _list(captured['uploadedAssetIds']).map((item) => '$item').toList();
    _expect(
      uploadedAssetIds.length == 1,
      'submitAttachmentCapture did not return exactly one uploaded asset id',
    );
    final assetId = uploadedAssetIds.single;
    final latestCapture = _map(captured['latestCapture']);
    final captureAssetIds =
        _list(latestCapture['assetIds']).map((item) => '$item').toSet();
    _expect(
      captureAssetIds.contains(assetId),
      'latest capture does not reference uploaded asset $assetId',
    );

    final extraction = await _waitForAssetExtraction(
      memoStack,
      assetId: assetId,
    );
    _expect(
      _field(extraction, 'parserName') == 'simple_text',
      'text attachment was not parsed by simple_text',
    );
    _expect(
      _list(extraction['resultDocumentIds']).isNotEmpty,
      'text attachment extraction did not create a document',
    );
    _expect(
      _list(extraction['artifactTypes']).contains('markdown'),
      'text attachment extraction did not create a markdown artifact',
    );
    _log('attachment capture linked asset $assetId to extracted document');
  }

  Future<Map<String, dynamic>> _waitForPendingContextLinkSuggestion(
    MemoStackExtensionClient memoStack, {
    required String targetAnchorId,
  }) async {
    final deadline = DateTime.now().add(config.callTimeout);
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await memoStack.call('memoStack.refresh', {});
      final matching = _list(lastState['pendingLinkSuggestions'])
          .map(_map)
          .where((item) => _field(item, 'targetId') == targetAnchorId)
          .toList(growable: false);
      if (matching.isNotEmpty) {
        return lastState;
      }
      await Future<void>.delayed(const Duration(milliseconds: 400));
    }
    throw StateError(
      'No pending context-link suggestion before timeout: $lastState',
    );
  }

  Future<Map<String, dynamic>> _waitForAssetExtraction(
    MemoStackExtensionClient memoStack, {
    required String assetId,
  }) async {
    final deadline = DateTime.now().add(
      Duration(seconds: config.callTimeout.inSeconds * 2),
    );
    Map<String, dynamic>? lastState;
    Map<String, dynamic>? lastJob;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await memoStack.call('memoStack.refresh', {});
      for (final item in _list(lastState['assetExtractions'])) {
        final job = _map(item);
        if (_field(job, 'assetId') != assetId) continue;
        lastJob = job;
        final status = _field(job, 'status');
        if (status == 'succeeded') {
          return job;
        }
        if (status == 'failed' ||
            status == 'unsupported' ||
            status == 'canceled') {
          throw StateError(
            'Asset extraction reached terminal failure for $assetId: $job',
          );
        }
      }
      await Future<void>.delayed(const Duration(milliseconds: 500));
    }
    throw StateError(
      'No succeeded asset extraction before timeout for $assetId: '
      'lastJob=$lastJob lastState=$lastState',
    );
  }

  Future<Map<String, dynamic>> _waitForContextLinkCount(
    MemoStackExtensionClient memoStack,
  ) async {
    final deadline = DateTime.now().add(config.callTimeout);
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      lastState = await memoStack.call('memoStack.refresh', {});
      if (_int(lastState['memoryBrowserContextLinkCount']) > 0) {
        return lastState;
      }
      await Future<void>.delayed(const Duration(milliseconds: 400));
    }
    throw StateError('No visible context link before timeout: $lastState');
  }

  Future<void> _cleanupRunAnchors(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    final state = await memoStack.call('memoStack.e2eState', {});
    final anchors = _anchorsWithMarker(state, runMarker);
    for (final anchor in anchors) {
      await memoStack.call(
        'memoStack.deleteMemoryAnchor',
        {
          'anchorId': _field(anchor, 'id'),
          'reason': 'automated Marionette anchor lifecycle e2e cleanup',
        },
      );
    }
  }

  Future<void> _bestEffortCleanup(
    MemoStackExtensionClient memoStack,
    String runMarker,
  ) async {
    try {
      await memoStack.call(
        'memoStack.switchMemoryScope',
        {'externalRef': config.scopeRef},
      );
      await _cleanupRunAnchors(memoStack, runMarker);
    } catch (error) {
      _log('cleanup warning: $error');
    }
  }
}

class FlutterRunHandle {
  final Process process;
  final Uri vmServiceUri;
  final Future<int> exitCode;

  FlutterRunHandle({
    required this.process,
    required this.vmServiceUri,
    required this.exitCode,
  });

  Future<void> stop() async {
    if (await _hasExited(exitCode)) return;
    try {
      process.stdin.writeln('q');
      await exitCode.timeout(const Duration(seconds: 15));
    } on Object {
      process.kill();
      await exitCode.timeout(
        const Duration(seconds: 5),
        onTimeout: () => -1,
      );
    }
  }
}

class VmServiceClient {
  final WebSocket _socket;
  final Duration _callTimeout;
  final Map<int, Completer<Map<String, dynamic>>> _pending =
      <int, Completer<Map<String, dynamic>>>{};
  late final StreamSubscription<dynamic> _subscription;
  int _nextId = 1;

  VmServiceClient._(this._socket, this._callTimeout) {
    _subscription = _socket.listen(
      _onMessage,
      onError: _onError,
      onDone: _onDone,
    );
  }

  static Future<VmServiceClient> connect(
    Uri uri,
    Duration callTimeout,
  ) async {
    final socket = await WebSocket.connect(uri.toString());
    return VmServiceClient._(socket, callTimeout);
  }

  Future<Map<String, dynamic>> request(
    String method, {
    Map<String, dynamic> params = const <String, dynamic>{},
  }) async {
    final id = _nextId++;
    final completer = Completer<Map<String, dynamic>>();
    _pending[id] = completer;
    _socket.add(
      jsonEncode({
        'jsonrpc': '2.0',
        'id': id,
        'method': method,
        'params': params,
      }),
    );
    final response = await completer.future.timeout(
      _callTimeout,
      onTimeout: () {
        _pending.remove(id);
        throw TimeoutException('VM service call timed out: $method');
      },
    );
    if (response['error'] != null) {
      throw StateError('VM service call failed: $method ${response['error']}');
    }
    return response;
  }

  Future<void> close() async {
    for (final completer in _pending.values) {
      if (!completer.isCompleted) {
        completer.completeError(StateError('VM service client closed'));
      }
    }
    _pending.clear();
    await _subscription.cancel();
    await _socket.close();
  }

  void _onMessage(dynamic message) {
    final text = message is List<int> ? utf8.decode(message) : '$message';
    final decoded = jsonDecode(text);
    if (decoded is! Map<String, dynamic>) return;
    final id = decoded['id'];
    if (id is! int) return;
    final completer = _pending.remove(id);
    if (completer == null || completer.isCompleted) return;
    completer.complete(decoded);
  }

  void _onError(Object error) {
    for (final completer in _pending.values) {
      if (!completer.isCompleted) completer.completeError(error);
    }
    _pending.clear();
  }

  void _onDone() {
    for (final completer in _pending.values) {
      if (!completer.isCompleted) {
        completer.completeError(StateError('VM service socket closed'));
      }
    }
    _pending.clear();
  }
}

class MemoStackExtensionClient {
  final VmServiceClient _vm;
  final Duration _callTimeout;
  String? _isolateId;

  MemoStackExtensionClient(this._vm, this._callTimeout);

  Future<void> init() async {
    final response = await _vm.request('getVM');
    final result = _map(response['result']);
    final isolates = _list(result['isolates']);
    if (isolates.isEmpty) {
      throw StateError('VM service returned no isolates');
    }
    _isolateId = _field(_map(isolates.first), 'id');
  }

  Future<Map<String, dynamic>> waitUntilReady() async {
    final deadline = DateTime.now().add(
      Duration(seconds: _callTimeout.inSeconds * 2),
    );
    Object? lastError;
    Map<String, dynamic>? lastState;
    while (DateTime.now().isBefore(deadline)) {
      try {
        final state = await call('memoStack.e2eState', {});
        lastState = state;
        if (state['activeChatId'] != null &&
            state['connection'] == 'connected') {
          return state;
        }
        final refreshed = await call('memoStack.refresh', {});
        lastState = refreshed;
        if (refreshed['activeChatId'] != null &&
            refreshed['connection'] == 'connected') {
          return refreshed;
        }
      } catch (error) {
        lastError = error;
      }
      await Future<void>.delayed(const Duration(milliseconds: 400));
    }
    throw StateError(
      'Memo Stack E2E extension not ready: '
      'lastState=$lastState lastError=$lastError',
    );
  }

  Future<Map<String, dynamic>> call(
    String extension,
    Map<String, String> args,
  ) async {
    final isolateId = _isolateId;
    if (isolateId == null) {
      throw StateError('Memo Stack extension client is not initialized');
    }
    final response = await _vm.request(
      'ext.flutter.$extension',
      params: {
        'isolateId': isolateId,
        ...args,
      },
    );
    final payload = _decodeExtensionPayload(response['result']);
    if (payload['ok'] != true) {
      throw StateError('Memo Stack extension failed: $extension $payload');
    }
    return payload;
  }
}

Future<FlutterRunHandle> _startFlutterApp(
  MarionetteAnchorLifecycleConfig config,
) async {
  final args = <String>[
    'run',
    '-d',
    config.device,
    '--debug',
    '--dart-define=MEMO_STACK_BACKEND_HOST=${config.backendHost}',
    '--dart-define=MEMO_STACK_BACKEND_PORT=${config.backendPort}',
    '--dart-define=MEMO_STACK_SERVICE_TOKEN=${config.serviceToken}',
    '--dart-define=MEMO_STACK_SPACE_SLUG=${config.spaceSlug}',
    '--dart-define=MEMO_STACK_MEMORY_SCOPE_EXTERNAL_REF=${config.scopeRef}',
  ];
  _log('starting ${config.flutterBin} ${args.join(' ')}');
  final process = await Process.start(
    config.flutterBin,
    args,
    workingDirectory: Directory.current.path,
  );
  final serviceUri = Completer<Uri>();
  final exitCode = process.exitCode;

  process.stdout
      .transform(utf8.decoder)
      .transform(const LineSplitter())
      .listen((line) {
    _logFlutter(line);
    final uri = _extractVmServiceUri(line);
    if (uri != null && !serviceUri.isCompleted) {
      serviceUri.complete(_toWebSocketUri(uri));
    }
  });
  process.stderr
      .transform(utf8.decoder)
      .transform(const LineSplitter())
      .listen(_logFlutter);

  unawaited(
    exitCode.then((code) {
      if (!serviceUri.isCompleted) {
        serviceUri.completeError(
          StateError('flutter run exited before VM service was ready: $code'),
        );
      }
    }),
  );

  final vmServiceUri = await serviceUri.future.timeout(
    config.startupTimeout,
    onTimeout: () {
      process.kill();
      throw TimeoutException(
        'flutter run did not expose VM service in '
        '${config.startupTimeout.inSeconds}s',
      );
    },
  );
  return FlutterRunHandle(
    process: process,
    vmServiceUri: vmServiceUri,
    exitCode: exitCode,
  );
}

Map<String, dynamic> _decodeExtensionPayload(dynamic raw) {
  if (raw is Map<String, dynamic>) {
    final payload = raw['payload'];
    if (payload is String) {
      final decoded = jsonDecode(payload);
      if (decoded is Map<String, dynamic>) return decoded;
    }
    if (raw['ok'] != null) return raw;
  }
  if (raw is String) {
    final decoded = jsonDecode(raw);
    if (decoded is Map<String, dynamic>) return decoded;
  }
  throw StateError('Unsupported extension payload: $raw');
}

Uri? _extractVmServiceUri(String line) {
  if (!line.contains('Dart VM Service')) return null;
  final match = RegExp(r'https?://\S+').firstMatch(line);
  if (match == null) return null;
  return Uri.parse(match.group(0)!.replaceAll(RegExp(r'[),.]+$'), ''));
}

Uri _parseWebSocketUri(String value) => _toWebSocketUri(Uri.parse(value));

Uri _toWebSocketUri(Uri uri) {
  if (uri.scheme == 'ws' || uri.scheme == 'wss') return uri;
  final path = uri.path.endsWith('/') ? '${uri.path}ws' : '${uri.path}/ws';
  return uri.replace(
    scheme: uri.scheme == 'https' ? 'wss' : 'ws',
    path: path,
  );
}

List<Map<String, dynamic>> _anchorsWithMarker(
  Map<String, dynamic> state,
  String marker,
) {
  return _list(state['memoryBrowserAnchors'])
      .map(_map)
      .where((anchor) => _field(anchor, 'label').contains(marker))
      .toList(growable: false);
}

Map<String, dynamic> _map(dynamic value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  throw StateError('Expected map, got $value');
}

List<dynamic> _list(dynamic value) {
  if (value is List) return value;
  if (value == null) return const <dynamic>[];
  throw StateError('Expected list, got $value');
}

String _field(Map<String, dynamic> map, String key) {
  final value = map[key];
  if (value == null || value.toString().isEmpty) {
    throw StateError('Missing field: $key in $map');
  }
  return value.toString();
}

int _int(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '') ?? 0;
}

void _expect(bool condition, String message) {
  if (!condition) throw StateError(message);
}

String _runMarker(String scopeRef) {
  final parts = scopeRef.split('-');
  return parts.isEmpty ? scopeRef : parts.last;
}

String? _env(Map<String, String> env, String key) {
  final value = env[key]?.trim();
  return value == null || value.isEmpty ? null : value;
}

bool _truthy(String? value) {
  final normalized = value?.trim().toLowerCase();
  return normalized == '1' || normalized == 'true' || normalized == 'yes';
}

String _defaultFlutterBin() {
  final home = Platform.environment['HOME'];
  if (home != null) {
    final candidate = File('$home/dev/flutter/bin/flutter');
    if (candidate.existsSync()) return candidate.path;
  }
  return 'flutter';
}

Future<bool> _hasExited(Future<int> exitCode) async {
  final marker = Object();
  final value = await Future.any<Object>([
    exitCode.then<Object>((_) => true),
    Future<Object>.delayed(Duration.zero, () => marker),
  ]);
  return value == true;
}

void _log(String message) {
  stdout.writeln('[marionette-anchor-e2e] $message');
}

void _logFlutter(String message) {
  stdout.writeln('[flutter] $message');
}
