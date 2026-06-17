import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;

import 'package:flutter/widgets.dart';
import 'package:frontend/src/features/chat/application/stores/chat_store.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_session.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_browser.dart';
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
    _register(
      'memoStack.createMemoryAnchor',
      (handler, params) => handler.createMemoryAnchor(params),
    );
    _register(
      'memoStack.updateMemoryAnchor',
      (handler, params) => handler.updateMemoryAnchor(params),
    );
    _register(
      'memoStack.deleteMemoryAnchor',
      (handler, params) => handler.deleteMemoryAnchor(params),
    );
    _register(
      'memoStack.splitMemoryAnchorAlias',
      (handler, params) => handler.splitMemoryAnchorAlias(params),
    );
    _register(
      'memoStack.mergeFirstAnchorSuggestion',
      (handler, params) => handler.mergeFirstAnchorSuggestion(params),
    );
    _register(
      'memoStack.backfillMemoryAnchors',
      (handler, params) => handler.backfillMemoryAnchors(params),
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

  Future<Map<String, dynamic>> createMemoryAnchor(
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
    final label = _required(params, 'label');
    final ok = await store.createMemoryAnchor(
      kind: _optional(params, 'kind') ?? 'person',
      label: label,
      aliases: _listParam(params, 'aliases'),
      description: _optional(params, 'description'),
    );
    _throwIfFailed(
        ok, store.memoryBrowserError.value, 'Anchor was not created');
    await _refreshEvidence(store);
    final anchor = await _findAnchor(store, label: label);
    return {
      ..._state(store),
      'anchor': _anchorToMap(anchor),
    };
  }

  Future<Map<String, dynamic>> updateMemoryAnchor(
    Map<String, String> params,
  ) async {
    final store = _store();
    final anchor = await _findAnchor(
      store,
      anchorId: _optional(params, 'anchorId'),
      label: _optional(params, 'currentLabel'),
    );
    final label = _required(params, 'label');
    final ok = await store.updateMemoryAnchor(
      anchor,
      label: label,
      aliases: _listParam(params, 'aliases'),
      description: _optional(params, 'description'),
    );
    _throwIfFailed(
        ok, store.memoryBrowserError.value, 'Anchor was not updated');
    await _refreshEvidence(store);
    final updated = await _findAnchor(store, anchorId: anchor.id, label: label);
    return {
      ..._state(store),
      'anchor': _anchorToMap(updated),
    };
  }

  Future<Map<String, dynamic>> deleteMemoryAnchor(
    Map<String, String> params,
  ) async {
    final store = _store();
    final anchor = await _findAnchor(
      store,
      anchorId: _optional(params, 'anchorId'),
      label: _optional(params, 'label'),
    );
    final ok = await store.deleteMemoryAnchor(
      anchor,
      reason: _optional(params, 'reason') ?? 'deleted by marionette e2e',
    );
    _throwIfFailed(
        ok, store.memoryBrowserError.value, 'Anchor was not deleted');
    await _refreshEvidence(store);
    return {
      ..._state(store),
      'deletedAnchorId': anchor.id,
      'deletedAnchorLabel': anchor.label,
    };
  }

  Future<Map<String, dynamic>> splitMemoryAnchorAlias(
    Map<String, String> params,
  ) async {
    final store = _store();
    final anchor = await _findAnchor(
      store,
      anchorId: _optional(params, 'anchorId'),
      label: _optional(params, 'label'),
    );
    final alias = _required(params, 'alias');
    final ok = await store.splitMemoryAnchorAlias(
      anchor,
      alias: alias,
      newLabel: _optional(params, 'newLabel'),
      reason: _optional(params, 'reason') ?? 'split by marionette e2e',
    );
    _throwIfFailed(ok, store.memoryBrowserError.value, 'Anchor was not split');
    await _refreshEvidence(store);
    final split = await _findAnchor(
      store,
      label: _optional(params, 'newLabel') ?? alias,
    );
    return {
      ..._state(store),
      'sourceAnchorId': anchor.id,
      'splitAnchor': _anchorToMap(split),
    };
  }

  Future<Map<String, dynamic>> mergeFirstAnchorSuggestion(
    Map<String, String> params,
  ) async {
    final store = _store();
    await store.refreshMemoryBrowser(showLoading: false);
    final sourceAnchorId = _optional(params, 'sourceAnchorId');
    final targetAnchorId = _optional(params, 'targetAnchorId');
    final suggestions = store.anchorMergeSuggestions.where((item) {
      final sourceMatches =
          sourceAnchorId == null || item.sourceAnchor.id == sourceAnchorId;
      final targetMatches =
          targetAnchorId == null || item.targetAnchor.id == targetAnchorId;
      return sourceMatches && targetMatches;
    }).toList(growable: false);
    if (suggestions.isEmpty) {
      return {
        ..._state(store),
        'merged': false,
      };
    }
    final suggestion = suggestions.first;
    final ok = await store.mergeMemoryAnchorSuggestion(suggestion);
    _throwIfFailed(ok, store.memoryBrowserError.value, 'Anchor was not merged');
    await _refreshEvidence(store);
    return {
      ..._state(store),
      'merged': true,
      'mergedSourceAnchorId': suggestion.sourceAnchor.id,
      'mergedTargetAnchorId': suggestion.targetAnchor.id,
    };
  }

  Future<Map<String, dynamic>> backfillMemoryAnchors(
    Map<String, String> params,
  ) async {
    final store = _store();
    final ok = await store.backfillMemoryAnchors(
      limitPerSource: _intParam(params, 'limitPerSource', fallback: 100),
    );
    _throwIfFailed(
      ok,
      store.memoryBrowserError.value,
      'Anchor backfill failed',
    );
    await _refreshEvidence(store);
    return _state(store);
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
    final browser = store.memoryBrowser.value;
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
      'memoryBrowserAnchorCount': browser?.anchors.length ?? 0,
      'memoryBrowserContextLinkCount': browser?.contextLinks.length ?? 0,
      'memoryBrowserCaptureCount': browser?.captures.length ?? 0,
      'pendingAnchorMergeSuggestionCount': store.anchorMergeSuggestions.length,
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
      'memoryBrowserAnchors':
          browser?.anchors.map(_anchorToMap).toList(growable: false) ??
              const <Map<String, dynamic>>[],
      'pendingAnchorMergeSuggestions': store.anchorMergeSuggestions
          .map(_anchorMergeSuggestionToMap)
          .toList(growable: false),
    };
  }

  Future<MemoryBrowserAnchor> _findAnchor(
    ChatStore store, {
    String? anchorId,
    String? label,
  }) async {
    await store.refreshMemoryBrowser(showLoading: false);
    final anchors = store.memoryBrowser.value?.anchors ?? const [];
    final normalizedLabel = label?.trim().toLowerCase();
    for (final anchor in anchors) {
      final idMatches = anchorId != null && anchor.id == anchorId;
      final labelMatches = normalizedLabel != null &&
          anchor.label.trim().toLowerCase() == normalizedLabel;
      if (idMatches || labelMatches) {
        return anchor;
      }
    }
    final selector = anchorId ?? label ?? '<missing selector>';
    throw StateError('Memory anchor not found: $selector');
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

Map<String, dynamic> _anchorToMap(MemoryBrowserAnchor anchor) {
  return {
    'id': anchor.id,
    'spaceId': anchor.spaceId,
    'memoryScopeId': anchor.memoryScopeId,
    'kind': anchor.kind,
    'normalizedKey': anchor.normalizedKey,
    'label': anchor.label,
    'aliases': anchor.aliases,
    'description': anchor.description,
    'status': anchor.status,
  };
}

Map<String, dynamic> _anchorMergeSuggestionToMap(
  MemoryAnchorMergeSuggestion suggestion,
) {
  return {
    'id': suggestion.id,
    'sourceAnchor': _anchorToMap(suggestion.sourceAnchor),
    'targetAnchor': _anchorToMap(suggestion.targetAnchor),
    'confidence': suggestion.confidence,
    'score': suggestion.score,
    'reasons': suggestion.reasons,
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

List<String> _listParam(Map<String, String> params, String key) {
  final value = _optional(params, key);
  if (value == null) return const <String>[];
  if (value.startsWith('[')) {
    final decoded = jsonDecode(value);
    if (decoded is List) {
      return decoded
          .map((item) => item.toString().trim())
          .where((item) => item.isNotEmpty)
          .toSet()
          .toList(growable: false);
    }
    throw ArgumentError.value(value, key, 'must be a JSON array');
  }
  return value
      .split(',')
      .map((item) => item.trim())
      .where((item) => item.isNotEmpty)
      .toSet()
      .toList(growable: false);
}

int _intParam(
  Map<String, String> params,
  String key, {
  required int fallback,
}) {
  final value = _optional(params, key);
  if (value == null) return fallback;
  final parsed = int.tryParse(value);
  if (parsed == null || parsed <= 0) {
    throw ArgumentError.value(value, key, 'must be a positive integer');
  }
  return parsed;
}

void _throwIfFailed(bool ok, String? error, String fallback) {
  if (!ok) {
    throw StateError(error ?? fallback);
  }
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
