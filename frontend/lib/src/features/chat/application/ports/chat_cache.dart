import 'package:frontend/src/features/chat/domain/entities/chat_message.dart';
import 'package:frontend/src/features/chat/domain/entities/chat_session.dart';

abstract class ChatCache {
  Future<List<ChatSession>> loadSessions();
  Future<void> upsertSession(ChatSession session);
  Future<void> removeSession(String id);

  Future<List<ChatMessage>> loadMessages(String chatId);
  Future<void> saveMessage(String chatId, ChatMessage message);
  Future<void> removeMessages(String chatId);
}
