import 'package:equatable/equatable.dart';

class MemoryContextLink extends Equatable {
  final String id;
  final String spaceId;
  final String memoryScopeId;
  final String sourceType;
  final String sourceId;
  final String targetType;
  final String targetId;
  final String relationType;
  final String confidence;
  final String reason;
  final String status;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;
  final DateTime updatedAt;

  const MemoryContextLink({
    required this.id,
    required this.spaceId,
    required this.memoryScopeId,
    required this.sourceType,
    required this.sourceId,
    required this.targetType,
    required this.targetId,
    required this.relationType,
    required this.confidence,
    required this.reason,
    required this.status,
    required this.metadata,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MemoryContextLink.fromMap(Map<String, dynamic> map) {
    return MemoryContextLink(
      id: _string(map['id']),
      spaceId: _string(map['space_id']),
      memoryScopeId: _string(map['memory_scope_id']),
      sourceType: _string(map['source_type']),
      sourceId: _string(map['source_id']),
      targetType: _string(map['target_type']),
      targetId: _string(map['target_id']),
      relationType: _string(map['relation_type'], fallback: 'related_to'),
      confidence: _string(map['confidence'], fallback: 'medium'),
      reason: _string(map['reason']),
      status: _string(map['status'], fallback: 'active'),
      metadata: _map(map['metadata']),
      createdAt: _date(map['created_at']),
      updatedAt: _date(map['updated_at']),
    );
  }

  String get targetLabel {
    final label = metadata['target_label']?.toString().trim();
    if (label != null && label.isNotEmpty) return label;
    return '$targetType $targetId';
  }

  @override
  List<Object?> get props => [
        id,
        spaceId,
        memoryScopeId,
        sourceType,
        sourceId,
        targetType,
        targetId,
        relationType,
        confidence,
        reason,
        status,
        metadata,
        createdAt,
        updatedAt,
      ];
}

String _string(Object? value, {String fallback = ''}) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? fallback : text;
}

DateTime _date(Object? value) => _nullableDate(value) ?? DateTime.now();

DateTime? _nullableDate(Object? value) {
  final text = value?.toString();
  if (text == null || text.isEmpty) return null;
  return DateTime.tryParse(text);
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return Map<String, dynamic>.from(value);
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const <String, dynamic>{};
}
