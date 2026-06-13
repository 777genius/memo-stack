import 'package:injectable/injectable.dart';
import 'package:frontend/src/features/chat/domain/repositories/chat_repository.dart';

@injectable
class RunTaskUseCase {
  final ChatRepository repo;
  RunTaskUseCase(this.repo);

  Future<String> call(String task) => repo.runTask(task: task);
}
