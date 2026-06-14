import 'package:equatable/equatable.dart';

import 'package:frontend/src/features/chat/domain/entities/asset_extraction.dart';
import 'package:frontend/src/features/chat/domain/entities/memory_context_link.dart';

class MemoryOperationsConsole extends Equatable {
  final DateTime? generatedAt;
  final Map<String, dynamic> scope;
  final Map<String, int> extractionStatusCounts;
  final Map<String, int> linkSuggestionStatusCounts;
  final List<AssetExtractionJob> extractionJobs;
  final List<MemoryContextLinkSuggestion> contextLinkSuggestions;
  final Map<String, dynamic> diagnostics;

  const MemoryOperationsConsole({
    required this.generatedAt,
    required this.scope,
    required this.extractionStatusCounts,
    required this.linkSuggestionStatusCounts,
    required this.extractionJobs,
    required this.contextLinkSuggestions,
    required this.diagnostics,
  });

  factory MemoryOperationsConsole.fromMap(Map<String, dynamic> map) {
    return MemoryOperationsConsole(
      generatedAt: _nullableDate(map['generated_at']),
      scope: _map(map['scope']),
      extractionStatusCounts: _intMap(map['extraction_status_counts']),
      linkSuggestionStatusCounts: _intMap(map['link_suggestion_status_counts']),
      extractionJobs: _listOfMaps(map['extraction_jobs'])
          .map(AssetExtractionJob.fromMap)
          .toList(growable: false),
      contextLinkSuggestions: _listOfMaps(map['context_link_suggestions'])
          .map(MemoryContextLinkSuggestion.fromMap)
          .toList(growable: false),
      diagnostics: _map(map['diagnostics']),
    );
  }

  int extractionCount(String status) => extractionStatusCounts[status] ?? 0;
  int linkSuggestionCount(String status) =>
      linkSuggestionStatusCounts[status] ?? 0;

  int get activeExtractionCount =>
      extractionCount('pending') + extractionCount('running');

  int get retryableExtractionCount =>
      extractionCount('failed') +
      extractionCount('unsupported') +
      extractionCount('canceled') +
      extractionCount('stale');

  int get pendingLinkSuggestionCount => linkSuggestionCount('pending');

  @override
  List<Object?> get props => [
        generatedAt,
        scope,
        extractionStatusCounts,
        linkSuggestionStatusCounts,
        extractionJobs,
        contextLinkSuggestions,
        diagnostics,
      ];
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return Map<String, dynamic>.from(value);
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const <String, dynamic>{};
}

Map<String, int> _intMap(Object? value) {
  final raw = _map(value);
  return raw.map((key, item) {
    if (item is int) return MapEntry(key, item);
    if (item is num) return MapEntry(key, item.toInt());
    return MapEntry(key, int.tryParse(item?.toString() ?? '') ?? 0);
  });
}

List<Map<String, dynamic>> _listOfMaps(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => item.map((key, value) => MapEntry(key.toString(), value)))
      .toList(growable: false);
}

DateTime? _nullableDate(Object? value) {
  final text = value?.toString();
  if (text == null || text.isEmpty) return null;
  return DateTime.tryParse(text);
}
