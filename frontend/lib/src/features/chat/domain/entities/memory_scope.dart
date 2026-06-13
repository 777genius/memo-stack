import 'package:equatable/equatable.dart';

class MemoryScope extends Equatable {
  final String id;
  final String spaceId;
  final String externalRef;
  final String name;
  final String status;
  final DateTime createdAt;
  final DateTime updatedAt;

  const MemoryScope({
    required this.id,
    required this.spaceId,
    required this.externalRef,
    required this.name,
    required this.status,
    required this.createdAt,
    required this.updatedAt,
  });

  factory MemoryScope.local({
    required String externalRef,
    String? name,
  }) {
    final now = DateTime.now();
    final ref = externalRef.trim().isEmpty ? 'default' : externalRef.trim();
    return MemoryScope(
      id: '',
      spaceId: '',
      externalRef: ref,
      name: name?.trim().isNotEmpty == true ? name!.trim() : _titleFromRef(ref),
      status: 'active',
      createdAt: now,
      updatedAt: now,
    );
  }

  factory MemoryScope.fromMap(Map<String, dynamic> map) {
    final externalRef = (map['external_ref'] as String?)?.trim() ?? 'default';
    return MemoryScope(
      id: (map['id'] as String?) ?? '',
      spaceId: (map['space_id'] as String?) ?? '',
      externalRef: externalRef.isEmpty ? 'default' : externalRef,
      name: (map['name'] as String?)?.trim().isNotEmpty == true
          ? (map['name'] as String).trim()
          : _titleFromRef(externalRef),
      status: (map['status'] as String?) ?? 'active',
      createdAt: DateTime.tryParse((map['created_at'] as String?) ?? '') ??
          DateTime.now(),
      updatedAt: DateTime.tryParse((map['updated_at'] as String?) ?? '') ??
          DateTime.now(),
    );
  }

  MemoryScope copyWith({
    String? id,
    String? spaceId,
    String? externalRef,
    String? name,
    String? status,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return MemoryScope(
      id: id ?? this.id,
      spaceId: spaceId ?? this.spaceId,
      externalRef: externalRef ?? this.externalRef,
      name: name ?? this.name,
      status: status ?? this.status,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  List<Object?> get props => [
        id,
        spaceId,
        externalRef,
        name,
        status,
        createdAt,
        updatedAt,
      ];
}

String _titleFromRef(String ref) {
  if (ref.trim().isEmpty) return 'Default';
  return ref
      .replaceAll(RegExp(r'[-_]+'), ' ')
      .split(' ')
      .where((part) => part.isNotEmpty)
      .map((part) => part[0].toUpperCase() + part.substring(1))
      .join(' ');
}
