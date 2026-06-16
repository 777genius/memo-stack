import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;

import 'package:flutter/widgets.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_session.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_capture.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_scope.dart';
import 'package:provider/provider.dart';

typedef ChatStoreResolver = ChatStore Function();

class MemoStackMarionetteE2eBridge extends StatefulWidget {
  final Widget child;

  const MemoStackMarionetteE2eBridge({
    required this.child,
    super.key,
  });

  @override
  State<MemoStackMarionetteE2eBridge> createState() =>
      _MemoStackMarionetteE2eBridgeState();
}

class _MemoStackMarionetteE2eBridgeState
    extends State<MemoStackMarionetteE2eBridge> {
  static MemoStackMarionetteE2eCommandHandler? _activeHandler;
  static final Set<String> _registeredExtensions = <String>{};

  @override
  void initState() {
    super.initState();
    _registerExtensions();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _activeHandler = MemoStackMarionetteE2eCommandHandler(() {
      if (!mounted) {
        throw StateError('Memo Stack E2E bridge is not mounted');
      }
      return context.read<ChatStore>();
    });
  }

  @override
  void dispose() {
    _activeHandler = null;
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => widget.child;

  static void _registerExtensions() {
    _register(
      'memoStack.e2eState',
      (handler, params) => handler.state(),
    );
    _register(
      'memoStack.refresh',
      (handler, params) => handler.refresh(),
    );
    _register(
      'memoStack.createMemoryScope',
      (handler, params) => handler.createMemoryScope(params),
    );
    _register(
      'memoStack.switchMemoryScope',
      (handler, params) => handler.switchMemoryScope(params),
    );
    _register(
      'memoStack.createThread',
      (handler, params) => handler.createThread(params),
    );
    _register(
      'memoStack.submitCapture',
      (handler, params) => handler.submitCapture(params),
    );
    _register(
      'memoStack.reviewFirstPendingLinkSuggestion',
      (handler, params) => handler.reviewFirstPendingLinkSuggestion(params),
    );
  }

  static void _register(
    String name,
    Future<Map<String, dynamic>> Function(
      MemoStackMarionetteE2eCommandHandler handler,
      Map<String, String> params,
    ) callback,
  ) {
    if (_registeredExtensions.contains(name)) return;
    _registeredExtensions.add(name);
    developer.registerExtension(
      'ext.flutter.$name',
      (String method, Map<String, String> params) async {
        final handler = _activeHandler;
        if (handler == null) {
          return _errorResponse(
            StateError('Memo Stack E2E bridge is not ready'),
            StackTrace.current,
          );
        }
        try {
          final result = await callback(handler, params);
          return _resultResponse(result);
        } catch (error, stack) {
          return _errorResponse(error, stack);
        }
      },
    );
  }
}

@visibleForTesting
class MemoStackMarionetteE2eCommandHandler {
  final ChatStoreResolver _store;

  MemoStackMarionetteE2eCommandHandler(this._store);

  Future<Map<String, dynamic>> state() async {
    return _state(_store());
  }

  Future<Map<String, dynamic>> refresh() async {
    final store = _store();
    await _refreshEvidence(store);
    return _state(store);
  }

  Future<Map<String, dynamic>> createMemoryScope(
    Map<String, String> params,
  ) async {
    final store = _store();
    final externalRef = _required(params, 'externalRef');
    final scope = await _ensureMemoryScope(
      store,
      externalRef: externalRef,
      name: params['name'],
    );
    await _refreshEvidence(store);
    return {
      ..._state(store),
      'memoryScope': _scopeToMap(scope),
    };
  }

  Future<Map<String, dynamic>> switchMemoryScope(
    Map<String, String> params,
  ) async {
    final store = _store();
    await store.setActiveMemoryScope(_required(params, 'externalRef'));
    await _refreshEvidence(store);
    return _state(store);
  }

  Future<Map<String, dynamic>> createThread(Map<String, String> params) async {
    final store = _store();
    final scopeRef = _optional(params, 'memoryScopeExternalRef');
    if (scopeRef != null) {
      await _ensureMemoryScope(
        store,
        externalRef: scopeRef,
        name: params['memoryScopeName'],
      );
    }
    final threadId = store.createNewChat(
      title: _optional(params, 'title'),
      memoryScopeExternalRef: scopeRef,
    );
    await _refreshEvidence(store);
    return {
      ..._state(store),
      'threadId': threadId,
    };
  }

  Future<Map<String, dynamic>> submitCapture(
    Map<String, String> params,
  ) async {
    final store = _store();
    final scopeRef = _optional(params, 'memoryScopeExternalRef');
    if (scopeRef != null) {
      await _ensureMemoryScope(
        store,
        externalRef: scopeRef,
        name: params['memoryScopeName'],
      );
    }
    final threadId = _optional(params, 'threadId');
    if (threadId != null) {
      await store.setActiveChat(threadId);
    } else if (_truthy(params['createThread']) ||
        _optional(params, 'threadTitle') != null) {
      store.createNewChat(
        title: _optional(params, 'threadTitle'),
        memoryScopeExternalRef: scopeRef,
      );
    }
    await store.sendTask(_required(params, 'text'));
    await _refreshEvidence(store);
    return _state(store);
  }

  Future<Map<String, dynamic>> reviewFirstPendingLinkSuggestion(
    Map<String, String> params,
  ) async {
    final store = _store();
    await store.refreshContextLinkSuggestions(showLoading: false);
    final pending = store.contextLinkSuggestions
        .where((item) => item.isPending)
        .toList(growable: false);
    if (pending.isEmpty) {
      return {
        ..._state(store),
        'reviewed': false,
      };
    }
    final approve = !_falsey(params['approve']);
    await store.reviewContextLinkSuggestion(
      pending.first,
      approve: approve,
    );
    await _refreshEvidence(store);
    return {
      ..._state(store),
      'reviewed': true,
      'reviewedSuggestionId': pending.first.id,
      'reviewAction': approve ? 'approve' : 'reject',
    };
  }

  Future<MemoryScope> _ensureMemoryScope(
    ChatStore store, {
    required String externalRef,
    String? name,
  }) async {
    await store.refreshMemoryScopes();
    final ref = _normalizeRef(externalRef);
    final existing = store.memoryScopes
        .where((scope) => scope.externalRef == ref)
        .firstOrNull;
    if (existing != null) {
      await store.setActiveMemoryScope(existing.externalRef);
      return existing;
    }
    final created = await store.createMemoryScope(
      externalRef: ref,
      name: _optionalName(name) ?? _titleFromRef(ref),
    );
    if (created == null) {
      throw StateError(
          store.memoryScopeError ?? 'Memory scope was not created');
    }
    return created;
  }

  Future<void> _refreshEvidence(ChatStore store) async {
    await Future.wait([
      store.refreshMemoryCaptures(showLoading: false),
      store.refreshOperationsConsole(showLoading: false),
      store.refreshMemoryBrowser(showLoading: false),
    ]);
  }

  Map<String, dynamic> _state(ChatStore store) {
    final lastMessage = store.messages.isEmpty ? null : store.messages.last;
    final latestCapture =
        store.memoryCaptures.isEmpty ? null : store.memoryCaptures.first;
    final pendingLinkSuggestionCount =
        store.contextLinkSuggestions.where((item) => item.isPending).length;
    return {
      'activeChatId': store.activeChatId,
      'activeMemoryScopeExternalRef': store.activeMemoryScopeExternalRef,
      'running': store.running,
      'connection': store.connection.name,
      'sessionCount': store.sessions.length,
      'memoryScopeCount': store.memoryScopes.length,
      'messageCount': store.messages.length,
      'captureCount': store.memoryCaptures.length,
      'assetExtractionCount': store.assetExtractions.length,
      'pendingLinkSuggestionCount': pendingLinkSuggestionCount,
      'operationsPendingLinkSuggestionCount': pendingLinkSuggestionCount,
      'lastMessage': lastMessage == null ? null : _messageToMap(lastMessage),
      'latestCapture':
          latestCapture == null ? null : _captureToMap(latestCapture),
      'activeThread': _sessionToMap(
        store.sessions.firstWhere(
          (item) => item.id == store.activeChatId,
          orElse: () => ChatSession(
            id: store.activeChatId,
            title: '',
            createdAt: DateTime.fromMillisecondsSinceEpoch(0),
            memoryScopeExternalRef: store.activeMemoryScopeExternalRef,
          ),
        ),
      ),
      'memoryScopes':
          store.memoryScopes.map(_scopeToMap).toList(growable: false),
      'threads': store.sessions.map(_sessionToMap).toList(growable: false),
      'pendingLinkSuggestions': store.contextLinkSuggestions
          .where((item) => item.isPending)
          .map(_suggestionToMap)
          .toList(growable: false),
    };
  }
}

developer.ServiceExtensionResponse _resultResponse(
  Map<String, dynamic> payload,
) {
  return developer.ServiceExtensionResponse.result(
    jsonEncode({
      'ok': true,
      ...payload,
    }),
  );
}

developer.ServiceExtensionResponse _errorResponse(
  Object error,
  StackTrace stack,
) {
  return developer.ServiceExtensionResponse.error(
    developer.ServiceExtensionResponse.extensionError,
    jsonEncode({
      'ok': false,
      'error': error.toString(),
      'stack': stack.toString(),
    }),
  );
}

Map<String, dynamic> _scopeToMap(MemoryScope scope) {
  return {
    'id': scope.id,
    'spaceId': scope.spaceId,
    'externalRef': scope.externalRef,
    'name': scope.name,
    'status': scope.status,
  };
}

Map<String, dynamic> _sessionToMap(ChatSession session) {
  return {
    'id': session.id,
    'title': session.title,
    'memoryScopeExternalRef': session.memoryScopeExternalRef,
    'lastMessageText': session.lastMessageText,
  };
}

Map<String, dynamic> _messageToMap(ChatMessage message) {
  return {
    'id': message.id,
    'role': message.role,
    'kind': message.kind,
    'text': message.text,
  };
}

Map<String, dynamic> _captureToMap(MemoryCapture capture) {
  return {
    'id': capture.id,
    'memoryScopeId': capture.memoryScopeId,
    'threadId': capture.threadId,
    'preview': capture.preview,
    'status': capture.status,
    'consolidationStatus': capture.consolidationStatus,
    'assetIds': capture.assetIds,
  };
}

Map<String, dynamic> _suggestionToMap(MemoryContextLinkSuggestion suggestion) {
  return {
    'id': suggestion.id,
    'sourceType': suggestion.sourceType,
    'sourceId': suggestion.sourceId,
    'targetType': suggestion.targetType,
    'targetId': suggestion.targetId,
    'targetLabel': suggestion.targetLabel,
    'relationType': suggestion.relationType,
    'confidence': suggestion.confidence,
    'score': suggestion.score,
    'status': suggestion.status,
    'reason': suggestion.reason,
  };
}

String _required(Map<String, String> params, String key) {
  final value = _optional(params, key);
  if (value == null) {
    throw ArgumentError.value(null, key, 'required service extension param');
  }
  return value;
}

String? _optional(Map<String, String> params, String key) {
  final value = params[key]?.trim();
  return value == null || value.isEmpty ? null : value;
}

String? _optionalName(String? value) {
  final normalized = value?.trim();
  return normalized == null || normalized.isEmpty ? null : normalized;
}

String _normalizeRef(String value) {
  final trimmed = value.trim();
  return trimmed.isEmpty ? 'default' : trimmed;
}

bool _truthy(String? value) {
  final normalized = value?.trim().toLowerCase();
  return normalized == '1' || normalized == 'true' || normalized == 'yes';
}

bool _falsey(String? value) {
  final normalized = value?.trim().toLowerCase();
  return normalized == '0' || normalized == 'false' || normalized == 'no';
}

String _titleFromRef(String ref) {
  return ref
      .replaceAll(RegExp(r'[-_]+'), ' ')
      .split(' ')
      .where((part) => part.isNotEmpty)
      .map((part) => part[0].toUpperCase() + part.substring(1))
      .join(' ');
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull {
    final iterator = this.iterator;
    if (iterator.moveNext()) return iterator.current;
    return null;
  }
}
