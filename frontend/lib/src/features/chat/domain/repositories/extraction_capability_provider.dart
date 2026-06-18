import 'package:frontend/src/features/chat/domain/entities/extraction_capabilities.dart';

abstract class ExtractionCapabilityProvider {
  Future<ExtractionCapabilities> getExtractionCapabilities();
}
