part of 'marionette_e2e_extensions.dart';

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

Map<String, dynamic> _extractionToMap(AssetExtractionJob job) {
  return {
    'id': job.id,
    'assetId': job.assetId,
    'threadId': job.threadId,
    'status': job.status,
    'parserName': job.parserName,
    'resultDocumentIds': job.resultDocumentIds,
    'artifactTypes':
        job.artifacts.map((artifact) => artifact.artifactType).toList(),
    'progressPercent': job.progress.percent,
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

List<int> _attachmentBytes(Map<String, String> params) {
  final base64Value = _optional(params, 'contentBase64');
  if (base64Value != null) {
    return base64Decode(base64Value);
  }
  return utf8.encode(
    _optional(params, 'content') ?? 'Memo Stack E2E attachment.',
  );
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
