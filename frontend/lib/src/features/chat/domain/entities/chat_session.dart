import 'package:equatable/equatable.dart';

class ChatSession extends Equatable {
  final String id;
  final String title;
  final DateTime createdAt;
  final String memoryScopeExternalRef;
  final double totalUsd;
  final int totalInputTokens;
  final int totalOutputTokens;
  final String? lastMessageText;
  final String?
      lastResponseId; // OpenAI previous_response_id for session resume

  const ChatSession({
    required this.id,
    required this.title,
    required this.createdAt,
    this.memoryScopeExternalRef = 'default',
    this.totalUsd = 0.0,
    this.totalInputTokens = 0,
    this.totalOutputTokens = 0,
    this.lastMessageText,
    this.lastResponseId,
  });

  ChatSession copyWith({
    String? id,
    String? title,
    DateTime? createdAt,
    String? memoryScopeExternalRef,
    double? totalUsd,
    int? totalInputTokens,
    int? totalOutputTokens,
    String? lastMessageText,
    String? lastResponseId,
  }) {
    return ChatSession(
      id: id ?? this.id,
      title: title ?? this.title,
      createdAt: createdAt ?? this.createdAt,
      memoryScopeExternalRef:
          memoryScopeExternalRef ?? this.memoryScopeExternalRef,
      totalUsd: totalUsd ?? this.totalUsd,
      totalInputTokens: totalInputTokens ?? this.totalInputTokens,
      totalOutputTokens: totalOutputTokens ?? this.totalOutputTokens,
      lastMessageText: lastMessageText ?? this.lastMessageText,
      lastResponseId: lastResponseId ?? this.lastResponseId,
    );
  }

  @override
  List<Object?> get props => [
        id,
        title,
        createdAt,
        memoryScopeExternalRef,
        totalUsd,
        totalInputTokens,
        totalOutputTokens,
        lastMessageText,
        lastResponseId,
      ];
}
