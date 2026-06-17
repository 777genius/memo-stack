abstract class AttachmentUploadLimits {
  Future<int> maxUploadBytes();
}

class AttachmentUploadDefaults {
  static const int maxBytes = 25 * 1024 * 1024;

  const AttachmentUploadDefaults._();
}
