import 'package:equatable/equatable.dart';

class DocumentSourceRef extends Equatable {
  final String sourceType;
  final String sourceId;
  final String? assetId;
  final String? kind;
  final int? pageNumber;
  final int? timeStartMs;
  final int? timeEndMs;
  final int? charStart;
  final int? charEnd;
  final int? chunkCharStart;
  final int? chunkCharEnd;
  final List<double> bbox;
  final double? confidence;
  final String? providerSource;
  final String? quotePreview;
  final Map<String, dynamic> raw;

  const DocumentSourceRef({
    required this.sourceType,
    required this.sourceId,
    required this.assetId,
    required this.kind,
    required this.pageNumber,
    required this.timeStartMs,
    required this.timeEndMs,
    required this.charStart,
    required this.charEnd,
    required this.chunkCharStart,
    required this.chunkCharEnd,
    required this.bbox,
    required this.confidence,
    required this.providerSource,
    required this.quotePreview,
    required this.raw,
  });

  factory DocumentSourceRef.fromMap(Map<String, dynamic> map) {
    return DocumentSourceRef(
      sourceType: _string(map['source_type']),
      sourceId: _string(map['source_id']),
      assetId: _nullableString(map['asset_id']),
      kind: _nullableString(map['kind']),
      pageNumber: _nullableInt(map['page_number']),
      timeStartMs: _nullableInt(map['time_start_ms']),
      timeEndMs: _nullableInt(map['time_end_ms']),
      charStart: _nullableInt(map['char_start']),
      charEnd: _nullableInt(map['char_end']),
      chunkCharStart: _nullableInt(map['chunk_char_start']),
      chunkCharEnd: _nullableInt(map['chunk_char_end']),
      bbox: _doubleList(map['bbox']),
      confidence: _nullableDouble(map['confidence']),
      providerSource: _nullableString(map['provider_source']),
      quotePreview: _nullableString(map['quote_preview']),
      raw: Map<String, dynamic>.from(map),
    );
  }

  bool get hasPage => pageNumber != null && pageNumber! > 0;
  bool get hasTime => timeStartMs != null || timeEndMs != null;
  bool get hasBBox => bbox.length == 4;

  @override
  List<Object?> get props => [
        sourceType,
        sourceId,
        assetId,
        kind,
        pageNumber,
        timeStartMs,
        timeEndMs,
        charStart,
        charEnd,
        chunkCharStart,
        chunkCharEnd,
        bbox,
        confidence,
        providerSource,
        quotePreview,
        raw,
      ];
}

class DocumentChunk extends Equatable {
  final String id;
  final String? documentId;
  final String text;
  final String kind;
  final int sequence;
  final String status;
  final String classification;
  final List<DocumentSourceRef> sourceRefs;
  final Map<String, dynamic> metadata;

  const DocumentChunk({
    required this.id,
    required this.documentId,
    required this.text,
    required this.kind,
    required this.sequence,
    required this.status,
    required this.classification,
    required this.sourceRefs,
    required this.metadata,
  });

  factory DocumentChunk.fromMap(Map<String, dynamic> map) {
    final metadata = _map(map['metadata']);
    return DocumentChunk(
      id: _string(map['id']),
      documentId: _nullableString(map['document_id']),
      text: _string(map['text']),
      kind: _string(map['kind'], fallback: 'document_section'),
      sequence: _int(map['sequence']),
      status: _string(map['status'], fallback: 'active'),
      classification: _string(map['classification'], fallback: 'unknown'),
      sourceRefs: _sourceRefs(map['source_refs'], metadata),
      metadata: metadata,
    );
  }

  String get preview {
    final collapsed = text.trim().replaceAll(RegExp(r'\s+'), ' ');
    if (collapsed.length <= 180) return collapsed;
    return '${collapsed.substring(0, 177)}...';
  }

  @override
  List<Object?> get props => [
        id,
        documentId,
        text,
        kind,
        sequence,
        status,
        classification,
        sourceRefs,
        metadata,
      ];
}

List<DocumentSourceRef> _sourceRefs(
  Object? direct,
  Map<String, dynamic> metadata,
) {
  final value = direct is List ? direct : metadata['source_refs'];
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

int _int(Object? value) => _nullableInt(value) ?? 0;

int? _nullableInt(Object? value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  return int.tryParse(value?.toString() ?? '');
}

double? _nullableDouble(Object? value) {
  if (value is num) return value.toDouble();
  return double.tryParse(value?.toString() ?? '');
}

List<double> _doubleList(Object? value) {
  if (value is! List) return const <double>[];
  return value.map(_nullableDouble).whereType<double>().toList(growable: false);
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return Map<String, dynamic>.from(value);
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const <String, dynamic>{};
}
