import 'package:equatable/equatable.dart';

import 'package:frontend/src/features/chat/domain/entities/extraction_capabilities.dart';

class AttachmentExtractionPlan extends Equatable {
  final String modality;
  final String displayModality;
  final bool withinExtractionLimit;
  final int? maxBytes;
  final List<AttachmentExtractionActionPlan> actions;
  final List<String> warnings;

  const AttachmentExtractionPlan({
    required this.modality,
    required this.displayModality,
    required this.withinExtractionLimit,
    required this.maxBytes,
    required this.actions,
    required this.warnings,
  });

  bool get hasCapabilityData => actions.isNotEmpty;
  bool get hasDegradedActions => actions.any((action) => action.isDegraded);
  bool get hasExternalAi =>
      actions.any((action) => action.externalProviderEgress);

  List<AttachmentExtractionActionPlan> get enabledActions =>
      actions.where((action) => action.enabled).toList(growable: false);

  List<AttachmentExtractionActionPlan> get degradedActions =>
      actions.where((action) => action.isDegraded).toList(growable: false);

  String get compactLabel {
    if (!withinExtractionLimit) return 'Extraction limit exceeded';
    if (actions.isEmpty) return 'Stored, server will inspect type';
    final enabled = enabledActions.map((action) => action.displayName).toList();
    final degraded =
        degradedActions.map((action) => action.displayName).toList();
    if (enabled.isEmpty && degraded.isNotEmpty) {
      return '$displayModality: ${degraded.first} unavailable';
    }
    final primary = enabled.take(2).join(' + ');
    if (degraded.isEmpty) return '$displayModality: $primary';
    return '$displayModality: $primary, ${degraded.length} degraded';
  }

  @override
  List<Object?> get props => [
        modality,
        displayModality,
        withinExtractionLimit,
        maxBytes,
        actions,
        warnings,
      ];
}

class AttachmentExtractionActionPlan extends Equatable {
  final String action;
  final String displayName;
  final bool enabled;
  final String status;
  final String? reason;
  final String? operatorAction;
  final bool externalProviderEgress;
  final bool requiresExplicitExternalAi;
  final List<String> artifactTypes;
  final List<String> evidenceCoordinates;
  final List<String> fallbackProfiles;

  const AttachmentExtractionActionPlan({
    required this.action,
    required this.displayName,
    required this.enabled,
    required this.status,
    required this.reason,
    required this.operatorAction,
    required this.externalProviderEgress,
    required this.requiresExplicitExternalAi,
    required this.artifactTypes,
    required this.evidenceCoordinates,
    required this.fallbackProfiles,
  });

  factory AttachmentExtractionActionPlan.fromCapability(
    ExtractionModalityAction capability,
  ) {
    return AttachmentExtractionActionPlan(
      action: capability.action,
      displayName: _actionDisplayName(capability.modality, capability.action),
      enabled: capability.enabled,
      status: capability.status,
      reason: capability.reason,
      operatorAction: capability.operatorAction,
      externalProviderEgress: capability.externalProviderEgress,
      requiresExplicitExternalAi: capability.requiresExplicitExternalAi,
      artifactTypes: capability.artifactTypes,
      evidenceCoordinates: capability.evidenceCoordinates,
      fallbackProfiles: capability.fallbackProfiles,
    );
  }

  bool get isDegraded =>
      !enabled ||
      status == 'blocked' ||
      status == 'unavailable' ||
      status == 'degraded' ||
      status == 'disabled';

  String get degradedReason {
    final action = operatorAction;
    if (action != null && action.isNotEmpty) return action;
    final text = reason;
    if (text != null && text.isNotEmpty) return text;
    return status;
  }

  @override
  List<Object?> get props => [
        action,
        displayName,
        enabled,
        status,
        reason,
        operatorAction,
        externalProviderEgress,
        requiresExplicitExternalAi,
        artifactTypes,
        evidenceCoordinates,
        fallbackProfiles,
      ];
}

extension ExtractionCapabilitiesAttachmentPlanning on ExtractionCapabilities {
  AttachmentExtractionPlan planAttachment({
    required String filename,
    required int bytes,
    String? mime,
  }) {
    final modality = _detectModality(filename: filename, mime: mime);
    final actionNames = _actionNamesForModality(modality);
    final actionPlans = <AttachmentExtractionActionPlan>[];
    for (final actionName in actionNames) {
      final action = modalityAction(modality, actionName);
      if (action == null) continue;
      actionPlans.add(AttachmentExtractionActionPlan.fromCapability(action));
    }
    final maxBytes = _positiveInt(limits['max_bytes']);
    final warnings = <String>[
      if (maxBytes != null && bytes > maxBytes)
        'File exceeds extraction limit ${_formatBytes(maxBytes)}',
      if (modality == 'unknown')
        'Unknown file type; backend will store the file and inspect it safely',
      for (final action in actionPlans.where((action) => action.isDegraded))
        '${action.displayName}: ${action.degradedReason}',
    ];
    return AttachmentExtractionPlan(
      modality: modality,
      displayModality: _modalityDisplayName(modality),
      withinExtractionLimit: maxBytes == null || bytes <= maxBytes,
      maxBytes: maxBytes,
      actions: actionPlans,
      warnings: warnings,
    );
  }
}

String _detectModality({required String filename, String? mime}) {
  final contentType = mime?.trim().toLowerCase() ?? '';
  final extension = _extension(filename);
  if (contentType.startsWith('image/') ||
      const {
        '.avif',
        '.bmp',
        '.gif',
        '.heic',
        '.heif',
        '.jpeg',
        '.jpg',
        '.png',
        '.tif',
        '.tiff',
        '.webp',
      }.contains(extension)) {
    return 'image';
  }
  if (contentType.startsWith('audio/') ||
      const {
        '.flac',
        '.m4a',
        '.mp3',
        '.mpga',
        '.oga',
        '.ogg',
        '.wav',
      }.contains(extension)) {
    return 'audio';
  }
  if (contentType.startsWith('video/') ||
      const {
        '.m4v',
        '.mkv',
        '.mov',
        '.mp4',
        '.mpeg',
        '.webm',
      }.contains(extension)) {
    return 'video';
  }
  if (contentType.startsWith('text/') ||
      contentType.startsWith('message/') ||
      contentType == 'application/pdf' ||
      contentType == 'application/json' ||
      contentType == 'application/zip' ||
      contentType.contains('document') ||
      contentType.contains('spreadsheet') ||
      contentType.contains('presentation') ||
      const {
        '.csv',
        '.doc',
        '.docx',
        '.eml',
        '.epub',
        '.html',
        '.htm',
        '.json',
        '.md',
        '.pdf',
        '.ppt',
        '.pptx',
        '.srt',
        '.txt',
        '.vtt',
        '.xls',
        '.xlsx',
        '.zip',
      }.contains(extension)) {
    return 'document';
  }
  return 'unknown';
}

List<String> _actionNamesForModality(String modality) {
  return switch (modality) {
    'document' => const ['text_extraction', 'layout_extraction'],
    'image' => const ['metadata', 'vision'],
    'audio' => const ['metadata', 'transcription_api', 'transcription_local'],
    'video' => const ['metadata_keyframes', 'transcription_api'],
    _ => const <String>[],
  };
}

String _actionDisplayName(String modality, String action) {
  return switch ('$modality.$action') {
    'document.text_extraction' => 'text',
    'document.layout_extraction' => 'layout',
    'image.metadata' => 'metadata',
    'image.vision' => 'vision',
    'audio.metadata' => 'metadata',
    'audio.transcription_api' => 'API transcript',
    'audio.transcription_local' => 'local transcript',
    'video.metadata_keyframes' => 'metadata/keyframes',
    'video.transcription_api' => 'API transcript',
    _ => action.replaceAll('_', ' '),
  };
}

String _modalityDisplayName(String modality) {
  return switch (modality) {
    'document' => 'Document',
    'image' => 'Image',
    'audio' => 'Audio',
    'video' => 'Video',
    _ => 'File',
  };
}

String _extension(String filename) {
  final lower = filename.trim().toLowerCase();
  final index = lower.lastIndexOf('.');
  if (index < 0 || index == lower.length - 1) return '';
  return lower.substring(index);
}

int? _positiveInt(Object? value) {
  if (value is int && value > 0) return value;
  if (value is num && value > 0) return value.toInt();
  final parsed = int.tryParse(value?.toString() ?? '');
  if (parsed == null || parsed <= 0) return null;
  return parsed;
}

String _formatBytes(int bytes) {
  const mb = 1024 * 1024;
  const kb = 1024;
  if (bytes >= mb) return '${(bytes / mb).toStringAsFixed(1)} MB';
  if (bytes >= kb) return '${(bytes / kb).toStringAsFixed(1)} KB';
  return '$bytes B';
}
