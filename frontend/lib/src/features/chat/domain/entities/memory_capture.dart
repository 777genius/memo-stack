import 'package:equatable/equatable.dart';

import 'package:frontend/src/features/chat/domain/entities/document_chunk.dart';

class MemoryCapture extends Equatable {
  final String id;
  final String spaceId;
  final String memoryScopeId;
  final String? threadId;
  final String sourceAgent;
  final String sourceKind;
  final String eventType;
  final String actorRole;
  final String textPreview;
  final String status;
  final String consolidationStatus;
  final String trustLevel;
  final String sourceAuthority;
  final String sensitivity;
  final String dataClassification;
  final List<DocumentSourceRef> evidenceRefs;
  final Map<String, dynamic> metadata;
  final DateTime createdAt;
  final DateTime updatedAt;
  final DateTime occurredAt;
  final String? lastErrorCode;

  const MemoryCapture({
    required this.id,
    required this.spaceId,
    required this.memoryScopeId,
    required this.threadId,
    required this.sourceAgent,
    required this.sourceKind,
    required this.eventType,
    required this.actorRole,
    required this.textPreview,
    required this.status,
    required this.consolidationStatus,
    required this.trustLevel,
    required this.sourceAuthority,
    required this.sensitivity,
    required this.dataClassification,
    required this.evidenceRefs,
    required this.metadata,
    required this.createdAt,
    required this.updatedAt,
    required this.occurredAt,
    required this.lastErrorCode,
  });

  factory MemoryCapture.fromMap(Map<String, dynamic> map) {
    return MemoryCapture(
      id: _string(map['id']),
      spaceId: _string(map['space_id']),
      memoryScopeId: _string(map['memory_scope_id']),
      threadId: _nullableString(map['thread_id']),
      sourceAgent: _string(map['source_agent']),
      sourceKind: _string(map['source_kind'], fallback: 'manual'),
      eventType: _string(map['event_type'], fallback: 'Capture'),
      actorRole: _string(map['actor_role'], fallback: 'user'),
      textPreview: _string(map['text_preview']),
      status: _string(map['status'], fallback: 'accepted'),
      consolidationStatus:
          _string(map['consolidation_status'], fallback: 'pending'),
      trustLevel: _string(map['trust_level'], fallback: 'medium'),
      sourceAuthority: _string(map['source_authority'], fallback: 'unknown'),
      sensitivity: _string(map['sensitivity'], fallback: 'medium'),
      dataClassification:
          _string(map['data_classification'], fallback: 'internal'),
      evidenceRefs: _sourceRefs(map['evidence_refs']),
      metadata: _map(map['metadata']),
      createdAt: _date(map['created_at']),
      updatedAt: _date(map['updated_at']),
      occurredAt: _date(map['occurred_at']),
      lastErrorCode: _nullableString(map['last_error_code']),
    );
  }

  String get preview {
    final collapsed = textPreview.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (collapsed.length <= 160) return collapsed;
    return '${collapsed.substring(0, 157)}...';
  }

  List<String> get assetIds {
    final raw = metadata['asset_ids'];
    if (raw is List) {
      return raw.map((item) => item.toString()).toList(growable: false);
    }
    return evidenceRefs
        .where((ref) => ref.sourceType == 'asset' && ref.sourceId.isNotEmpty)
        .map((ref) => ref.sourceId)
        .toList(growable: false);
  }

  @override
  List<Object?> get props => [
        id,
        spaceId,
        memoryScopeId,
        threadId,
        sourceAgent,
        sourceKind,
        eventType,
        actorRole,
        textPreview,
        status,
        consolidationStatus,
        trustLevel,
        sourceAuthority,
        sensitivity,
        dataClassification,
        evidenceRefs,
        metadata,
        createdAt,
        updatedAt,
        occurredAt,
        lastErrorCode,
      ];
}

List<DocumentSourceRef> _sourceRefs(Object? value) {
  if (value is! List) return const <DocumentSourceRef>[];
  return value
      .whereType<Map>()
      .map((item) => DocumentSourceRef.fromMap(_map(item)))
      .toList(growable: false);
}

String _string(Object? value, {String fallback = ''}) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? fallback : text;
}

String? _nullableString(Object? value) {
  final text = value?.toString().trim();
  return text == null || text.isEmpty ? null : text;
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
