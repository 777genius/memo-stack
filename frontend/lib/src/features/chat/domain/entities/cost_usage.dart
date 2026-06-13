import 'package:equatable/equatable.dart';

class CostUsage extends Equatable {
  final int inputTokens;
  final int outputTokens;
  final double inputUsd;
  final double outputUsd;

  const CostUsage({
    required this.inputTokens,
    required this.outputTokens,
    required this.inputUsd,
    required this.outputUsd,
  });

  double get totalUsd => inputUsd + outputUsd;

  @override
  List<Object?> get props => [inputTokens, outputTokens, inputUsd, outputUsd];
}
