import 'package:equatable/equatable.dart';

class MemorySuggestionResolutionOption extends Equatable {
  final String id;
  final String reviewAction;
  final String effect;
  final String availability;
  final String resolutionAction;

  const MemorySuggestionResolutionOption({
    required this.id,
    required this.reviewAction,
    required this.effect,
    required this.availability,
    required this.resolutionAction,
  });

  factory MemorySuggestionResolutionOption.fromMap(Map<String, dynamic> map) {
    return MemorySuggestionResolutionOption(
      id: _string(map['id']),
      reviewAction: _string(map['review_action']),
      effect: _string(map['effect']),
      availability: _string(map['availability'], fallback: 'available'),
      resolutionAction: _string(map['resolution_action']),
    );
  }

  String get label {
    return switch (id) {
      'merge_source_refs' => 'Merge sources',
      'keep_separate_fact' => 'Keep separate',
      'reject_duplicate_candidate' => 'Reject',
      'expire_duplicate_candidate' => 'Hide',
      final value => value.replaceAll('_', ' '),
    };
  }

  @override
  List<Object?> get props => [
        id,
        reviewAction,
        effect,
        availability,
        resolutionAction,
      ];
}

class MemorySuggestion extends Equatable {
  final String id;
  final String spaceId;
  final String memoryScopeId;
  final String candidateText;
  final String kind;
  final String operation;
  final String status;
  final String confidence;
  final String trustLevel;
  final String safeReason;
  final String? targetFactId;
  final int? targetFactVersion;
  final String reviewKind;
  final bool reviewActionable;
  final List<String> availableReviewActions;
  final List<MemorySuggestionResolutionOption> reviewResolutionOptions;
  final Map<String, dynamic> reviewPayload;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime? reviewedAt;
  final String? reviewReason;

  const MemorySuggestion({
    required this.id,
    required this.spaceId,
    required this.memoryScopeId,
    required this.candidateText,
    required this.kind,
    required this.operation,
    required this.status,
    required this.confidence,
    required this.trustLevel,
    required this.safeReason,
    required this.targetFactId,
    required this.targetFactVersion,
    required this.reviewKind,
    required this.reviewActionable,
    required this.availableReviewActions,
    required this.reviewResolutionOptions,
    required this.reviewPayload,
    required this.createdAt,
    required this.updatedAt,
    this.reviewedAt,
    this.reviewReason,
  });

  factory MemorySuggestion.fromMap(Map<String, dynamic> map) {
    return MemorySuggestion(
      id: _string(map['id']),
      spaceId: _string(map['space_id']),
      memoryScopeId: _string(map['memory_scope_id']),
      candidateText: _string(map['candidate_text']),
      kind: _string(map['kind'], fallback: 'note'),
      operation: _string(map['operation'], fallback: 'add'),
      status: _string(map['status'], fallback: 'pending'),
      confidence: _string(map['confidence'], fallback: 'medium'),
      trustLevel: _string(map['trust_level'], fallback: 'medium'),
      safeReason: _string(map['safe_reason']),
      targetFactId: _nullableString(map['target_fact_id']),
      targetFactVersion: _nullableInt(map['target_fact_version']),
      reviewKind: _string(map['review_kind'], fallback: 'candidate_review'),
      reviewActionable: map['review_actionable'] == true,
      availableReviewActions: _stringList(map['available_review_actions']),
      reviewResolutionOptions: _mapList(map['review_resolution_options'])
          .map(MemorySuggestionResolutionOption.fromMap)
          .toList(growable: false),
      reviewPayload: _map(map['review_payload']),
      createdAt: _date(map['created_at']),
      updatedAt: _date(map['updated_at']),
      reviewedAt: _nullableDate(map['reviewed_at']),
      reviewReason: _nullableString(map['review_reason']),
    );
  }

  bool get isPending => status == 'pending';

  bool get isDuplicateMergeReview => reviewKind == 'duplicate_fact_merge';

  bool get canResolveDuplicate =>
      isPending && availableReviewActions.contains('resolve_duplicate');

  String? get recommendedAction {
    final value = reviewPayload['recommended_action']?.toString().trim();
    return value == null || value.isEmpty ? null : value;
  }

  String? get defaultResolution {
    final value = reviewPayload['default_resolution']?.toString().trim();
    return value == null || value.isEmpty ? null : value;
  }

  String get reviewTitle {
    if (isDuplicateMergeReview) return 'Duplicate memory';
    if (reviewKind == 'conflict_review') return 'Memory conflict';
    return 'Memory review';
  }

  @override
  List<Object?> get props => [
        id,
        spaceId,
        memoryScopeId,
        candidateText,
        kind,
        operation,
        status,
        confidence,
        trustLevel,
        safeReason,
        targetFactId,
        targetFactVersion,
        reviewKind,
        reviewActionable,
        availableReviewActions,
        reviewResolutionOptions,
        reviewPayload,
        createdAt,
        updatedAt,
        reviewedAt,
        reviewReason,
      ];
}

String _string(Object? value, {String fallback = ''}) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? fallback : text;
}

String? _nullableString(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
}

int? _nullableInt(Object? value) {
  if (value is int) return value;
  return int.tryParse(value?.toString() ?? '');
}

DateTime _date(Object? value) {
  return _nullableDate(value) ?? DateTime.fromMillisecondsSinceEpoch(0);
}

DateTime? _nullableDate(Object? value) {
  final text = value?.toString();
  if (text == null || text.isEmpty) return null;
  return DateTime.tryParse(text);
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return value;
  if (value is Map) {
    return value.map((key, value) => MapEntry(key.toString(), value));
  }
  return const <String, dynamic>{};
}

List<Map<String, dynamic>> _mapList(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => item.map((key, value) => MapEntry(key.toString(), value)))
      .toList(growable: false);
}

List<String> _stringList(Object? value) {
  if (value is! List) return const <String>[];
  final items = <String>[];
  for (final item in value) {
    final text = item?.toString().trim();
    if (text != null && text.isNotEmpty && !items.contains(text)) {
      items.add(text);
    }
  }
  return items;
}
