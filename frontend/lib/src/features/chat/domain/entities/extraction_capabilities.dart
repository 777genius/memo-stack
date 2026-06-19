import 'package:equatable/equatable.dart';

class ExtractionCapabilities extends Equatable {
  final bool enabled;
  final String? defaultProfile;
  final Map<String, ExtractionProfileCapability> profiles;
  final Map<String, ExtractionProviderCapability> providers;
  final Map<String, Map<String, ExtractionModalityAction>> modalityActions;
  final List<ExtractionDegradedComponent> degradedComponents;
  final Map<String, dynamic> policy;
  final Map<String, dynamic> evidenceContract;
  final Map<String, dynamic> featureContract;
  final Map<String, dynamic> providerContract;
  final Map<String, dynamic> manifestContract;
  final Map<String, dynamic> fileTypeDetection;
  final Map<String, dynamic> limits;
  final Map<String, dynamic> raw;

  const ExtractionCapabilities({
    required this.enabled,
    required this.defaultProfile,
    required this.profiles,
    required this.providers,
    required this.modalityActions,
    required this.degradedComponents,
    required this.policy,
    required this.evidenceContract,
    required this.featureContract,
    required this.providerContract,
    required this.manifestContract,
    required this.fileTypeDetection,
    required this.limits,
    required this.raw,
  });

  factory ExtractionCapabilities.fromMap(Map<String, dynamic> map) {
    final profiles = {
      for (final item in _listOfMaps(map['profiles_v2']))
        if (_string(item['name']).isNotEmpty)
          _string(item['name']): ExtractionProfileCapability.fromMap(item),
    };
    return ExtractionCapabilities(
      enabled: map['enabled'] == true,
      defaultProfile: _nullableString(map['default_profile']),
      profiles: profiles,
      providers: _providerMap(map['providers']),
      modalityActions: _modalityActionMap(map['modality_actions']),
      degradedComponents: _listOfMaps(map['degraded_components'])
          .map(ExtractionDegradedComponent.fromMap)
          .toList(growable: false),
      policy: _map(map['policy']),
      evidenceContract: _map(map['evidence_contract']),
      featureContract: _map(map['feature_contract']),
      providerContract: _map(map['provider_contract']),
      manifestContract: _map(map['manifest_contract']),
      fileTypeDetection: _map(map['file_type_detection']),
      limits: _map(map['limits']),
      raw: Map<String, dynamic>.from(map),
    );
  }

  ExtractionProfileCapability? profile(String name) => profiles[name];
  ExtractionProviderCapability? provider(String name) => providers[name];

  ExtractionModalityAction? modalityAction(String modality, String action) {
    return modalityActions[modality]?[action];
  }

  bool get hasDegradedComponents => degradedComponents.isNotEmpty;

  List<String> get degradedLabels => degradedComponents
      .map((item) => item.label)
      .where((item) => item.isNotEmpty)
      .toList(growable: false);

  @override
  List<Object?> get props => [
        enabled,
        defaultProfile,
        profiles,
        providers,
        modalityActions,
        degradedComponents,
        policy,
        evidenceContract,
        featureContract,
        providerContract,
        manifestContract,
        fileTypeDetection,
        limits,
        raw,
      ];
}

class ExtractionProfileCapability extends Equatable {
  final String name;
  final bool enabled;
  final String status;
  final String? reason;
  final List<String> providers;
  final List<String> inputModalities;
  final List<String> evidenceCoordinates;
  final List<String> primaryArtifactTypes;
  final List<String> documentFeatures;
  final List<String> visionFeatures;
  final List<String> transcriptFeatures;
  final List<String> videoFeatures;
  final bool externalProviderEgress;
  final bool requiresExplicitExternalAi;
  final bool mayRunLocalAsr;
  final bool deprecated;
  final List<String> fallbackProfiles;
  final List<String> replacementProfiles;
  final String memoryPromotion;
  final String sourceTextPolicy;
  final bool artifactPayloadsBounded;
  final Map<String, dynamic> raw;

  const ExtractionProfileCapability({
    required this.name,
    required this.enabled,
    required this.status,
    required this.reason,
    required this.providers,
    required this.inputModalities,
    required this.evidenceCoordinates,
    required this.primaryArtifactTypes,
    required this.documentFeatures,
    required this.visionFeatures,
    required this.transcriptFeatures,
    required this.videoFeatures,
    required this.externalProviderEgress,
    required this.requiresExplicitExternalAi,
    required this.mayRunLocalAsr,
    required this.deprecated,
    required this.fallbackProfiles,
    required this.replacementProfiles,
    required this.memoryPromotion,
    required this.sourceTextPolicy,
    required this.artifactPayloadsBounded,
    required this.raw,
  });

  factory ExtractionProfileCapability.fromMap(Map<String, dynamic> map) {
    return ExtractionProfileCapability(
      name: _string(map['name']),
      enabled: map['enabled'] == true,
      status: _string(map['status'], fallback: 'unknown'),
      reason: _nullableString(map['reason']),
      providers: _stringList(map['providers']),
      inputModalities: _stringList(map['input_modalities']),
      evidenceCoordinates: _stringList(map['evidence_coordinates']),
      primaryArtifactTypes: _stringList(map['primary_artifact_types']),
      documentFeatures: _stringList(map['document_features']),
      visionFeatures: _stringList(map['vision_features']),
      transcriptFeatures: _stringList(map['transcript_features']),
      videoFeatures: _stringList(map['video_features']),
      externalProviderEgress: map['external_provider_egress'] == true,
      requiresExplicitExternalAi: map['requires_explicit_external_ai'] == true,
      mayRunLocalAsr: map['may_run_local_asr'] == true,
      deprecated: map['deprecated'] == true,
      fallbackProfiles: _stringList(map['fallback_profiles']),
      replacementProfiles: _stringList(map['replacement_profiles']),
      memoryPromotion: _string(map['memory_promotion']),
      sourceTextPolicy: _string(map['source_text_policy']),
      artifactPayloadsBounded: map['artifact_payloads_bounded'] == true,
      raw: Map<String, dynamic>.from(map),
    );
  }

  @override
  List<Object?> get props => [
        name,
        enabled,
        status,
        reason,
        providers,
        inputModalities,
        evidenceCoordinates,
        primaryArtifactTypes,
        documentFeatures,
        visionFeatures,
        transcriptFeatures,
        videoFeatures,
        externalProviderEgress,
        requiresExplicitExternalAi,
        mayRunLocalAsr,
        deprecated,
        fallbackProfiles,
        replacementProfiles,
        memoryPromotion,
        sourceTextPolicy,
        artifactPayloadsBounded,
        raw,
      ];
}

class ExtractionProviderCapability extends Equatable {
  final String name;
  final String kind;
  final bool installed;
  final bool configured;
  final bool enabled;
  final String status;
  final String? reason;
  final List<String> profiles;
  final bool externalProviderEgress;
  final String? operatorAction;
  final bool? userRetryable;
  final Map<String, dynamic> raw;

  const ExtractionProviderCapability({
    required this.name,
    required this.kind,
    required this.installed,
    required this.configured,
    required this.enabled,
    required this.status,
    required this.reason,
    required this.profiles,
    required this.externalProviderEgress,
    required this.operatorAction,
    required this.userRetryable,
    required this.raw,
  });

  factory ExtractionProviderCapability.fromMap(
    String name,
    Map<String, dynamic> map,
  ) {
    return ExtractionProviderCapability(
      name: name,
      kind: _string(map['kind']),
      installed: map['installed'] == true,
      configured: map['configured'] == true,
      enabled: map['enabled'] == true,
      status: _string(map['status'], fallback: 'unknown'),
      reason: _nullableString(map['reason']),
      profiles: _stringList(map['profiles']),
      externalProviderEgress: map['external_provider_egress'] == true,
      operatorAction: _nullableString(map['operator_action']),
      userRetryable: _nullableBool(map['user_retryable']),
      raw: Map<String, dynamic>.from(map),
    );
  }

  bool get isDegraded =>
      status == 'blocked' || status == 'unavailable' || status == 'degraded';

  String get label {
    final action = operatorAction;
    if (action != null && action.isNotEmpty) return '$name: $action';
    final text = reason;
    if (text != null && text.isNotEmpty) return '$name: $text';
    return '$name: $status';
  }

  @override
  List<Object?> get props => [
        name,
        kind,
        installed,
        configured,
        enabled,
        status,
        reason,
        profiles,
        externalProviderEgress,
        operatorAction,
        userRetryable,
        raw,
      ];
}

class ExtractionModalityAction extends Equatable {
  final String modality;
  final String action;
  final bool enabled;
  final String status;
  final String? reason;
  final List<String> profiles;
  final List<String> providers;
  final List<String> artifactTypes;
  final List<String> evidenceCoordinates;
  final bool externalProviderEgress;
  final bool requiresExplicitExternalAi;
  final List<String> fallbackProfiles;
  final String memoryPromotion;
  final String sourceTextPolicy;
  final bool artifactPayloadsBounded;
  final String? operatorAction;
  final bool? userRetryable;
  final Map<String, dynamic> raw;

  const ExtractionModalityAction({
    required this.modality,
    required this.action,
    required this.enabled,
    required this.status,
    required this.reason,
    required this.profiles,
    required this.providers,
    required this.artifactTypes,
    required this.evidenceCoordinates,
    required this.externalProviderEgress,
    required this.requiresExplicitExternalAi,
    required this.fallbackProfiles,
    required this.memoryPromotion,
    required this.sourceTextPolicy,
    required this.artifactPayloadsBounded,
    required this.operatorAction,
    required this.userRetryable,
    required this.raw,
  });

  factory ExtractionModalityAction.fromMap(
    String modality,
    String action,
    Map<String, dynamic> map,
  ) {
    return ExtractionModalityAction(
      modality: modality,
      action: action,
      enabled: map['enabled'] == true,
      status: _string(map['status'], fallback: 'unknown'),
      reason: _nullableString(map['reason']),
      profiles: _stringList(map['profiles']),
      providers: _stringList(map['providers']),
      artifactTypes: _stringList(map['artifact_types']),
      evidenceCoordinates: _stringList(map['evidence_coordinates']),
      externalProviderEgress: map['external_provider_egress'] == true,
      requiresExplicitExternalAi: map['requires_explicit_external_ai'] == true,
      fallbackProfiles: _stringList(map['fallback_profiles']),
      memoryPromotion: _string(map['memory_promotion']),
      sourceTextPolicy: _string(map['source_text_policy']),
      artifactPayloadsBounded: map['artifact_payloads_bounded'] != false,
      operatorAction: _nullableString(map['operator_action']),
      userRetryable: _nullableBool(map['user_retryable']),
      raw: Map<String, dynamic>.from(map),
    );
  }

  bool get isDegraded =>
      !enabled ||
      status == 'blocked' ||
      status == 'unavailable' ||
      status == 'degraded' ||
      status == 'disabled';

  String get label {
    final actionText = operatorAction;
    if (actionText != null && actionText.isNotEmpty) {
      return '$modality.$action: $actionText';
    }
    final reasonText = reason;
    if (reasonText != null && reasonText.isNotEmpty) {
      return '$modality.$action: $reasonText';
    }
    return '$modality.$action: $status';
  }

  @override
  List<Object?> get props => [
        modality,
        action,
        enabled,
        status,
        reason,
        profiles,
        providers,
        artifactTypes,
        evidenceCoordinates,
        externalProviderEgress,
        requiresExplicitExternalAi,
        fallbackProfiles,
        memoryPromotion,
        sourceTextPolicy,
        artifactPayloadsBounded,
        operatorAction,
        userRetryable,
        raw,
      ];
}

class ExtractionDegradedComponent extends Equatable {
  final String componentType;
  final String name;
  final String status;
  final String? reason;
  final String? operatorAction;
  final bool? userRetryable;
  final Map<String, dynamic> raw;

  const ExtractionDegradedComponent({
    required this.componentType,
    required this.name,
    required this.status,
    required this.reason,
    required this.operatorAction,
    required this.userRetryable,
    required this.raw,
  });

  factory ExtractionDegradedComponent.fromMap(Map<String, dynamic> map) {
    return ExtractionDegradedComponent(
      componentType: _string(map['component_type']),
      name: _string(map['name']),
      status: _string(map['status'], fallback: 'unknown'),
      reason: _nullableString(map['reason']),
      operatorAction: _nullableString(map['operator_action']),
      userRetryable: _nullableBool(map['user_retryable']),
      raw: Map<String, dynamic>.from(map),
    );
  }

  String get label {
    final target = name.isEmpty ? componentType : name;
    final action = operatorAction;
    if (action != null && action.isNotEmpty) return '$target: $action';
    final text = reason;
    if (text != null && text.isNotEmpty) return '$target: $text';
    return '$target: $status';
  }

  @override
  List<Object?> get props => [
        componentType,
        name,
        status,
        reason,
        operatorAction,
        userRetryable,
        raw,
      ];
}

Map<String, ExtractionProviderCapability> _providerMap(Object? value) {
  final raw = _map(value);
  return {
    for (final entry in raw.entries)
      if (entry.value is Map)
        entry.key: ExtractionProviderCapability.fromMap(
          entry.key,
          _map(entry.value),
        ),
  };
}

Map<String, Map<String, ExtractionModalityAction>> _modalityActionMap(
  Object? value,
) {
  final raw = _map(value);
  final parsed = <String, Map<String, ExtractionModalityAction>>{};
  for (final modalityEntry in raw.entries) {
    final actions = _map(modalityEntry.value);
    final parsedActions = <String, ExtractionModalityAction>{};
    for (final actionEntry in actions.entries) {
      if (actionEntry.value is! Map) continue;
      parsedActions[actionEntry.key] = ExtractionModalityAction.fromMap(
        modalityEntry.key,
        actionEntry.key,
        _map(actionEntry.value),
      );
    }
    if (parsedActions.isNotEmpty) parsed[modalityEntry.key] = parsedActions;
  }
  return parsed;
}

Map<String, dynamic> _map(Object? value) {
  if (value is Map<String, dynamic>) return Map<String, dynamic>.from(value);
  if (value is Map) {
    return value.map((key, item) => MapEntry(key.toString(), item));
  }
  return const <String, dynamic>{};
}

List<Map<String, dynamic>> _listOfMaps(Object? value) {
  if (value is! List) return const <Map<String, dynamic>>[];
  return value
      .whereType<Map>()
      .map((item) => item.map((key, value) => MapEntry(key.toString(), value)))
      .toList(growable: false);
}

List<String> _stringList(Object? value) {
  if (value is! List) return const <String>[];
  return value
      .map((item) => item.toString().trim())
      .where((item) => item.isNotEmpty)
      .toList(growable: false);
}

String _string(Object? value, {String fallback = ''}) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty) return fallback;
  return text;
}

String? _nullableString(Object? value) {
  final text = value?.toString().trim();
  if (text == null || text.isEmpty) return null;
  return text;
}

bool? _nullableBool(Object? value) {
  if (value is bool) return value;
  return null;
}
