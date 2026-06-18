part of 'marionette_anchor_lifecycle_e2e.dart';

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

class InfinityContextExtensionClient {
  final VmServiceClient _vm;
  final Duration _callTimeout;
  String? _isolateId;

  InfinityContextExtensionClient(this._vm, this._callTimeout);

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
      'Infinity Context E2E extension not ready: '
      'lastState=$lastState lastError=$lastError',
    );
  }

  Future<Map<String, dynamic>> call(
    String extension,
    Map<String, String> args,
  ) async {
    final isolateId = _isolateId;
    if (isolateId == null) {
      throw StateError('Infinity Context extension client is not initialized');
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
      throw StateError('Infinity Context extension failed: $extension $payload');
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
    '--dart-define=INFINITY_CONTEXT_BACKEND_HOST=${config.backendHost}',
    '--dart-define=INFINITY_CONTEXT_BACKEND_PORT=${config.backendPort}',
    '--dart-define=INFINITY_CONTEXT_SERVICE_TOKEN=${config.serviceToken}',
    '--dart-define=INFINITY_CONTEXT_SPACE_SLUG=${config.spaceSlug}',
    '--dart-define=INFINITY_CONTEXT_MEMORY_SCOPE_EXTERNAL_REF=${config.scopeRef}',
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
